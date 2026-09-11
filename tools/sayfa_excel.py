"""Sayfa bazli inceleme Excel'i: 37 sutunlu EPLAN standardi + yardimci sayfalar.

Bu dosya URETIM/IMPORT LISTESI DEGILDIR. MAIN.md'nin 37 sutun sirasi birebir korunur;
varsayilan olarak yalniz 1/8/15/22/30/31 doldurulur ve kaniti olmayan alan BOS birakilir.
Kesit/renk yalnizca cizimde o iletkenin yaninda yazili ise veya MAIN'de acikca yazili bir
kural varsa girilir; her giris icin kaynak `Kaynak_Kontrol` sayfasinda gosterilir.

Kullanim: python tools/sayfa_excel.py [sayfa ...]
"""
import sys
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analyzer_v3.service import Pilot                                    # noqa: E402
from analyzer_v3.document import classify_label                          # noqa: E402

RUN = Path(__file__).resolve().parents[1]/'output'/'pilots'/'E122'/'20260910_v3_p05_rev8'
OUT = RUN/'review'
PAGES = (2, 4, 5, 28, 36)
NEAR = 25.0            # bir kesit yazisinin iletkene sayilmasi icin en buyuk uzaklik (pt)

HEADERS = [
    '(Hedef)\n Hedef Bağlantı Noktasının Adı (tam)', '(Hedef)\nCE Proje yapıları',
    '(Hedef)\nCE: Ön Rakam', '(Hedef)\nCE: Tanımlama Harfi', '(Hedef)\nCE: Sayaç',
    '(Hedef)\nCE: Süzme Sayaç', '(Hedef)\nFiş Tanımlayıcı Metni',
    '(Hedef)\nHedef Bağlantı Noktasının Adı', '(Hedef)\nDöşeme Yönü', '(Hedef)\nMin Kesit',
    '(Hedef)\nMax Kesit', '(Hedef)\nÇift Kovan Öngörüldü', '(Hedef)\nSoket Büyüklüğü',
    '(Hedef)\nSıyırma Uzunluğu', '(Kaynak)\n Kaynak Bağlantı Noktasının Adı (tam)',
    '(Kaynak)\nCE Proje yapıları', '(Kaynak)\nCE: Ön Rakam', '(Kaynak)\nCE: Tanımlama Harfi',
    '(Kaynak)\nCE: Sayaç', '(Kaynak)\nCE: Süzme Sayaç', '(Kaynak)\nFiş Tanımlayıcı Metni',
    '(Kaynak)\nKaynak Bağlantı Noktasının Adı', '(Kaynak)\nDöşeme Yönü', '(Kaynak)\nMin Kesit',
    '(Kaynak)\nMax Kesit', '(Kaynak)\nÇift Kovan Öngörüldü', '(Kaynak)\nSoket Büyüklüğü',
    '(Kaynak)\nSıyırma Uzunluğu', 'Bağlantı Noktası Uzunluk', 'Kesit', 'Renk',
    'Bağlantı Tip Tanımı', 'Bağlantı Tanımlayıcı Metni', 'Almanyada Üretilecek',
    '(Hedef)\nNot', '(Kaynak)\nNot', '(Liste)\nNot']

HEAD_FILL = PatternFill('solid', fgColor='DDE5E2')


def head(ws, values, widths=None):
    ws.append(values)
    for i, cell in enumerate(ws[1], start=1):
        cell.font = Font(bold=True)
        cell.fill = HEAD_FILL
        cell.alignment = Alignment(wrap_text=True, vertical='top')
        ws.column_dimensions[cell.column_letter].width = (widths or {}).get(i, 20)
    ws.freeze_panes = 'A2'


def seg_distance(segment, point):
    (ax, ay), (bx, by) = segment['a'], segment['b']
    if abs(ax-bx) < 0.01:
        return abs(point[0]-ax) + max(0.0, min(ay, by)-point[1], point[1]-max(ay, by))
    if abs(ay-by) < 0.01:
        return abs(point[1]-ay) + max(0.0, min(ax, bx)-point[0], point[0]-max(ax, bx))
    return min(abs(point[0]-ax)+abs(point[1]-ay), abs(point[0]-bx)+abs(point[1]-by))


import re                                                                # noqa: E402

MULTICORE = re.compile(r'^\d+\s*[xX]\s*\d')
CONTROL24 = re.compile(r'^[PN]24\.')
POWER_PHASE = {'L1', 'L2', 'L3'}
LEADER_MAX = 80.0       # kesit isaretinin kendi cizgisi: olculen 56,6 pt
LEADER_TOUCH = 2.5      # cizginin ucu yazi kutusuna bu kadar yakinsa o yazinin isaretidir


def crosses(leader, other):
    """Dik iki parca gercekten kesisiyor mu? Yalnizca birbirine dik olanlar sinanir."""
    lh = abs(leader['a'][1]-leader['b'][1]) < 0.01
    oh = abs(other['a'][1]-other['b'][1]) < 0.01
    if lh == oh:
        return False
    h, v = (leader, other) if lh else (other, leader)
    x0, x1 = sorted((h['a'][0], h['b'][0]))
    y0, y1 = sorted((v['a'][1], v['b'][1]))
    return x0-0.01 <= v['a'][0] <= x1+0.01 and y0-0.01 <= h['a'][1] <= y1+0.01


def leader_of(text_box, segments):
    """Yazinin kendi isaret cizgisi: bir ucu yazi kutusuna degen kisa parca."""
    for s in segments:
        if max(abs(s['a'][0]-s['b'][0]), abs(s['a'][1]-s['b'][1])) > LEADER_MAX:
            continue
        for p in (s['a'], s['b']):
            dx = max(text_box[0]-p[0], p[0]-text_box[2], 0.0)
            dy = max(text_box[1]-p[1], p[1]-text_box[3], 0.0)
            if dx <= LEADER_TOUCH and dy <= LEADER_TOUCH:
                return s
    return None


def cross_section_owners(pilot, number):
    """Sayfadaki her kesit yazisini SAHIBI olan iletken parcasina bagla.

    Sahiplik kurali `nearest_word` ile aynidir: yazi EN YAKIN iletkene aittir ve bu yakinlik
    ikinci adaydan acikca kucuk olmalidir. Aksi halde sahip yok sayilir; kesit uydurulmaz.
    `4x2,5mm²` gibi KABLO yapisi tek damar kesiti degildir (MAIN "ÇOK DAMARLI KABLOLAR")
    ve ayri gerekceyle disarida birakilir.
    """
    page = pilot._page(number)
    bbox = page['render_bbox']
    owners, skipped = {}, []
    for w in page['words']:
        text = w['text'].strip()
        if 'mm' not in text.lower() or classify_label(text) != 'MEASUREMENT_OR_UNIT':
            continue
        point = ((w['x0']+w['x1'])/2-bbox[0], (w['top']+w['bottom'])/2-bbox[1])
        if MULTICORE.match(text):
            skipped.append((text, 'COK_DAMARLI_KABLO_YAPISI_TEK_DAMAR_KESITI_DEGIL'))
            continue
        # EPLAN kesit yazisi kendi ISARET CIZGISIYLE birlikte durur ve o cizginin KESTIGI
        # iletkenleri adlandirir. En yakin nesne isaret cizgisinin kendisidir; sahiplik
        # oraya degil, kesilen iletkenlere aittir.
        box = (w['x0']-bbox[0], w['top']-bbox[1], w['x1']-bbox[0], w['bottom']-bbox[1])
        leader = leader_of(box, page['segments'])
        if leader is not None:
            crossed = [s for s in page['segments']
                       if s['id'] != leader['id'] and crosses(leader, s)]
            if crossed:
                for s in crossed:
                    owners[s['id']] = (text, 0.0, [round(point[0], 2), round(point[1], 2)],
                                       'ISARET_CIZGISI:%s' % leader['id'])
                continue
            skipped.append((text, 'ISARET_CIZGISI_HICBIR_ILETKENI_KESMIYOR'))
            continue
        ranked = sorted((seg_distance(s, point), s['id']) for s in page['segments'])
        if not ranked or ranked[0][0] > NEAR:
            skipped.append((text, 'HICBIR_ILETKENE_YETERINCE_YAKIN_DEGIL'))
            continue
        rival = next((d for d, i in ranked[1:] if i != ranked[0][1]), None)
        if rival is not None and rival < ranked[0][0]*1.5:
            skipped.append((text, 'IKI_ILETKEN_AYNI_UZAKLIKTA_SAHIPLIK_KURULAMADI'))
            continue
        owners[ranked[0][1]] = (text, round(ranked[0][0], 2),
                                [round(point[0], 2), round(point[1], 2)], 'YAZI_YANINDA')
    return owners, skipped


def cross_section(owners, row):
    """Bu satirin parcalarindan birine yazi sahipligi kurulduysa kesit odur."""
    hits = {(h[0], h[1], tuple(h[2]), h[3])
            for h in (owners[i] for i in (row.get('segment_ids') or []) if i in owners)}
    if not hits:
        return None, None
    if len({h[0] for h in hits}) > 1:
        return None, 'BIRDEN_COK_KESIT_YAZISI:' + ','.join(sorted(h[0] for h in hits))
    text, d, point, how = sorted(hits)[0]
    value = text.replace('mm²', '').replace('mm2', '').strip()
    return value, 'CIZIM(seviye 1) %s @%s · %s' % (text, point, how)


# --- Devre görevi: kanıtı olan satıra kaynaklı kesit/renk uygulanır -----------------------
#
# MAIN öncelik sırası: 1) projeye özel bilgi (çizim/proje notu), 2) TROESTER, 3) UVP.
# Çelişkide TROESTER geçerlidir ve UVP uygulanmaz. Akımdan kesit hesaplanmaz.
TROESTER_24VDC_COLOUR = 'DBU'      # "24 VDC (+)/(−) → Mavi / DBU (RAL5010)"
UVP_POWER_COLOUR = 'BK'            # "Faz R/S/T 400V → Siyah"; TROESTER satırı BOŞ
NOTE_CONTROL_MM2 = '1'             # sayfa notu: "Steuerleitungen 1 mm² Cu"
NOTE_DEFAULT_MM2 = '1,5'           # sayfa notu: "Alle Leitungen ohne Querschnittsangabe 1,5 mm² Cu"


def device_potentials(pilot, number, table):
    """Her cihazın ulaştığı potansiyel adları — cihazın KENDİ sayfasındaki çizgilerinden."""
    page = pilot._page(number)
    bbox = page['render_bbox']
    pots = [(w['text'], ((w['x0']+w['x1'])/2-bbox[0], (w['top']+w['bottom'])/2-bbox[1]))
            for w in page['words'] if classify_label(w['text']) == 'POTENTIAL']
    by_id = {s['id']: s for s in page['segments']}
    found = {}
    for row in table['rows']:
        segs = [by_id[i] for i in (row.get('segment_ids') or []) if i in by_id]
        if not segs:
            continue
        near = {t for t, p in pots if min(seg_distance(s, p) for s in segs) <= 30}
        for q in row['pins']:
            found.setdefault(q['device'], set()).update(near)
    return found


def circuit_classes(pilot, number, table):
    """Cihaz → (devre görevi, kanıt). Kanıt yoksa BELIRSIZ; uydurma yok."""
    pots = device_potentials(pilot, number, table)
    out = {}
    for device, names in pots.items():
        control = sorted(n for n in names if CONTROL24.match(n))
        power = sorted(n for n in names if n in POWER_PHASE)
        if control and not power:
            out[device] = ('KUMANDA_24VDC', 'çizimde bu cihazın hattında %s potansiyeli yazılı'
                           % ', '.join(control))
        elif power and not control:
            out[device] = ('GUC_400V', 'çizimde bu cihazın hattında %s fazı yazılı'
                           % ', '.join(power))
        elif control and power:
            out[device] = ('CELISKI', 'hem %s hem %s aynı cihazda'
                           % (', '.join(control), ', '.join(power)))
    # PLC modülü: başlıktaki gerilim yazısı doğrudan kanıttır.
    for module in pilot.module_report(number)['modules']:
        if not module.get('device'):
            continue
        header = ' '.join(module['header_texts'])
        if '24VDC' in header.replace(' ', ''):
            out[module['device']] = ('KUMANDA_24VDC',
                                     'modül başlığında "%s" yazılı' % header.strip())
    return out


def row_circuit(row, classes):
    """Satırın devre görevi: iki ucun kanıtından. Uçlar çelişirse karar KULLANICIYA kalır."""
    seen = [(q['device'], classes.get(q['device'])) for q in row['pins']]
    kinds = {c[0] for _, c in seen if c}
    if 'CELISKI' in kinds or kinds == {'KUMANDA_24VDC', 'GUC_400V'}:
        return 'CELISKI', '; '.join('%s: %s' % (d, c[1]) for d, c in seen if c)
    for want in ('KUMANDA_24VDC', 'GUC_400V'):
        if want in kinds:
            return want, '; '.join('%s: %s' % (d, c[1]) for d, c in seen if c and c[0] == want)
    return 'BELIRSIZ', 'Uçların hiçbirinde devre görevini kanıtlayan potansiyel/gerilim yazısı yok.'


def inherit_module_circuit(pilot, number, table, classes):
    """Aynı PLC modülünün diğer kanalı kanıtlıysa, o modülün bütün kanalları aynı devrededir.

    8DO/8DI modülü tek tiptir ve kanalları ortak L+/M grubundan beslenir; bir kanalın
    kanıtı modülün kendisine aittir. Kanıt metninde hangi kardeş satırdan geldiği yazılır.
    """
    for module in pilot.module_report(number)['modules']:
        device = module.get('device')
        if not device or device in classes:
            continue
        proofs = []
        for row in table['rows']:
            names = [q['device'] for q in row['pins']]
            if device not in names:
                continue
            other = [d for d in names if d != device]
            for d in other:
                if classes.get(d, ('', ''))[0] == 'KUMANDA_24VDC':
                    proofs.append('%s (%s)' % (d, classes[d][1]))
        if proofs:
            classes[device] = ('KUMANDA_24VDC',
                               'aynı modülün başka kanalı kanıtlı: ' + '; '.join(sorted(set(proofs))[:2]))
    return classes


def electrical_values(circuit, drawn_kesit, drawn_source):
    """Kaynaklı kesit ve renk. Çizim her zaman 1. seviyedir; standart ancak sessizlikte devreye girer."""
    kesit, kesit_src = drawn_kesit, drawn_source
    renk, renk_src = '', ''
    if circuit == 'KUMANDA_24VDC':
        renk = TROESTER_24VDC_COLOUR
        renk_src = ('TROESTER(seviye 2) "Kablolama Standartları": 24 VDC (+)/(−) → Mavi / DBU '
                    '(RAL5010). UVP (−) için DBUWH diyor; MAIN "TROESTER>UVP" gereği UVP '
                    'uygulanmadı. Bu satırların hepsi 24 V (+) taşır.')
        if not kesit:
            kesit = NOTE_CONTROL_MM2
            kesit_src = ('PROJE NOTU(seviye 1) "Steuerleitungen 1 mm² Cu" — devre görevi kumanda '
                         'olarak kanıtlandı. UVP "PLC\'de 0,75 mm²" diyor; MAIN "çizim veya '
                         'standart 1 mm² diyorsa 1 mm²" gereği uygulanmadı.')
    elif circuit == 'GUC_400V':
        renk = UVP_POWER_COLOUR
        renk_src = ('UVP(seviye 3) "Faz R/S/T 400V → Siyah". TROESTER tablosunda bu satır BOŞ, '
                    'bu yüzden çelişki yok. Renk çizimdeki siyah çizgiden DEĞİL, standarttan.')
        if not kesit:
            kesit_src = ('KESIT YOK: çizimde işaret yok; sayfa notundaki 1,5 mm² yalnız '
                         '"Querschnittsangabe olmayan" iletken içindir, güç devresinde akıma '
                         'göre seçim UVP tablosundadır ve MAIN akımdan hesap yapmayı yasaklar.')
    elif circuit == 'CELISKI':
        kesit_src = kesit_src or 'ÇELİŞKİ: devre görevi iki uçta farklı çıkıyor; kullanıcı kararı.'
        renk_src = 'ÇELİŞKİ: devre görevi çözülmeden renk atanmaz.'
    else:
        kesit_src = kesit_src or 'DEVRE GÖREVİ KANITLANMADI: kesit/renk atanmadı.'
        renk_src = 'DEVRE GÖREVİ KANITLANMADI: renk atanmadı.'
    return kesit or '', kesit_src, renk, renk_src


def pair_rows(table):
    return [r for r in table['rows']
            if r['kind'] in ('PHYSICAL_PAIR', 'CONFIRMED_PHYSICAL_PAIR')
            and r.get('scope_state') == 'IN_SCOPE_BOTH']


def build(pilot, number):
    table = pilot.table(number)
    view = pilot.overview(number)
    modules = pilot.module_report(number)
    conts = pilot.continuations(number)
    facts = next((q for q in pilot._index() if q['physical_page'] == number), {})
    owners, skipped = cross_section_owners(pilot, number)
    classes = inherit_module_circuit(pilot, number, table,
                                     circuit_classes(pilot, number, table))
    wb = openpyxl.Workbook()

    banner = wb.active
    banner.title = 'OKU_ONCE'
    head(banner, ['Alan', 'Değer'], {1: 34, 2: 110})
    for k, v in [
        ('Belge', pilot.manifest['source_path']),
        ('Belge SHA-256', pilot.manifest['source_sha256']),
        ('Çalışma', RUN.name),
        ('Fiziksel sayfa', number),
        ('Sayfa kimliği', view['page_label']),
        ('Bu dosya nedir?', 'İNCELEME çıktısıdır. Üretim listesi veya EPLAN import dosyası DEĞİLDİR.'),
        ('Doldurulan sütunlar', '1, 8, 15, 22 (adlar) ve kanıtı varsa 30 (Kesit), 31 (Renk). '
                                'Diğer alanlar MAIN.md gereği boştur.'),
        ('Uzunluk / döşeme yönü', 'Pro Panel 3B güzergâhından gelir; bu araçtan ÇIKMAZ, boş bırakıldı.'),
        ('Onay durumu', 'İlişki teyidi, yeniden inceleme ve üretime uygunluk AYRI alanlardır; '
                        'üretime uygun satır sayısı 0.'),
        ('Özet', view['headline']),
    ]:
        banner.append([k, str(v)])

    ws = wb.create_sheet('EPLAN_37')
    head(ws, HEADERS, {i: 26 for i in range(1, 38)})
    sources = []
    for row in pair_rows(table):
        a, b = row['pins'][0], row['pins'][1]
        drawn, drawn_src = cross_section(owners, row)
        circuit, circuit_why = row_circuit(row, classes)
        kesit, kesit_src, renk, renk_src = electrical_values(circuit, drawn, drawn_src)
        values = [''] * 37
        values[0] = '%s:%s' % (b['device'], b['pin'])
        values[7] = b['pin']
        values[14] = '%s:%s' % (a['device'], a['pin'])
        values[21] = a['pin']
        values[29] = kesit
        values[30] = renk
        ws.append(values)
        sources.append(dict(row=row, kesit=kesit, kesit_kaynak=kesit_src, renk=renk,
                            renk_kaynak=renk_src, circuit=circuit, circuit_why=circuit_why))

    ws = wb.create_sheet('Kontrol')
    head(ws, ['Cihaz nerden', 'Pin nerden', 'Cihaz nereye', 'Pin nereye', 'Kesit', 'Renk',
              'İlişki teyidi', 'Uygulama türü', 'Kapsam', 'Üretime uygun', 'Kanıt / referans'],
         {1: 24, 3: 24, 7: 30, 8: 16, 9: 16, 11: 34})
    for item in sources:
        row = item['row']
        a, b = row['pins'][0], row['pins'][1]
        view_row = next((c for c in view['connections']
                         if c['from_pin'] == a['pin'] and c['to_pin'] == b['pin']), {})
        ws.append([a['device'], a['pin'], b['device'], b['pin'], item['kesit'], item['renk'],
                   view_row.get('state', ''), row.get('implementation_type', ''),
                   row.get('scope_state', ''), 'HAYIR',
                   row.get('reference') or row['net_id']])

    ws = wb.create_sheet('Kaynak_Kontrol')
    head(ws, ['Kaynak', 'Pin', 'Hedef', 'Pin', 'Devre görevi', 'Devre kanıtı',
              'Kesit', 'Kesit kaynağı', 'Renk', 'Renk kaynağı', 'İşaret yöntemleri',
              'Sayfa / Blatt'],
         {1: 24, 3: 24, 5: 18, 6: 54, 8: 58, 10: 58, 11: 22, 12: 18})
    for item in sources:
        row = item['row']
        a, b = row['pins'][0], row['pins'][1]
        ws.append([a['device'], a['pin'], b['device'], b['pin'],
                   item['circuit'], item['circuit_why'],
                   item['kesit'], item['kesit_kaynak'], item['renk'], item['renk_kaynak'],
                   ','.join(sorted({q.get('method', '') for q in row['pins']})),
                   'sayfa %s / Blatt %s' % (number, facts.get('blatt'))])
    for text, why in skipped:
        ws.append(['—', '—', '—', '—', '—', '—', '',
                   'KULLANILMADI:%s — %s' % (text, why), '', '', '',
                   'sayfa %s / Blatt %s' % (number, facts.get('blatt'))])
    ws.append(['—', '—', '—', '—', 'KURAL', 'PE iletkeni için MAIN "PE → GNYE" ve UVP '
               '"Toprak → Sarı-Yeşil" geçerlidir; bu sayfada PE fiziksel çifti yok, '
               'uygulanacak satır çıkmadı.', '', '', '', '', '',
               'sayfa %s / Blatt %s' % (number, facts.get('blatt'))])

    ws = wb.create_sheet('Teyit_Bekleyenler')
    head(ws, ['Tür', 'Uçlar', 'Sorun', 'Neden kesinleştirilemedi', 'Sayfa'],
         {2: 52, 3: 40, 4: 70})
    for row in table['rows']:
        if row['kind'] == 'CONFIRMED_NETWORK_RELATION':
            ws.append(['HAT_SEVİYESİNDE_TEYİTLİ (%s)' % row.get('reference'),
                       ', '.join('%s:%s' % (q['device'], q['pin']) for q in row['pins']),
                       'Fiziksel klemens seçimi bekleniyor',
                       'Kullanıcı bu hat ilişkisini teyit etti; hangi fiziksel klemensin '
                       'kullanılacağı çizimden çıkmıyor. MAIN.md 2026-09-08 §1: ilişki ana '
                       'tabloda görünür kalır, üretim listesine giremez.', number])
        elif row['kind'] == 'NETWORK_GROUP':
            ws.append(['ORTAK_AĞ',
                       ', '.join('%s:%s' % (q['device'], q['pin']) for q in row['pins']),
                       'Fiziksel dağıtım topolojisi belirsiz',
                       'Aynı potansiyeldeki uçlar. Hangi telin hangi uca gittiği çizimden '
                       'çıkmıyor; MAIN "ORTAK POTANSİYEL" gereği tel çifti türetilmedi.', number])
        elif row['kind'] == 'SINGLE_END':
            q = row['pins'][0]
            ws.append(['TEK_UÇ', '%s:%s' % (q['device'], q['pin']), 'Karşı uç işaretli değil',
                       'Bu sayfada karşı uç bulunamadı veya işaretlenmedi.', number])
        elif row['kind'] == 'PAIR_OUT_OF_PANEL_SCOPE':
            ws.append(['KAPSAM_DIŞI',
                       ', '.join('%s:%s' % (q['device'], q['pin']) for q in row['pins']),
                       'Bir uç pano dışında', 'MAIN "PANO SINIRI KURALI": saha/başka pano ucu '
                       'taşıyan bağlantı pano içi tel adayı değildir.', number])
    for module in modules['modules']:
        for q in module['unresolved']:
            ws.append(['PLC_UCU_ÇÖZÜLEMEDİ', '%s (x=%.2f)' % (module['device'] or '?', q['x']),
                       q['why'], 'Ucun yanında pin adı basılı değil; ad uydurulmadı.', number])
        for q in module['no_conductor']:
            ws.append(['PLC_UCU_İLETKENSİZ', '%s:%s' % (module['device'], q['pin']),
                       'Dış iletken çizilmemiş',
                       'Bu uçtan çıkan tel çizimde YOK. Kaçırılmış tel değildir; '
                       'ayrı kovada tutulur.', number])
    for row in conts['rows']:
        if row['status'] not in ('RECIPROCAL_END_MATCHED', 'DEVICE_REFERENCE_NOT_A_CONTINUATION'):
            ws.append(['SAYFA_DEVAMI', row['text'], row['status'],
                       'Hedef sayfada karşılıklı uç doğrulanamadı.', number])

    ws = wb.create_sheet('Sayfa_Kapsami')
    head(ws, ['Alan', 'Değer'], {1: 38, 2: 96})
    s = view['summary']
    for k, v in [
        ('Anlage / Einbauort / Blatt', view['page_label']),
        ('Bulunan tel (iki ucu izlenen)', s['connections']),
        ('İlişki teyidi — güncel', s['confirmed_current']),
        ('İlişki teyidi — askıda (yeniden inceleme)', s['confirmed_suspended']),
        ('Onay bekleyen', s['awaiting_confirmation']),
        ('Üretime uygun', s['production_ready']),
        ('Ortak hat (tel çifti üretilmedi)', s['networks']),
        ('Yarım kayıt', s['singles']),
        ('İşaretli uç', s['marks']),
        ('Gerekçeli boşluk', s['unresolved']),
        ('PLC modülü', modules['counts']['modules']),
        ('PLC ucu — kimliği çözüldü, iletkeni var', modules['counts']['resolved']),
        ('PLC ucu — kimliği çözüldü, iletkeni yok', modules['counts']['no_conductor']),
        ('PLC ucu — kimliği çözülemedi', modules['counts']['unresolved']),
        ('Sayfa devamı — karşılıklı eşleşti',
         sum(1 for r in conts['rows'] if r['status'] == 'RECIPROCAL_END_MATCHED')),
        ('Sayfa devamı — çözülemedi',
         sum(1 for r in conts['rows'] if r['status'] not in
             ('RECIPROCAL_END_MATCHED', 'DEVICE_REFERENCE_NOT_A_CONTINUATION'))),
    ]:
        ws.append([k, str(v)])

    path = OUT/('20260911_sayfa%d_inceleme.xlsx' % number)
    wb.save(path)
    return path, len(sources)


def main(pages):
    pilot = Pilot(RUN, verify=False)
    for number in pages:
        path, rows = build(pilot, number)
        print('%s  (%d EPLAN satiri)' % (path.name, rows))


if __name__ == '__main__':
    main([int(a) for a in sys.argv[1:]] or list(PAGES))
