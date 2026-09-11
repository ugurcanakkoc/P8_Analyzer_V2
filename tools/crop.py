"""Sayfa PNG'sinden PDF koordinatlariyla kirpma. Yalniz okur; hicbir kayit degistirmez.

Kullanim:
  python tools/crop.py <sayfa> <x0> <y0> <x1> <y1> <cikti.png> [buyutme]
Koordinatlar `display` PDF puntosudur (render_bbox koseleri cikarilmis hali) — service.py,
geometry.json ve /api/* ciktilarindaki koordinatlarla ayni.
"""
import sys
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / 'output' / 'pilots' / 'E122' / '20260910_v3_p05_rev8'
DPI = 300 / 72


def sheet(number):
    number = int(number)
    p = RUN / 'page.png' if number == 4 else RUN / 'pages' / str(number) / 'page.png'
    if not p.exists():
        raise SystemExit('Bu sayfa bu calismada izlenmiyor: %s' % number)
    return p


def crop(number, box, out, scale=1.0):
    im = Image.open(sheet(number))
    x0, y0, x1, y1 = [v * DPI for v in box]
    x0, y0 = max(0, int(x0)), max(0, int(y0))
    x1, y1 = min(im.size[0], int(x1)), min(im.size[1], int(y1))
    if x1 <= x0 or y1 <= y0:
        raise SystemExit('Bos kirpma: %s' % box)
    piece = im.crop((x0, y0, x1, y1))
    if scale != 1.0:
        piece = piece.resize((int(piece.size[0]*scale), int(piece.size[1]*scale)), Image.LANCZOS)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    piece.save(out)
    print('%s  %dx%d  pdf=%s' % (out, piece.size[0], piece.size[1], box))


if __name__ == '__main__':
    a = sys.argv[1:]
    if len(a) < 6:
        raise SystemExit(__doc__)
    crop(a[0], [float(v) for v in a[1:5]], a[5], float(a[6]) if len(a) > 6 else 1.0)
