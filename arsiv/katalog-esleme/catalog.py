"""K2/K3 — EPLAN sembol kataloğunu vektör olarak oku, PDF şekliyle eşleştir.

Katalog PDF'ini `UvpPdfToP8Catalog` üretir: her hücrede bir sembol varyantı ve sol alt
köşesinde `C0001` biçiminde bir kod yazısı vardır. Hücre kutusu bu kodun PDF'teki
konumundan çıkarılır — mm ↔ PDF nokta dönüşümü TAHMİN EDİLMEZ, kodların kendi aralığından
ölçülür.

Şekiller mm'ye çevrilip kutularının sol üst köşesine taşınır; müşteri belgesindeki şekil de
aynı biçime getirilince ikisi doğrudan karşılaştırılabilir. Eşleşme PUANLIDIR: karar
kullanıcınındır, bu modül yalnız aday listeler.
"""
import json
from pathlib import Path
import re

CODE = re.compile(r'^C\d{4}$')
MM_TOL = 0.4          # mm — aynı satır sayılmak için izin verilen kayma
MIN_ROWS = 1


def load_layout(path):
    """`yerlesim.json` — action'ın yazdığı hücre kaydı."""
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if not data.get('cells'):
        raise ValueError('Yerleşim kaydında hücre yok: %s' % path)
    return data


def code_words(words):
    """Yalnız hücre kodu yazıları (C0001…). Başka yazı hücre bulmada kullanılmaz."""
    return [w for w in words if CODE.match((w.get('text') or '').strip())]


def scale_from_codes(codes, cell_mm):
    """Bir PDF noktası kaç mm? Aynı satırdaki komşu kodların arası tam bir hücredir.

    Ölçek tahmin edilmez, ölçülür. Tek kod varsa ölçülemez ve None döner.
    """
    rows = {}
    for w in codes:
        key = round((w['top'] + w['bottom']) / 2, 1)
        rows.setdefault(key, []).append(w)
    gaps = []
    for members in rows.values():
        xs = sorted(w['x0'] for w in members)
        gaps += [b - a for a, b in zip(xs, xs[1:]) if b - a > 1]
    if not gaps:
        return None
    gaps.sort()
    pitch = gaps[len(gaps) // 2]          # ortanca: tek tük boş hücre ölçeği bozmasın
    return cell_mm / pitch


def cell_box(word, mm_per_pt, cell_mm, label_offset_mm=0.8):
    """Kod yazısının PDF konumundan hücre kutusu (x0, top, x1, bottom) — PDF noktası."""
    side = cell_mm / mm_per_pt
    offset = label_offset_mm / mm_per_pt
    x0 = word['x0'] - offset
    bottom = word['bottom'] + offset
    return (x0, bottom - side, x0 + side, bottom)


def _inside(box, x0, top, x1, bottom):
    return box[0] <= x0 and x1 <= box[2] and box[1] <= top and bottom <= box[3]


def shape_rows(box, segments, curves, mm_per_pt):
    """Kutunun içindeki çizim, mm cinsinden ve kendi sol üst köşesine taşınmış satırlar.

    Kutunun tamamen içinde kalmayan nesne alınmaz: komşu hücreye taşan bir parça şekli
    kirletir. Kaç nesnenin bu yüzden atlandığı da döner, sessiz düşürme olmaz.
    """
    picked, dropped = [], 0
    for s in segments:
        (ax, ay), (bx, by) = s['a'], s['b']
        if _inside(box, min(ax, bx), min(ay, by), max(ax, bx), max(ay, by)):
            picked.append(('line', ax, ay, bx, by, bool(s.get('dash'))))
        elif _overlaps(box, min(ax, bx), min(ay, by), max(ax, bx), max(ay, by)):
            dropped += 1
    for c in curves:
        x0, y0, x1, y1 = c['bbox']
        if _inside(box, x0, y0, x1, y1):
            picked.append(('curve', x0, y0, x1, y1, bool(c.get('fill'))))
        elif _overlaps(box, x0, y0, x1, y1):
            dropped += 1
    if not picked:
        return dict(rows=[], size_mm=None, dropped=dropped)
    xs = [v for r in picked for v in (r[1], r[3])]
    ys = [v for r in picked for v in (r[2], r[4])]
    ox, oy = min(xs), min(ys)
    rows = []
    for kind, ax, ay, bx, by, flag in picked:
        a = (round((ax - ox) * mm_per_pt, 2), round((ay - oy) * mm_per_pt, 2))
        b = (round((bx - ox) * mm_per_pt, 2), round((by - oy) * mm_per_pt, 2))
        low, high = sorted([a, b])        # uç sırası PDF'te keyfîdir
        rows.append((kind, low[0], low[1], high[0], high[1], flag))
    return dict(rows=sorted(rows), dropped=dropped,
                size_mm=[round((max(xs) - ox) * mm_per_pt, 2), round((max(ys) - oy) * mm_per_pt, 2)])


def _overlaps(box, x0, top, x1, bottom):
    return not (x1 < box[0] or x0 > box[2] or bottom < box[1] or top > box[3])


def page_shapes(words, segments, curves, cell_mm):
    """Bir katalog sayfasındaki hücreler: kod → şekil satırları."""
    codes = code_words(words)
    mm_per_pt = scale_from_codes(codes, cell_mm)
    if mm_per_pt is None:
        return dict(cells={}, note='Ölçek ölçülemedi: sayfada yan yana iki hücre kodu yok.')
    out = {}
    for w in codes:
        code = w['text'].strip()
        out[code] = shape_rows(cell_box(w, mm_per_pt, cell_mm), segments, curves, mm_per_pt)
    return dict(cells=out, mm_per_pt=round(mm_per_pt, 6))


def read_pdf(pdf_path, cell_mm, pages=None):
    """Katalog PDF'ini oku (görüntü üretmeden). Sayfa sırası action'ın sayfa sırasıdır."""
    import pdfplumber
    result = {}
    with pdfplumber.open(str(pdf_path)) as pdf:
        for number, page in enumerate(pdf.pages, start=1):
            if pages and number not in pages:
                continue
            segments = [dict(a=(p[0][0], p[0][1]), b=(p[1][0], p[1][1]), dash=bool(line.get('dash')))
                        for line in page.lines
                        for p in [line.get('pts', [])] if len(p) == 2]
            curves = [dict(bbox=(c['x0'], c['top'], c['x1'], c['bottom']), fill=bool(c.get('fill')))
                      for c in page.curves]
            found = page_shapes(page.extract_words(), segments, curves, cell_mm)
            for code, shape in found.get('cells', {}).items():
                result[code] = dict(shape, page=number)
    return result


def build(layout_path, pdf_path, out_path):
    """Yerleşim kaydı + katalog PDF'i → sembol şekilleri veritabanı (JSON)."""
    layout = load_layout(layout_path)
    cell_mm = float(layout.get('cell_mm') or 24)
    shapes = read_pdf(pdf_path, cell_mm)
    entries, missing = [], []
    for cell in layout['cells']:
        shape = shapes.get(cell['code'])
        if not shape or not shape['rows']:
            missing.append(dict(code=cell['code'], library=cell['library'], symbol=cell['symbol'],
                                variant=cell['variant'],
                                reason='PDF hücresinde çizim bulunamadı' if shape else
                                       'Hücre kodu PDF\'te okunamadı'))
            continue
        entries.append(dict(code=cell['code'], library=cell['library'], symbol=cell['symbol'],
                            variant=cell['variant'], symbol_type=cell.get('symbol_type'),
                            connection_points=cell.get('connection_points', []),
                            rows=shape['rows'], size_mm=shape['size_mm'],
                            dropped_objects=shape['dropped']))
    groups = group_shapes(entries)
    data = dict(contract='uvp.pdf2p8.catalog-shapes', contract_version='1.0', cell_mm=cell_mm,
                source_layout=str(layout_path), source_pdf=str(pdf_path),
                symbols=entries, groups=groups, without_shape=missing)
    Path(out_path).write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    return data


def group_shapes(entries):
    """Aynı çizime sahip semboller tek grup olur.

    ÖLÇÜM (200'lük deneme kataloğu): 165 sembol, 59 ayrı şekil. Aynı şekli 12 sembol
    paylaşabiliyor; hepsini ayrı aday diye göstermek kullanıcıyı boğar. Grup üyeleri
    ATILMAZ, listelenir — seçim yine kullanıcınındır.
    """
    groups = {}
    for entry in entries:
        key = repr(entry['rows'])
        group = groups.get(key)
        if group is None:
            group = dict(rows=[tuple(r) for r in entry['rows']], size_mm=entry['size_mm'], members=[])
            groups[key] = group
        group['members'].append(dict(library=entry['library'], symbol=entry['symbol'],
                                     variant=entry['variant'], symbol_type=entry.get('symbol_type'),
                                     connection_points=len(entry.get('connection_points') or [])))
    out = list(groups.values())
    for index, group in enumerate(out):
        group['id'] = 'G%04d' % (index + 1)
        group['member_count'] = len(group['members'])
    return out


# --- Kütüphaneden gelen geometri ------------------------------------------------------

def _arc_box(element):
    """Yayın kutusu: açı aralığı örneklenerek ölçülür (yarım daire tam elips sayılmaz)."""
    import math
    cx, cy = element['center']
    rx = element.get('radius') or 0.0
    ry = element.get('radius2') or rx
    start, end = element.get('start_angle', 0.0), element.get('end_angle', 360.0)
    if end <= start:
        end += 360.0
    steps = max(8, int(end - start))
    xs, ys = [], []
    for i in range(steps + 1):
        angle = math.radians(start + (end - start) * i / steps)
        xs.append(cx + rx * math.cos(angle))
        ys.append(cy + ry * math.sin(angle))
    return min(xs), min(ys), max(xs), max(ys)


def element_rows(elements):
    """EPLAN çizim nesneleri → karşılaştırılabilir satırlar (mm, y AŞAĞI doğru).

    EPLAN'da y yukarı, PDF'te aşağı büyür; y işareti çevrilmezse aynı sembol aynada
    görünür ve hiç eşleşmez. Dikdörtgen ve polyline çizgilere ayrılır, çünkü PDF tarafında
    da ayrı çizgi nesneleri olarak gelirler. Yay kutusuyla temsil edilir.
    """
    rows, ignored = [], []
    for element in elements:
        kind = element.get('kind')
        if kind == 'line':
            (ax, ay), (bx, by) = element['a'], element['b']
            rows.append(('line', ax, -ay, bx, -by))
        elif kind == 'rect':
            (x0, y0), (x1, y1) = element['a'], element['b']
            rows += [('line', x0, -y0, x1, -y0), ('line', x1, -y0, x1, -y1),
                     ('line', x1, -y1, x0, -y1), ('line', x0, -y1, x0, -y0)]
        elif kind == 'polyline':
            points = element.get('points') or []
            for (ax, ay), (bx, by) in zip(points, points[1:]):
                rows.append(('line', ax, -ay, bx, -by))
            if element.get('closed') and len(points) > 2:
                (ax, ay), (bx, by) = points[-1], points[0]
                rows.append(('line', ax, -ay, bx, -by))
        elif kind == 'arc':
            x0, y0, x1, y1 = _arc_box(element)
            rows.append(('curve', x0, -y1, x1, -y0))
        else:
            ignored.append(kind)
    return normalise(rows), ignored


def normalise(rows):
    """Şekli kendi sol üst köşesine taşı, uç sırasını sabitle, parçalı çizgileri birleştir."""
    if not rows:
        return []
    xs = [v for r in rows for v in (r[1], r[3])]
    ys = [v for r in rows for v in (r[2], r[4])]
    ox, oy = min(xs), min(ys)
    out = []
    for kind, ax, ay, bx, by in rows:
        a = (round(ax - ox, 2), round(ay - oy, 2))
        b = (round(bx - ox, 2), round(by - oy, 2))
        low, high = sorted([a, b])
        if low == high:
            continue                       # sıfır uzunluklu nesne şekil taşımaz
        out.append((kind, low[0], low[1], high[0], high[1], False))
    return sorted(merge_runs(out))


def merge_runs(rows, tol=0.01):
    """Aynı doğru üzerindeki bitişik/örtüşen çizgileri tek çizgi yap.

    Gerek: aynı kenar PDF'te iki parça (yolun başı ve sonu), EPLAN'da tek çizgi olabiliyor.
    Birleştirilmezse aynı sembol farklı görünür. Eğri/yay satırları dokunulmadan geçer.
    """
    lanes, out = {}, []
    for row in rows:
        kind, x0, y0, x1, y1 = row[0], row[1], row[2], row[3], row[4]
        if kind != 'line':
            out.append(row)
        elif abs(y0 - y1) <= tol:
            lanes.setdefault(('h', round(y0, 2)), []).append((x0, x1))
        elif abs(x0 - x1) <= tol:
            lanes.setdefault(('v', round(x0, 2)), []).append((y0, y1))
        else:
            out.append(row)                # eğik çizgi: birleştirme denenmez
    for (orient, fixed), spans in lanes.items():
        spans.sort()
        low, high = spans[0]
        for start, end in spans[1:]:
            if start <= high + tol:
                high = max(high, end)
                continue
            out.append(('line', low, fixed, high, fixed, False) if orient == 'h'
                       else ('line', fixed, low, fixed, high, False))
            low, high = start, end
        out.append(('line', low, fixed, high, fixed, False) if orient == 'h'
                   else ('line', fixed, low, fixed, high, False))
    return out


PT_TO_MM = 25.4 / 72.0          # PDF noktası → mm (1:1 ölçekli sayfada ölçülmüştür)


def _axis_parallel(points, tol=0.01):
    return all(abs(a[0] - b[0]) <= tol or abs(a[1] - b[1]) <= tol
               for a, b in zip(points, points[1:]))


def rows_from_pdf(segments, curves, scale=PT_TO_MM):
    """Müşteri PDF'indeki çizim → katalogla aynı dilde satırlar (mm).

    PDF'te bir sembol tek bir YOL nesnesi olabiliyor (sigorta: dikdörtgen + orta çizgi,
    7 nokta). Yolun kenarları eksene paralelse çizgilere ayrılır; eğri içeriyorsa
    (klemens dairesi 12 noktayla çizilmiş) bütün olarak kutusuyla temsil edilir — çünkü
    EPLAN tarafında da yay tek nesnedir.
    """
    rows = []
    for segment in segments:
        (ax, ay), (bx, by) = segment['a'], segment['b']
        rows.append(('line', ax * scale, ay * scale, bx * scale, by * scale))
    for curve in curves:
        points = curve.get('points') or []
        if len(points) >= 2 and _axis_parallel(points):
            for a, b in zip(points, points[1:]):
                rows.append(('line', a[0] * scale, a[1] * scale, b[0] * scale, b[1] * scale))
            continue
        x0, y0, x1, y1 = curve['bbox']
        rows.append(('curve', x0 * scale, y0 * scale, x1 * scale, y1 * scale))
    return normalise(rows)


def size_of(rows):
    if not rows:
        return None
    xs = [v for r in rows for v in (r[1], r[3])]
    ys = [v for r in rows for v in (r[2], r[4])]
    return [round(max(xs) - min(xs), 2), round(max(ys) - min(ys), 2)]


def build_from_library(symbols_path, out_path):
    """`semboller.json` (EPLAN kütüphanesinden okunmuş geometri) → şekil veritabanı.

    PDF'e basıp geri okumaya gerek yok: kaynağın kendisi budur.
    """
    data = json.loads(Path(symbols_path).read_text(encoding='utf-8'))
    entries, without, ignored_kinds = [], [], {}
    for symbol in data.get('symbols', []):
        rows, ignored = element_rows(symbol.get('elements') or [])
        for kind in ignored:
            ignored_kinds[str(kind)] = ignored_kinds.get(str(kind), 0) + 1
        row = dict(library=symbol['library'], symbol=symbol['symbol'], variant=symbol['variant'],
                   symbol_type=symbol.get('symbol_type'),
                   connection_points=symbol.get('connection_points', []))
        if not rows:
            without.append(dict(row, reason='sembolde çizim nesnesi yok'))
            continue
        entries.append(dict(row, rows=rows, size_mm=size_of(rows), dropped_objects=0))
    groups = group_shapes(entries)
    out = dict(contract='uvp.pdf2p8.catalog-shapes', contract_version='1.0',
               source='EPLAN_SYMBOL_LIBRARY', source_file=str(symbols_path),
               libraries=data.get('libraries_in_project'), symbols=entries, groups=groups,
               without_shape=without, ignored_element_kinds=ignored_kinds,
               ignored_types_in_eplan=data.get('ignored_types'))
    Path(out_path).write_text(json.dumps(out, ensure_ascii=False), encoding='utf-8')
    return out


# --- K3: eşleştirme -------------------------------------------------------------------

def _close(a, b, tol=MM_TOL):
    return a[0] == b[0] and all(abs(x - y) <= tol for x, y in zip(a[1:5], b[1:5]))


def score(rows_a, rows_b, tol=MM_TOL):
    """0..1 — iki şeklin ortak satır oranı. Ölçek farkı satırları kaydırır ve puanı düşürür."""
    if not rows_a or not rows_b:
        return 0.0
    free = list(rows_b)
    hit = 0
    for row in rows_a:
        for i, other in enumerate(free):
            if _close(row, other, tol):
                del free[i]
                hit += 1
                break
    return round(2.0 * hit / (len(rows_a) + len(rows_b)), 4)


def match(rows, database, limit=3, min_score=0.5, pins=None, libraries=None):
    """Bir şekle en çok benzeyen katalog ŞEKİLLERİ (sembol değil, şekil grubu).

    Aynı çizimi paylaşan semboller tek aday olarak döner; üyeleri listede durur.
    `pins` verilirse bağlantı noktası SAYISI tutmayan üye elenir, üyesi kalmayan grup düşer.
    Aday kalmazsa boş liste döner: "bulamadım" demek serbesttir.
    """
    groups = database.get('groups') or group_shapes(database['symbols'])
    out = []
    for group in groups:
        members = group['members']
        if libraries is not None:
            # Kullanıcının gerçekten kullandığı kütüphaneler. Süzgeç, puanı değiştirmez:
            # yalnız listeyi daraltır, sıralama yine şekil benzerliğiyledir.
            members = [m for m in members if m['library'] in libraries]
            if not members:
                continue
        if pins is not None:
            members = [m for m in members if m['connection_points'] == pins]
            if not members:
                continue
        value = score(rows, [tuple(r) for r in group['rows']])
        if value >= min_score:
            out.append(dict(id=group.get('id'), score=value, size_mm=group['size_mm'],
                            members=sorted(members, key=lambda m: (m['library'], m['symbol'], m['variant'])),
                            member_count=len(members)))
    out.sort(key=lambda r: (-r['score'], r['members'][0]['library'], r['members'][0]['symbol'],
                            r['members'][0]['variant']))
    return out[:limit]


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description='EPLAN katalog şekilleri')
    parser.add_argument('symbols', help='semboller.json (EPLAN kütüphanesinden)')
    parser.add_argument('out', help='çıkış json')
    args = parser.parse_args(argv)
    data = build_from_library(args.symbols, args.out)
    print('okunan sembol: %d, ayrı şekil: %d, çizimsiz: %d'
          % (len(data['symbols']), len(data['groups']), len(data['without_shape'])))
    if data['ignored_element_kinds']:
        print('çevrilemeyen nesne türleri:', data['ignored_element_kinds'])


if __name__ == '__main__':
    main()
