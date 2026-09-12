'use strict';
/* UVP · Cihaz işaretle — tek ekran.
 *
 * Amaç: PDF'te gezip PROGRAMIN BULAMADIĞI cihazı elle işaretlemek. Seçimin içine giren
 * ama sembole ait olmayan parça (etiket kırıntısı, komşu telin ucu) kapatılabilir; parça
 * silinmez, yalnız şekle ve benzer aramaya girmez.
 *
 * Koordinat: her şey PDF puntosu. SVG viewBox da punto; görüntü sayfa boyutunda basılır.
 */

const $ = (id) => document.getElementById(id);
const SVGNS = 'http://www.w3.org/2000/svg';

let state = null;          // /api/state
let index = [];            // /api/pages
let page = null;
let view = [0, 0, 100, 100];
let proposal = null;       // { bbox, pins, objects, excluded, device, issues }
let lastBoxId = null;
let busy = false;

/* ============================================================ sunucu */

async function api(path) {
  const r = await fetch(path, { headers: { 'Accept': 'application/json' } });
  const body = await r.json();
  if (!r.ok) throw new Error(body.error || ('HTTP ' + r.status));
  return body;
}

async function post(path, payload) {
  const r = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Pilot-Token': state.csrf_token },
    body: JSON.stringify(payload),
  });
  const body = await r.json();
  if (!r.ok) throw new Error(body.error || ('HTTP ' + r.status));
  return body;
}

function say(text, bad) {
  $('log').textContent = text;
  $('log').style.color = bad ? '#b02a37' : '';
}

function fail(error) { say(String(error.message || error), true); }

/* ============================================================ sayfa */

function rowOf(n) { return index.find((r) => r.page === n) || null; }

function pageSize(n) {
  const v = state.viewable[String(n)];
  return v || [state.manifest.width, state.manifest.height];
}

function prepared(n) {
  return Boolean(state.viewable[String(n)]);
}

function screenScale() {
  const r = $('svg').getBoundingClientRect();
  return Math.min(r.width / view[2], r.height / view[3]);
}

/* Ekran noktası → çizim noktası. viewBox 'meet' ile ortalandığı için boşluk hesaba katılır. */
function svgPoint(ev) {
  const r = $('svg').getBoundingClientRect();
  const s = screenScale();
  return [view[0] + (ev.clientX - r.left - (r.width - view[2] * s) / 2) / s,
          view[1] + (ev.clientY - r.top - (r.height - view[3] * s) / 2) / s];
}

function setView(box) {
  let [x, y, w, h] = box || view;
  const [pw, ph] = page ? pageSize(page) : [w, h];
  const limit = Math.min(Math.max(w, 12), pw * 1.5) / w;      // en fazla sayfanın 1.5 katı
  w *= limit; h *= limit;
  x = Math.min(Math.max(x, -w / 2), pw - w / 2);
  y = Math.min(Math.max(y, -h / 2), ph - h / 2);
  view = [x, y, w, h];
  $('svg').setAttribute('viewBox', view.join(' '));
  if (proposal) drawSelection();
}

function fitPage() {
  const [w, h] = pageSize(page);
  setView([0, 0, w, h]);
}

async function loadIndex() {
  index = (await api('/api/pages')).pages || [];
}

async function loadState() {
  state = await api('/api/state');
}

async function openPage(n, keepView) {
  closeProposal();
  page = n;
  $('page-no').value = String(n);
  const size = pageSize(n);
  $('sheet').setAttribute('width', size[0]);
  $('sheet').setAttribute('height', size[1]);
  if (!keepView) fitPage(); else setView(view);
  const row = rowOf(n);
  const where = row ? [row.anlage, row.einbauort, row.blatt].filter(Boolean).join(' ') : '';
  if (prepared(n)) {
    $('sheet').setAttribute('href', '/page.png?page=' + n);
    $('prepare').hidden = true;
    $('page-state').textContent = where + ' · hazır';
    say('Sayfa ' + n + ' açıldı.');
  } else {
    $('sheet').removeAttribute('href');
    $('prepare').hidden = false;
    $('page-state').textContent = where + ' · hazırlanmadı';
    say('Sayfa ' + n + ' hazırlanmadı. Geometrisi olmadan işaret konamaz.');
  }
  drawExisting();
}

async function preparePage() {
  try {
    say('Sayfa ' + page + ' kuyruğa alındı…');
    await post('/api/prepare', { action: 'enqueue', pages: [page], front: true });
    const started = Date.now();
    const timer = setInterval(async () => {
      try {
        await loadState();
        if (prepared(page)) { clearInterval(timer); await loadIndex(); openPage(page); }
        else if (Date.now() - started > 300000) { clearInterval(timer); say('Hazırlama uzun sürdü.', true); }
      } catch (e) { clearInterval(timer); fail(e); }
    }, 2000);
  } catch (e) { fail(e); }
}

/* ============================================================ çizim */

function el(name, attrs) {
  const node = document.createElementNS(SVGNS, name);
  for (const key in attrs) node.setAttribute(key, attrs[key]);
  return node;
}

function drawExisting() {
  const layer = $('existing');
  layer.replaceChildren();
  if (!$('show-marks').checked || !state) return;
  for (const box of state.boxes) {
    if ((box.page || 4) !== page || box.active === false) continue;
    const b = box.bbox;
    layer.appendChild(el('rect', { x: b[0], y: b[1], width: b[2] - b[0], height: b[3] - b[1], class: 'mark' }));
  }
  for (const pin of state.pins) {
    if ((pin.page || 4) !== page) continue;
    layer.appendChild(el('circle', { cx: pin.point[0], cy: pin.point[1], r: 0.7, class: 'mark-dot' }));
  }
}

function drawSelection() {
  const parts = $('parts');
  const sel = $('selection');
  parts.replaceChildren();
  sel.replaceChildren();
  if (!proposal) return;
  const dropped = new Set(proposal.excluded || []);

  for (const o of proposal.objects || []) {
    const off = dropped.has(o.id);
    let shape, hit;
    if (o.kind === 'segment') {
      const attrs = { x1: o.a[0], y1: o.a[1], x2: o.b[0], y2: o.b[1] };
      shape = el('line', Object.assign({ class: 'part' + (off ? ' off' : '') }, attrs));
      hit = el('line', Object.assign({ class: 'part-hit' }, attrs));
    } else {
      const b = o.bbox;
      const attrs = { x: b[0], y: b[1], width: Math.max(b[2] - b[0], 0.3), height: Math.max(b[3] - b[1], 0.3) };
      shape = el('rect', Object.assign({ class: 'part' + (off ? ' off' : '') }, attrs));
      hit = el('rect', Object.assign({ class: 'part-hit' }, attrs));
    }
    hit.addEventListener('pointerdown', (ev) => { ev.stopPropagation(); toggleObject(o.id); });
    parts.appendChild(shape);
    parts.appendChild(hit);
  }

  const b = proposal.bbox;
  sel.appendChild(el('rect', { x: b[0], y: b[1], width: b[2] - b[0], height: b[3] - b[1], class: 'sel-box' }));
  for (const p of proposal.pins || []) {
    sel.appendChild(el('circle', { cx: p.point[0], cy: p.point[1], r: 0.6, class: 'pin-dot' }));
  }
  const size = 7 / screenScale();                       // tutamaç ekranda sabit büyüklükte
  const corners = [[b[0], b[1]], [b[2], b[1]], [b[0], b[3]], [b[2], b[3]]];
  corners.forEach((c, i) => {
    const handle = el('rect', { x: c[0] - size / 2, y: c[1] - size / 2, width: size, height: size, class: 'handle' });
    handle.addEventListener('pointerdown', (ev) => startResize(ev, i));
    sel.appendChild(handle);
  });
}

/* ============================================================ seçim */

function closeProposal() {
  proposal = null;
  lastBoxId = null;
  $('panel').hidden = true;
  $('similar-out').replaceChildren();
  drawSelection();
}

async function propose(query) {
  if (busy) return;
  busy = true;
  try {
    const dropped = (proposal && proposal.excluded) || [];
    const drop = dropped.length ? '&exclude=' + encodeURIComponent(dropped.join(',')) : '';
    const found = await api('/api/propose?page=' + page + '&' + query + drop);
    proposal = found;
    lastBoxId = null;
    renderPanel();
    drawSelection();
    say(found.device ? ('Öneri: ' + found.device) : 'Cihaz adı okunamadı; siz yazın.');
  } catch (e) {
    fail(e);
  } finally {
    busy = false;
  }
}

function toggleObject(id) {
  if (!proposal) return;
  const dropped = new Set(proposal.excluded || []);
  if (dropped.has(id)) dropped.delete(id); else dropped.add(id);
  proposal.excluded = Array.from(dropped).sort();
  const b = proposal.bbox;
  propose('bbox=' + b.join(','));
}

function renderPanel() {
  $('panel').hidden = false;
  $('device').value = proposal.device || '';
  $('device-note').textContent = proposal.device_source
    ? ('ad kaynağı: ' + proposal.device_source) : 'ad bu sayfanın yazısından okunamadı';

  const pins = $('pins');
  pins.replaceChildren();
  (proposal.pins || []).forEach((p, i) => {
    const li = document.createElement('li');
    const input = document.createElement('input');
    input.type = 'text';
    input.value = p.pin || '';
    input.placeholder = 'uç adı';
    input.addEventListener('input', () => { proposal.pins[i].pin = input.value; });
    const where = document.createElement('span');
    where.className = 'where';
    where.textContent = p.point[0].toFixed(1) + ', ' + p.point[1].toFixed(1);
    const drop = document.createElement('button');
    drop.textContent = '✕';
    drop.title = 'Bu ucu alma';
    drop.addEventListener('click', () => { proposal.pins.splice(i, 1); renderPanel(); drawSelection(); });
    li.append(input, where, drop);
    if (p.already_label) {
      const note = document.createElement('span');
      note.className = 'where';
      note.textContent = 'kayıtlı: ' + p.already_label;
      li.append(note);
    }
    pins.appendChild(li);
  });
  if (!(proposal.pins || []).length) {
    const li = document.createElement('li');
    li.className = 'off';
    li.textContent = 'Uç bulunamadı — kutuya giren tel yok.';
    pins.appendChild(li);
  }

  const objects = $('objects');
  objects.replaceChildren();
  const dropped = new Set(proposal.excluded || []);
  (proposal.objects || []).forEach((o) => {
    const li = document.createElement('li');
    const box = document.createElement('input');
    box.type = 'checkbox';
    box.checked = !dropped.has(o.id);
    box.addEventListener('change', () => toggleObject(o.id));
    const name = document.createElement('span');
    name.textContent = (o.kind === 'segment' ? 'çizgi' : 'eğri') + ' · ' + o.id;
    li.className = dropped.has(o.id) ? 'off' : '';
    li.append(box, name);
    if (!o.inside) {
      const note = document.createElement('span');
      note.className = 'where';
      note.textContent = 'kutuya taşıyor';
      li.append(note);
    }
    objects.appendChild(li);
  });

  const issues = $('issues');
  issues.replaceChildren();
  for (const text of proposal.issues || []) {
    const li = document.createElement('li');
    li.textContent = text;
    issues.appendChild(li);
  }
  $('similar').disabled = true;
  $('similar').title = 'Önce kaydet';
}

async function save() {
  if (!proposal) return;
  const device = $('device').value.trim();
  if (!device) { say('Cihaz adı boş olamaz.', true); $('device').focus(); return; }
  const pins = (proposal.pins || []).filter((p) => String(p.pin || '').trim());
  if (!pins.length) { say('En az bir uç adı gerekir.', true); return; }
  try {
    const saved = await post('/api/mark', {
      page: page,
      device: device,
      bbox: proposal.bbox,
      exclude: proposal.excluded || [],
      pins: pins.map((p) => ({ point: p.point, pin: String(p.pin).trim() })),
    });
    lastBoxId = saved.created.box ? saved.created.box.id : null;
    await loadState();
    drawExisting();
    $('similar').disabled = !lastBoxId;
    $('similar').title = lastBoxId ? 'Aynı şekli diğer sayfalarda ara' : 'Kutu kaydedilmedi';
    const off = (proposal.excluded || []).length;
    say('Kaydedildi: ' + device + ' · ' + pins.length + ' uç' + (off ? (' · ' + off + ' parça dışarıda') : ''));
  } catch (e) { fail(e); }
}

async function findSimilar() {
  if (!lastBoxId) return;
  const out = $('similar-out');
  out.replaceChildren();
  out.textContent = 'aranıyor…';
  try {
    const result = await api('/api/similar?template=' + encodeURIComponent(lastBoxId) + '&pages=ALL');
    out.replaceChildren();
    const head = document.createElement('p');
    head.className = 'muted';
    head.textContent = result.candidates_total + ' aday · ' + result.pages.length + ' sayfa tarandı · '
      + result.unprepared_pages.length + ' sayfa hazırlanmadı (tarandı sayılmaz)';
    out.appendChild(head);
    for (const row of result.results) {
      if (!row.candidates.length) continue;
      const link = document.createElement('a');
      link.textContent = 'Sayfa ' + row.page + ': ' + row.candidates.length + ' aday';
      link.addEventListener('click', () => openPage(row.page));
      out.appendChild(link);
    }
  } catch (e) { out.textContent = ''; fail(e); }
}

/* ============================================================ fare ve klavye */

let drag = null;

function onPointerDown(ev) {
  if (ev.button !== 0 && ev.button !== 1) return;
  if (!page || !prepared(page)) return;
  const start = svgPoint(ev);
  const boxing = ev.shiftKey || ev.button === 1;
  drag = { start: start, view: view.slice(), boxing: boxing, moved: false, node: null };
  $('svg').classList.toggle(boxing ? 'boxing' : 'panning', true);
  $('svg').setPointerCapture(ev.pointerId);
}

function onPointerMove(ev) {
  if (!drag) return;
  const at = svgPoint(ev);
  const dx = at[0] - drag.start[0], dy = at[1] - drag.start[1];
  if (!drag.moved && Math.abs(dx) + Math.abs(dy) < 0.5) return;
  drag.moved = true;
  if (drag.boxing) {
    if (!drag.node) { drag.node = el('rect', { class: 'sel-box' }); $('selection').appendChild(drag.node); }
    drag.node.setAttribute('x', Math.min(drag.start[0], at[0]));
    drag.node.setAttribute('y', Math.min(drag.start[1], at[1]));
    drag.node.setAttribute('width', Math.abs(dx));
    drag.node.setAttribute('height', Math.abs(dy));
  } else {
    setView([drag.view[0] - dx, drag.view[1] - dy, drag.view[2], drag.view[3]]);
    drag.start = svgPoint(ev);                 // kaydırmada başlangıç imlecin altında kalır
  }
}

function onPointerUp(ev) {
  if (!drag) return;
  const at = svgPoint(ev);
  const started = drag;
  drag = null;
  $('svg').classList.remove('panning', 'boxing');
  if (started.boxing && started.moved) {
    const box = [Math.min(started.start[0], at[0]), Math.min(started.start[1], at[1]),
                 Math.max(started.start[0], at[0]), Math.max(started.start[1], at[1])];
    if (box[2] - box[0] > 0.5 && box[3] - box[1] > 0.5) {
      proposal = null;
      propose('bbox=' + box.map((v) => v.toFixed(2)).join(','));
      return;
    }
  }
  if (!started.moved && !started.boxing) {
    proposal = null;
    propose('point=' + at.map((v) => v.toFixed(2)).join(','));
  }
  drawSelection();
}

function startResize(ev, corner) {
  ev.stopPropagation();
  const box = proposal.bbox.slice();
  const move = (m) => {
    const at = svgPoint(m);
    if (corner === 0) { box[0] = at[0]; box[1] = at[1]; }
    else if (corner === 1) { box[2] = at[0]; box[1] = at[1]; }
    else if (corner === 2) { box[0] = at[0]; box[3] = at[1]; }
    else { box[2] = at[0]; box[3] = at[1]; }
    proposal.bbox = [Math.min(box[0], box[2]), Math.min(box[1], box[3]),
                     Math.max(box[0], box[2]), Math.max(box[1], box[3])];
    drawSelection();
  };
  const done = () => {
    window.removeEventListener('pointermove', move);
    window.removeEventListener('pointerup', done);
    const b = proposal.bbox;
    if (b[2] - b[0] > 0.5 && b[3] - b[1] > 0.5) propose('bbox=' + b.map((v) => v.toFixed(2)).join(','));
  };
  window.addEventListener('pointermove', move);
  window.addEventListener('pointerup', done);
}

function onWheel(ev) {
  ev.preventDefault();
  const at = svgPoint(ev);
  const factor = ev.deltaY > 0 ? 1.2 : 1 / 1.2;
  const w = view[2] * factor, h = view[3] * factor;
  setView([at[0] - (at[0] - view[0]) * factor, at[1] - (at[1] - view[1]) * factor, w, h]);
}

function step(delta) {
  const order = index.map((r) => r.page);
  const at = order.indexOf(page);
  const next = order[Math.min(Math.max(at + delta, 0), order.length - 1)];
  if (next && next !== page) openPage(next);
}

function onKey(ev) {
  const typing = /^(INPUT|TEXTAREA)$/.test(ev.target.tagName);
  if (ev.key === 'Escape') { closeProposal(); return; }
  if (ev.key === 'Enter' && proposal) { ev.preventDefault(); save(); return; }
  if (typing) return;
  if (ev.key === 'PageUp') { ev.preventDefault(); step(-1); }
  else if (ev.key === 'PageDown') { ev.preventDefault(); step(1); }
  else if (ev.key === '0') fitPage();
}

/* ============================================================ açılış */

async function start() {
  try {
    await loadState();
    await loadIndex();
    const first = state.manifest.physical_page;
    $('page-no').addEventListener('change', () => {
      const n = parseInt($('page-no').value, 10);
      if (n && rowOf(n)) openPage(n); else say('Böyle bir sayfa yok.', true);
    });
    $('prev').addEventListener('click', () => step(-1));
    $('next').addEventListener('click', () => step(1));
    $('fit').addEventListener('click', fitPage);
    $('prepare').addEventListener('click', preparePage);
    $('save').addEventListener('click', save);
    $('cancel').addEventListener('click', closeProposal);
    $('similar').addEventListener('click', findSimilar);
    $('show-marks').addEventListener('change', drawExisting);
    const svg = $('svg');
    svg.addEventListener('pointerdown', onPointerDown);
    svg.addEventListener('pointermove', onPointerMove);
    svg.addEventListener('pointerup', onPointerUp);
    svg.addEventListener('wheel', onWheel, { passive: false });
    window.addEventListener('keydown', onKey);
    window.addEventListener('resize', () => setView(view));
    await openPage(first);
  } catch (e) { fail(e); }
}

start();
