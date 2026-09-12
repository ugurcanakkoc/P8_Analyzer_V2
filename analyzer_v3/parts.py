"""Ürün kodları: belgenin KENDİ malzeme listesi (Stückliste) sayfalarından okunur.

Şema sayfasında ürün kodu yazmaz; kodlar ayrı liste sayfalarındadır. Burada yapılan tek şey
o satırları okumaktır: cihaz etiketi, üretici, tip numarası, açıklama. Hiçbir kod uydurulmaz,
eşleşmeyen satır atılmaz — nedeniyle birlikte döner.

Bir cihazın birden çok satırı olur (sigorta + paşa vidası + sigorta yuvası). Hangisinin şema
makrosu olduğu BURADA seçilmez; aday listesi olduğu gibi taşınır, seçim EPLAN parça
veritabanında makrosu olan ilk adaya göre yapılır.
"""
import re

# Satırdaki üretici adı çapadır: tip numarası onun hemen yanındadır.
MANUFACTURERS = {'SIEMENS', 'RITTAL', 'PHOENIX', 'WEIDMÜLLER', 'WEIDMUELLER', 'WAGO', 'SCHNEIDER',
                 'ABB', 'EATON', 'MURR', 'MURRELEKTRONIK', 'PILZ', 'FINDER', 'LAPP', 'HARTING',
                 'TURCK', 'IFM', 'BALLUFF', 'SICK', 'FESTO', 'SMC', 'HELUKABEL', 'LÜTZE', 'LUETZE'}
DEVICE = re.compile(r'^-[0-9A-Za-zÄÖÜäöü]+[0-9A-Za-zÄÖÜäöü.]*$')
# Tip numarası: en az bir rakam ve bir harf, 5+ karakter (5SE2316, 3RH2122-1BB40, SV9340.950).
TYPE_NUMBER = re.compile(r'^(?=.*[0-9])(?=.*[A-Za-z])[0-9A-Za-z][0-9A-Za-z./-]{4,}$')
INTERNAL = re.compile(r'^\d{5,7}$')           # firma iç numarası: tip numarası değildir
PAGE_REF = re.compile(r'^=?\d*[/.]\d')        # =112/4.22 gibi sayfa göndermesi


def _rows(words, band=3.0):
    """Okuma sırasına göre satırlara böl. Aynı bant içindeki kelimeler bir satırdır."""
    out, current, last = [], [], None
    for word in sorted(words, key=lambda w: (round(w['top']/band), w['x0'])):
        key = round(word['top']/band)
        if last is not None and key != last and current:
            out.append(current)
            current = []
        current.append(word)
        last = key
    if current:
        out.append(current)
    return out


def page_articles(words):
    """Bir malzeme listesi sayfasındaki satırlar: cihaz → ürün kodu adayları.

    Tablo hücresi birden çok satıra taşabilir: cihaz satırından sonra gelen, cihazı olmayan
    satırlardaki tip numarası/üretici aynı cihaza eklenir (en çok iki satır ileriye bakılır).
    """
    found = []
    pending = []
    for row in _rows(words):
        texts = [w['text'].strip() for w in row if w['text'].strip()]
        devices = [t for t in texts if DEVICE.match(t) and not PAGE_REF.match(t)]
        if not devices:
            # Taşan hücre: en son cihaz satırına ait olabilir.
            extra = [t for t in texts if TYPE_NUMBER.match(t) and not INTERNAL.match(t)
                     and not PAGE_REF.match(t)]
            maker = next((t for t in texts if t.upper().strip('.,') in MANUFACTURERS), None)
            for entry in pending:
                for number in extra:
                    if number not in entry['type_numbers']:
                        entry['type_numbers'].append(number)
                if entry['type_numbers']:
                    entry['issue'] = None
                if maker and not entry['manufacturer']:
                    entry['manufacturer'] = maker
            continue
        maker = next((t for t in texts if t.upper().strip('.,') in MANUFACTURERS), None)
        candidates = [t for t in texts
                      if TYPE_NUMBER.match(t) and not INTERNAL.match(t) and not PAGE_REF.match(t)
                      and t != maker and t not in devices]
        if maker:
            # Üreticinin hemen solundaki aday en güçlüsüdür; kalanlar sırayı korur.
            index = texts.index(maker)
            candidates.sort(key=lambda t: abs(texts.index(t) - index))
        description = next((t for t in texts if t.isalpha() and len(t) > 3 and t != maker), '')
        pending = []
        for device in devices:
            entry = dict(device=device, manufacturer=maker, description=description,
                         type_numbers=candidates,
                         issue=None if candidates else 'TIP_NUMARASI_OKUNAMADI',
                         row=' '.join(texts)[:160])
            found.append(entry)
            pending.append(entry)
    return found


def document_articles(pilot, pages=None):
    """Belgedeki malzeme listesi sayfalarını tara. Hazırlanmamış sayfa taranmaz ve söylenir."""
    index = {row['physical_page']: row for row in pilot._index()}
    viewable = pilot.viewable_pages()
    wanted = [n for n, row in sorted(index.items())
              if (pages is None and 'ckliste' in (row.get('doc_type') or ''))
              or (pages is not None and n in pages)]
    devices, scanned, skipped = {}, [], []
    for number in wanted:
        if number not in viewable:
            skipped.append(number)
            continue
        scanned.append(number)
        for row in page_articles(pilot._page(number)['words']):
            entry = devices.setdefault(row['device'], dict(device=row['device'], candidates=[]))
            entry['candidates'].append(dict(type_numbers=row['type_numbers'],
                                            manufacturer=row['manufacturer'],
                                            description=row['description'], page=number,
                                            issue=row['issue'], row=row['row']))
    return dict(devices=devices, scanned_pages=scanned, unprepared_pages=skipped,
                note='Ürün kodları belgenin kendi malzeme listesinden okundu. Bir cihazın birden '
                     'çok satırı olabilir (gövde, yuva, vida); şema makrosu olan aday EPLAN parça '
                     'veritabanında seçilir. Hazırlanmamış liste sayfası taranmadı.')
