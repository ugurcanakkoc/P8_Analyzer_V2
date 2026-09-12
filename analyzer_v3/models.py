"""Identity and evidence contracts; no name guessing or production approval."""
from dataclasses import dataclass
import math
import re

STATUSES = {"CONFIRMED_BOTH", "VECTOR_ONLY", "VISUAL_ONLY", "CONFLICT", "UNRESOLVED"}
PROVENANCE = {"UNKNOWN", "EXPLICIT_WIRE_LABEL", "EXPLICIT_PAGE_DEFAULT", "BOM_REFERENCE", "ELECTRICAL_RULE"}
FUNCTIONS = {"112", "122", "132", "152", "170"}


def normalized(value: str) -> str:
    return "".join(value.split()).upper()


def address_context(device: str):
    match = re.fullmatch(r"=([^+]+)\+([^-]+)-(.+)", normalized(device))
    return match.groups() if match else None


PARTIAL_DEVICE = re.compile(r"^(?:=([^+\-]+))?(?:\+([^\-]+))?-(.+)$")


def device_parts(device: str):
    """Adres parcalari: (anlage, ort, tag). Yazilmamis parca None doner, UYDURULMAZ."""
    match = PARTIAL_DEVICE.fullmatch(normalized(device))
    if not match:
        return None
    return match.group(1), match.group(2), match.group(3)


def device_tail(device: str):
    """Cihaz kuyrugu: `=112-17K53`, `+E122-17K53` ve `-17K53` ayni kuyrugu verir."""
    parts = device_parts(device)
    return parts[2] if parts else None


def in_scope(device: str) -> bool:
    parts = address_context(device)
    return bool(parts and parts[0] in FUNCTIONS and parts[1] == "E122")


# Uygulama türü, ilişki teyidinden ve üretime uygunluktan AYRI bir boyuttur (MAIN 2026-09-08 §1).
# Bir bağlantının doğru olduğunu bilmek, nasıl imal edildiğini bilmek DEĞİLDİR.
IMPLEMENTATION_TYPES = {"TEL", "AKSESUAR_KOPRU", "CIHAZ_ICI", "BELIRSIZ"}


def endpoint_scope(device: str, pin: str) -> str:
    """Bir ucun pano kapsamındaki durumu. Üç değer, ikisi değil.

    IN_SCOPE          — fonksiyon ve Einbauort okunuyor ve kapsam içinde, pin adı var.
    OUT_OF_PANEL      — adres okunuyor ama başka pano/saha (örn. +M113 saha cihazı).
    SCOPE_UNCERTAIN   — adres tam okunamıyor ya da pin adı yok; kapsam KARARI VERİLEMEZ.

    Belirsiz, "kapsam içi" ile aynı kovaya konmaz: MAIN.md tahmin yasağı.
    """
    if not str(device).strip() or not str(pin).strip():
        return "SCOPE_UNCERTAIN"
    parts = address_context(device)
    if not parts:
        return "SCOPE_UNCERTAIN"
    return "IN_SCOPE" if (parts[0] in FUNCTIONS and parts[1] == "E122") else "OUT_OF_PANEL"


def pair_scope(states) -> str:
    """İki ucun birleşik kapsam durumu. Pano içi tel adayı YALNIZ ikisi de kapsam içiyse olur."""
    states = list(states)
    if all(x == "IN_SCOPE" for x in states) and states:
        return "IN_SCOPE_BOTH"
    if any(x == "SCOPE_UNCERTAIN" for x in states):
        return "SCOPE_UNCERTAIN"
    return "OUT_OF_PANEL_END"


@dataclass(frozen=True)
class Endpoint:
    device: str
    pin: str

    @property
    def key(self):
        # No splitting/trimming of terminal suffixes. Unknowns are NOT keys.
        if not self.device.strip() or not self.pin.strip():
            return None
        return normalized(self.device), normalized(self.pin)


# AGENT_DRAFT: gelistirme calismasinda ajanin ornek olarak koydugu isaret. Insan isareti
# (MANUAL) ve programin bulgusu (P04_CANDIDATE) ile AYNI KOVAYA konmaz.
MARK_METHODS = {"MANUAL", "P04_CANDIDATE", "AGENT_DRAFT"}


def validate_page(data, pages):
    """A mark belongs to exactly one traced sheet; an untraced page is refused, not guessed."""
    page = data.get("page", 4)
    if isinstance(page, bool) or not isinstance(page, int) or page not in pages:
        raise ValueError("Bu çalışmada izlenmeyen sayfa: " + str(data.get("page")))
    return page, pages[page]


def validate_point(point, size):
    if not isinstance(point, list) or len(point) != 2 or any(
            type(v) not in (int, float) or not math.isfinite(v) for v in point):
        raise ValueError("Geçerli iki koordinat gerekli.")
    if not (0 <= point[0] <= size[0] and 0 <= point[1] <= size[1]):
        raise ValueError("Nokta sayfanın dışında.")


def validate_pin(data, pages):
    if not isinstance(data, dict):
        raise ValueError("Pin kaydı nesne olmalı.")
    for name in ("device", "pin", "note"):
        if not isinstance(data.get(name, ""), str) or len(data.get(name, "")) > 300:
            raise ValueError("Geçersiz pin yazısı.")
    page, size = validate_page(data, pages)
    validate_point(data.get("point"), size)
    if data.get("kind") not in ("PHYSICAL", "NETWORK"):
        raise ValueError("Pin türü PHYSICAL veya NETWORK olmalı.")
    method = data.get("method", "MANUAL")
    if method not in MARK_METHODS:
        raise ValueError("İşaretleme yöntemi bilinmiyor.")
    # Geri alınan işaret SİLİNMEZ: `active=False` ile pasifleşir, kaydı ve olay geçmişi durur.
    active = data.get("active", True)
    if not isinstance(active, bool):
        raise ValueError("İşaret durumu doğru/yanlış olmalı.")
    # The method is recorded for effort measurement; it never turns a proposal into a confirmation.
    return dict({k: data.get(k, "") for k in ("device", "pin", "point", "kind", "note")},
                page=page, method=method, active=active)


REVIEW_DECISIONS = {"CONFIRMED", "REJECTED", "NEEDS_MORE_EVIDENCE"}
REVIEW_SUBJECTS = {"PIN", "PIN_PAIR", "CONTINUATION", "CLAIM", "DASH_RUN",
                   "IMPLEMENTATION_TYPE"}
REVIEW_SOURCES = {"UI_REVIEW", "CHAT_APPROVAL_TRANSCRIBED"}


def validate_review(data):
    """A recorded human decision. It stores WHAT was reviewed and at WHICH pin versions."""
    if not isinstance(data, dict):
        raise ValueError("İnceleme kaydı nesne olmalı.")
    if data.get("subject") not in REVIEW_SUBJECTS:
        raise ValueError("İnceleme konusu bilinmiyor.")
    if data.get("decision") not in REVIEW_DECISIONS:
        raise ValueError("İnceleme kararı bilinmiyor.")
    if data.get("source", "UI_REVIEW") not in REVIEW_SOURCES:
        raise ValueError("İnceleme kaynağı bilinmiyor.")
    reviewer = data.get("reviewer", "")
    if not isinstance(reviewer, str) or not reviewer.strip() or len(reviewer) > 200:
        raise ValueError("İnceleyen adı zorunlu.")
    for name in ("note", "reference"):
        if not isinstance(data.get(name, ""), str) or len(data.get(name, "")) > 600:
            raise ValueError("Geçersiz inceleme metni.")
    pins = data.get("pin_ids", [])
    if not isinstance(pins, list) or not all(isinstance(p, str) and 0 < len(p) <= 100 for p in pins):
        raise ValueError("İncelenen pin kimlikleri geçersiz.")
    if data["subject"] in ("PIN", "PIN_PAIR") and not pins:
        raise ValueError("Bu inceleme en az bir pin ister.")
    run_key = data.get("run_key", "")
    if not isinstance(run_key, str) or len(run_key) > 100:
        raise ValueError("Koşu kimliği geçersiz.")
    if data["subject"] == "DASH_RUN" and not run_key.strip():
        raise ValueError("Kesikli hat incelemesi koşu kimliği ister.")
    implementation = data.get("implementation", "")
    if data["subject"] == "IMPLEMENTATION_TYPE":
        if implementation not in IMPLEMENTATION_TYPES:
            raise ValueError("Uygulama türü bilinmiyor: TEL / AKSESUAR_KOPRU / CIHAZ_ICI / BELIRSIZ.")
        if not (data.get("reference") or "").strip():
            raise ValueError("Uygulama türü kaydı bağlantı referansı ister.")
    elif implementation and implementation not in IMPLEMENTATION_TYPES:
        raise ValueError("Uygulama türü bilinmiyor.")
    return dict(subject=data["subject"], decision=data["decision"], reviewer=reviewer.strip(),
                source=data.get("source", "UI_REVIEW"), note=data.get("note", ""),
                reference=data.get("reference", ""), pin_ids=pins,
                run_key=run_key.strip(), implementation=implementation)


def validate_box(data, pages):
    """A symbol mask the user drew: its interior is excluded from line tracing."""
    if not isinstance(data, dict):
        raise ValueError("Kutu kaydı nesne olmalı.")
    page, size = validate_page(data, pages)
    box = data.get("bbox")
    if not isinstance(box, list) or len(box) != 4:
        raise ValueError("Kutu dört koordinat ister.")
    validate_point(box[:2], size)
    validate_point(box[2:], size)
    if not (box[2] - box[0] > 0.5 and box[3] - box[1] > 0.5):
        raise ValueError("Kutu çok küçük.")
    if not isinstance(data.get("note", ""), str) or len(data.get("note", "")) > 300:
        raise ValueError("Geçersiz kutu notu.")
    if not isinstance(data.get("active", True), bool):
        raise ValueError("Kutu durumu doğru/yanlış olmalı.")
    # Kullanıcının sembol dışı saydığı çizim parçaları. Parça SİLİNMEZ; yalnız bu kutunun
    # şekline girmez ve neyin dışarıda bırakıldığı kayıtta durur.
    excluded = data.get("excluded_objects") or []
    if not isinstance(excluded, list) or len(excluded) > 200:
        raise ValueError("Çıkarılan parça listesi geçersiz.")
    for item in excluded:
        if not isinstance(item, str) or not (0 < len(item) <= 60):
            raise ValueError("Çıkarılan parça kimliği geçersiz: %r" % (item,))
    # A retired mask is kept as a record and only switched off: nothing is deleted.
    return dict(bbox=[round(v, 4) for v in box], page=page, note=data.get("note", ""),
                active=data.get("active", True), source="MANUAL_VISUAL_MASK",
                excluded_objects=sorted(set(excluded)))


def validate_evidence_row(row):
    if row["status"] not in STATUSES:
        raise ValueError("Unknown evidence status")
    if row["status"] == "CONFIRMED_BOTH" and not (row.get("vector_evidence") and row.get("visual_evidence")):
        raise ValueError("Both independent evidence references are required")
    if row.get("review_status") == "APPROVED" and not row.get("reviewer"):
        raise ValueError("Approval requires named reviewer")
    for attr in ("cross_section", "wire_color"):
        provenance = row.get(attr + "_provenance", "UNKNOWN")
        if provenance not in PROVENANCE or bool(row.get(attr)) == (provenance == "UNKNOWN"):
            raise ValueError("Attribute/provenance mismatch")
    if row.get("production_ready"):
        raise ValueError("Production export is not implemented in this pilot")


def pair_key(a, b):
    if a.key is None or b.key is None:
        raise ValueError("Unknown endpoints cannot be deduplicated by name")
    return tuple(sorted((a.key, b.key)))
