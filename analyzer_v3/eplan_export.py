"""PLAN S03 / EPLAN_ADDIN_PLAN E04: erken gerçek P8 kanıtı için KÜÇÜK kaynak paketi.

Bu bizim sözleşmemizdir (`uvp.pdf2p8.import-request` 1.0), EPLAN'ın import biçimi değildir.
Paket yalnız kaynak modeli taşır: sayfa, cihaz/pin konumu, birleşim, devam, beklenen topoloji.
Hedef sembol seçimi AYRI eşleme dosyasındadır (`mapping`), çünkü sembol adı hedef kataloğa aittir.

Kanıt bölgesi bilinçli olarak dardır (CLAUDE_NEXT §5): sayfa 4 `L1 → -3F22:1`, `-3F22:2 → -X1:1`,
L1 rayında çizilmiş noktalı T ve `/4.11` → sayfa 5 `/3.19` devamı; sayfa 5'te aynı L1 yapısı.
Seçili kimlikler kaynak modelden okunur; bulunamayan hiçbir şey uydurulmaz — paket kurulmaz.

Koordinat: kaynak pt, sol üst köken. Hedef mm, sol alt köken: x_mm = x·25.4/72,
y_mm = (H − y)·25.4/72. Bu bir VARSAYIMDIR; E04 geri okumasında ölçülür (EPLAN_ADDIN_PLAN §5).
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

PT_TO_MM = 25.4/72

# Kanıt bölgesi: sayfa → (sigorta cihazı, sigortanın L1 giriş/çıkış pini, klemens ucu).
PROOF = {4: ('-3F22', '1', '2', ('-X1', '1')),
         5: ('-4F22', '1', '2', ('-X1', '4'))}


def _mm(point, height):
    return [round(point[0]*PT_TO_MM, 3), round((height-point[1])*PT_TO_MM, 3)]


def _continuation_ids(body):
    """Potansiyel adı devam kimliği değildir; yalnız karşılıklı uçlar kimlik paylaşır."""
    ends = [(pg['physical_page'], o) for pg in body['pages'] for o in pg['objects']
            if o['kind'] == 'INTERRUPTION']
    pairs, done = [], set()
    for number, end in ends:
        matches = [(n, other) for n, other in ends if other['id'] != end['id']
                   and end.get('verified') and other.get('verified')
                   and end.get('target_page') == n and other.get('target_page') == number
                   and end.get('target_reference') == other.get('reference')
                   and other.get('target_reference') == end.get('reference')
                   and end.get('name') == other.get('name')]
        ids = sorted([end['id'], matches[0][1]['id']]) if len(matches) == 1 else [end['id']]
        seed = body['document_sha256'] + '|' + '|'.join(ids)
        end['import_name'] = 'UVP_' + hashlib.sha256(seed.encode('utf-8')).hexdigest()[:20]
        end['partner_in_package'] = len(matches) == 1
        if len(matches) == 1 and tuple(ids) not in done:
            pairs.append(dict(a=ids[0], b=ids[1], evidence='RECIPROCAL_SOURCE_REFERENCE'))
            done.add(tuple(ids))
    body['expected_continuations'] = pairs


def proof_package(pilot, pages=(4, 5)):
    """Kaynak modelden kanıt paketi. Beklenen her bağ bir çizilmiş segmentten gelir."""
    out_pages, expected, issues = [], [], []
    continuation_names = {}
    for number in pages:
        model = pilot.page_model(number)
        rel = pilot.relations(number)
        height = model['page']['height']
        fuse, pin_in, pin_out, (strip, strip_pin) = PROOF[number]

        def pin_node(tail, pin):
            for n in model['nodes']:
                if n['kind'] == 'PIN' and n['device'].endswith(tail) and n['pin'] == pin:
                    return n
            raise ValueError('Sayfa %s: kaynak pin yok: %s:%s' % (number, tail, pin))

        l1 = [n for n in rel['networks'] if n['potential'] == 'L1'
              and any(q['label'] == '%s:%s' % (fuse, pin_in) for q in n['pins'])]
        if len(l1) != 1:
            raise ValueError('Sayfa %s: L1 ağı tek değil: %d' % (number, len(l1)))
        l1 = l1[0]
        dots = [j for j in l1['junctions'] if j['evidence'] == 'DRAWN_DOT']
        if len(dots) != 1:
            raise ValueError('Sayfa %s: L1 rayında tek çizilmiş birleşim beklenirdi: %d' % (number, len(dots)))
        junction = dots[0]['point']
        p_in, p_out, p_strip = pin_node(fuse, pin_in), pin_node(fuse, pin_out), pin_node(strip, strip_pin)
        objects = [
            dict(id='p%d:dev:%s' % (number, fuse), kind='DEVICE', family='fuse_1pole',
                 device_tag=p_in['device'], note='3 kutuplu cihazın yalnız L1 kutbu (kanıt bölgesi).',
                 pins=[dict(name=pin_in, index=0, point_pt=p_in['point'], point_mm=_mm(p_in['point'], height),
                            source_id=p_in['id']),
                       dict(name=pin_out, index=1, point_pt=p_out['point'], point_mm=_mm(p_out['point'], height),
                            source_id=p_out['id'])]),
            dict(id='p%d:dev:%s:%s' % (number, strip, strip_pin), kind='DEVICE', family='terminal',
                 device_tag=p_strip['device'], terminal=strip_pin,
                 pins=[dict(name=strip_pin, index=0, point_pt=p_strip['point'],
                            point_mm=_mm(p_strip['point'], height), source_id=p_strip['id'])]),
            dict(id='p%d:junction:L1' % number, kind='JUNCTION', family='tnode_down', evidence='DRAWN_DOT',
                 point_pt=junction, point_mm=_mm(junction, height)),
        ]
        ends = []
        for c in l1['continuations']:
            left = c['point'][0] < junction[0]
            partner_in_package = c.get('target_page') in pages and c.get('verified')
            if partner_in_package:
                kind, family = 'INTERRUPTION', 'interruption'
            elif left:
                # Kaynağı paket dışı sayfa: ad kaynaktaki basılı potansiyelden, sınır olarak.
                kind, family = 'POTENTIAL_BOUNDARY', 'potential_definition'
            else:
                # Hedefi paket dışı: EPLAN'da eşsiz kesinti noktası olarak kalır (çapraz ref. yok).
                kind, family = 'INTERRUPTION', 'interruption'
            end = dict(id='p%d:end:%s' % (number, c['reference']), kind=kind, family=family,
                       name='L1', reference=c['reference'], target_page=c.get('target_page'),
                       target_reference=c.get('target_reference'),
                       verified=bool(c.get('verified')), partner_in_package=bool(partner_in_package),
                       side='LEFT' if left else 'RIGHT', point_pt=c['point'], point_mm=_mm(c['point'], height))
            objects.append(end)
            ends.append(end)
            if partner_in_package:
                continuation_names.setdefault('L1', []).append(end['id'])
        # Beklenen topoloji: kaynak ilişkilerindeki gerçek segmentlerden.
        jid = 'p%d:junction:L1' % number
        for end in ends:
            expected.append(dict(page=number, a=end['id'], b=jid, via='L1 rayı (çizilmiş segment)'))
        expected.append(dict(page=number, a=jid, b='p%d:dev:%s#%s' % (number, fuse, pin_in),
                             via='T dalı → %s:%s' % (fuse, pin_in)))
        pp = [r for r in rel['relations'] if r['kind'] == 'PIN_PIN'
              and {r['source'], r['target']} == {'%s:%s' % (fuse, pin_out), '%s:%s' % (strip, strip_pin)}]
        if len(pp) != 1:
            raise ValueError('Sayfa %s: %s:%s → %s:%s yolu kaynakta tek değil' % (number, fuse, pin_out, strip, strip_pin))
        expected.append(dict(page=number, a='p%d:dev:%s#%s' % (number, fuse, pin_out),
                             b='p%d:dev:%s:%s#%s' % (number, strip, strip_pin, strip_pin),
                             via='çizilmiş yol', segment_ids=pp[0]['segment_ids']))
        out_pages.append(dict(physical_page=number, blatt=model['page']['blatt'],
                              anlage=model['page']['anlage'], einbauort=model['page']['einbauort'],
                              source_size_pt=[model['page']['width'], height], objects=objects))
    for name, ids in continuation_names.items():
        if len(ids) != 2:
            issues.append('Devam %s paket içinde çift değil: %s' % (name, ids))
    body = dict(contract='uvp.pdf2p8.import-request', contract_version='1.0',
                document_sha256=pilot.manifest.get('source_sha256'),
                page_model_contract='uvp.pdf2p8.page/1.0',
                coordinate=dict(source='pt, sol üst köken (render bbox çıkarılmış)', target='mm, sol alt köken',
                                transform='x*25.4/72, (H-y)*25.4/72', calibrated=False,
                                note='Kalibrasyon E04 geri okumasında ölçülür; bu dönüşüm varsayımdır.'),
                target_policy=dict(new_test_project_only=True, live_project_writes=False,
                                   production_released=False),
                pages=out_pages, expected_links=expected, issues=issues)
    _continuation_ids(body)
    raw = json.dumps(body, ensure_ascii=False, sort_keys=True).encode('utf-8')
    body['payload_sha256'] = hashlib.sha256(raw).hexdigest()
    return body


# Cihaz ailesi CİHAZ HARFİ ve PİN ADLARINDAN okunur; EPLAN sembolü eşleme dosyasından gelir.
# Tanınmayan aile UYDURULMAZ: 'unmapped:...' kalır ve aktarımda reddedilir (sessizce atlanmaz).
FAMILY_BY_LETTER = {'F': 'fuse_1pole', 'X': 'terminal'}
NO_CONTACT_ENDS = {('3', '4'), ('1', '4')}      # 13/14, 23/24, 11/14 (değiştirici NO yolu)
NC_CONTACT_ENDS = {('1', '2')}                  # 11/12, 21/22


def _letter(device_tag):
    for ch in device_tag.split('-')[-1]:
        if ch.isalpha():
            return ch.upper()
    return '?'


def _family(device_tag, pin_names, profile=None):
    """Cihaz ailesi. Kurallar MÜŞTERİ PROFİLİNDEN gelir; profil yoksa yerleşik kurallar."""
    from . import customer
    return customer.family_of(profile or customer.load(), device_tag, pin_names)


def _label_table(pilot, profile):
    """Etiket listesi (Excel) — belgenin yanındaki dosyadan, bir kez okunur.

    Dosya yoksa boş tablo döner ve paket bunu `issues` altında söyler: sessizce
    "kod yok" denmez, "liste bulunamadı" denir.
    """
    from . import labels
    if getattr(pilot, '_label_cache', None) is not None:
        return pilot._label_cache
    given = (profile or {}).get('label_file')
    path = Path(given) if given else labels.find_file(Path(pilot.manifest['source_path']).parent)
    table, note = {}, None
    if path is None:
        note = 'Etiket listesi (Excel) bulunamadı; ürün kodu yalnız malzeme listesinden aranacak.'
    else:
        try:
            table = labels.read(path)
        except Exception as error:                        # noqa: BLE001 — paket düşmez
            note = 'Etiket listesi okunamadı (%s): %s' % (path, error)
    pilot._label_cache = dict(table=table, path=str(path) if path else None, note=note)
    return pilot._label_cache


def _articles(pilot):
    """Belgenin malzeme listesinden cihaz → ürün kodu adayları (bir kez okunur)."""
    from . import parts
    if not hasattr(pilot, '_article_cache'):
        try:
            pilot._article_cache = parts.document_articles(pilot)
        except Exception as error:                        # noqa: BLE001 — liste okunamazsa paket düşmez
            pilot._article_cache = dict(devices={}, scanned_pages=[], unprepared_pages=[],
                                        note='Malzeme listesi okunamadı: %s' % error)
    return pilot._article_cache


def _drawn_links(net, anchors, number, height):
    """Yıldız/zincir üretmeden yalnız grafın ölçülmüş kenarlarında yürü.

    Derece-2 köşeler polyline'da korunur. Eksik çapa veya işaretsiz dallanma
    yeni bir bağlantı icat etmez; gerekçesiyle açık kalır.
    """
    adjacency = {}
    for edge in net['edges']:
        a, b = tuple(edge[:2]), tuple(edge[2:])
        if a == b:
            continue
        adjacency.setdefault(a, set()).add(b)
        adjacency.setdefault(b, set()).add(a)
    by_point, issues = {}, []
    for identity, point in anchors.items():
        hits = [p for p in adjacency if math.dist(p, point) <= 0.6]
        if len(hits) != 1 or hits[0] in by_point:
            issues.append('%s: uç çizilmiş grafta tekil değil (%s).' % (net['id'], identity))
            continue
        by_point[hits[0]] = identity
    visited, links = set(), []
    for start in sorted(by_point):
        for following in sorted(adjacency[start]):
            if frozenset((start, following)) in visited:
                continue
            route, previous, current = [start], start, following
            while True:
                edge_id = frozenset((previous, current))
                if edge_id in visited:
                    break
                visited.add(edge_id)
                route.append(current)
                if current in by_point:
                    points = [route[0]]
                    for i in range(1, len(route)-1):
                        a, b, c = points[-1], route[i], route[i+1]
                        cross = (b[0]-a[0])*(c[1]-b[1]) - (b[1]-a[1])*(c[0]-b[0])
                        if abs(cross) > 1e-7:
                            points.append(b)
                    points.append(route[-1])
                    links.append(dict(page=number, a=by_point[start], b=by_point[current],
                                      via='çizilmiş graf yolu', network=net['id'],
                                      potential=net.get('potential'),
                                      polyline_pt=[list(p) for p in points],
                                      polyline_mm=[_mm(p, height) for p in points],
                                      source_edges=[list(a+b) for a, b in zip(route, route[1:])]))
                    break
                next_points = adjacency[current] - {previous}
                if len(adjacency[current]) != 2 or len(next_points) != 1:
                    issues.append('%s: işaretsiz açık uç/dal %s; bağlantı uydurulmadı.' % (net['id'], current))
                    break
                previous, current = current, next(iter(next_points))
    all_edges = {frozenset((a, b)) for a, bs in adjacency.items() for b in bs}
    if all_edges - visited:
        issues.append('%s: %d çizilmiş parça aktarım ucuna bağlanamadı.' % (net['id'], len(all_edges-visited)))
    return links, issues


def _wire_directions(rel, tol=0.6):
    """Her uç noktası için telin gittiği yön (Up/Down/Left/Right), PDF koordinatında.

    Noktaya değen çizilmiş kenarın öbür ucu yukarıdaysa 'Up'. Aynı noktada birden çok yön
    varsa (uç bir dalın ortasında) `_direction_at` None döner — yön uydurulmaz.
    PDF'te y aşağı büyür; EPLAN'da yukarı. Yön ADI ikisinde de aynı görsel anlamı taşır.
    """
    out = {}
    for net in rel.get('networks') or []:
        for edge in net.get('edges') or []:
            a, b = (edge[0], edge[1]), (edge[2], edge[3])
            for here, there in ((a, b), (b, a)):
                dx, dy = there[0] - here[0], there[1] - here[1]
                if abs(dx) < tol and abs(dy) < tol:
                    continue
                if abs(dx) >= abs(dy):
                    way = 'Right' if dx > 0 else 'Left'
                else:
                    way = 'Down' if dy > 0 else 'Up'
                out.setdefault((round(here[0], 1), round(here[1], 1)), set()).add(way)
    return out


def _direction_at(directions, point, tol=0.6):
    """Noktadaki TEK tel yönü; yoksa ya da birden çoksa None."""
    found = set()
    for (x, y), ways in directions.items():
        if abs(x - point[0]) <= tol and abs(y - point[1]) <= tol:
            found |= ways
    return next(iter(found)) if len(found) == 1 else None


def _majority_direction(directions, pins):
    """Cihazın telden OKUNABİLEN uç yönlerinin çoğunluğu; hiç yoksa ya da eşitse None."""
    from collections import Counter
    counts = Counter(d for d in (_direction_at(directions, q['point']) for q in pins) if d)
    if not counts:
        return None
    ranked = counts.most_common(2)
    if len(ranked) == 2 and ranked[0][1] == ranked[1][1]:
        return None
    return ranked[0][0]


def _box_groups(pins, gap_pt):
    """Aynı yükseklikte, aralarında `gap_pt`'den az olan uçlar TEK KUTU olur.

    Dönüş: uç kimliği → kutunun İLK (en soldaki) ucunun kimliği. Ölçüt, hedef proje s.45:
    -13D22 kutusu 1+9 ve 3+11 taşıyor; kaynakta bu çiftlerin arası 10 mm, kanal aralığı 40 mm.
    """
    out, rows = {}, {}
    for pin in pins:
        rows.setdefault(round(pin['point'][1]), []).append(pin)
    for row in rows.values():
        row.sort(key=lambda q: q['point'][0])
        head = row[0]
        out[head['id']] = head['id']
        for previous, pin in zip(row, row[1:]):
            if pin['point'][0] - previous['point'][0] > gap_pt:
                head = pin
            out[pin['id']] = head['id']
    return out


def _box_roles(pins, gap_pt):
    """Uç kimliği → 'single' | 'first' | 'extra' (kutunun ilk ucu 'first')."""
    from collections import Counter
    groups = _box_groups(pins, gap_pt)
    size = Counter(groups.values())
    return {pid: 'single' if size[head] == 1 else 'first' if pid == head else 'extra'
            for pid, head in groups.items()}


def page_package(pilot, number, profile=None):
    """Bu sayfanın işaretli cihazları, birleşimleri ve sayfa devamlarıyla aktarım paketi.

    Kaynak: kullanıcının işaretleri + çizimden çıkarılan ağlar. Uydurma yoktur:
    işaretlenmemiş cihaz pakete girmez; tanınmayan cihaz ailesi 'unmapped' kalır ve
    aktarımda reddedilir (sessizce atlanmaz).
    """
    from . import customer
    profile = profile or customer.load(getattr(pilot, 'customer', None))
    model = pilot.page_model(number)
    rel = pilot.relations(number)
    height = model['page']['height']
    objects, expected, issues = [], [], []
    marks = [n for n in model['nodes'] if n['kind'] == 'PIN']
    articles = _articles(pilot)
    label_data = _label_table(pilot, profile)
    if label_data['note']:
        issues.append(label_data['note'])
    if articles['unprepared_pages']:
        issues.append('Malzeme listesi sayfaları hazırlanmadı: %s — ürün kodu okunamadı.'
                      % ', '.join(str(n) for n in articles['unprepared_pages']))

    devices = {}
    for pin in marks:
        devices.setdefault(pin['device'], []).append(pin)
    node_of_pin, family_of_pin = {}, {}
    # Tel yönü (uç hangi yöne bakmalı) ve kutu rolü (yakın uçlar tek kutu) EPLAN tarafında
    # sembol varyantını ve sembolü seçer. Bkz. _wire_directions, _box_roles.
    directions = _wire_directions(rel)
    box_roles, box_groups, device_direction = {}, {}, {}
    for tag, pins in sorted(devices.items()):
        # Bir cihazın her KUTBU ayrı sembol yerleşimidir: 3 kutuplu sigorta = 3 tek kutuplu
        # sembol, klemens sırasının her ucu = ayrı klemens. Aynı cihaz adı hepsinde durur.
        columns = {}
        for pin in pins:
            columns.setdefault(round(pin['point'][0], 1), []).append(pin)
        letter = _letter(tag)
        for column in sorted(columns):
            unit = sorted(columns[column], key=lambda q: q['point'][1])
            family = _family(tag, [q['pin'] for q in unit], profile)
            if letter == 'X':
                unit_groups = [[q] for q in unit]          # her klemens ucu kendi nesnesi
            else:
                unit_groups = [unit]
            for group in unit_groups:
                names = [q['pin'] for q in group]
                family = _family(tag, names, profile)
                terminal = names[0] if family == 'terminal' else None
                suffix = ':' + terminal if terminal else ':%s' % '-'.join(names)
                oid = 'p%d:dev:%s%s' % (number, tag.split('-')[-1], suffix)
                # Aynı adlı iki uç (ör. klemens sırasında iki N24.30) ayrı nesnedir: kimlik çakışmaz.
                if any(q['id'] == oid for q in objects):
                    copy = 2
                    while any(q['id'] == '%s@%d' % (oid, copy) for q in objects):
                        copy += 1
                    oid = '%s@%d' % (oid, copy)
                entry = customer.symbol_of(profile, family) or {}
                if entry.get('group_gap_mm') and tag not in box_roles:
                    # Kutu birleştirme cihazın BÜTÜN uçlarına bakar: 1 ile 9 ayrı sütunda durur.
                    box_roles[tag] = _box_roles(pins, float(entry['group_gap_mm']) / PT_TO_MM)
                    box_groups[tag] = _box_groups(pins, float(entry['group_gap_mm']) / PT_TO_MM)
                if tag not in device_direction:
                    device_direction[tag] = _majority_direction(directions, pins)
                rows = []
                for index, pin in enumerate(group):
                    own = _direction_at(directions, pin['point'])
                    rows.append(dict(name=pin['pin'], index=index, point_pt=pin['point'],
                                     point_mm=_mm(pin['point'], height), source_id=pin['id'],
                                     method=pin.get('source_kind'),
                                     wire_direction=own or device_direction[tag],
                                     wire_direction_source=('EDGE' if own else
                                                            'DEVICE_MAJORITY' if device_direction[tag]
                                                            else None),
                                     box_role=box_roles.get(tag, {}).get(pin['id']),
                                     # Tek kutudaki uçlar EPLAN'da gruplanır (biri taşınınca öteki gelir).
                                     box_group=(box_groups.get(tag, {}).get(pin['id'])
                                                if box_roles.get(tag, {}).get(pin['id']) in ('first', 'extra')
                                                else None)))
                    # page_model düğüm kimliği 'pin:<id>' önekli, relations ise ham kimlik verir:
                    # ikisi de aynı düğüme çözülsün, yoksa cihazlar hiçbir hatta bağlı görünmez.
                    for key in {pin['id'], pin['id'].split('pin:', 1)[-1]}:
                        node_of_pin[key] = oid + '#' + pin['pin']
                        family_of_pin[key] = family
                # Ürün kodu ADAYLARI taşınır; hangisinin şema makrosu olduğu EPLAN parça
                # veritabanında belli olur. Kod bulunamazsa alan boş kalır, uydurulmaz.
                found = articles['devices'].get('-' + tag.split('-')[-1], {})
                candidates = [dict(type_number=number, manufacturer=row.get('manufacturer'),
                                   description=row.get('description'), source_page=row.get('page'))
                              for row in found.get('candidates', []) for number in row['type_numbers']]
                # Ürün kodu ÖNCE etiket listesinden (yapılandırılmış veri), sonra belgenin
                # malzeme listesinden (metin çıkarımı) gelir. İkisi de yoksa alan boş kalır.
                from . import labels as label_reader
                strategy = (profile.get('part_pick') or {}).get('strategy', 'first_qty_1')
                prefer = (profile.get('part_pick') or {}).get('prefer_prefix', {}).get(
                    customer.letter_of(tag))
                found_label = label_reader.for_device(label_data['table'], tag, strategy, prefer)
                objects.append(dict(id=oid, kind='DEVICE', family=family, device_tag=tag,
                                    terminal=terminal, pins=rows, part_candidates=candidates,
                                    part_number=(found_label['code'] if found_label else
                                                 candidates[0]['type_number'] if len(candidates) == 1 else None),
                                    part_source=('LABEL_LIST' if found_label else
                                                 'DOCUMENT_PARTS_LIST' if candidates else None),
                                    part_reason=found_label['reason'] if found_label else None,
                                    part_other_codes=found_label['other_codes'] if found_label else []))
                if family.startswith('unmapped'):
                    issues.append('%s (%s): cihaz ailesi eşlenmedi; aktarımda reddedilir.'
                                  % (tag, ', '.join(names)))

    for net in rel['networks']:
        members = [node_of_pin[q['id']] for q in net['pins'] if q['id'] in node_of_pin]
        # KULLANICI KURALI: adlı bir hat (PE, P24.30, N24.30 …) bu sayfada bir CİHAZA girmiyorsa
        # hattı, birleşimini ve sayfa devamını aktarma; klemens uçları zaten ayrı ayrı konuldu.
        # Sessiz atlama yok: gerekçe pakete yazılır.
        devices_on_net = [q for q in net['pins']
                          if family_of_pin.get(q['id']) not in (None, 'terminal')]
        if net['potential'] and not devices_on_net:
            issues.append('%s (%s): hat bu sayfada bir cihaza girmiyor; yalnız klemens(ler) '
                          'aktarıldı, hat çizilmedi.' % (net['id'], net['potential']))
            continue
        junctions = [j for j in net['junctions'] if j['evidence'] in ('DRAWN_DOT', 'T_GEOMETRY')]
        for index, junction in enumerate(junctions):
            jid = '%s:junction:%d' % (net['id'], index)
            objects.append(dict(id=jid, kind='JUNCTION', family='tnode_down',
                                evidence=junction['evidence'], point_pt=junction['point'],
                                point_mm=_mm(junction['point'], height)))
            members.append(jid)
        for end in net['continuations']:
            eid = '%s:end:%s' % (net['id'], end['reference'])
            objects.append(dict(id=eid, kind='INTERRUPTION', family='interruption',
                                name=net['potential'] or end.get('potential') or end['reference'],
                                reference=end['reference'], target_page=end.get('target_page'),
                                target_reference=end.get('target_reference'),
                                verified=bool(end.get('verified')), point_pt=end['point'],
                                point_mm=_mm(end['point'], height)))
            members.append(eid)
        for end in net['potential_anchors']:
            aid = '%s:pot:%s' % (net['id'], end['potential'])
            objects.append(dict(id=aid, kind='POTENTIAL_BOUNDARY', family='potential_definition',
                                name=end['potential'], point_pt=end['point'],
                                point_mm=_mm(end['point'], height)))
            members.append(aid)
        if len(members) < 2:
            continue
        points = {}
        for o in objects:
            if o['kind'] == 'DEVICE':
                points.update((o['id']+'#'+p['name'], p['point_pt']) for p in o['pins'])
            else:
                points[o['id']] = o['point_pt']
        links, route_issues = _drawn_links(net, {k: points[k] for k in members}, number, height)
        expected.extend(links)
        issues.extend(route_issues)
        if not net['potential']:
            issues.append('%s: hat adsız; potansiyel yazılmadı.' % net['id'])

    # Şablon yerleşimi: cihazlar UVP çerçevesinin taslak satırlarına oturur (bkz. layout.py).
    from . import layout
    template = layout.load(profile)
    placement = layout.apply(objects, expected, template, profile) if template else None
    if profile.get('template') and not template:
        issues.append('Şablon %s bulunamadı (output/sablon): nesneler kaynak koordinatında kaldı. '
                      'EPLAN\'da UvpSayfaDok.cs, sonra tools/sablon_cikar.py çalıştırılmalı.'
                      % profile['template'])
    if placement:
        if placement['issue']:
            issues.append('Şablon yerleşimi: %s' % placement['issue'])
        if placement['devices_without_row']:
            issues.append('Şablonda satırı olmayan cihaz yerinde kaldı: %s'
                          % ', '.join(placement['devices_without_row']))
        if placement['nodes_unresolved']:
            issues.append('Bağlı ucu çözülemeyen nokta yerinde kaldı: %s'
                          % ', '.join(placement['nodes_unresolved']))

    page = model['page']
    body = dict(contract='uvp.pdf2p8.import-request', contract_version='1.0',
                document_sha256=pilot.manifest.get('source_sha256'),
                page_model_contract='uvp.pdf2p8.page/1.0',
                coordinate=dict(source='pt, sol üst köken', target='mm, sol alt köken',
                                transform='x*25.4/72, (H-y)*25.4/72', calibrated=False),
                target_policy=dict(new_test_project_only=False, live_project_writes='USER_CHOICE',
                                   production_released=False),
                pages=[dict(physical_page=number, blatt=page['blatt'], anlage=page['anlage'],
                            einbauort=page['einbauort'],
                            source_size_pt=[page['width'], page['height']], objects=objects,
                            layout=placement)],
                expected_links=expected, issues=issues,
                limitation='Yalnız İŞARETLİ cihazlar pakete girer. Bağlar çizilmiş graf '
                           'yolunu korur; fiziksel tel/köprü kararı DEĞİLDİR. '
                           'EPLAN köşe/yön ve pin aralığı eşlemesi ayrıca doğrulanmalıdır.')
    _continuation_ids(body)
    raw = json.dumps(body, ensure_ascii=False, sort_keys=True).encode('utf-8')
    body['payload_sha256'] = hashlib.sha256(raw).hexdigest()
    return body


TOL_MM = 0.6


def document_package(pilot, pages=None, profile=None):
    """İşaretli sayfaların hepsini TEK pakete koy. Sayfa sırası korunur.

    Her sayfa kendi `page_package` çıktısıyla girer; bir sayfa paket üretemezse öteki
    sayfalar düşmez, o sayfa gerekçesiyle `failed_pages` altına yazılır — sessizce atlanmaz.
    """
    from . import customer
    profile = profile or customer.load(getattr(pilot, 'customer', None))
    if pages is None:
        pages = sorted({q.get('page', 4) for q in pilot.pins})
    out_pages, expected, issues, failed = [], [], [], []
    for number in pages:
        try:
            package = page_package(pilot, number, profile)
        except Exception as error:                      # noqa: BLE001 — sayfa düşer, sebebi yazılır
            failed.append(dict(page=number, error='%s: %s' % (type(error).__name__, error)))
            continue
        out_pages += package['pages']
        expected += package['expected_links']
        issues += ['sayfa %d: %s' % (number, text) for text in package['issues']]
    # Eşleme YALNIZ cihazlar için değildir: birleşim (tnode_down), kesinti noktası
    # (interruption) ve potansiyel sınırı da sembolle konur. Hepsi listeye girer, yoksa
    # aktarımda "eşleme yok" diye reddedilirler.
    families = sorted({o['family'] for page in out_pages for o in page['objects']})
    missing = [f for f in families if not customer.symbol_of(profile, f)]
    if missing:
        issues.append('Sembolü eşlenmemiş aile: %s — bu cihazlar aktarımda reddedilir.'
                      % ', '.join(missing))
    body = dict(contract='uvp.pdf2p8.import-request', contract_version='1.0',
                customer=profile.get('customer'),
                document_sha256=pilot.manifest.get('source_sha256'),
                limits=dict(writes_eplan=False, approved_for_production=False,
                            production_released=False),
                pages=out_pages, expected_links=expected, issues=issues,
                failed_pages=failed, families=families, families_without_symbol=missing,
                symbol_map={f: customer.symbol_of(profile, f) for f in families
                            if customer.symbol_of(profile, f)})
    _continuation_ids(body)
    raw = json.dumps(body, ensure_ascii=False, sort_keys=True).encode('utf-8')
    body['payload_sha256'] = hashlib.sha256(raw).hexdigest()
    return body


def _nodes(package):
    """Paket düğümleri: kimlik → (sayfa, mm konumu, beklenen EPLAN adı/pini)."""
    out = {}
    for page in package['pages']:
        n = page['physical_page']
        for o in page['objects']:
            if o['kind'] == 'DEVICE':
                name = o['device_tag'] + (':' + o['terminal'] if o['family'] == 'terminal' else '')
                for p in o['pins']:
                    out['%s#%s' % (o['id'], p['name'])] = dict(page=n, mm=p['point_mm'], function=name, pin=p['name'])
            else:
                out[o['id']] = dict(page=n, mm=o['point_mm'], kind=o['kind'], name=o.get('name'))
    return out


def compare(package, readback):
    """Geri okunan EPLAN topolojisini beklenenle karşılaştır.

    Her EPLAN bağlantı ucu KONUMUYLA paket düğümüne eşlenir (tolerans TOL_MM); cihaz uçlarında
    fonksiyon adı ve pin adı da ayrıca denetlenir. Beklenen her bağ FOUND/MISSING; beklenmeyen
    her bağ EXTRA (yanlış birleşme). Toplam sayı eşitliği tamlık değildir.
    """
    nodes = _nodes(package)

    def locate(page, end):
        loc = end.get('location')
        if (not isinstance(loc, (list, tuple)) or len(loc) != 2
                or any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in loc)):
            return None, 'UÇ KONUMU OKUNAMADI'
        hits = [k for k, v in nodes.items() if v['page'] == page
                and abs(v['mm'][0]-loc[0]) <= TOL_MM and abs(v['mm'][1]-loc[1]) <= TOL_MM]
        if len(hits) != 1:
            return None, 'KONUMDA %d PAKET DÜĞÜMÜ' % len(hits)
        node = nodes[hits[0]]
        if 'function' in node and (end.get('function'), end.get('pin')) != (node['function'], node['pin']):
            return hits[0], 'KİMLİK FARKI: EPLAN %s:%s, kaynak %s:%s' % (end.get('function'), end.get('pin'),
                                                                     node['function'], node['pin'])
        return hits[0], None

    seen, extra, issues, valid = set(), [], [], set()
    for c in readback.get('connections', []):
        page = c['physical_page']
        a, why_a = locate(page, c['start'])
        b, why_b = locate(page, c['end'])
        for why in (why_a, why_b):
            if why:
                issues.append(dict(page=page, connection=c, issue=why))
        if a and b:
            seen.add(frozenset((a, b)))
            if not why_a and not why_b:
                valid.add(frozenset((a, b)))
    expected = {frozenset((e['a'], e['b'])): e for e in package['expected_links']}
    found = [e for k, e in expected.items() if k in valid]
    missing = [e for k, e in expected.items() if k not in valid]
    extra = [sorted(k) for k in seen if k not in expected]
    # Konum sapması: kaynak nokta ile EPLAN'daki gerçek pin konumu.
    deviation, inventory_issues, inventoried = [], [], set()
    for page in readback.get('pages', []):
        for f in page.get('functions', []):
            for p in f.get('pins', []):
                endpoint = dict(location=p.get('location'), function=f.get('name'), pin=p.get('name'))
                key, why = locate(page['physical_page'], endpoint)
                if key and 'function' in nodes[key] and not why:
                    if key in inventoried:
                        inventory_issues.append(dict(node=key, issue='MÜKERRER GERİ OKUNAN PIN'))
                    inventoried.add(key)
                    src = nodes[key]
                    dx, dy = p['location'][0]-src['mm'][0], p['location'][1]-src['mm'][1]
                    deviation.append(dict(page=page['physical_page'], function=f.get('name'), pin=p.get('name'),
                                          dx_mm=round(dx, 3), dy_mm=round(dy, 3)))
                elif p.get('name'):
                    inventory_issues.append(dict(page=page['physical_page'], function=f.get('name'),
                                                 pin=p.get('name'), issue=why or 'BEKLENMEYEN PIN'))
    for key, src in nodes.items():
        if 'function' in src and key not in inventoried:
            inventory_issues.append(dict(node=key, issue='PIN ENVANTERDE DOĞRULANAMADI'))
    evidence_issues = []
    for field in ('document_sha256', 'package_sha256'):
        wanted = package.get('payload_sha256' if field == 'package_sha256' else field)
        if not wanted or readback.get(field) != wanted:
            evidence_issues.append('GERİ OKUMA KAYNAĞI EŞLEŞMEDİ: ' + field)
    if readback.get('contract') != 'uvp.pdf2p8.readback' or readback.get('contract_version') != '1.0':
        evidence_issues.append('GERİ OKUMA SÖZLEŞMESİ DOĞRULANAMADI')
    # Yerel çizgi uçları ile sayfalar arası elektriksel eşleşme ayrı kanıtlardır.
    # Mevcut host yalnız kesinti adını/metnini okur; gerçek partner nesne kimliği okumaz.
    # Bu kanıt gelene kadar iki sayfayı ayrı ayrı doğru çizmek S03'ü tamamlamaz.
    has_continuations = any(o['kind'] == 'INTERRUPTION' for pg in package['pages'] for o in pg['objects'])
    if has_continuations:
        evidence_issues.append('SAYFA DEVAMI PARTNER KİMLİĞİ GERİ OKUNMADI')
    if not expected:
        evidence_issues.append('BEKLENEN BAĞLANTI YOK: BOŞ PAKET BAŞARI SAYILMAZ')
    if readback.get('import_ok') is not True:
        evidence_issues.append('HOST YERLEŞTİRME İŞLEMİ DOĞRULANMADI')
    ips = sorted((ip['page'], ip['name']) for ip in readback.get('interruption_points', []))
    return dict(contract='uvp.pdf2p8.diff', contract_version='1.0',
                expected=len(expected), found=len(found), missing=missing, extra=extra,
                endpoint_issues=issues, pin_deviation=deviation, interruption_points=ips,
                inventory_issues=inventory_issues, evidence_issues=evidence_issues,
                local_geometry_complete=bool(expected) and not (missing or extra or issues),
                identity_complete=not inventory_issues,
                verification_scope='DECLARED_LOCAL_LINKS_AND_PIN_INVENTORY',
                complete=not (missing or extra or issues or inventory_issues or evidence_issues))


def main():
    from .service import Pilot
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', type=Path, default=Path(__file__).resolve().parents[1]/'output/pilots/E122/20260910_v3_p05_rev8')
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--readback', type=Path, help='EPLAN readback.json: pakete karşı diff.json yazar')
    args = ap.parse_args()
    if args.readback:
        package = json.loads(args.out.read_text(encoding='utf-8'))
        diff = compare(package, json.loads(args.readback.read_text(encoding='utf-8-sig')))
        target = args.readback.with_name('diff.json')
        target.write_text(json.dumps(diff, ensure_ascii=False, indent=1), encoding='utf-8')
        print('diff:', target, 'beklenen', diff['expected'], 'bulunan', diff['found'],
              'eksik', len(diff['missing']), 'fazla', len(diff['extra']), 'tam', diff['complete'])
        return
    package = proof_package(Pilot(args.run))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(package, ensure_ascii=False, indent=1), encoding='utf-8')
    print('paket:', args.out, 'nesne:', sum(len(p['objects']) for p in package['pages']),
          'beklenen bağ:', len(package['expected_links']), 'sorun:', package['issues'])


if __name__ == '__main__':
    main()
