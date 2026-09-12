'use strict';
const NS = 'http://www.w3.org/2000/svg';
const $ = id => document.getElementById(id);
let state = null, index = null, data = null, rel = null, view = null, page = null;
let showAll = false, poll = null, markMode = false, proposal = null;
let pageRequest = 0;

function el(tag, attrs) {
  const n = document.createElementNS(NS, tag);
  Object.entries(attrs || {}).forEach(([k, v]) => n.setAttribute(k, v));
  return n;
}
function node(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}
async function api(path, opts) {
  const r = await fetch(path, Object.assign({ headers: { Accept: 'application/json' } }, opts || {}));
  const body = await r.json();
  if (!r.ok) throw new Error(body.error || ('İstek başarısız: ' + r.status));
  return body;
}
function post(path, body) {
  return api(path, { method: 'POST', body: JSON.stringify(body),
    headers: { 'Content-Type': 'application/json', Accept: 'application/json', 'X-Pilot-Token': state.csrf_token } });
}
function fail(e) { const b = $('error'); b.textContent = 'Hata: ' + e.message; b.hidden = false; }

/* ============================================================ sayfa gezgini */
const STATE_TEXT = { NOT_PREPARED: 'hazırlanmadı', QUEUED: 'sırada', PREPARING: 'hazırlanıyor',
                     PREPARED: 'hazırlandı', FAILED: 'hata' };
const TYPE_TEXT = { Schaltplan: 'Şema', 'Stückliste': 'Liste', Layout: 'Yerleşim' };
function rowOf(n) { return index && index.pages.find(r => r.page === n); }
function stateText(r) {
  if (r.state !== 'PREPARED') return STATE_TEXT[r.state] || r.state;
  return r.marks ? r.marks + ' işaret' : 'hazırlandı · işaretsiz';
}
function stateClass(r) {
  if (r.state === 'PREPARED') return r.marks ? 's-marked' : 's-ready';
  if (r.state === 'FAILED') return 's-fail';
  if (r.state === 'QUEUED' || r.state === 'PREPARING') return 's-busy';
  return 's-none';
}
function structure(r) { return (r.anlage ? '=' + r.anlage : '=?') + (r.einbauort ? '+' + r.einbauort : '+?'); }

function renderIndex() {
  const c = index.counts;
  $('nav-count').textContent = c.total + ' sayfa · ' + c.default_selected + ' aday şema · ' + c.prepared + ' hazırlandı';
  $('f-default').textContent = 'Aday şemalar (' + c.default_selected + ')';
  $('f-all').textContent = 'Tümü (' + c.total + ')';
  $('f-default').classList.toggle('on', !showAll); $('f-default').setAttribute('aria-pressed', String(!showAll));
  $('f-all').classList.toggle('on', showAll); $('f-all').setAttribute('aria-pressed', String(showAll));

  const q = index.queue;
  $('q-text').textContent = 'Aday şemalar: ' + c.prepared_default + ' / ' + c.default_selected + ' hazır'
    + (q && q.current ? ' · şimdi sayfa ' + q.current : '')
    + (q && q.queue.length ? ' · sırada ' + q.queue.length : '')
    + (c.failed ? ' · ' + c.failed + ' hata' : '');
  $('q-fill').style.width = (c.default_selected ? 100 * c.prepared_default / c.default_selected : 0) + '%';
  const pending = q && q.queue.length > 0;
  $('q-start').hidden = !index.cache_enabled;
  $('q-start').disabled = c.prepared_default >= c.default_selected || (pending && !q.stopped);
  $('q-toggle').hidden = !pending;
  $('q-toggle').textContent = q && q.stopped ? 'Devam' : 'Durdur';

  const failed = $('q-failed'); failed.replaceChildren();
  for (const f of (q ? q.failed : [])) {
    const row = node('div', 'failed-row');
    row.append(node('span', null, 'Sayfa ' + f.page + ': ' + (f.error || 'hata')));
    const b = node('button', null, 'Yeniden dene'); b.type = 'button';
    b.addEventListener('click', () => post('/api/prepare', { action: 'retry', page: f.page }).then(refreshIndex).catch(fail));
    row.append(b); failed.append(row);
  }

  const list = $('page-list'); list.replaceChildren();
  for (const r of index.pages) {
    if (!showAll && !r.default_selected) continue;
    const b = node('button', 'pg-row' + (r.page === page ? ' on' : '') + (r.default_selected ? '' : ' ctx'));
    b.type = 'button';
    b.append(node('span', 'pg-no', String(r.page)), node('span', 'pg-bl', 'Blatt ' + (r.blatt || '?')),
             node('span', 'pg-st', structure(r)), node('span', 'pg-ty', TYPE_TEXT[r.doc_type] || r.doc_type || '?'),
             node('span', 'pg-state ' + stateClass(r), stateText(r)));
    b.title = 'Fiziksel sayfa ' + r.page + ' · kapsam: ' + (r.scope || 'bilinmiyor')
      + (r.issues.length ? ' · ' + r.issues.join(', ') : '');
    b.addEventListener('click', () => openPage(r.page));
    list.append(b);
  }
}

async function refreshIndex() {
  index = await api('/api/pages');
  renderIndex();
  const q = index.queue;
  const busy = q && (q.running || (q.queue.length && !q.stopped));
  if (busy && !poll) poll = setInterval(tick, 1500);
  if (!busy && poll) { clearInterval(poll); poll = null; }
}
async function tick() {
  const before = rowOf(page) && rowOf(page).state;
  try { await refreshIndex(); } catch (e) { fail(e); return; }
  const after = rowOf(page) && rowOf(page).state;
  if (before !== 'PREPARED' && after === 'PREPARED') openPage(page);
}

/* ============================================================ çizim */
/* Ekran ölçeği: viewBox 'meet' ile ortalanır, yatay/dikey ölçek AYNIDIR. Kaydırma da bunu
   kullanmalı; ayrı sx/sy kullanılırsa çizim imlecin altından kayar. */
function screenScale() {
  const r = $('svg').getBoundingClientRect();
  return Math.min(r.width / view[2], r.height / view[3]);
}

function setView(box) {
  let [x, y, w, h] = box || view;
  if (page && state) {                       // sınırlar tek yerde: pan, tekerlek, düğme, klavye
    const [pw, ph] = pageSize(page);
    const limit = Math.min(Math.max(w, 20), pw * 1.5) / w;
    w *= limit; h *= limit;
    x = Math.min(Math.max(x, -w / 2), pw - w / 2);
    y = Math.min(Math.max(y, -h / 2), ph - h / 2);
  }
  view = [x, y, w, h];
  $('svg').setAttribute('viewBox', view.join(' '));
  if (proposal) drawHandles();               // tutamaç boyutu ekran pikseline sabit
}
function zoom(f) { const [x, y, w, h] = view; setView([x + (w - w * f) / 2, y + (h - h * f) / 2, w * f, h * f]); }
function inView(box) {
  return box[0] >= view[0] && box[1] >= view[1] &&
         box[2] <= view[0] + view[2] && box[3] <= view[1] + view[3];
}
function clearMarks() { $('marks').replaceChildren(); }
function pageSize(n) {
  const v = state.viewable[String(n)];
  return v || [state.manifest.width, state.manifest.height];
}

function drawAll() {
  clearMarks();
  if (!data) return;
  const g = $('marks');
  for (const c of data.connections) {
    const [a, b] = c.points;
    g.append(el('line', { x1: a[0], y1: a[1], x2: b[0], y2: b[1], class: 'wire-line' }));
    for (const p of c.points) g.append(el('circle', { cx: p[0], cy: p[1], r: 2.1, class: 'wire-end' }));
  }
  for (const n of data.networks) for (const p of n.points) g.append(el('circle', { cx: p[0], cy: p[1], r: 2.1, class: 'net-end' }));
  for (const s of data.singles) for (const p of s.points) g.append(el('circle', { cx: p[0], cy: p[1], r: 2.1, class: 'net-end' }));
  for (const t of data.todo) for (const p of t.points || []) g.append(el('circle', { cx: p[0], cy: p[1], r: 3.1, class: 'todo-end' }));
}

function zoomTo(points, pad) {
  if (!points.length) return;
  const xs = points.map(p => p[0]), ys = points.map(p => p[1]);
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
  const w = Math.max(x1 - x0, 80) + pad * 2, h = Math.max(y1 - y0, 80) + pad * 2;
  setView([(x0 + x1) / 2 - w / 2, (y0 + y1) / 2 - h / 2, w, h]);
}

/* Gerçek segmentleri vurgula: kenar listesi [ax, ay, bx, by] çizimin kendi parçalarıdır. */
function highlightEdges(edges, dots) {
  drawAll();
  const g = $('marks');
  const pts = [];
  for (const e of edges) {
    g.append(el('line', { x1: e[0], y1: e[1], x2: e[2], y2: e[3], class: 'seg' }));
    pts.push([e[0], e[1]], [e[2], e[3]]);
  }
  for (const d of dots || []) { g.append(el('circle', { cx: d[0], cy: d[1], r: 4, class: 'seg-end' })); pts.push(d); }
  zoomTo(pts, 30);
}

function focusOn(points, box) {
  drawAll();
  const g = $('marks');
  if (points && points.length === 2)
    g.append(el('line', { x1: points[0][0], y1: points[0][1], x2: points[1][0], y2: points[1][1], class: 'focus' }));
  for (const p of points || []) g.append(el('circle', { cx: p[0], cy: p[1], r: 4.2, class: 'focus' }));
  if (box) zoomTo([[box[0], box[1]], [box[2], box[3]]], 40);
  else if (points && points.length) zoomTo(points, 60);
}

/* ============================================================ sağ panel */
function rowFor(title, sub, tag, onClick, cls) {
  const b = node('button', 'row' + (cls ? ' ' + cls : ''));
  b.type = 'button';
  const head = node('span', 'title', title);
  if (tag) head.append(node('span', 'tag', tag));
  b.append(head);
  if (sub) b.append(node('span', 'sub', sub));
  b.addEventListener('click', onClick);
  return b;
}

function contText(c) {
  const target = c.target_page ? 'sayfa ' + c.target_page : 'belge dışı';
  const r = c.target_page && rowOf(c.target_page);
  if (c.verified) return c.reference + ' → ' + target + ' ✓';
  if (c.status === 'TARGET_PAGE_NOT_TRACED' || (r && r.state !== 'PREPARED')) return c.reference + ' → ' + target + ' · hazırlanmadı';
  return c.reference + ' → ' + target + ' · karşılık bulunamadı';
}

function renderRelations() {
  const box = $('rels'); box.replaceChildren();
  $('rel-count').textContent = rel ? rel.networks.length : 0;
  if (!rel || !rel.networks.length) { box.append(node('p', 'empty', 'Bu sayfada izlenebilen hat yok.')); return; }
  for (const n of rel.networks) {
    const card = node('div', 'net-card' + (n.potential ? '' : ' unnamed'));
    const name = n.potential || (n.potential_conflict.length ? 'çelişkili ad: ' + n.potential_conflict.join(' / ') : 'adsız hat');
    const head = node('button', 'net-head'); head.type = 'button';
    head.append(node('b', null, name),
      node('small', null, n.pins.length + ' pin · ' + n.continuations.length + ' devam · ' + n.junctions.length + ' birleşim'));
    head.addEventListener('click', () => highlightEdges(n.edges, n.continuations.map(c => c.point)));
    card.append(head);

    if (n.pins.length) {
      const pins = node('div', 'chips');
      for (const p of n.pins) {
        const c = node('button', 'chip-btn', (n.potential ? n.potential + ' → ' : '') + p.label); c.type = 'button';
        c.title = 'Bu pinin hatta giden gerçek yolu';
        c.addEventListener('click', () => {
          const rs = rel.relations.filter(r => r.network === n.id &&
            (r.source_pin_id === p.id || (r.kind === 'PIN_PIN' && r.target_pin_id === p.id)));
          highlightEdges(rs.flatMap(r => r.edges), [p.point]);
        });
        pins.append(c);
      }
      card.append(pins);
    }
    if (n.continuations.length) {
      const conts = node('div', 'chips');
      for (const c of n.continuations) {
        const b = node('button', 'chip-btn go' + (c.verified ? ' ok' : ''), contText(c)); b.type = 'button';
        if (c.signal && !c.potential) b.title = 'Eşleşme kanıtı ' + c.signal_kind + ': ' + c.signal + ' (potansiyel adı değil)';
        b.disabled = !c.target_page;
        b.addEventListener('click', () => openPage(c.target_page, c.target_end));
        conts.append(b);
      }
      card.append(conts);
    }
    if (n.open_ends.length)
      card.append(node('p', 'net-note', n.open_ends.length + ' uç bilinmiyor'
        + (n.open_ends.some(e => e.nearby_text) ? ' (yakın yazı: ' + n.open_ends.map(e => e.nearby_text).filter(Boolean).join(', ') + ')' : '')
        + ' — uydurulmadı.'));
    if (n.potential_conflict.length) card.append(node('p', 'net-note warn', 'Aynı hatta iki farklı ad okundu; ad verilmedi.'));
    box.append(card);
  }
}

/* Yarım kalan ucun karşı tarafı: bilinen hat/devam varsa onu yaz, "karşı uç yok" deme. */
function knownFor(label) {
  if (!rel) return null;
  for (const n of rel.networks) {
    if (!n.pins.some(p => p.label === label)) continue;
    const parts = [];
    if (n.potential) parts.push(n.potential + ' hattına bağlı');
    const pages = n.continuations.filter(c => c.target_page).map(c => 'sayfa ' + c.target_page);
    if (pages.length) parts.push('devam: ' + pages.join(', '));
    if (n.open_ends.length) parts.push(n.open_ends.length + ' uç bilinmiyor');
    if (parts.length) return { text: parts.join(' · '), net: n, known: !!(n.potential || pages.length) };
  }
  return null;
}

function realEdgesFor(conn) {
  if (!rel) return null;
  const a = '-' + conn.from_device.split('-').slice(1).join('-') + ':' + conn.from_pin;
  const b = '-' + conn.to_device.split('-').slice(1).join('-') + ':' + conn.to_pin;
  const r = rel.relations.find(x => x.kind === 'PIN_PIN' && ((x.source === a && x.target === b) || (x.source === b && x.target === a)));
  return r ? r.edges : null;
}

function render() {
  $('page-label').textContent = data.page_label;
  $('headline').textContent = markMode
    ? 'İşaretleme açık: cihaza tıkla, program kutusunu ve uçlarını çıkarsın. Şekil bulunamazsa kutuyu sürükle.'
    : data.headline + (rel ? ' ' + rel.summary.networks + ' hat, ' + rel.summary.named_networks + ' tanesi adlı.' : '');
  $('note').textContent = data.note;
  renderRelations();
  renderMarks();

  const wires = $('wires'); wires.replaceChildren();
  $('wire-count').textContent = data.connections.length;
  if (!data.connections.length) wires.append(node('p', 'empty', 'Bu sayfada takip edilen tel yok.'));
  for (const c of data.connections)
    wires.append(rowFor(c.plain, c.evidence + ' · uygulama: ' +
      (c.implementation === 'BELIRSIZ' ? 'belirlenmedi' : c.implementation.toLowerCase()),
      c.state, () => { const e = realEdgesFor(c); if (e) highlightEdges(e, c.points); else focusOn(c.points, c.bbox); }));

  const nets = $('nets'); nets.replaceChildren();
  const lines = data.line_relations || [];
  $('net-count').textContent = data.networks.length + lines.length;
  if (!data.networks.length && !lines.length) nets.append(node('p', 'empty', 'Ortak hat yok.'));
  for (const r of lines)
    nets.append(rowFor(r.plain + '   [' + r.reference + ']', r.warning + ' ' + r.state,
      'hat seviyesinde teyitli', () => focusOn(r.points, r.bbox), 'net warn'));
  for (const n of data.networks)
    nets.append(rowFor(n.plain, n.warning, 'tel çifti üretilmedi', () => focusOn(n.points, n.bbox), 'net warn'));

  const singles = $('singles'); singles.replaceChildren();
  $('single-count').textContent = data.singles.length;
  if (!data.singles.length) singles.append(node('p', 'empty', 'Yarım kalan kayıt yok.'));
  for (const s of data.singles) {
    const known = knownFor(s.plain);
    singles.append(rowFor(s.plain, known ? known.text : s.why, known && known.known ? 'hat biliniyor' : null,
      () => known ? highlightEdges(known.net.edges, s.points) : focusOn(s.points, s.bbox)));
  }

  const todo = $('todo'); todo.replaceChildren();
  if (!data.todo.length) todo.append(node('p', 'empty', 'Bu sayfada senden beklenen bir şey yok.'));
  for (const t of data.todo) {
    const card = node('div', 'task');
    card.append(node('h4', null, t.title), node('p', null, t.why));
    if (t.items && t.items.length) {
      const list = node('div', 'items');
      for (const item of t.items.slice(0, 24)) list.append(node('span', null, item));
      if (t.items.length > 24) list.append(node('span', null, '+' + (t.items.length - 24) + ' tane daha'));
      card.append(list);
    }
    if (t.points && t.points.length) {
      const b = node('button', null, 'Çizimde göster'); b.type = 'button';
      b.addEventListener('click', () => focusOn(t.points, null));
      card.append(b);
    }
    todo.append(card);
  }

  const s = data.summary;
  const box = $('summary'); box.replaceChildren();
  for (const [label, value] of [['Bulunan tel', s.connections], ['Ortak hat', s.networks], ['İşaretli uç', s.marks],
    ['Yarım kayıt', s.singles], ['Çözülmemiş yer', s.unresolved], ['Yenilenecek inceleme', s.reviews_needing_refresh]]) {
    const cell = node('div'); cell.append(node('b', null, String(value)), node('span', null, label)); box.append(cell);
  }
  const dims = $('dimensions'); dims.replaceChildren();
  for (const d of data.dimensions || []) {
    const cell = node('div', 'dim' + (d.value ? ' on' : ''));
    cell.append(node('b', null, String(d.value)), node('span', 'dim-label', d.label), node('span', 'dim-hint', d.hint));
    dims.append(cell);
  }
}

/* ============================================================ cihaz işaretleme */
/* Ekrandaki tıklama noktasını çizim koordinatına çevirir. viewBox 'meet' ile ortalandığı için
   ölçek ve boşluk hesaba katılır; yoksa işaret birkaç puntoluk kayar. */
function svgPoint(ev) {
  const r = $('svg').getBoundingClientRect();
  const s = Math.min(r.width / view[2], r.height / view[3]);
  return [view[0] + (ev.clientX - r.left - (r.width - view[2] * s) / 2) / s,
          view[1] + (ev.clientY - r.top - (r.height - view[3] * s) / 2) / s];
}

function setMarkMode(on) {
  markMode = on;
  $('mark-mode').classList.toggle('on', on);
  $('mark-mode').setAttribute('aria-pressed', String(on));
  $('svg').classList.toggle('marking', on);
  if (!on) closeProposal();
}
function closeProposal() { proposal = null; $('proposal').hidden = true; $('proposal').replaceChildren(); drawAll(); }

/* Kutu tutamaçları: 8 köşe/kenar. Ekran boyutu sabit kalsın diye her görünüm değişiminde
   yeniden çizilir (vector-effect yalnız çizgi kalınlığını sabitler, kareyi değil). */
const HANDLES = [['nw', 0, 0], ['n', .5, 0], ['ne', 1, 0], ['e', 1, .5],
                 ['se', 1, 1], ['s', .5, 1], ['sw', 0, 1], ['w', 0, .5]];

function drawHandles() {
  const g = $('marks');
  g.querySelectorAll('.handle').forEach(n => n.remove());
  if (!proposal || !proposal.bbox) return;
  const b = proposal.bbox, size = 9 / screenScale();
  for (const [id, fx, fy] of HANDLES) {
    const cx = b[0] + (b[2] - b[0]) * fx, cy = b[1] + (b[3] - b[1]) * fy;
    const r = el('rect', { x: cx - size / 2, y: cy - size / 2, width: size, height: size, class: 'handle' });
    r.dataset.h = id;
    g.append(r);
  }
}

/* fit=false: kamera OYNAMAZ. Kutuyu sürüklerken görüntü zıplamasın diye şart. */
function drawProposal(p, fit) {
  drawAll();
  const g = $('marks');
  g.append(el('rect', { x: p.bbox[0], y: p.bbox[1], width: p.bbox[2] - p.bbox[0], height: p.bbox[3] - p.bbox[1],
                        class: 'prop-box' }));
  for (const q of (p.pins || [])) g.append(el('circle', { cx: q.point[0], cy: q.point[1], r: 3.4, class: 'prop-pin' }));
  if (fit !== false && !inView(p.bbox)) zoomTo([[p.bbox[0], p.bbox[1]], [p.bbox[2], p.bbox[3]]], 45);
  drawHandles();
}

const SOURCE_TEXT = { TEMPLATE_OFFSET: 'cihaz yazısı yanında', STRIP_LABEL_OWNERSHIP: 'klemens çubuğu adından',
                      MODULE_HEADER_OWNERSHIP: 'modül başlığından' };

function renderProposal(p, fit) {
  proposal = p;
  const host = $('proposal'); host.replaceChildren(); host.hidden = false;
  const head = node('div', 'prop-head');
  head.append(node('b', null, 'Cihaz işareti'),
    node('span', 'muted', p.device ? 'ad ' + (SOURCE_TEXT[p.device_source] || 'sayfadan') + ' okundu'
                                   : 'ad okunamadı — sen yaz'));
  host.append(head);

  const dev = node('label', 'prop-field');
  dev.append(node('span', null, 'Cihaz adı'));
  const devInput = document.createElement('input');
  devInput.type = 'text'; devInput.id = 'prop-device'; devInput.value = p.device || '';
  devInput.placeholder = '=112+E122-3F22';
  dev.append(devInput); host.append(dev);
  if (p.device_inherited && p.device_inherited.length)
    host.append(node('p', 'prop-note', 'Sayfadan devralınan bölüm: ' + p.device_inherited.join(', ')));

  const list = node('div', 'prop-pins');
  p.pins.forEach((q, i) => {
    const row = node('label', 'prop-pin-row');
    const use = document.createElement('input');
    use.type = 'checkbox';
    use.checked = q.keep_use !== undefined ? q.keep_use : !q.already_marked.length;
    use.dataset.use = String(i);
    const name = document.createElement('input');
    name.type = 'text'; name.value = q.pin || ''; name.dataset.pin = String(i); name.placeholder = 'uç adı';
    row.append(use, name,
      node('span', 'prop-xy', q.point[0].toFixed(1) + ' / ' + q.point[1].toFixed(1)),
      node('span', 'prop-state', q.already_label ? 'zaten ' + q.already_label
                                                 : (q.pin ? 'sayfadan okundu' : 'yazı yok')));
    list.append(row);
  });
  if (!p.pins.length) list.append(node('p', 'prop-note', 'Kutuya giren tel yok; uç üretilmedi.'));
  host.append(list);
  if (p.issues.length) host.append(node('p', 'prop-note warn', 'Not: ' + p.issues.join(', ')));

  const buttons = node('div', 'prop-buttons');
  const save = node('button', 'primary', 'Kaydet'); save.type = 'button';
  save.addEventListener('click', saveProposal);
  const cancel = node('button', null, 'Vazgeç'); cancel.type = 'button';
  cancel.addEventListener('click', closeProposal);
  buttons.append(save, cancel,
    node('span', 'prop-note', 'Enter kaydeder, Esc kapatır. Kutuyu tutamaklarından düzeltebilirsin.'));
  host.append(buttons);
  drawProposal(p, fit);
  devInput.focus(); devInput.select();          // elin klavyede kalsın
}

/* Kutu düzeltilince yeniden öneri alınır; kullanıcının YAZDIĞI ad ve uç adları kaybolmaz.
   Eşleme uç NOKTASINA göredir: kutu büyüyünce yeni uç gelir, küçülünce gider; indeks yanıltır. */
function captureEdits() {
  if (!proposal || !$('prop-device')) return null;
  const host = $('proposal');
  const pins = {};
  host.querySelectorAll('input[data-pin]').forEach(input => {
    const q = proposal.pins[Number(input.dataset.pin)];
    if (q) pins[q.point[0].toFixed(1) + '/' + q.point[1].toFixed(1)] =
      { name: input.value, use: host.querySelector('input[data-use="' + input.dataset.pin + '"]').checked };
  });
  return { device: $('prop-device').value, pins: pins };
}

function applyEdits(p, keep) {
  if (!keep) return p;
  if (keep.device.trim()) p.device = keep.device;
  for (const q of p.pins) {
    const hit = keep.pins[q.point[0].toFixed(1) + '/' + q.point[1].toFixed(1)];
    if (hit) { q.pin = hit.name; q.keep_use = hit.use; }
  }
  return p;
}

let proposeAbort = null;
async function propose(query, options) {
  const keep = (options && options.keepEdits) ? captureEdits() : null;
  if (proposeAbort) proposeAbort.abort();
  proposeAbort = new AbortController();
  try {
    $('error').hidden = true;
    const answer = await api('/api/propose?page=' + page + '&' + query, { signal: proposeAbort.signal });
    renderProposal(applyEdits(answer, keep), options && options.fit === false ? false : true);
  } catch (e) {
    if (e.name === 'AbortError') return;
    closeProposal(); fail(e);
  }
}

/* Bir cihazı işaretledikten sonra AYNI ŞEKLİ ara: bu sayfada veya bütün hazırlanmış sayfalarda.
   Aday işaret değildir: ad ve pin yazıları her örnekte kendi sayfasından okunur, uygulamayı sen seçersin. */
function candidateState(c) {
  if (c.pins.some(p => p.already_marked.length)) return { text: 'zaten işaretli', ready: false };
  if (!c.device_name) return { text: (c.issues || []).join(', ') || 'ad okunamadı', ready: false };
  if (!c.pins.every(p => p.page_pin_texts.length === 1)) return { text: 'uç adı okunamadı', ready: false };
  return { text: 'hazır', ready: true };
}

async function findSimilar(boxId, scope) {
  const host = $('proposal'); host.replaceChildren(); host.hidden = false;
  host.append(node('div', 'prop-head', scope === 'all' ? 'Tüm sayfalarda aranıyor…' : 'Bu sayfada aranıyor…'));
  try {
    const query = scope === 'all' ? 'pages=ALL' : 'pages=' + page;
    const data = await api('/api/similar?template=' + encodeURIComponent(boxId) + '&' + query);
    host.replaceChildren();
    const head = node('div', 'prop-head');
    head.append(node('b', null, scope === 'all' ? 'Belgedeki benzerleri' : 'Bu sayfadaki benzerleri'),
      node('span', 'muted', data.candidates_total + ' aday · ' + data.pages.length + ' sayfa tarandı' +
           (data.unprepared_pages.length ? ' · ' + data.unprepared_pages.length + ' sayfa hazırlanmadı, taranmadı' : '')));
    host.append(head);

    const list = node('div', 'prop-pins');
    let index = 0;
    const rows = [];
    for (const row of data.results) {
      if (!row.candidates.length) continue;
      list.append(node('p', 'prop-note', 'Sayfa ' + row.page + ' — ' + row.candidates.length + ' aday'));
      for (const c of row.candidates) {
        const state = candidateState(c);
        const line = node('label', 'prop-pin-row');
        const use = document.createElement('input');
        use.type = 'checkbox'; use.dataset.cand = String(index); use.checked = state.ready; use.disabled = !state.ready;
        rows[index++] = c;
        line.append(use, node('b', null, c.device_name || '[ad yok]'),
          node('span', 'prop-xy', c.pins.map(p => p.page_pin_texts[0] || '?').join(', ')),
          node('span', 'prop-state', state.text));
        line.addEventListener('mouseenter', () => {
          if (c.page !== page) return;         // hover kamerayı OYNATMAZ: yalnız kutuyu gösterir
          drawAll();
          $('marks').append(el('rect', { x: c.bbox[0], y: c.bbox[1], width: c.bbox[2] - c.bbox[0],
                                         height: c.bbox[3] - c.bbox[1], class: 'prop-box' }));
        });
        list.append(line);
      }
    }
    if (!data.candidates_total) list.append(node('p', 'prop-note', 'Aynı şekilden başka örnek bulunamadı.'));
    host.append(list);

    const buttons = node('div', 'prop-buttons');
    const count = node('span', 'prop-note', '');
    const boxes = () => [...host.querySelectorAll('input[data-cand]')];
    const refreshCount = () => {
      const usable = boxes().filter(b => !b.disabled).length;
      count.textContent = boxes().filter(b => b.checked).length + ' / ' + usable + ' seçili';
    };
    host.addEventListener('change', refreshCount);
    const all = node('button', null, 'Tümünü seç'); all.type = 'button';
    all.addEventListener('click', () => { boxes().forEach(b => { if (!b.disabled) b.checked = true; }); refreshCount(); });
    const none = node('button', null, 'Temizle'); none.type = 'button';
    none.addEventListener('click', () => { boxes().forEach(b => b.checked = false); refreshCount(); });
    const apply = node('button', 'primary', 'Seçilenleri işaretle'); apply.type = 'button';
    apply.addEventListener('click', async () => {
      apply.disabled = true;
      const chosen = [...host.querySelectorAll('input[data-cand]')].filter(b => b.checked)
        .map(b => rows[Number(b.dataset.cand)]);
      try {
        for (const c of chosen)
          await post('/api/mark', { page: c.page, bbox: c.bbox, device: c.device_name,
                                    method: 'P04_CANDIDATE',       // program buldu, sen seçtin: elle değil
                                    pins: c.pins.map(p => ({ point: p.point, pin: p.page_pin_texts[0] })) });
        closeProposal();
        await reload();
      } catch (e) { apply.disabled = false; fail(e); }
    });
    buttons.append(apply, all, none, count);
    refreshCount();
    if (scope !== 'all') {
      const all = node('button', null, 'Tüm sayfalarda ara'); all.type = 'button';
      all.addEventListener('click', () => findSimilar(boxId, 'all'));
      buttons.append(all);
    }
    const close = node('button', null, 'Kapat'); close.type = 'button';
    close.addEventListener('click', closeProposal);
    buttons.append(close, node('span', 'prop-note', data.limitation || ''));
    host.append(buttons);
  } catch (e) { closeProposal(); fail(e); }
}

async function saveProposal() {
  const host = $('proposal');
  const device = $('prop-device').value.trim();
  const pins = [];
  host.querySelectorAll('input[data-use]').forEach(box => {
    if (!box.checked) return;
    const i = Number(box.dataset.use);
    const name = host.querySelector('input[data-pin="' + i + '"]').value.trim();
    pins.push({ point: proposal.pins[i].point, pin: name });
  });
  try {
    if (!pins.length) throw new Error('En az bir uç seçin.');
    const saved = await post('/api/mark', { page: page, bbox: proposal.bbox, device: device, pins: pins });
    closeProposal();
    await reload();
    const boxId = saved.created.box && saved.created.box.id;
    if (boxId) {                       // aynı şekilden bu sayfada başka var mı?
      const host = $('proposal'); host.replaceChildren(); host.hidden = false;
      const head = node('div', 'prop-head');
      head.append(node('b', null, device + ' işaretlendi'),
                  node('span', 'muted', 'aynı şekilden bu sayfada başkaları olabilir'));
      const buttons = node('div', 'prop-buttons');
      const search = node('button', 'primary', 'Bu sayfadaki benzerlerini bul'); search.type = 'button';
      search.addEventListener('click', () => findSimilar(boxId, 'page'));
      const everywhere = node('button', null, 'Tüm sayfalarda ara'); everywhere.type = 'button';
      everywhere.addEventListener('click', () => findSimilar(boxId, 'all'));
      const close = node('button', null, 'Kapat'); close.type = 'button';
      close.addEventListener('click', closeProposal);
      buttons.append(search, everywhere, close);
      host.append(head, buttons);
    }
  } catch (e) { fail(e); }
}

function pageMarks() {
  return (state.pins || []).filter(p => (p.page || 4) === page);
}

const METHOD_TEXT = { MANUAL: 'elle', P04_CANDIDATE: 'program adayı', AGENT_DRAFT: 'ajan taslağı' };

function renderMarks() {
  const host = $('mark-list'); host.replaceChildren();     // SVG'deki 'marks' katmanıyla karışmasın
  const rows = pageMarks();
  $('mark-count').textContent = rows.length;
  if (!rows.length) { host.append(node('p', 'empty', 'Bu sayfada işaret yok.')); return; }
  const groups = new Map();
  for (const p of rows) {
    if (!groups.has(p.device)) groups.set(p.device, []);
    groups.get(p.device).push(p);
  }
  for (const [device, pins] of [...groups].sort((a, b) => a[0].localeCompare(b[0]))) {
    const card = node('div', 'mark-card');
    const head = node('div', 'mark-head');
    head.append(node('b', null, device || '[cihaz adı yok]'),
                node('small', null, pins.map(p => p.pin || '?').join(', ') + ' · ' +
                     [...new Set(pins.map(p => METHOD_TEXT[p.method] || p.method))].join(', ')));
    card.append(head);
    const buttons = node('div', 'mark-buttons');
    const show = node('button', null, 'Çizimde göster'); show.type = 'button';
    show.addEventListener('click', () => focusOn(pins.map(p => p.point), null));
    buttons.append(show);
    // Bu cihazın şablon kutusu: uçlarını içine alan kutu (elle çizilen de, eski tohum da olur).
    const inside = (t, p) => p.point[0] >= t.bbox[0] - 2 && p.point[0] <= t.bbox[2] + 2 &&
                             p.point[1] >= t.bbox[1] - 2 && p.point[1] <= t.bbox[3] + 2;
    const box = (state.templates || []).find(t => t.page === page && pins.every(p => inside(t, p)));
    if (box) {
      const search = node('button', null, 'Benzerlerini ara'); search.type = 'button';
      search.addEventListener('click', () => findSimilar(box.id, 'page'));
      buttons.append(search);
    }
    for (const p of pins) {
      const undo = node('button', 'danger', 'Geri al: ' + (p.pin || '?')); undo.type = 'button';
      undo.title = 'Kayıt silinmez, pasifleşir.';
      undo.addEventListener('click', () => retire(p));
      buttons.append(undo);
    }
    card.append(buttons);
    host.append(card);
  }
}

async function retire(pin) {
  try {
    await post('/api/pins', { id: pin.id, expected_version: pin.version, page: pin.page, device: pin.device,
                              pin: pin.pin, point: pin.point, kind: pin.kind, method: pin.method,
                              note: pin.note || '', active: false });
    await reload();
  } catch (e) { fail(e); }
}

async function reload() {
  state = await api('/api/state');
  await refreshIndex();            // sayfa listesindeki işaret rozeti de yenilensin
  await openPage(page);
}

function setPanels(visible) { for (const p of document.querySelectorAll('#aside .panel')) p.hidden = !visible; }

function showUnprepared(r) {
  data = null; rel = null; clearMarks(); setMarkMode(false);
  $('sheet').setAttribute('href', '/preview.png?page=' + page);
  $('page-label').textContent = (r ? structure(r) + ' · Blatt ' + (r.blatt || '?') + ' · ' : '') + 'fiziksel sayfa ' + page;
  let text = 'Bu sayfa hazırlanmadı. Görünen yalnız küçük önizleme; üzerinde tanıma ve ilişki yok.';
  let button = 'Bu sayfayı hazırla';
  if (r && (r.state === 'QUEUED' || r.state === 'PREPARING')) { text = 'Hazırlanıyor… Bitince sayfa kendiliğinden açılır.'; button = ''; }
  if (r && r.state === 'FAILED') { text = 'Hazırlama başarısız: ' + (r.error || 'bilinmeyen hata') + '. Yeniden denenebilir.'; button = 'Yeniden dene'; }
  if (!index.cache_enabled) { text = 'Bu sayfa hazırlanmadı ve sunucuda sayfa önbelleği kapalı.'; button = ''; }
  $('headline').textContent = text;
  $('unprepared-text').textContent = text;
  $('prepare-one').textContent = button;
  $('prepare-one').hidden = !button;
  $('unprepared').hidden = false;
  setPanels(false);
}

async function openPage(n, focusPoint) {
  const request = ++pageRequest;
  try {
    $('error').hidden = true;
    if (proposal) closeProposal();
    const samePage = page === n && view;      // aynı sayfaya dönerken zoom/kaydırma korunur
    page = n; data = null; rel = null; renderIndex();
    $('marks').replaceChildren();
    const size = pageSize(n);
    $('sheet').setAttribute('width', size[0]); $('sheet').setAttribute('height', size[1]);
    if (!samePage) setView([0, 0, size[0], size[1]]); else setView(view);
    const r = rowOf(n);
    if (!r || r.state !== 'PREPARED') { showUnprepared(r); return; }
    $('unprepared').hidden = true; setPanels(false);
    $('headline').textContent = 'Sayfa ' + n + ' yükleniyor…';
    $('sheet').setAttribute('href', '/page.png?page=' + n);
    const result = await Promise.all([api('/api/overview?page=' + n), api('/api/relations?page=' + n)]);
    if (request !== pageRequest) return; // Eski yanıt yeni sayfanın çizimine uygulanamaz.
    [data, rel] = result;
    setPanels(true);
    render(); drawAll();
    if (focusPoint) highlightEdges([], [focusPoint]);
  } catch (e) { if (request === pageRequest) fail(e); }
}

/* ============================================================ belge (PDF) seçimi */
let doc = null, bridgeWaiters = {};

function renderDocument() {
  const c = doc && doc.current;
  $('doc-name').textContent = c ? (c.name + ' · ' + c.page_count + ' sayfa · ' + c.marks + ' işaret')
                                : 'belge yok';
  $('doc-name').title = c ? c.path : '';
}

async function loadDocument() {
  doc = await api('/api/documents');
  renderDocument();
}

async function openDocument(target) {
  ++pageRequest; // Önceki belgenin yoldaki sayfa yanıtları artık geçersiz.
  const body = typeof target === 'string' ? { path: target } : target;
  const panel = $('doc-panel');
  panel.replaceChildren(node('p', null, 'Açılıyor: ' + (body.path || body.run) + ' …'));
  panel.hidden = false;
  try {
    doc = await post('/api/open', body);
    state = await api('/api/state');
    panel.hidden = true;
    renderDocument();
    await refreshIndex();
    await openPage(Number(state.manifest.physical_page));
  } catch (e) { panel.hidden = true; fail(e); }
}

function askPdf() {
  const bridge = eplanBridge();
  if (bridge) { bridge.postMessage({ action: 'pickPdf' }); return; }   // EPLAN paneli dosya seçtirir
  const panel = $('doc-panel'); panel.replaceChildren(); panel.hidden = false;
  const row = node('div', 'doc-row');
  const input = document.createElement('input');
  input.type = 'text'; input.placeholder = 'PDF yolu: C:\\...\\sema.pdf';
  input.value = (doc && doc.current && doc.current.path) || '';
  const open = node('button', 'primary', 'Aç'); open.type = 'button';
  open.addEventListener('click', () => { panel.hidden = true; openDocument(input.value.trim()); });
  const close = node('button', null, 'Kapat'); close.type = 'button';
  close.addEventListener('click', () => { panel.hidden = true; });
  row.append(node('span', null, 'PDF'), input, open, close);
  panel.append(row);
  if (doc && doc.recent.length) {
    panel.append(node('p', 'hint', 'Var olan çalışmalar (işaretleri korunur):'));
    const list = node('div', 'doc-list');
    for (const r of doc.recent) {
      const b = node('button', null, r.name + '  ·  ' + r.page_count + ' sayfa  ·  ' +
                     (r.marks === null || r.marks === undefined ? 'işaret bilinmiyor' : r.marks + ' işaret') +
                     (r.run === (doc.current && doc.current.run) ? '  ·  açık' : '') +
                     (r.missing_source ? '  ·  kaynak dosya bulunamadı' : ''));
      b.type = 'button'; b.disabled = r.missing_source;
      b.addEventListener('click', () => { panel.hidden = true; openDocument({ run: r.run }); });
      list.append(b);
    }
    panel.append(list);
  }
  panel.append(node('p', 'hint', 'Tarayıcıda yol yazılır; EPLAN panelinde dosya seçme penceresi açılır.'));
}

/* ============================================================ EPLAN köprüsü
   Araç EPLAN'ın içinde (WebView2 paneli) açıldığında `window.chrome.webview` vardır.
   Tarayıcıda açıkken düğme kapalı kalır: aktarımı yalnız EPLAN içindeki add-in yapar. */
function eplanBridge() { return window.chrome && window.chrome.webview ? window.chrome.webview : null; }

function setupBridge() {
  const bridge = eplanBridge();
  const button = $('eplan');
  if (!bridge) {
    button.title = 'Aktarım EPLAN içinden yapılır: EPLAN > UvpPdfToP8Panel. Tarayıcıda kapalıdır.';
    return;
  }
  button.disabled = false;
  button.textContent = "EPLAN'a aktar · ayrı test projesi";
  // Katalog düğmesi yalnız EPLAN panelinde görünür: sembol eşlemesi katalogdan kurulur.
  const catalog = node('button', null, 'EPLAN kataloğunu al'); catalog.type = 'button';
  catalog.addEventListener('click', () => {
    catalog.disabled = true;
    $('headline').textContent = 'EPLAN kataloğu alınıyor (yeni test projesi açılıp kapatılır)…';
    bridge.postMessage({ action: 'catalog',
                         template: 'C:\\ProgramData\\EPLAN\\O_Data\\Electric P8 Data\\2026.0.3\\Templates\\EPLAN\\IEC_bas001.zw9' });
  });
  button.parentNode.insertBefore(catalog, button);
  button.title = 'Paketi üretir ve EPLAN add-in’ine gönderir. Açık projeye yazılmaz.';
  bridge.addEventListener('message', ev => {
    const answer = ev.data || {};
    if (answer.action === 'catalog') {
      const catalogButton = [...document.querySelectorAll('.head-right button')]
        .find(b => b.textContent === 'EPLAN kataloğunu al');
      if (catalogButton) catalogButton.disabled = false;
      $('headline').textContent = answer.ok ? 'Katalog yazıldı: ' + answer.catalog
                                            : 'Katalog alınamadı: ' + (answer.error || 'bilinmeyen');
      return;
    }
    if (answer.action === 'pickPdf') {                 // EPLAN dosya seçme penceresi sonucu
      if (answer.ok && answer.path) openDocument(answer.path);
      else if (answer.error) fail(new Error(answer.error));
      return;
    }
    if (answer.action !== 'import') return;
    button.disabled = false;
    if (answer.ok) $('headline').textContent = 'EPLAN aktarımı çalıştı. Makbuz: ' + answer.receipt +
                                               ' · geri okuma: ' + answer.readback;
    else fail(new Error('EPLAN aktarımı yapılmadı: ' + (answer.error || 'bilinmeyen')));
  });
  button.addEventListener('click', async () => {
    try {
      $('error').hidden = true;
      button.disabled = true;
      const built = await post('/api/package', { pages: [4, 5] });
      if (!built.mapping) throw new Error('Sembol eşlemesi yok (' + built.package +
        ' hazır). Önce EPLAN kataloğu alınıp eşleme dosyası yazılmalı.');
      bridge.postMessage({ action: 'import', package: built.package, mapping: built.mapping });
      $('headline').textContent = 'Paket EPLAN’a gönderildi: ' + built.objects + ' nesne, ' +
                                  built.expected_links + ' beklenen bağ.';
    } catch (e) { button.disabled = false; fail(e); }
  });
}

async function start() {
  try {
    state = await api('/api/state');
    setupBridge();
    await loadDocument();
    $('doc-pick').addEventListener('click', askPdf);
    await refreshIndex();
    $('mark-mode').addEventListener('click', () => {
      const row = rowOf(page);
      if (!row || row.state !== 'PREPARED') return fail(new Error('Önce sayfayı hazırlayın.'));
      setMarkMode(!markMode);
      if (data) render();
    });
    $('f-default').addEventListener('click', () => { showAll = false; renderIndex(); });
    $('f-all').addEventListener('click', () => { showAll = true; renderIndex(); });
    $('q-start').addEventListener('click', () => {
      const pages = index.pages.filter(r => r.default_selected && r.state === 'NOT_PREPARED').map(r => r.page);
      if (pages.length) post('/api/prepare', { action: 'enqueue', pages }).then(refreshIndex).catch(fail);
    });
    $('q-toggle').addEventListener('click', () => {
      const stopped = index.queue && index.queue.stopped;
      post('/api/prepare', { action: stopped ? 'resume' : 'stop' }).then(refreshIndex).catch(fail);
    });
    $('prepare-one').addEventListener('click', () => {
      const r = rowOf(page);
      const body = r && r.state === 'FAILED' ? { action: 'retry', page } : { action: 'enqueue', pages: [page], front: true };
      post('/api/prepare', body).then(refreshIndex).then(() => showUnprepared(rowOf(page))).catch(fail);
    });
    $('page-json').addEventListener('click', async () => {
      const button = $('page-json');
      try {
        $('error').hidden = true;
        button.disabled = true;
        const built = await post('/api/package', { page: page });
        $('headline').textContent = 'Sayfa ' + page + ' paketi yazıldı: ' + built.package +
          ' · ' + built.objects + ' nesne, ' + built.expected_links + ' bağ' +
          (built.issues.length ? ' · ' + built.issues.length + ' uyarı: ' + built.issues[0] : '');
      } catch (e) { fail(e); } finally { button.disabled = false; }
    });
    $('fit').addEventListener('click', () => { const s = pageSize(page); setView([0, 0, s[0], s[1]]); drawAll(); });
    $('zoom-in').addEventListener('click', () => zoom(0.7));
    $('zoom-out').addEventListener('click', () => zoom(1.4));
    const svg = $('svg'); let drag = null, spaceDown = false;
    const typing = e => ['INPUT', 'TEXTAREA'].includes((e.target || {}).tagName);
    svg.addEventListener('contextmenu', e => e.preventDefault());   // sağ tuş = kaydırma
    svg.addEventListener('auxclick', e => e.preventDefault());      // orta tuş = kaydırma

    svg.addEventListener('pointerdown', e => {
      // Kaydırma her modda açık: orta tuş, sağ tuş veya boşluk. Sol tuş işaretlemede kutu çizer.
      const pan = !markMode || spaceDown || e.button === 1 || e.button === 2;
      const handle = e.target && e.target.dataset ? e.target.dataset.h : null;
      const onBox = e.target && e.target.classList && e.target.classList.contains('prop-box');
      drag = { x: e.clientX, y: e.clientY, view: view.slice(), pan: pan,
               start: pan ? null : svgPoint(e), handle: pan ? null : handle,
               moveBox: !pan && !handle && onBox,
               bbox: proposal ? proposal.bbox.slice() : null };
      svg.classList.toggle('drag', pan);
      e.preventDefault();
      try { svg.setPointerCapture(e.pointerId); } catch (err) { /* kalemsiz olay */ }
    });

    svg.addEventListener('pointermove', e => {
      if (!drag) return;
      if (drag.pan) {
        const s = screenScale();
        setView([drag.view[0] - (e.clientX - drag.x) / s, drag.view[1] - (e.clientY - drag.y) / s,
                 drag.view[2], drag.view[3]]);
        return;
      }
      const now = svgPoint(e);
      if (drag.handle && proposal) {                    // kenardan kırp
        const b = proposal.bbox;
        if (drag.handle.includes('w')) b[0] = Math.min(now[0], b[2] - 1);
        if (drag.handle.includes('e')) b[2] = Math.max(now[0], b[0] + 1);
        if (drag.handle.includes('n')) b[1] = Math.min(now[1], b[3] - 1);
        if (drag.handle.includes('s')) b[3] = Math.max(now[1], b[1] + 1);
        drawProposal(proposal, false);
        return;
      }
      if (drag.moveBox && proposal) {                   // kutuyu taşı
        const dx = now[0] - drag.start[0], dy = now[1] - drag.start[1];
        proposal.bbox = [drag.bbox[0] + dx, drag.bbox[1] + dy, drag.bbox[2] + dx, drag.bbox[3] + dy];
        drawProposal(proposal, false);
        return;
      }
      if (Math.abs(e.clientX - drag.x) + Math.abs(e.clientY - drag.y) > 4) {
        drawAll();
        $('marks').append(el('rect', { x: Math.min(drag.start[0], now[0]), y: Math.min(drag.start[1], now[1]),
                                       width: Math.abs(now[0] - drag.start[0]), height: Math.abs(now[1] - drag.start[1]),
                                       class: 'prop-box' }));
      }
    });

    svg.addEventListener('pointerup', e => {
      const started = drag; drag = null;
      svg.classList.remove('drag');
      try { svg.releasePointerCapture(e.pointerId); } catch (err) { /* yakalanmamış olabilir */ }
      if (!started || started.pan) return;              // kaydırma sonrası istek YOK
      if ((started.handle || started.moveBox) && proposal) {
        const b = proposal.bbox;
        // Kutu değişti: uçlar ve adlar yeniden okunur, yazdıkların korunur, kamera oynamaz.
        propose('bbox=' + b.map(v => v.toFixed(2)).join(','), { keepEdits: true, fit: false });
        return;
      }
      const end = svgPoint(e);
      const moved = Math.abs(e.clientX - started.x) + Math.abs(e.clientY - started.y) > 4;
      propose(moved ? 'bbox=' + [started.start[0], started.start[1], end[0], end[1]].map(v => v.toFixed(2)).join(',')
                    : 'point=' + end.map(v => v.toFixed(2)).join(','));
    });

    svg.addEventListener('wheel', e => {                // imleç merkezli zoom
      e.preventDefault();
      const p = svgPoint(e);
      const k = e.deltaY > 0 ? 1.15 : 1 / 1.15;
      setView([p[0] - (p[0] - view[0]) * k, p[1] - (p[1] - view[1]) * k, view[2] * k, view[3] * k]);
    }, { passive: false });

    addEventListener('keydown', e => {
      if (e.code === 'Space' && !typing(e)) { spaceDown = true; svg.classList.add('pan-ready'); e.preventDefault(); return; }
      if (e.key === 'Escape' && proposal) { closeProposal(); return; }
      if (e.key === 'Enter' && proposal && $('prop-device') && !e.shiftKey) { saveProposal(); return; }
      if (typing(e) || e.ctrlKey || e.altKey) return;
      const step = 0.12, [x, y, w, h] = view;
      switch (e.key) {
        case 'ArrowLeft': setView([x - w * step, y, w, h]); break;
        case 'ArrowRight': setView([x + w * step, y, w, h]); break;
        case 'ArrowUp': setView([x, y - h * step, w, h]); break;
        case 'ArrowDown': setView([x, y + h * step, w, h]); break;
        case '+': case '=': zoom(0.7); break;
        case '-': zoom(1.4); break;
        case '0': { const size = pageSize(page); setView([0, 0, size[0], size[1]]); drawAll(); break; }
        case 'i': case 'I': $('mark-mode').click(); break;
        default: return;
      }
      e.preventDefault();
    });
    addEventListener('keyup', e => {
      if (e.code === 'Space') { spaceDown = false; svg.classList.remove('pan-ready'); }
    });
    addEventListener('resize', () => { if (proposal) drawHandles(); });
    await openPage(Number(state.manifest.physical_page));
  } catch (e) { fail(e); }
}
start();
