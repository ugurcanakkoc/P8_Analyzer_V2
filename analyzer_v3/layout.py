"""Şablon yerleşimi: cihazlar UVP çerçevesinin taslak satırlarına oturur.

Şablon satır adı → y verir (tools/sablon_cikar.py, EPLAN çerçevesinden okunur). Hangi ailenin
hangi satıra gittiği müşteri profilindedir: 'template_row', PLC için 'template_row_by_io'
(giriş/çıkış türü 'plc_io_by_part' ile parça kodundan).

  * Cihaz nesnesi bütün olarak kayar, uç aralıkları korunur; ortası satır çizgisine oturur.
    Tek uçlu PLC kutusunda uç kutunun kenarındadır: kutu satıra ortalanır, uç yönüne göre
    box_half_mm yukarıda/aşağıda durur (şablon: çıkış ucu işaretleri y=236, satır y=240).
  * Sayfanın hepsi TEK dx ile yatay kayar; dik teller dik kalır. dx, uçların çoğunu şablon
    ızgarasına oturtan ve bütün cihazları çizim alanında tutan en küçük kaymadır.
  * Aynı satırda aynı yere düşen ikinci cihaz ilkinin kaymasını alır: kaynaktaki dik aralık korunur.
  * Birleşim, kesinti ve potansiyel noktaları bağlı oldukları uçlardan kaynakta yüksekliği en
    yakın olanın kaymasını alır. Uç şablonda ters yöne döndüyse (müşteride tel aşağı, şablonda uç
    yukarı) aradaki dik mesafe aynalanır. Ucun tam üstündeki nokta uca yapışır; bara (L1..PE)
    üstündeki nokta şablon barasına oturur. Bağı olmayan nokta yerinde kalır ve rapora yazılır.
Kaynak koordinat 'source_point_mm' olarak kalır; hiçbir nesne atılmaz, bağ eklenmez.
"""
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FLAT_MM = 0.6        # iki nokta bu kadar yakınsa aynı yatay/dik hatta ya da üst üstedir
SAME_SLOT_MM = 4.0   # aynı satırda bu kadar yakın iki cihaz aynı yeri ister


def load(profile):
    """Profilin şablonu; profil şablon adı vermiyorsa ya da dosya yoksa None."""
    from . import customer
    name = (profile or {}).get('template')
    if not name:
        return None
    path = ROOT / 'output' / 'sablon' / ('%s.json' % customer.valid_name(name))
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else None


def row_y(template, ref):
    """'Klemens' → satırın y'si. "PLC IO'ları#2" yukarıdan ikinci aynı adlı satır; ad baştan eşleşir."""
    name, _, nth = ref.partition('#')
    hits = [r['y'] for r in template.get('rows') or [] if r['label'].startswith(name)]
    index = int(nth) - 1 if nth.isdigit() else 0
    return hits[index] if 0 <= index < len(hits) else None


def _plan(obj, entry, template, profile):
    """Cihazın satırı: (dy, satır, io, şablondaki uç yönü) ya da None (şablonda yeri yok)."""
    io = None
    ref = entry.get('template_row')
    if entry.get('template_row_by_io'):
        io = (profile.get('plc_io_by_part') or {}).get(obj.get('part_number') or '')
        ref = entry['template_row_by_io'].get(io)
    y = row_y(template, ref) if ref else None
    if y is None or not obj.get('pins'):
        return None
    ys = [p['point_mm'][1] for p in obj['pins']]
    half = float(entry.get('box_half_mm') or 0)
    if io and half and len(ys) == 1:
        facing = (entry.get('facing_by_io') or {}).get(io)
        target = y + half if facing == 'Up' else y - half if facing == 'Down' else y
        return target - ys[0], ref, io, facing
    return y - (min(ys) + max(ys)) / 2, ref, io, None


def _page_dx(planned, template):
    """(dx, sorun). Izgara: PLC sayfasında şablonun PLC uç işaretleri, yoksa sütun çizgileri."""
    area, columns = template.get('area') or {}, template.get('columns') or {}
    pitch = columns.get('pitch')
    xs = [p['point_mm'][0] for obj, _ in planned for p in obj['pins']]
    if not (area and pitch and xs):
        return 0.0, None
    plc = [(obj, plan) for obj, plan in planned if plan[2]]
    marks = template.get('pin_marks') or []
    # ponytail: ilk işaret sırası alınır; şablonda PLC dışı işaret sırası çıkarsa satıra göre seçilmeli.
    base = marks[0]['xs'][0] if plc and marks else (columns.get('lines') or [None])[0]
    if base is None:
        return 0.0, None
    # Kutunun ek ucu (1+9'daki 9) kutuyu taşımaz; oy yalnız kutu başlarından.
    anchors = [p['point_mm'][0] for obj, _ in (plc or planned) for p in obj['pins'] if p.get('box_role') != 'extra']
    votes = Counter(round((base - x) % pitch, 2) for x in anchors)
    phase = max(votes, key=lambda ph: (votes[ph], -min(ph, pitch - ph)))
    lo, hi = min(xs), max(xs)
    fits = [phase + k * pitch for k in range(-12, 13)
            if area['x0'] <= lo + phase + k * pitch and hi + phase + k * pitch <= area['x1']]
    if not fits:
        return 0.0, 'cihazlar şablon alanına sığmıyor (%.0f..%.0f mm); yatay kayma uygulanmadı' % (lo, hi)
    return round(min(fits, key=abs), 3), None


def _slot_shifts(planned):
    """Cihaz kimliği → dy. Aynı satırda aynı yere düşen cihaz o yerin ilk cihazının dy'sini alır."""
    shifts, slots, followers = {}, {}, 0
    for obj, plan in sorted(planned, key=lambda t: -max(p['point_mm'][1] for p in t[0]['pins'])):
        dy, ref = plan[0], plan[1]
        x = min(p['point_mm'][0] for p in obj['pins'])
        first = next((d for sx, d in slots.get(ref, ()) if abs(sx - x) < SAME_SLOT_MM), None)
        if first is None:
            slots.setdefault(ref, []).append((x, dy))
            shifts[obj['id']] = dy
        else:
            shifts[obj['id']] = first
            followers += 1
    return shifts, followers


def _follow(objects, links, dx, template):
    """Birleşim/kesinti/potansiyel noktalarını bağlı uçlara göre kaydır; bağsız kalanları döndür."""
    old, new, flipped = {}, {}, set()
    for o in objects:
        if o['kind'] == 'DEVICE':
            for p in o['pins']:
                key = '%s#%s' % (o['id'], p['name'])
                old.setdefault(key, p['source_point_mm'])
                new.setdefault(key, p['point_mm'])
                if p.get('layout_flipped'):
                    flipped.add(key)
        else:
            old[o['id']] = list(o['point_mm'])
    nodes = [o for o in objects if o['kind'] != 'DEVICE']
    near = {}
    for link in links:
        near.setdefault(link['a'], []).append(link['b'])
        near.setdefault(link['b'], []).append(link['a'])
    for o in nodes:   # ucun tam üstündeki nokta (ör. uca konmuş birleşim) o uca bağlı sayılır
        x, y = old[o['id']]
        near.setdefault(o['id'], []).extend(
            key for key in new if abs(old[key][0] - x) <= FLAT_MM and abs(old[key][1] - y) <= FLAT_MM)
    rails = template.get('rails') or {}
    ys = {}
    for link in links:
        a, b = old.get(link['a']), old.get(link['b'])
        if link.get('potential') in rails and a and b and abs(a[1] - b[1]) <= FLAT_MM:
            for end in (link['a'], link['b']):
                if end not in new:          # cihaz ucu baraya çekilmez, yalnız noktalar
                    ys[end] = float(rails[link['potential']])
    pending = sorted(o['id'] for o in nodes if o['id'] not in ys)
    while pending:
        best = None
        for oid in pending:
            y = old[oid][1]
            for other in near.get(oid, ()):
                moved = new[other][1] if other in new else ys.get(other)
                if moved is None or other not in old:
                    continue
                gap = y - old[other][1]
                if best is None or abs(gap) < best[0]:
                    best = (abs(gap), oid, moved + (-gap if other in flipped else gap))
        if best is None:
            break
        ys[best[1]] = best[2]
        pending.remove(best[1])
    area = template.get('area') or {}
    for o in nodes:
        x, y = old[o['id']]
        nx = x + dx
        if area:
            nx = min(max(nx, area['x0']), area['x1'])
        o['source_point_mm'] = [x, y]
        o['point_mm'] = [round(nx, 3), round(ys.get(o['id'], y), 3)]
        new[o['id']] = o['point_mm']
    for link in links:
        if link['a'] in new and link['b'] in new:
            link['source_polyline_mm'] = link.get('polyline_mm')
            link['polyline_mm'] = [new[link['a']], new[link['b']]]
    return pending


def apply(objects, links, template, profile):
    """Sayfa nesnelerini ve bağlarını şablona yerleştir (yerinde değiştirir); rapor döner."""
    from . import customer
    planned, without_row = [], []
    for obj in objects:
        if obj['kind'] != 'DEVICE':
            continue
        plan = _plan(obj, customer.symbol_of(profile, obj['family']) or {}, template, profile)
        if plan:
            planned.append((obj, plan))
        else:
            without_row.append(obj['id'])
    dx, dx_issue = _page_dx(planned, template)
    shifts, followers = _slot_shifts(planned)
    rows = Counter()
    for obj, (_, ref, io, facing) in planned:
        obj['template_row'] = ref
        rows[ref] += 1
        if io:
            obj['io'] = io
        for p in obj['pins']:
            if facing and p.get('wire_direction') in ('Up', 'Down') and p['wire_direction'] != facing:
                p['layout_flipped'] = True
    for obj in objects:
        if obj['kind'] != 'DEVICE':
            continue
        dy = shifts.get(obj['id'], 0.0)
        for p in obj['pins']:
            x, y = p['point_mm']
            p['source_point_mm'] = [x, y]
            p['point_mm'] = [round(x + dx, 3), round(y + dy, 3)]
    unresolved = _follow(objects, links, dx, template)
    return dict(template=template.get('frame'), dx_mm=dx, rows=dict(rows), slot_followers=followers,
                devices_without_row=without_row, nodes_unresolved=unresolved, issue=dx_issue)
