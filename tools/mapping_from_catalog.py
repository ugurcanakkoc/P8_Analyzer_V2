"""EPLAN kataloğundan (capabilities.json) sembol eşlemesi seçmeye yardımcı araç.

Eşleme TAHMİNLE kurulmaz: aday semboller türleri, açıklamaları ve bağlantı noktası sayılarıyla
listelenir; seçim `--write` ile açıkça verilir. Yazılan dosya `UvpPdfToP8Import /MAPPING:` girdisidir.

    python tools/mapping_from_catalog.py --catalog output/p8test/probe/capabilities.json
    python tools/mapping_from_catalog.py --catalog ... --write output/exchange/proof_s03/mapping.json \
        --pick fuse_1pole=IEC_symbol/F1_1 --pick terminal=IEC_symbol/X1 ...
"""
import argparse
import json
from pathlib import Path

# Aradığımız aileler ve kanıt ipuçları. Eşleşme ZORUNLU değildir; yalnız listeyi kısaltır.
FAMILIES = {
    'fuse_1pole': dict(types=('Function',), words=('sicherung', 'fuse', 'schmelz', 'sigorta'), points=2),
    'terminal': dict(types=('Function',), words=('klemme', 'terminal', 'klemens'), points=2),
    'tnode_down': dict(types=('TNodeDown',), words=(), points=None),
    'interruption': dict(types=('InterruptionPoint',), words=(), points=None),
    'potential_definition': dict(types=('PotentialDefinition',), words=(), points=None),
}


def rows(catalog):
    for library in catalog.get('symbol_libraries', []):
        for symbol in library.get('symbols', []):
            yield library['name'], symbol


def matches(symbol, rule):
    if rule['types'] and symbol.get('type') not in rule['types']:
        return False
    text = ' '.join(str(symbol.get(k, '')) for k in ('description', 'function_type', 'function_description')).lower()
    if rule['words'] and not any(w in text for w in rule['words']):
        return False
    if rule['points'] is not None and symbol.get('connection_points_v0') != rule['points']:
        return False
    return True


def report(catalog):
    out = {}
    for family, rule in FAMILIES.items():
        hits = [(lib, s) for lib, s in rows(catalog) if matches(s, rule)]
        out[family] = hits
        print('== %s  (%d aday)' % (family, len(hits)))
        for lib, s in hits[:15]:
            print('   %-12s %-10s %-22s uç=%s  %s' % (lib, s['name'], s.get('type'),
                                                      s.get('connection_points_v0'),
                                                      (s.get('description') or s.get('function_type') or '')[:60]))
        if len(hits) > 15:
            print('   … %d aday daha' % (len(hits)-15))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--catalog', type=Path, required=True)
    ap.add_argument('--write', type=Path)
    ap.add_argument('--pick', action='append', default=[],
                    help='aile=KÜTÜPHANE/SEMBOL[/varyant]  (varyant yazılmazsa 0)')
    args = ap.parse_args()
    catalog = json.loads(args.catalog.read_text(encoding='utf-8-sig'))
    if not catalog.get('ok'):
        print('UYARI: katalog raporu başarısız:', catalog.get('error'))
    known = {(lib, s['name']): s for lib, s in rows(catalog)}
    report(catalog)
    if not args.write:
        return
    families = {}
    for pick in args.pick:
        family, _, target = pick.partition('=')
        parts = target.split('/')
        if family not in FAMILIES or len(parts) < 2:
            raise SystemExit('Geçersiz seçim: ' + pick)
        library, symbol = parts[0], parts[1]
        variant = int(parts[2]) if len(parts) > 2 else 0
        if (library, symbol) not in known:
            raise SystemExit('Katalogda yok: %s/%s' % (library, symbol))
        evidence = known[(library, symbol)]
        families[family] = dict(library=library, symbol=symbol, variant=variant,
                                catalog_type=evidence.get('type'),
                                catalog_description=evidence.get('description'),
                                catalog_connection_points=evidence.get('connection_points_v0'))
    missing = [f for f in FAMILIES if f not in families]
    args.write.parent.mkdir(parents=True, exist_ok=True)
    args.write.write_text(json.dumps(dict(contract='uvp.pdf2p8.mapping', contract_version='1.0',
                                          source_catalog=str(args.catalog), families=families,
                                          missing_families=missing,
                                          note='Seçim kullanıcı/operatör kararıdır; katalog kanıtı her '
                                               'aile için kayıtlıdır. Eksik aile varsa aktarım o nesneyi '
                                               'reddeder, sessizce atlamaz.'),
                                     ensure_ascii=False, indent=1), encoding='utf-8')
    print('eşleme yazıldı:', args.write, '| eksik aile:', missing or 'yok')


if __name__ == '__main__':
    main()
