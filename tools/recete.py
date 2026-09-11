"""analyzer_v3 cikarimi -> SemaKopru recetesi (EPLAN P8 sema aktarimi).

Kopru: C:\\Users\\UVW-U\\Desktop\\EPLANScriptAgent\\my-scripts\\SemaKopru\\
Sozlesme: o klasordeki RECETE-SOZLESMESI.md. Alan adlari oradan alinmistir.

Bu betik RECETE URETIR; EPLAN'a hicbir sey yazmaz. Uretilen receteyi once
`tools/recete_dogrula.py` (kopru tarafinda) ile dogrula, sonra EPLAN icinde calistir.

Kurallar:
  * Kaniti olmayan alan BOS birakilir ve `_sorunlar` listesine gerekce yazilir.
  * Ortak ag (NETWORK_GROUP) fiziksel tel DEGILDIR: `wires[]` icine GIRMEZ.
  * Sembol eslemesi ONAYSIZDIR; `SEMBOL_ESLEME` tablosu kullanicidan teyit bekler.
  * Kapsam disi uc tasiyan satir disarida kalir (MAIN "PANO SINIRI KURALI").

Kullanim:
  python tools/recete.py --pages 4,5,28,36 --out output/recete/
"""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analyzer_v3.service import Pilot                                    # noqa: E402
from analyzer_v3.models import device_parts                              # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sayfa_excel import (cross_section_owners, cross_section,            # noqa: E402
                         circuit_classes, inherit_module_circuit,
                         row_circuit, electrical_values)

RUN = Path(__file__).resolve().parents[1]/'output'/'pilots'/'E122'/'20260910_v3_p05_rev8'
PT_TO_MM = 25.4/72.0

# PDF'te ogretilmis sembol ailesi -> EPLAN sembolu.
# KAYNAK: kb/eplan-sembol-listesi.json (2276 sembol, aciklama + uc sayisi).
# DURUM: hicbiri kullanici tarafindan TEYIT EDILMEDI. Kopru recetesinde `symbol`
# alani doldurulur ama her satir `_sorunlar` icinde onay bekler olarak isaretlenir.
SEMBOL_ESLEME = {
    'Klemens (normal, tek uçlu)': dict(
        symbol='X2_NB', symbol_library='IEC_symbol', uc=2,
        why='"Terminal with 2 connection points without saddle jumper connections" — '
            'PDF sembolu tek daire + ust/alt tel ucu; kopru ustunden gecen hatti bekler.'),
    'Klemens (yalnız daire, sayfa 2 stili)': dict(
        symbol='X1_NB', symbol_library='IEC_symbol', uc=1,
        why='"Terminal with one connection point without saddle jumper connections".'),
    'PE klemensi': dict(
        symbol='AXTRPE', symbol_library='IEC_symbol', uc=None,
        why='"Ground-isolating terminal". PE klemensi PDF tarafinda normal klemensten '
            'sekil olarak ayrisiyor (10 parca vs 2).'),
    'Sigorta kutbu (3F22 ailesi)': dict(
        symbol=None, symbol_library='IEC_symbol', uc=2,
        why='ONAY GEREKIYOR: tek kutuplu sigorta mi, motor koruma salteri kutbu mu '
            'oldugu PDF sembolunden kesin degil. kb listesinde birden cok aday var.'),
    'Röle bobini (A1/A2)': dict(
        symbol=None, symbol_library='IEC_symbol', uc=2,
        why='ONAY GEREKIYOR: bobin sembolu ailesi genis (kontaktor/role/zaman rolesi). '
            'Urun kodu bilinirse `part_number` yolu sembolden daha guvenlidir.'),
    'K çizgili 2 uçlu sembol': dict(
        symbol=None, symbol_library='IEC_symbol', uc=2,
        why='ONAY GEREKIYOR: role KONTAGI. NO/NC ayrimi PDF sekliyle dogrulanmali '
            '(kb: SL / SSV / OOV gibi ayri semboller var).'),
    'PLC DO çıkış klemensi (ET200SP 8DO)': dict(
        symbol=None, symbol_library='IEC_symbol', uc=1,
        why='ONAY GEREKIYOR: PLC uclari icin sembol degil, MODUL MAKROSU dogru yoldur. '
            'ET200SP 8DO parca kodu 6ES7132-6BF01-0BA0 -> `part_number` ile makro bulunur.'),
    'PLC DI giriş klemensi (ET200SP 8DI)': dict(
        symbol=None, symbol_library='IEC_symbol', uc=1,
        why='ONAY GEREKIYOR: ayni sekilde; 6ES7131-6BF01-0BA0.'),
}

KLEMENS_AILELERI = {'Klemens (normal, tek uçlu)', 'Klemens (yalnız daire, sayfa 2 stili)',
                    'PE klemensi'}

# PDF'te okunan modul parca kodlari (sayfa 22/28/36 baslik bloklarindan).
MODUL_PARCA = {'8DO': '6ES7132-6BF01-0BA0', '8DI': '6ES7131-6BF01-0BA0'}


def mm(point, height_pt):
    """PDF puntosu (sol-ust orijin, y asagi) -> mm (sol-alt orijin, y yukari)."""
    return (round(point[0]*PT_TO_MM, 2), round((height_pt-point[1])*PT_TO_MM, 2))


def bmk_of(device):
    """`=112+E122-17K52` -> ('112','E122','-17K52'). Recete BMK'yi yapi tanimlayicisiz ister."""
    parts = device_parts(device)
    if not parts:
        return None, None, device
    anlage, ort, tag = parts
    return anlage, ort, '-'+tag


def page_devices(pilot, number, height_pt, problems):
    """Bu sayfada isaretli her ucun cihazi -> tek recete satiri (cihaz basina)."""
    marks = [q for q in pilot.pins if q.get('page', 4) == number]
    families = {}
    for entry in pilot.library_entries()['rows']:
        if entry['status'] == 'RETIRED':
            continue
        for cand in pilot.library_candidates(entry['id'], number)['candidates']:
            for pin in cand['pins']:
                families[(round(pin['point'][0], 2), round(pin['point'][1], 2))] = entry['family']

    modules = {m['device']: m for m in pilot.module_report(number)['modules'] if m.get('device')}
    out, seen, flagged = [], {}, set()
    for q in sorted(marks, key=lambda q: (q['point'][1], q['point'][0])):
        anlage, ort, bmk = bmk_of(q['device'])
        family = families.get((round(q['point'][0], 2), round(q['point'][1], 2)))
        # Sinyal ekli klemens adi: sozlesme "gercek BMK" ister, `-X4.I` gibi adi KABUL ETMEZ.
        if bmk and '.' in bmk and q['device'] not in flagged:
            flagged.add(q['device'])
            problems.append(dict(kind='SINYAL_EKLI_BMK', device=q['device'],
                                 detail='Recete sozlesmesi "gercek BMK" istiyor; `%s` sinyal ekli '
                                        'klemens adidir. Cizimdeki ad korunmali mi, yoksa EPLAN '
                                        'tarafinda `-X4` blogu + klemens no mu kullanilmali? '
                                        'Kullanici karari.' % bmk))
        # KLEMENS: her fiziksel klemens AYRI recete satiridir (ornek recetedeki -X1 gibi).
        # Yalniz GERCEK klemens cubugu aileleri. "PLC DI giris klemensi" gibi modul uclari
        # buraya GIRMEZ: onlar modulun kendi satirinda ve urun koduyla tasinir.
        if family in KLEMENS_AILELERI:
            x_mm, y_mm = mm(q['point'], height_pt)
            row = dict(bmk=bmk, terminal_no=q['pin'], x_mm=x_mm, y_mm=y_mm,
                       _anlage=anlage, _ort=ort, _pdf=[round(v, 2) for v in q['point']],
                       _family=family, _pins=[q['pin']])
            mapped = SEMBOL_ESLEME.get(family) or {}
            if mapped.get('symbol'):
                row.update(symbol=mapped['symbol'], symbol_library=mapped['symbol_library'],
                           symbol_variant=0)
                if family not in flagged:
                    flagged.add(family)
                    problems.append(dict(kind='SEMBOL_ONAYSIZ', device=family,
                                         detail='%s -> %s (%s)' % (family, mapped['symbol'],
                                                                   mapped['why'])))
            elif family not in flagged:
                flagged.add(family)
                problems.append(dict(kind='SEMBOL_ESLESMEDI', device=family,
                                     detail='%s: %s' % (family, mapped.get('why') or 'esleme yok')))
            out.append(row)
            continue
        row = seen.get(q['device'])
        if row is None:
            x_mm, y_mm = mm(q['point'], height_pt)
            row = dict(bmk=bmk, x_mm=x_mm, y_mm=y_mm,
                       _anlage=anlage, _ort=ort, _pdf=[round(v, 2) for v in q['point']],
                       _family=family, _pins=[])
            module = modules.get(q['device'])
            if module:
                kind = next((k for k in MODUL_PARCA if k in ' '.join(module['header_texts'])), None)
                if kind:
                    row['part_number'] = MODUL_PARCA[kind]
                    row['function_text'] = ' '.join(module['header_texts'][2:6])
            elif family:
                mapped = SEMBOL_ESLEME.get(family) or {}
                if mapped.get('symbol'):
                    row['symbol'] = mapped['symbol']
                    row['symbol_library'] = mapped['symbol_library']
                    row['symbol_variant'] = 0
                    problems.append(dict(kind='SEMBOL_ONAYSIZ', device=q['device'],
                                         detail='%s -> %s (%s)' % (family, mapped['symbol'],
                                                                   mapped['why'])))
                else:
                    problems.append(dict(kind='SEMBOL_ESLESMEDI', device=q['device'],
                                         detail='%s: %s' % (family, (mapped.get('why') or
                                                                     'bu aile icin esleme yok'))))
            else:
                problems.append(dict(kind='AILE_BILINMIYOR', device=q['device'],
                                     detail='Bu uc bir kutuphane ailesine baglanmadi; sembol secilemedi.'))
            seen[q['device']] = row
            out.append(row)
        row['_pins'].append(q['pin'])
    return out


def page_wires(pilot, number, table, problems, standart=False):
    """Yalnizca FIZIKSEL cift satirlari. Ortak ag ve kapsam disi uc GIRMEZ."""
    owners, _ = cross_section_owners(pilot, number)
    classes = inherit_module_circuit(pilot, number, table,
                                     circuit_classes(pilot, number, table))
    wires = []
    for row in table['rows']:
        if row['kind'] == 'NETWORK_GROUP':
            problems.append(dict(kind='ORTAK_AG_TEL_DEGIL', device=row['net_id'],
                                 detail='%d uc ayni hatta; hangi telin nereye gittigi cizimden '
                                        'cikmiyor. Fiziksel cift uretilmedi.' % len(row['pins'])))
            continue
        if row['kind'] == 'CONFIRMED_NETWORK_RELATION':
            problems.append(dict(kind='HAT_SEVIYESINDE_TEYIT', device=row.get('reference'),
                                 detail='Kullanici hat iliskisini teyit etti ama fiziksel klemens '
                                        'secimi bekliyor; tel olarak aktarilmaz.'))
            continue
        if row['kind'] not in ('PHYSICAL_PAIR', 'CONFIRMED_PHYSICAL_PAIR'):
            continue
        if row.get('scope_state') != 'IN_SCOPE_BOTH':
            problems.append(dict(kind='KAPSAM_DISI', device=row['net_id'],
                                 detail='Kapsam: %s. Pano ici tel adayi degil.' % row.get('scope_state')))
            continue
        a, b = row['pins'][0], row['pins'][1]
        drawn, drawn_src = cross_section(owners, row)
        circuit, _ = row_circuit(row, classes)
        kesit, kesit_src, renk, renk_src = electrical_values(circuit, drawn, drawn_src)
        wire = dict(source=dict(device=bmk_of(a['device'])[2], pin=a['pin']),
                    target=dict(device=bmk_of(b['device'])[2], pin=b['pin']))
        # Tam adres KAYBOLMAZ: recete `-17K52` ister, Anlage/Einbauort burada tasinir.
        wire['_uclar'] = ['%s:%s' % (a['device'], a['pin']), '%s:%s' % (b['device'], b['pin'])]
        # MAIN 2026-09-11 §5: PDF'nin SADIK degeri ile standarttan TURETILEN deger ayridir.
        # Cizimde yazan kesit dogrudan gecer; standart kesit/renk ayri blokta durur ve yalniz
        # `--standart` secilirse gercek alana yazilir.
        if drawn:
            wire['cross_section'] = drawn
        derived = {}
        if kesit and not drawn:
            derived['cross_section'] = kesit
        if renk:
            derived['wire_color'] = renk
        if derived:
            derived.update(kaynak_kesit=kesit_src, kaynak_renk=renk_src, uygulandi=standart)
            wire['_standart'] = derived
            if standart:
                for key in ('cross_section', 'wire_color'):
                    if key in derived:
                        wire[key] = derived[key]
        wire['_kaynak'] = dict(kesit=drawn_src or kesit_src, devre=circuit,
                               referans=row.get('reference') or row['net_id'],
                               onay=row.get('review_state') or 'ONAY_BEKLIYOR')
        wires.append(wire)
    return wires


def build(pilot, numbers, standart=False):
    index = pilot._index()
    sizes = pilot.pages()
    pages, problems, plants = [], [], set()
    for number in numbers:
        facts = next((q for q in index if q['physical_page'] == number), {})
        height_pt = sizes[number][1]
        table = pilot.table(number)
        devices = page_devices(pilot, number, height_pt, problems)
        wires = page_wires(pilot, number, table, problems, standart)
        plants |= {d['_anlage'] for d in devices if d['_anlage']}
        pages.append(dict(page_number=int(facts.get('blatt') or number),
                          page_type='CircuitElectric',
                          page_title=facts.get('title') or ('Blatt %s (PDF sayfa %d)'
                                                            % (facts.get('blatt'), number)),
                          devices=devices, wires=wires,
                          _pdf_page=number, _anlage=facts.get('anlage'),
                          _einbauort=facts.get('einbauort')))
    if len(plants) > 1:
        problems.append(dict(kind='COK_ANLAGE', device=','.join(sorted(plants)),
                             detail='Recete kokunde TEK `plant` alani var, ama bu sayfalarda '
                                    'birden cok Anlage kullaniliyor. Anlage basina ayri recete '
                                    'gerekir veya kopru genisletilmelidir.'))
    return dict(project_name=Path(pilot.manifest['source_path']).stem,
                plant=sorted(plants)[0] if plants else None,
                panel_name='E122',
                macro_dir='',
                parts_db='',
                grid_size_mm=4.0,
                min_gap_mm=8.0,
                pages=pages,
                _uretim=dict(
                    kaynak='analyzer_v3 ' + RUN.name,
                    belge=pilot.manifest['source_path'],
                    belge_sha256=pilot.manifest['source_sha256'],
                    uyari='Bu recete ONAYSIZ bir tasagidir. Sembol eslemeleri teyit edilmedi, '
                          'hicbir baglanti uretim onayi tasimaz. EPLAN aktarimi ayri karardir.'),
                _sorunlar=problems)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run', default=str(RUN))
    ap.add_argument('--pages', default='4,5,28,36')
    ap.add_argument('--out', default=str(RUN/'recete'))
    ap.add_argument('--standart', action='store_true',
                    help='Standarttan turetilen kesit/rengi gercek alana da yaz (varsayilan: yalniz ayri blok)')
    args = ap.parse_args()
    pilot = Pilot(args.run, verify=False)
    pilot.refresh()
    numbers = [int(n) for n in args.pages.split(',') if n.strip()]
    recipe = build(pilot, numbers, args.standart)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    path = out/'recete_E122.json'
    path.write_text(json.dumps(recipe, ensure_ascii=False, indent=1), encoding='utf-8')
    devices = sum(len(p['devices']) for p in recipe['pages'])
    wires = sum(len(p['wires']) for p in recipe['pages'])
    print('%s\n  sayfa=%d  cihaz=%d  tel=%d  sorun=%d'
          % (path, len(recipe['pages']), devices, wires, len(recipe['_sorunlar'])))
    kinds = {}
    for p in recipe['_sorunlar']:
        kinds[p['kind']] = kinds.get(p['kind'], 0)+1
    for k in sorted(kinds):
        print('    %-24s %d' % (k, kinds[k]))


if __name__ == '__main__':
    main()
