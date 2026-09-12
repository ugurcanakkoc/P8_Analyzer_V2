"""Uç adı normalizasyonu ve eşleştirme.

Müşteri şemasında uç `1 2 3`, makroda `L1 L2 L3` olabiliyor; ya da `13/1` ↔ `13`,
`3.13` ↔ `13`, `L1intern` ↔ `L1`. Bunlar aynı uçtur, farklı yazılmıştır.

Motor `pin kontrol` projesinden (edz_audit/pin_diff.py) alındı: orada EDZ paketlerinde
2D/3D pin farklarını ayıklamak için yazılmış ve 9 ajanlı bir doğrulama turundan geçmişti.
KORUNAN kural: kesme işareti (`2` ≠ `2'`) ve büyük/küçük harf (`K` ≠ `k`) GERÇEK farktır,
normalize edilmez — primer/sekonder sargı ayrımı buna dayanır.
"""
import re

PHASE = re.compile(r'^(\d+)L\d+$', re.IGNORECASE)      # 1L1 → 1
PREFIX = re.compile(r'^\d+\.(\d+)$')                    # 3.13 → 13


def split_names(value):
    """EPLAN bir alana birden çok uç adını satır sonuyla paketler: böl."""
    return [token.strip() for token in re.split(r'[\r\n]+', value or '') if token.strip()]


def variants(name):
    """Bir uç adının eşdeğer yazımları. Kesme işareti ve harf büyüklüğü korunur."""
    name = (name or '').strip()
    if not name:
        return set()
    out = {name}
    if name.lower().endswith('intern') and len(name) > 6:
        out.add(name[:-6])
    if '/' in name:
        base = name.split('/')[0]
        if base:
            out.add(base)
    phase = PHASE.match(name)
    if phase:
        out.add(phase.group(1))
    prefix = PREFIX.match(name)
    if prefix:
        out.add(prefix.group(1))
    return out


def loose(name):
    """Büyük-küçük ve ayırıcı (. / - boşluk) yok sayılır; karakter sırası korunur.

    Kesme işareti KORUNUR: `2` ile `2'` ayrı terminaldir (primer/sekonder). Kaynak
    projede gevşek karşılaştırma kesme işaretini de siliyordu; test bunu yakaladı.
    """
    return re.sub(r"[^0-9a-z']", '', (name or '').lower())


def match(name, pool):
    """`name` için havuzdaki karşılık: birebir → gevşek → varyant. Yoksa None.

    Dönüş `(karşılık, nasıl)` — hangi yolla eşleştiği kayda geçsin diye.
    """
    if name in pool:
        return name, 'birebir'
    key = loose(name)
    for other in pool:
        if loose(other) == key:
            return other, 'gevşek (ayırıcı/harf farkı)'
    mine = variants(name)
    for other in pool:
        if variants(other) & mine:
            return other, 'varyant (faz/ön ek/eğik çizgi)'
    return None, None


def suggest_by_order(source_pins, macro_pins):
    """Sıraya göre eşleştirme ÖNERİSİ — kabul değil, öneri.

    Müşteri `1 2 3` yazarken makro `L1 L2 L3` diyor olabilir; bunlar ad olarak
    birbirini tutmaz ve otomatik eşleştirmek UYDURMAK olur. Uç sayısı aynıysa sıraya
    göre bir öneri çıkarılır; kullanıcı onaylayınca eşleme tablosuna (müşteri profili)
    yazılır ve bir daha sorulmaz.
    """
    if len(source_pins) != len(macro_pins) or not source_pins:
        return []
    return [dict(source=a, macro=b, how='sıraya göre ÖNERİ — onay gerekir')
            for a, b in zip(source_pins, macro_pins)]


def compare(source_pins, macro_pins, aliases=None):
    """Kaynak (müşteri) uçları ile makro uçlarını karşılaştır.

    Hiçbir uç sessizce atılmaz: eşleşen, eşleşmeyen ve makroda fazla olanlar ayrı ayrı
    listelenir. Karar vermez — eşleşmeyene ne yapılacağını kullanıcı söyler.
    """
    pool = list(macro_pins)
    aliases = aliases or {}
    matched, missing = [], []
    used = set()
    for name in source_pins:
        free = [p for p in pool if p not in used]
        wanted = aliases.get(name)
        if wanted is not None and wanted in free:
            used.add(wanted)
            matched.append(dict(source=name, macro=wanted, how='eşleme tablosu (onaylı)'))
            continue
        found, how = match(name, free)
        if found is None:
            missing.append(name)
            continue
        used.add(found)
        matched.append(dict(source=name, macro=found, how=how))
    extra = [p for p in pool if p not in used]
    return dict(matched=matched, unmatched_source=missing, unused_macro=extra,
                fits=not missing and not extra,
                suggestions=suggest_by_order(missing, extra))
