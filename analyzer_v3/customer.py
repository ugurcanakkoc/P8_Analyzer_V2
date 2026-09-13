"""Müşteri profili: cihaz ailesi kuralları ve EPLAN sembol eşlemesi.

Neden: semboller ve çizim alışkanlıkları müşteriden müşteriye değişir. Aile kuralı kodun
içinde sabit durursa her yeni müşteri kod değişikliği ister. Bu yüzden kurallar VERİDİR:
`output/musteri/<ad>/profil.json`.

İki bölüm var:
  rules    — cihaz harfi + uç adlarından AİLE çıkarır (sıra önemlidir, ilk uyan kazanır).
  families — aile → EPLAN sembolü. Sembolü olmayan aile aktarımda REDDEDİLİR, uydurulmaz.

Profil yoksa yerleşik varsayılan kullanılır; bu, bugüne kadarki davranışın aynısıdır.
"""
from functools import lru_cache
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
HOME = ROOT / 'output' / 'musteri'
DEFAULT = 'troester'
# Müşteri adı dosya yoludur: dışarıdan gelir (arayüz/istek gövdesi). Harf, rakam, tire ve
# alt çizgiden başkası kabul edilmez; yoksa '../' ile profil klasörünün dışına çıkılır.
NAME = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]{0,39}$')
PATTERN_MAX = 120          # profil dosyasındaki düzenli ifade sınırı

# Yerleşik kurallar: bugün kodda sabit olan davranış. Müşteri profili bunları genişletir
# veya değiştirir; hiçbiri "her müşteride böyledir" diye sunulmaz.
BUILTIN_RULES = [
    dict(family='fuse_1pole', letter='F'),
    dict(family='terminal', letter='X'),
    dict(family='coil', pins=['A1', 'A2']),
    dict(family='contact_no', pin_count=2, digit_ends=[['3', '4'], ['1', '4']]),
    dict(family='contact_nc', pin_count=2, digit_ends=[['1', '2']]),
]


def profiles():
    """Kurulu müşteri profilleri (klasör adları)."""
    if not HOME.exists():
        return []
    return sorted(p.name for p in HOME.iterdir() if (p / 'profil.json').exists())


def valid_name(name):
    """Müşteri adı. Geçersizse hata verilir; sessizce varsayılana düşülmez."""
    name = (name or DEFAULT).strip()
    if not NAME.match(name):
        raise ValueError('Geçersiz müşteri adı: %r (harf, rakam, - ve _ kullanın).' % name)
    return name


def path_of(name):
    name = valid_name(name)
    file = (HOME / name / 'profil.json').resolve()
    if HOME.resolve() not in file.parents:
        raise ValueError('Müşteri profili yalnız %s altında olabilir.' % HOME)
    return file


def load(name=None):
    """Profili oku. Yoksa yerleşik varsayılanla, boş sembol eşlemesiyle döner."""
    name = valid_name(name)
    file = path_of(name)
    if not file.exists():
        return dict(customer=name, source=None, rules=list(BUILTIN_RULES), families={},
                    note='Profil dosyası yok; yerleşik aile kuralları kullanıldı, sembol eşlemesi boş.')
    data = json.loads(file.read_text(encoding='utf-8'))
    rules = data.get('rules')
    return dict(customer=data.get('customer', name), source=str(file),
                rules=list(rules) if rules else list(BUILTIN_RULES),
                families=data.get('families') or {},
                note=data.get('note', ''),
                # İsteğe bağlı: şablon yerleşimi (layout.py) ve ürün kodu seçimi okur.
                template=data.get('template'),
                plc_io_by_part=data.get('plc_io_by_part') or {},
                part_pick=data.get('part_pick') or {})


def save(name, rules, families, note=''):
    name = valid_name(name)
    file = path_of(name)
    file.parent.mkdir(parents=True, exist_ok=True)
    # Dosyadaki öteki alanlar (şablon, PLC türü, ürün kodu seçimi) korunur; yalnız verilenler yazılır.
    data = json.loads(file.read_text(encoding='utf-8')) if file.exists() else {}
    data.update(contract='uvp.pdf2p8.customer-profile', contract_version='1.0',
                customer=name, rules=rules, families=families, note=note)
    file.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')
    return file


def letter_of(device_tag):
    for ch in str(device_tag).split('-')[-1]:
        if ch.isalpha():
            return ch.upper()
    return '?'


def _matches(rule, letter, names):
    if rule.get('letter') and rule['letter'].upper() != letter:
        return False
    if rule.get('letter_in') and letter not in [v.upper() for v in rule['letter_in']]:
        return False
    if rule.get('pins') is not None and [str(v).upper() for v in rule['pins']] != names:
        return False
    if rule.get('pin_set') is not None and set(str(v).upper() for v in rule['pin_set']) != set(names):
        return False
    if rule.get('pin_count') is not None and len(names) != int(rule['pin_count']):
        return False
    if rule.get('pin_pattern') is not None:
        source = str(rule['pin_pattern'])
        if len(source) > PATTERN_MAX:
            raise ValueError('Kural deseni çok uzun (%d karakter).' % len(source))
        pattern = _compiled(source)
        if not all(pattern.match(n) for n in names):
            return False
    if rule.get('digit_ends') is not None:
        if len(names) != 2 or not all(n.isdigit() for n in names):
            return False
        ends = (names[0][-1], names[1][-1])
        pairs = {tuple(pair) for pair in rule['digit_ends']}
        if ends not in pairs and ends[::-1] not in pairs:
            return False
    return True


@lru_cache(maxsize=256)
def _compiled(source):
    return re.compile(source)


def family_of(profile, device_tag, pin_names):
    """Cihaz ailesi. Hiçbir kural uymazsa UYDURULMAZ: 'unmapped:<harf>/<uçlar>' döner."""
    letter = letter_of(device_tag)
    names = [str(n).strip().upper() for n in pin_names]
    for rule in profile.get('rules') or BUILTIN_RULES:
        if _matches(rule, letter, names):
            return rule['family']
    return 'unmapped:%s/%s' % (letter, ','.join(names) or '?')


def symbol_of(profile, family):
    """Ailenin EPLAN sembolü. Eşlenmemişse None — aktarım bunu reddeder."""
    entry = (profile.get('families') or {}).get(family)
    if not entry or not entry.get('symbol'):
        return None
    return entry
