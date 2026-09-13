"""Onaylı hedef PDF'te PLC modüllerinin uç yönünü ölçer: Yukarı / Aşağı / Karışık.

Kullanım:
    python tools/plc_yon_tara.py [hedef.pdf] [paket.json]

Kanal etiketiyle (DI0, DQ.0, DQ-P0 ...) aynı x'teki bağlantı çizgisi etiketin ÜSTÜNDE
bitiyorsa uç yukarı, ALTINDA başlıyorsa aşağı bakar. Çizgi bulunamazsa '?' yazılır,
yön uydurulmaz. Her modül paketteki kaynak sayfasıyla ve paketin verdiği yönle yan yana
basılır: sistemin yönü kendisi mi bulduğu, yoksa bizim mi vermemiz gerektiği buradan okunur.
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

import pdfplumber

ROOT = Path(__file__).resolve().parents[1]
LABEL = re.compile(r'^(DI|DQ|AI|AQ)[.\-]?[PM]?\d+$')
PIN = re.compile(r'^(\d{1,2}|L\+|M)$')
TAG = re.compile(r'^-\d+D\d+$')
REACH_X, REACH_Y = 3.0, 8.0  # pt: etiket merkezine yatay, etiket kenarına dikey tolerans
PT_TO_MM = 25.4 / 72


def direction(label, lines):
    """Etiketin hemen üstünde biten ya da hemen altında başlayan dik çizgi → 'Up' / 'Down'."""
    cx = (label['x0'] + label['x1']) / 2
    best = None
    for line in lines:
        if abs(line['x0'] - line['x1']) > 0.2 or abs(line['x0'] - cx) > REACH_X:
            continue
        for gap, side in ((label['top'] - line['bottom'], 'Up'), (line['top'] - label['bottom'], 'Down')):
            if -0.5 <= gap <= REACH_Y and (best is None or gap < best[0]):
                best = (gap, side)
    return best[1] if best else None


def pin_name(label, side, words):
    """Bağlantı ucundaki uç numarası (1, 9, L+ ...): etiketin yön tarafındaki en yakın kısa yazı."""
    cx = (label['x0'] + label['x1']) / 2
    edge = label['top'] if side == 'Up' else label['bottom']
    near = [w for w in words if PIN.match(w['text']) and abs(w['x0'] - cx) <= 10
            and (edge - w['bottom'] if side == 'Up' else w['top'] - edge) >= -1
            and abs((w['top'] + w['bottom']) / 2 - edge) <= 14]
    near.sort(key=lambda w: abs(w['x0'] - cx) + abs((w['top'] + w['bottom']) / 2 - edge))
    return near[0]['text'] if near else ''


def scan(pdf_path):
    modules = []
    with pdfplumber.open(pdf_path) as pdf:
        for number, page in enumerate(pdf.pages, 1):
            words = page.extract_words()
            labels = [w for w in words if LABEL.match(w['text'])]
            if not labels:
                continue
            tags = [w for w in words if TAG.match(w['text'])]
            by_tag = {}
            for label in labels:
                tag = min(tags, key=lambda t: abs(t['x0'] - label['x0']) + abs(t['top'] - label['top']))['text'] \
                    if tags else '?'
                side = direction(label, page.lines)
                by_tag.setdefault(tag, []).append(dict(
                    label=label['text'], side=side, pin=pin_name(label, side, words) if side else '',
                    y_mm=round(label['top'] * PT_TO_MM)))
            for tag, channels in by_tag.items():
                modules.append(dict(page=number, tag=tag, channels=channels))
    return modules


def package_view(package_path):
    """Paketten cihaz → (kaynak sayfalar, uç yönü sayımı)."""
    if not package_path or not Path(package_path).exists():
        return {}
    data = json.loads(Path(package_path).read_text(encoding='utf-8'))
    view = {}
    for page in data.get('pages', []):
        for obj in page.get('objects', []):
            tag = obj.get('device_tag') or ''
            match = re.search(r'-\d+D\d+$', tag)
            if not match:
                continue
            pages, sides = view.setdefault(match.group(0), (set(), Counter()))
            pages.add(page.get('physical_page'))
            for pin in obj.get('pins') or []:
                if isinstance(pin, dict):
                    sides[pin.get('wire_direction') or '?'] += 1
    return view


def verdict(sides):
    known = {s for s in sides if s}
    if not known:
        return 'Belirsiz'
    if len(known) > 1:
        return 'Karışık'
    return 'Yukarı' if known == {'Up'} else 'Aşağı'


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else ROOT / '13SB003_05_+E122_V04.pdf'
    package_path = sys.argv[2] if len(sys.argv) > 2 else ROOT / 'output' / 'exchange' / 'troester_tum_sayfalar.json'
    view = package_view(package_path)
    groups = {}
    for module in scan(pdf_path):
        sides = [c['side'] for c in module['channels']]
        kind = verdict(sides)
        pages, package_sides = view.get(module['tag'], (set(), Counter()))
        source = ','.join(str(p) for p in sorted(pages)) or '-'
        wanted = Counter(s for s in sides if s).most_common(1)
        agrees = ('uyuşuyor' if wanted and package_sides and package_sides.most_common(1)[0][0] == wanted[0][0]
                  else 'UYUŞMUYOR' if package_sides else 'pakette yok')
        channels = ' '.join('%s(%s)%s' % (c['label'], c['pin'], {'Up': '^', 'Down': 'v'}.get(c['side'], '?'))
                            for c in module['channels'])
        print('s%-3d %-7s %-8s y=%smm  kaynak s.%s  paket=%s  %s' % (
            module['page'], module['tag'], kind, module['channels'][0]['y_mm'], source,
            dict(package_sides) or '-', agrees))
        print('      ' + channels)
        groups.setdefault(kind, []).append((module['tag'], source))
    print()
    for kind, items in groups.items():
        print('%-8s %s' % (kind, ' '.join('%s[s.%s]' % item for item in items)))


if __name__ == '__main__':
    main()
