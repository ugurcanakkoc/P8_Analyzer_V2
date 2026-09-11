'use strict';
const NS = 'http://www.w3.org/2000/svg';
const $ = id => document.getElementById(id);
let state = null, data = null, view = null, page = null;

function el(tag, attrs) {
  const node = document.createElementNS(NS, tag);
  Object.entries(attrs || {}).forEach(([k, v]) => node.setAttribute(k, v));
  return node;
}
function node(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}
async function api(path) {
  const r = await fetch(path, { headers: { Accept: 'application/json' } });
  const body = await r.json();
  if (!r.ok) throw new Error(body.error || ('İstek başarısız: ' + r.status));
  return body;
}
function fail(e) {
  const box = $('error');
  box.textContent = 'Hata: ' + e.message;
  box.hidden = false;
}

/* ---------------- çizim ---------------- */
function setView(box) {
  view = box || view;
  $('svg').setAttribute('viewBox', view.join(' '));
}
function fullView() {
  const m = state.manifest;
  setView([0, 0, m.width, m.height]);
}
function zoom(factor) {
  const [x, y, w, h] = view;
  const nw = w * factor, nh = h * factor;
  setView([x + (w - nw) / 2, y + (h - nh) / 2, nw, nh]);
}
function clearMarks() { $('marks').replaceChildren(); }

function drawAll() {
  clearMarks();
  const g = $('marks');
  for (const c of data.connections) {
    const [a, b] = c.points;
    g.append(el('line', { x1: a[0], y1: a[1], x2: b[0], y2: b[1], class: 'wire-line' }));
    for (const p of c.points) g.append(el('circle', { cx: p[0], cy: p[1], r: 2.1, class: 'wire-end' }));
  }
  for (const n of data.networks)
    for (const p of n.points) g.append(el('circle', { cx: p[0], cy: p[1], r: 2.1, class: 'net-end' }));
  for (const s of data.singles)
    for (const p of s.points) g.append(el('circle', { cx: p[0], cy: p[1], r: 2.1, class: 'net-end' }));
  for (const t of data.todo)
    for (const p of t.points || []) g.append(el('circle', { cx: p[0], cy: p[1], r: 3.1, class: 'todo-end' }));
}

function focusOn(points, box) {
  drawAll();
  const g = $('marks');
  if (points && points.length === 2)
    g.append(el('line', { x1: points[0][0], y1: points[0][1], x2: points[1][0], y2: points[1][1], class: 'focus' }));
  for (const p of points || []) g.append(el('circle', { cx: p[0], cy: p[1], r: 4.2, class: 'focus' }));
  if (box) {
    const pad = 26;
    g.append(el('rect', {
      x: box[0] - pad, y: box[1] - pad,
      width: Math.max(box[2] - box[0], 1) + pad * 2,
      height: Math.max(box[3] - box[1], 1) + pad * 2, class: 'focus-box'
    }));
    const w = Math.max(box[2] - box[0], 60) + pad * 4;
    const h = Math.max(box[3] - box[1], 60) + pad * 4;
    setView([box[0] - (w - (box[2] - box[0])) / 2, box[1] - (h - (box[3] - box[1])) / 2, w, h]);
  }
}

/* ---------------- sağ panel ---------------- */
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

function render() {
  $('page-label').textContent = data.page_label;
  $('headline').textContent = data.headline;
  $('note').textContent = data.note;

  const wires = $('wires'); wires.replaceChildren();
  $('wire-count').textContent = data.connections.length;
  if (!data.connections.length) wires.append(node('p', 'empty', 'Bu sayfada takip edilen tel yok.'));
  for (const c of data.connections)
    wires.append(rowFor(c.plain, c.evidence + ' · uygulama: ' +
      (c.implementation === 'BELIRSIZ' ? 'belirlenmedi' : c.implementation.toLowerCase()),
      c.state, () => focusOn(c.points, c.bbox)));

  const nets = $('nets'); nets.replaceChildren();
  const lines = data.line_relations || [];
  $('net-count').textContent = data.networks.length + lines.length;
  if (!data.networks.length && !lines.length) nets.append(node('p', 'empty', 'Ortak hat yok.'));
  // Kullanıcı teyitli HAT ilişkisi (örn. C01) burada görünür — tel olarak değil.
  for (const r of lines)
    nets.append(rowFor(r.plain + '   [' + r.reference + ']', r.warning + ' ' + r.state,
      'hat seviyesinde teyitli', () => focusOn(r.points, r.bbox), 'net warn'));
  for (const n of data.networks)
    nets.append(rowFor(n.plain, n.warning, 'tel çifti üretilmedi',
      () => focusOn(n.points, n.bbox), 'net warn'));

  const singles = $('singles'); singles.replaceChildren();
  $('single-count').textContent = data.singles.length;
  if (!data.singles.length) singles.append(node('p', 'empty', 'Yarım kalan kayıt yok.'));
  for (const s of data.singles)
    singles.append(rowFor(s.plain, s.why, null, () => focusOn(s.points, s.bbox)));

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
      const b = node('button', null, 'Çizimde göster');
      b.type = 'button';
      b.addEventListener('click', () => focusOn(t.points, null));
      card.append(b);
    }
    todo.append(card);
  }

  const s = data.summary;
  const box = $('summary'); box.replaceChildren();
  const cells = [['Bulunan tel', s.connections], ['Ortak hat', s.networks],
                 ['İşaretli uç', s.marks], ['Yarım kayıt', s.singles],
                 ['Çözülmemiş yer', s.unresolved],
                 ['Yenilenecek inceleme', s.reviews_needing_refresh]];
  for (const [label, value] of cells) {
    const cell = node('div');
    cell.append(node('b', null, String(value)), node('span', null, label));
    box.append(cell);
  }

  // Üç boyut ayrı gösterilir: ilişki teyidi, askıya alınan teyit, üretime uygunluk.
  const dims = $('dimensions'); dims.replaceChildren();
  for (const d of data.dimensions || []) {
    const cell = node('div', 'dim' + (d.value ? ' on' : ''));
    cell.append(node('b', null, String(d.value)), node('span', 'dim-label', d.label),
                node('span', 'dim-hint', d.hint));
    dims.append(cell);
  }
}

/* ---------------- yükleme ---------------- */
async function load(number) {
  try {
    $('error').hidden = true;
    data = await api('/api/overview?page=' + number);
    page = number;
    $('sheet').setAttribute('href', '/page.png?page=' + number);
    const size = state.pages[String(number)] || [state.manifest.width, state.manifest.height];
    $('sheet').setAttribute('width', size[0]);
    $('sheet').setAttribute('height', size[1]);
    setView([0, 0, size[0], size[1]]);
    render();
    drawAll();
  } catch (e) { fail(e); }
}

async function start() {
  try {
    state = await api('/api/state');
    const select = $('page');
    select.replaceChildren(...Object.keys(state.pages).map(n => {
      const o = document.createElement('option');
      o.value = n; o.textContent = 'Sayfa ' + n;
      return o;
    }));
    const first = String(state.manifest.physical_page);
    select.value = first;
    select.addEventListener('change', () => load(Number(select.value)));
    $('fit').addEventListener('click', () => {
      const size = state.pages[String(page)];
      setView([0, 0, size[0], size[1]]);
      drawAll();
    });
    $('zoom-in').addEventListener('click', () => zoom(0.7));
    $('zoom-out').addEventListener('click', () => zoom(1.4));
    const svg = $('svg');
    let drag = null;
    svg.addEventListener('pointerdown', e => {
      drag = { x: e.clientX, y: e.clientY, view: view.slice() };
      svg.classList.add('drag'); svg.setPointerCapture(e.pointerId);
    });
    svg.addEventListener('pointermove', e => {
      if (!drag) return;
      const rect = svg.getBoundingClientRect();
      const sx = drag.view[2] / rect.width, sy = drag.view[3] / rect.height;
      setView([drag.view[0] - (e.clientX - drag.x) * sx,
               drag.view[1] - (e.clientY - drag.y) * sy, drag.view[2], drag.view[3]]);
    });
    svg.addEventListener('pointerup', e => { drag = null; svg.classList.remove('drag'); svg.releasePointerCapture(e.pointerId); });
    await load(Number(first));
  } catch (e) { fail(e); }
}
start();
