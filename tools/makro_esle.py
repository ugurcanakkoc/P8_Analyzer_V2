"""Makro uçları ile müşteri uçlarını eşleştir; eşleşmeyenleri makro içinden sorgula.

Kullanım:
    python -m tools.makro_esle                       # rapor
    python -m tools.makro_esle --yaz                 # onaylı eşleşmeleri profile yaz

Girdi:  output/exchange/makro_pinleri.json   (EPLAN: UvpMakroPin.cs)
        output/exchange/<musteri>_tum_sayfalar.json

Ne yapar: her cihaz için kaynak uç adlarını makronun GERÇEK uçlarıyla karşılaştırır.
Birebir / gevşek (ayırıcı, harf) / varyant (faz eki, eğik çizgi, ön ek) eşleşmeleri
kabul eder. Eşleşmeyende UYDURMAZ: makronun hangi uçlarının boşta kaldığını gösterir ve
uç sayısı tutuyorsa sıraya göre ÖNERİ verir. Onay `--yaz` ile profile geçer.
"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analyzer_v3 import customer, pins                      # noqa: E402

MACROS = ROOT / 'output' / 'exchange' / 'makro_pinleri.json'


def load(name):
    profile = customer.load(name)
    package = ROOT / 'output' / 'exchange' / ('%s_tum_sayfalar.json' % customer.valid_name(name))
    if not MACROS.exists():
        raise SystemExit('Makro dosyası yok: %s\nEPLAN\'da UvpMakroPin.cs çalıştırın.' % MACROS)
    if not package.exists():
        raise SystemExit('Paket yok: %s' % package)
    return profile, json.loads(MACROS.read_text(encoding='utf-8')), \
        json.loads(package.read_text(encoding='utf-8'))


def macro_pin_names(entry):
    """Makronun bütün fonksiyonlarındaki uç adları (fonksiyon sırasıyla)."""
    out = []
    for function in entry.get('functions') or []:
        for pin in function.get('pins') or []:
            name = (pin.get('name') or '').strip()
            if name:
                out.append(name)
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('customer', nargs='?', default=customer.DEFAULT)
    parser.add_argument('--yaz', action='store_true', help='sıraya göre önerileri profile yaz')
    args = parser.parse_args(argv)

    profile, macros, package = load(args.customer)
    aliases = (profile.get('pin_aliases') or {})
    by_part = {row['part_number']: row for row in macros.get('parts') or []}

    print('makro dosyası: %d ürün kodu, bulunan %d, makrosu olan %d'
          % (len(by_part), sum(1 for r in by_part.values() if r.get('found')),
             sum(1 for r in by_part.values() if r.get('macro'))))

    devices = [o for page in package['pages'] for o in page['objects'] if o['kind'] == 'DEVICE']
    state = Counter()
    proposals = defaultdict(Counter)
    detail = []
    for device in devices:
        part = device.get('part_number')
        entry = by_part.get(part)
        source = [q['name'] for q in device['pins']]
        if not part:
            state['ürün kodu yok'] += 1
            continue
        if entry is None or not entry.get('found'):
            state['parça bulunamadı'] += 1
            continue
        if not entry.get('macro'):
            state['makro yok'] += 1
            continue
        names = macro_pin_names(entry)
        if not names:
            state['makro uçsuz'] += 1
            continue
        table = aliases.get(part) or {}
        result = pins.compare(source, names, table)
        if result['fits']:
            state['tam eşleşti'] += 1
        elif result['matched'] and not result['unmatched_source']:
            state['eşleşti (makroda fazla uç var)'] += 1
        elif result['suggestions']:
            state['öneri var (onay bekliyor)'] += 1
            for row in result['suggestions']:
                proposals[part][(row['source'], row['macro'])] += 1
        else:
            state['eşleşmedi'] += 1
        if not result['fits']:
            detail.append((device['device_tag'], part, source, names, result))

    print('\n=== DURUM ===')
    for key, count in state.most_common():
        print('  %-34s %d' % (key, count))

    print('\n=== EŞLEŞMEYEN ÖRNEKLER ===')
    for tag, part, source, names, result in detail[:10]:
        print('\n  %s  (%s)' % (tag, part))
        print('    kaynak uçlar: %s' % source)
        print('    makro uçları: %s' % names[:12])
        if result['matched']:
            print('    eşleşen: %s' % [(r['source'], r['macro'], r['how']) for r in result['matched']])
        if result['unmatched_source']:
            print('    KARŞILIĞI YOK: %s' % result['unmatched_source'])
        if result['unused_macro']:
            print('    makroda boşta: %s' % result['unused_macro'][:12])
        for row in result['suggestions']:
            print('    öneri: %s ↔ %s (%s)' % (row['source'], row['macro'], row['how']))

    if args.yaz and proposals:
        table = dict(aliases)
        for part, pairs in proposals.items():
            table.setdefault(part, {})
            for (source, macro), _ in pairs.items():
                table[part][source] = macro
        profile_rules = profile.get('rules')
        families = profile.get('families')
        file = customer.path_of(args.customer)
        data = json.loads(file.read_text(encoding='utf-8')) if file.exists() else {}
        data.update(customer=args.customer, rules=profile_rules, families=families,
                    pin_aliases=table)
        file.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')
        print('\neşleme tablosu yazıldı: %s (%d ürün kodu)' % (file, len(table)))
    elif args.yaz:
        print('\nyazılacak öneri yok.')


if __name__ == '__main__':
    main()
