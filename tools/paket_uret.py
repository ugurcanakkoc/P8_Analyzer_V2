"""EPLAN aktarım paketini komut satırından üretir; sayfa başına şablon yerleşimi özetini basar.

Kullanım:
    python tools/paket_uret.py [--musteri troester] [--run <pilot çalışması>] [--sayfa 24,38]

Sunucudaki paket düğmesiyle aynı iş (Pilot.package_request): işaretler çalışmadan yeniden okunur,
output/exchange/<müşteri>_tum_sayfalar.json ve <müşteri>_mapping.json yazılır.
--sayfa verilirse o sayfalardaki her nesnenin konumu da basılır (kaynak → şablon).
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analyzer_v3.pagecache import PageCache  # noqa: E402
from analyzer_v3.service import Pilot  # noqa: E402


def rounded(point):
    return [round(v) for v in point] if point else point


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser()
    parser.add_argument('--musteri', default='troester')
    parser.add_argument('--run', type=Path, default=ROOT / 'output/pilots/E122/20260910_v3_p05_rev8')
    parser.add_argument('--sayfa', default='')
    args = parser.parse_args()

    pilot = Pilot(args.run)
    pilot.cache = PageCache(pilot.manifest['source_path'], pilot.manifest['source_sha256'],
                            pilot.manifest['page_count'])
    pilot.refresh()   # işaretler burada yüklenir; yoksa paket 'pins' bulamaz
    result = pilot.package_request({'all': True, 'customer': args.musteri})
    print(result['package'])
    print('sayfa %d  nesne %d  bağ %d  düşen sayfa %s' % (
        len(result['pages']), result['objects'], result['expected_links'], result['failed_pages'] or '-'))

    package = json.loads(Path(result['package']).read_text(encoding='utf-8'))
    wanted = {int(n) for n in args.sayfa.split(',') if n.strip()}
    for page in package['pages']:
        lay = page.get('layout') or {}
        print('s%-3d dx=%-7s satır=%s satırsız=%d bağsız_nokta=%d %s' % (
            page['physical_page'], lay.get('dx_mm'), lay.get('rows'),
            len(lay.get('devices_without_row') or []), len(lay.get('nodes_unresolved') or []),
            lay.get('issue') or ''))
        if page['physical_page'] not in wanted:
            continue
        for o in page['objects']:
            if o['kind'] == 'DEVICE':
                print('     %-14s %-8s %s' % (o['family'], o['device_tag'].split('-')[-1], ' '.join(
                    '%s@%s%s' % (p['name'], rounded(p['point_mm']), ' ters' if p.get('layout_flipped') else '')
                    for p in o['pins'])))
            else:
                print('     %-14s %s <- %s' % (o['family'], rounded(o['point_mm']), rounded(o.get('source_point_mm'))))


if __name__ == '__main__':
    main()
