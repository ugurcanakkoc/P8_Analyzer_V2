"""Müşteri profilini kur ve eksik sembol kararlarını listele.

Kullanım:
    python -m tools.musteri_profil troester            # sayım + karar listesi
    python -m tools.musteri_profil troester --yaz      # profili dosyaya yaz

Ne yapar: işaretli sayfalardaki cihazları aileye göre sayar, hangi ailenin EPLAN sembolü
eksik olduğunu söyler ve katalogdan UÇ SAYISI TUTAN adayları listeler. Sembolü SEÇMEZ:
karar kullanıcınındır, profil dosyasındaki `symbol` alanı boş kalır.
"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analyzer_v3 import customer, eplan_export                     # noqa: E402
from analyzer_v3.pagecache import PageCache                        # noqa: E402
from analyzer_v3.prepare import digest                             # noqa: E402
from analyzer_v3.service import Pilot                              # noqa: E402

RUN = ROOT / 'output' / 'pilots' / 'E122' / '20260910_v3_p05_rev8'
CATALOG = ROOT / 'output' / 'p8test' / 'probe' / 'capabilities.json'
OLD_MAPPING = ROOT / 'output' / 'exchange' / 'proof_s03' / 'mapping.json'

# Troester belgesinde ÖLÇÜLEN yapılar. Bunlar sembol seçimi değil, SINIFLANDIRMA kuralıdır:
# cihaz harfi ve uç adlarından aile çıkarır. Yanlışsa profil dosyasından düzeltilir.
TROESTER_RULES = customer.BUILTIN_RULES + [
    dict(family='plc_supply', letter='D', pin_set=['L+'], pin_count=1),
    dict(family='plc_supply', letter='D', pin_set=['M'], pin_count=1),
    dict(family='plc_channel', letter='D', pin_count=1, pin_pattern=r'^\d{1,2}$'),
    dict(family='plc_channel_2pin', letter='D', pin_count=2, pin_pattern=r'^\d{1,2}$'),
    dict(family='contact_56', letter_in=['K', 'Q'], pin_count=2, digit_ends=[['5', '6']]),
    dict(family='changeover_contact', letter='K', pin_count=4),
    dict(family='supply_unit', letter='G'),
    dict(family='load_1pin', letter='E', pin_count=1),
]


def census(pilot, profile):
    rows = defaultdict(list)
    pages = sorted({q.get('page', 4) for q in pilot.pins})
    for number in pages:
        try:
            package = eplan_export.page_package(pilot, number, profile)
        except Exception as error:                              # noqa: BLE001 — sayfa atlanır, söylenir
            rows['PAKET ÇIKMADI'].append('sayfa %d: %s' % (number, error))
            continue
        for obj in package['pages'][0]['objects']:
            if obj['kind'] != 'DEVICE':
                continue
            rows[obj['family']].append((number, obj['device_tag'],
                                        tuple(q['name'] for q in obj['pins'])))
    return rows


def candidates(pin_count, limit=6):
    if not CATALOG.exists():
        return []
    data = json.loads(CATALOG.read_text(encoding='utf-8'))
    out = []
    for library in data.get('symbol_libraries', []):
        if library['name'] not in ('IEC_symbol', 'SPECIAL'):
            continue
        for symbol in library['symbols']:
            if symbol.get('connection_points_v0') != pin_count:
                continue
            description = (symbol.get('description') or '')
            turkish = [part[6:] for part in description.split(';') if part.startswith('tr_TR@')]
            out.append('%s/%s  uç=%d  %s' % (library['name'], symbol['name'], pin_count,
                                             turkish[0] if turkish else symbol.get('type', '')))
    return out[:limit]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('customer', nargs='?', default=customer.DEFAULT)
    parser.add_argument('--yaz', action='store_true', help='profili dosyaya yaz')
    args = parser.parse_args(argv)

    manifest = json.loads((RUN / 'manifest.json').read_text(encoding='utf-8'))
    source = Path(manifest['source_path'])
    pilot = Pilot(RUN)
    pilot.cache = PageCache(source, digest(source), manifest['page_count'])
    pilot.refresh()

    families = {}
    if OLD_MAPPING.exists():
        old = json.loads(OLD_MAPPING.read_text(encoding='utf-8'))
        for name, entry in (old.get('families') or {}).items():
            families[name] = dict(library=entry['library'], symbol=entry['symbol'],
                                  variant=entry.get('variant', 0),
                                  source='proof_s03/mapping.json')

    profile = dict(customer=args.customer, rules=TROESTER_RULES, families=families)
    rows = census(pilot, profile)

    print('=== AİLE SAYIMI (%d işaretli sayfa) ===' % len({q.get('page', 4) for q in pilot.pins}))
    decided = []
    for family, items in sorted(rows.items(), key=lambda kv: -len(kv[1])):
        mapped = customer.symbol_of(profile, family)
        state = ('%s/%s' % (mapped['library'], mapped['symbol'])) if mapped else 'SEMBOL YOK'
        print('%-22s %4d  %s' % (family, len(items), state))
        if not mapped and not family.startswith('unmapped'):
            decided.append((family, items))

    print('\n=== KARAR BEKLEYENLER ===')
    for family, items in decided:
        pins = Counter(len(row[2]) for row in items if isinstance(row, tuple))
        pin_count = pins.most_common(1)[0][0] if pins else 0
        example = next((row for row in items if isinstance(row, tuple)), None)
        print('\n%s  (%d cihaz, uç sayısı %d)' % (family, len(items), pin_count))
        if example:
            print('   örnek: sayfa %s  %s  uçlar %s' % (example[0], example[1], list(example[2])))
        for line in candidates(pin_count):
            print('   aday:', line)
        if not candidates(pin_count):
            print('   aday: katalogda bu uç sayısında sembol bulunamadı (katalog dosyası var mı?)')

    unmapped = {f: len(i) for f, i in rows.items() if f.startswith('unmapped')}
    if unmapped:
        print('\n=== KURAL BULAMADIKLARI (aile bile çıkmadı) ===')
        for family, count in sorted(unmapped.items(), key=lambda kv: -kv[1]):
            print('   %-28s %d' % (family, count))

    if args.yaz:
        file = customer.save(args.customer, TROESTER_RULES, families,
                             note='Aile kuralları Troester belgesinde ölçüldü; sembolü boş olan '
                                  'aile aktarımda reddedilir.')
        print('\nprofil yazıldı:', file)


if __name__ == '__main__':
    main()
