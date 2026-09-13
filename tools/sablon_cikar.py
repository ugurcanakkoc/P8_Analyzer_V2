"""EPLAN sayfa dökümünden (scripts/UvpSayfaDok.cs) şablonun taslak satırlarını çıkarır.

Kullanım:
    python tools/sablon_cikar.py [sayfa_dokum.json]

'U' ile görünen taslak yerleri sayfada değil ÇERÇEVEDE (Normblatt) durur: sol kenarda satır
adı + kısa yatay kılavuz çizgisi, baraların adı (L1..PE), çizim alanının dik sınır çizgileri
ve alt kenardaki sütun çentikleri. Hepsi okunur, uydurma yok; bulunamayan parça boş kalır.
Çıktı: output/sablon/<çerçeve adı>.json
"""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANGS = ('tr_TR', '??_??', 'en_US', 'de_DE')


def text_of(row):
    """'de_DE@Motor;en_US@Motor;' → dil önceliğiyle tek metin."""
    parts = dict(p.split('@', 1) for p in (row.get('text') or '').split(';') if '@' in p)
    for lang in LANGS:
        if parts.get(lang):
            return parts[lang].strip()
    return next(iter(parts.values()), '').strip()


def size(row):
    (x0, y0), (x1, y1) = row['box']
    return x1 - x0, y1 - y0


def extract(dump):
    rows = [r for r in dump.get('plot_frame_placements') or [] if r.get('box')]
    texts = [r for r in rows if r['type'] == 'Text']
    # Satır kılavuzu: sol kenarda ~12 mm uzun, düz yatay parça.
    guides = [r for r in rows if r['type'] in ('PolyLine', 'Line') and 10 <= size(r)[0] <= 15
              and size(r)[1] <= 1 and r['box'][1][0] <= 45]
    out_rows = []
    for guide in sorted(guides, key=lambda r: -r['box'][0][1]):
        y = round((guide['box'][0][1] + guide['box'][1][1]) / 2, 2)
        near = [t for t in texts if t['at'][0] < 25 and abs(t['at'][1] - y) <= 1.5]
        out_rows.append(dict(label=text_of(near[0]) if near else '', y=y, layer=guide.get('layer')))
    rails = {text_of(t): t['at'][1] for t in texts
             if text_of(t) in ('L1', 'L2', 'L3', 'N', 'PE') and 30 <= t['at'][0] <= 45}
    # Dik çizgiler uç noktalarıyla okunur (kutu çizgi kalınlığı kadar şişkin). Yalnız taslak
    # katmanları: çerçevenin kendi kenar çizgisi (x=3.56) çizim alanı sanılmasın.
    draft = {g.get('layer') for g in guides}
    verticals = [(r['from'][0], min(r['from'][1], r['to'][1]), max(r['from'][1], r['to'][1]))
                 for r in rows if r['type'] == 'Line' and r.get('from') and r['from'][0] == r['to'][0]
                 and r.get('layer') in draft]
    tall = [v for v in verticals if v[2] - v[1] > 200]
    area = None
    if len(tall) >= 2:
        area = dict(x0=min(v[0] for v in tall), x1=max(v[0] for v in tall),
                    y0=min(v[1] for v in tall), y1=max(v[2] for v in tall))
    columns, marks = None, []
    if area:
        short = [v for v in verticals if 1 <= v[2] - v[1] <= 4]
        # Alt kenardaki çentikler sütun sınırı; alan içindekiler uç yeri işareti (ör. PLC çıkış ucu).
        ticks = sorted(v[0] for v in short if abs(v[1] - area['y0']) <= 1)
        steps = Counter(round(b - a, 2) for a, b in zip(ticks, ticks[1:]))
        if steps:
            pitch = steps.most_common(1)[0][0]
            first = area['x0'] + ((ticks[0] - area['x0']) % pitch)
            lines, x = [], first
            while x <= area['x1']:
                lines.append(round(x, 2))
                x += pitch
            columns = dict(pitch=pitch, lines=lines, ticks=ticks)
        inside = {}
        for x, y0, _ in short:
            if abs(y0 - area['y0']) > 1:
                inside.setdefault(y0, []).append(x)
        marks = [dict(y=y, xs=sorted(xs)) for y, xs in sorted(inside.items(), reverse=True)]
    return dict(frame=dump.get('plot_frame'), source_page=dump.get('page'), rows=out_rows,
                rails=rails, area=area, columns=columns, pin_marks=marks)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'output' / 'p8test' / 'page_probe' / 'sayfa_dokum.json'
    template = extract(json.loads(path.read_text(encoding='utf-8')))
    target = ROOT / 'output' / 'sablon' / ('%s.json' % template['frame'])
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(template, ensure_ascii=False, indent=1), encoding='utf-8')
    print(target)
    for row in template['rows']:
        print('  y=%-6s %s' % (row['y'], row['label'].replace('\n', ' / ')))
    print('  baralar', template['rails'])
    print('  alan', template['area'])
    print('  sütun', template['columns'] and {k: v for k, v in template['columns'].items() if k != 'ticks'})


if __name__ == '__main__':
    main()
