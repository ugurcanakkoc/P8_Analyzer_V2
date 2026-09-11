"""Cross-page facts: page identity, cross-references, device occurrences.

Nothing here produces a wire. A cross-reference is a drawing pointer, not a conductor:
a contact/coil reference never becomes a wire continuation, and the page's own Anlage
never overwrites a device's printed function. Unresolvable or ambiguous targets stay
recorded as issues instead of being guessed away.
"""
import re

from .models import FUNCTIONS, normalized

LOCATION = "E122"

# =Anlage(+Ort)/Blatt.Position — the position part is kept raw: it is NOT a pin, column or terminal.
XREF = re.compile(r"^(?:=(?P<anlage>[0-9A-Z]+))?(?:\+(?P<ort>[0-9A-Z]+))?/(?P<blatt>\d+)\.(?P<position>\d+)$")
DEVICE = re.compile(r"^(?:=(?P<anlage>[0-9A-Z]+))?(?:\+(?P<ort>[0-9A-Z]+))?-(?P<tag>[0-9A-Z][0-9A-Z.:]*)$")
# A location printed under a device tag overrides the page location for that device only.
LOCAL_LOCATION = re.compile(r"^\+(?P<ort>[0-9A-Z]{2,})$")


def word_box(word):
    return [round(word["x0"], 2), round(word["top"], 2), round(word["x1"], 2), round(word["bottom"], 2)]


def title_block(words):
    """Read Anlage/Einbauort/Blatt/document type from their printed labels, not from fixed coordinates."""
    facts = {"anlage": None, "einbauort": None, "blatt": None, "doc_type": None, "issues": []}
    label = next((w for w in words if "Einbauort" in w["text"]), None)
    if label is None:
        facts["issues"].append("TITLE_BLOCK_EINBAUORT_LABEL_MISSING")
    else:
        row = [w for w in words if abs(w["top"] - (label["top"] + 10)) <= 6]
        anlage = [w for w in row if w["text"].startswith("=") and w["x0"] < label["x0"]]
        ort = [w for w in row if w["text"].startswith("+") and w["x0"] >= label["x0"] - 6]
        if len(anlage) == 1:
            facts["anlage"] = anlage[0]["text"][1:]
        else:
            facts["issues"].append("TITLE_BLOCK_ANLAGE_UNREADABLE")
        if len(ort) == 1:
            facts["einbauort"] = ort[0]["text"][1:]
            facts["einbauort_box"] = word_box(ort[0])
        else:
            facts["issues"].append("TITLE_BLOCK_EINBAUORT_UNREADABLE")
    blatt = next((w for w in words if w["text"] == "Blatt"), None)
    if blatt is None:
        facts["issues"].append("TITLE_BLOCK_BLATT_LABEL_MISSING")
    else:
        right = [w for w in words if abs(w["top"] - blatt["top"]) <= 4 and w["x0"] > blatt["x1"]
                 and w["text"].isdigit()]
        if right:
            facts["blatt"] = min(right, key=lambda w: w["x0"])["text"]
        else:
            facts["issues"].append("TITLE_BLOCK_BLATT_VALUE_MISSING")
    kommission = next((w for w in words if "Kommission" in w["text"]), None)
    if kommission is None:
        facts["issues"].append("TITLE_BLOCK_DOCTYPE_ANCHOR_MISSING")
    else:
        right = [w for w in words if abs(w["top"] - kommission["top"]) <= 4 and w["x0"] > kommission["x1"]]
        if right:
            facts["doc_type"] = min(right, key=lambda w: w["x0"])["text"]
        else:
            facts["issues"].append("TITLE_BLOCK_DOCTYPE_MISSING")
    return facts


def page_scope(facts):
    """Function AND mounting location must both match; =-number alone is never enough."""
    if facts["anlage"] is None or facts["einbauort"] is None:
        return "UNKNOWN"
    if normalized(facts["einbauort"]) != LOCATION:
        return "OUT_OF_SCOPE_LOCATION"
    return "IN_SCOPE" if facts["anlage"] in FUNCTIONS else "OUT_OF_SCOPE_FUNCTION"


def word_facts(word, pattern):
    match = pattern.match(word["text"])
    if not match:
        return None
    row = dict(text=word["text"], box=word_box(word), rotated=bool(word.get("rotated")), **match.groupdict())
    if row["rotated"]:
        row.update(raw_text=word.get("raw_text", word["text"]), rotation=word.get("rotation", "UNKNOWN"))
    return row


def assign_local_locations(facts, words):
    """A `+Ort` printed directly under a device tag belongs to that device, not to the page.

    An unassignable marker never falls back to the page location: every device on that page is
    marked uncertain instead, so a field device cannot be reported as panel-internal.
    """
    own = facts.get("einbauort_box")
    # Only the drawing area counts: the title block's own description fields ("Schaltschrank +E122")
    # are not location markers. Without a readable title block every marker stays in play.
    limit = own[1] - 20 if own else float("inf")
    markers = [w for w in words if LOCAL_LOCATION.match(w["text"]) and word_box(w) != own
               and w["top"] < limit]
    boxes = {id(d): d for d in facts["devices"]}
    unassigned = []
    for marker in markers:
        box = word_box(marker)
        above = [d for d in facts["devices"]
                 if 6 <= box[1] - d["box"][1] <= 26 and not (d["box"][2] < box[0] - 6 or d["box"][0] > box[2] + 6)]
        if len(above) == 1:
            boxes[id(above[0])]["local_location"] = LOCAL_LOCATION.match(marker["text"]).group("ort")
            boxes[id(above[0])]["local_location_box"] = box
        else:
            unassigned.append(dict(text=marker["text"], box=box, devices_above=len(above)))
    facts["local_location_markers"] = [d["local_location"] for d in facts["devices"] if d.get("local_location")]
    facts["unassigned_location_markers"] = unassigned
    if unassigned:
        facts["issues"].append("LOCAL_LOCATION_MARKER_UNASSIGNED")
        for d in facts["devices"]:
            d.setdefault("location_uncertain", True)
    return facts


def page_facts(number, words):
    facts = title_block(words)
    rotated = [w for w in words if w.get("rotated")]
    facts.update(physical_page=number, word_count=len(words), rotated_words=len(rotated),
                 undecided_rotation=[w.get("raw_text", w["text"]) for w in rotated
                                     if w.get("rotation") == "UNKNOWN"])
    facts["scope"] = page_scope(facts)
    facts["cross_references"] = [r for r in (word_facts(w, XREF) for w in words) if r]
    facts["devices"] = [r for r in (word_facts(w, DEVICE) for w in words) if r]
    assign_local_locations(facts, words)
    if facts["undecided_rotation"]:
        facts["issues"].append("ROTATED_TEXT_ORDER_UNDECIDED")
    return facts


def build_index(pages_words):
    return [page_facts(i + 1, words) for i, words in enumerate(pages_words)]


def full_device_name(device, page):
    """A printed =function wins over the page's Anlage; a bare tag inherits, and says so."""
    # EPLAN inherits each missing address part from the page independently: a printed =112 on a
    # =122 page keeps function 112, while the unprinted location still comes from the page.
    # A location printed under the device (e.g. +M113 for a field device) wins over the page.
    anlage = device.get("anlage") or page.get("anlage")
    local = device.get("local_location")
    ort = device.get("ort") or local or page.get("einbauort")
    inherited = ["anlage"] if device.get("anlage") is None else []
    if device.get("ort") is None and local is None:
        inherited.append("ort")
    name = ("=" + anlage if anlage else "") + ("+" + ort if ort else "") + "-" + device["tag"]
    return name, inherited


def resolve_target(reference, source_page, index):
    """(Anlage, Blatt) inside the same document type. Several hits stay ambiguous, never picked."""
    anlage = reference.get("anlage") or source_page.get("anlage")
    if anlage is None or source_page.get("doc_type") is None:
        return dict(status="SOURCE_PAGE_IDENTITY_UNKNOWN", target_pages=[], anlage=anlage)
    hits = [p["physical_page"] for p in index
            if p["anlage"] == anlage and p["blatt"] == reference["blatt"]
            and p["doc_type"] == source_page["doc_type"]
            and (reference.get("ort") is None or p["einbauort"] == reference["ort"])]
    status = ("TARGET_PAGE_NOT_FOUND" if not hits else
              "RESOLVED" if len(hits) == 1 else "AMBIGUOUS_TARGET_PAGE")
    return dict(status=status, target_pages=hits, anlage=anlage, blatt=reference["blatt"],
                position_token=reference["position"],
                position_note="Pozisyon ham metindir; pin, klemens veya sütun olarak yorumlanmaz.")


def nearest_device(reference, page, radius=22.0):
    """The device this reference is printed under, only when one is unmistakably closest."""
    x = (reference["box"][0] + reference["box"][2]) / 2
    ranked = sorted(((abs((d["box"][0]+d["box"][2])/2 - x) + abs(d["box"][1] - reference["box"][1]), d)
                     for d in page["devices"]), key=lambda pair: pair[0])
    close = [pair for pair in ranked if pair[0] <= radius]
    if not close:
        return None
    if len(close) == 1 or close[0][0] * 2 <= close[1][0]:
        return close[0][1]
    return None  # Two equally plausible owners: no guess.


def classify_reference(reference, source_page, index, pages_by_number):
    """Contact/coil pointer vs potential continuation. Neither is a wire."""
    resolved = resolve_target(reference, source_page, index)
    owner = nearest_device(reference, source_page)
    row = dict(reference, **resolved, source_page=source_page["physical_page"],
               relation="CROSS_REFERENCE_ONLY_NOT_A_WIRE", production_ready=False, issues=[])
    if owner is None:
        row.update(kind="LINE_CONTINUATION_CANDIDATE", owner_device=None,
                   note="Bir cihaza bağlanamayan referans; hat devamı adayı olarak izlenir, tel üretilmez.")
    else:
        name, inherited = full_device_name(owner, source_page)
        row.update(kind="DEVICE_CROSS_REFERENCE", owner_device=name, owner_text=owner["text"],
                   inherited_address_parts=inherited,
                   note="Kontak/bobin çapraz referansı; aynı cihazın başka sayfadaki sembolü, tel devamı değil.")
        if inherited:
            row["issues"].append("DEVICE_ADDRESS_PART_INHERITED_FROM_PAGE")
    if resolved["status"] != "RESOLVED":
        row["issues"].append(resolved["status"])
        return row
    target = pages_by_number[resolved["target_pages"][0]]
    if row["kind"] == "DEVICE_CROSS_REFERENCE":
        matches = [d for d in target["devices"]
                   if full_device_name(d, target)[0] == row["owner_device"]]
        if matches:
            row.update(target_device_texts=sorted({d["text"] for d in matches}),
                       target_device_boxes=[d["box"] for d in matches])
        else:
            row["issues"].append("DEVICE_NOT_FOUND_ON_TARGET_PAGE")
            # The page's own Anlage differs; report it instead of renaming the device.
            local = [d for d in target["devices"] if d["tag"] == owner["tag"]]
            if local:
                row["issues"].append("TARGET_PAGE_DEVICE_ADDRESS_DIFFERS")
                row["target_device_texts"] = sorted({d["text"] for d in local})
    if target["scope"] != "IN_SCOPE":
        row["issues"].append("TARGET_PAGE_" + target["scope"])
    return row


def references_for_page(number, index):
    pages = {p["physical_page"]: p for p in index}
    page = pages[number]
    return [classify_reference(r, page, index, pages) for r in page["cross_references"]]


# Bir potansiyel adı, ölçüm/ürün yazısından AYRILIR. Kesit, renk, birim, güç, gerilim aralığı
# ve kablo damar harfi bir potansiyel adı DEĞİLDİR; bunları sinyal gibi kullanmak MAIN.md'nin
# "siyah çizgi gördüğün için BK yazma" ve tahmin yasağı hükümlerine aykırıdır.
POTENTIAL = re.compile(r"^(?:PE|PEN|N|L[123]|[PN]\d{1,3}(?:\.\d{1,3})?)$", re.IGNORECASE)
MEASUREMENT = re.compile(
    r"(?:mm²|mm2|kW|kVA|VDC|VAC|AWG|Cu|Al)\b"          # birim / malzeme
    r"|^\d+\s*[xX]\s*\d"                              # 4x2,5 gibi kablo yapısı
    r"|^\d+[,.]\d+$"                                    # 0,75 / 2,5 gibi ölçü
    r"|^\d+\s*-\s*\d+$"                                # 10-32 gibi aralık
    r"|^\d+\s*(?:A|V|W|Hz)$",                            # 16 A, 24 V
    re.IGNORECASE)
CABLE_CORE = re.compile(r"^[UVWLN]$|^PE[0-9]*$", re.IGNORECASE)


def classify_label(text):
    """Bir uç yazısının TÜRÜ. Tanınmayan yazı SİLİNMEZ, belirsiz olarak döner."""
    value = (text or "").strip()
    if not value:
        return "EMPTY"
    if XREF.match(value):
        return "SHEET_REFERENCE"
    if DEVICE.match(value) or LOCAL_LOCATION.match(value):
        return "DEVICE_TAG"
    if MEASUREMENT.search(value):
        return "MEASUREMENT_OR_UNIT"
    if POTENTIAL.match(value):
        return "POTENTIAL"
    if CABLE_CORE.match(value):
        # U/V/W tek harfi kablo damarıdır; PE ise yukarıdaki POTENTIAL dalında yakalanır.
        return "CABLE_CORE"
    if value.replace(".", "").replace(",", "").isdigit():
        return "BARE_NUMBER"
    return "UNRECOGNISED"


def signal_labels(words, point, dx=120.0, dy=8.0, kinds=("POTENTIAL",)):
    """Texts printed at a wire end, CLASSIFIED. Nothing is invented and nothing is deleted.

    Varsayılan olarak yalnız POTENTIAL döner. Tanınmayan yazılar `classify_label` ile
    `UNRECOGNISED` etiketini alır ve çağıran isterse `kinds` ile talep eder; hiçbir durumda
    sessizce potansiyel adı sayılmazlar.
    """
    out = []
    for w in words:
        centre = ((w["x0"]+w["x1"])/2, (w["top"]+w["bottom"])/2)
        if abs(centre[0]-point[0]) > dx or abs(centre[1]-point[1]) > dy:
            continue
        kind = classify_label(w["text"])
        if kinds is not None and kind not in kinds:
            continue
        out.append(dict(text=w["text"], kind=kind, box=word_box(w),
                        distance=round(abs(centre[0]-point[0]) + abs(centre[1]-point[1]), 2)))
    return sorted(out, key=lambda r: r["distance"])


STRIP = re.compile(r"^-[0-9A-Z][0-9A-Z.]*$")


def strip_labels(words, render_bbox):
    """Sayfadaki klemens çubuğu etiketleri: `-X4.Q`, `-X1`, `-X4.I` gibi."""
    out = []
    for w in words:
        text = w["text"].strip()
        if not STRIP.match(normalized(text)):
            continue
        out.append(dict(text=text,
                        x0=w["x0"]-render_bbox[0], x1=w["x1"]-render_bbox[0],
                        top=w["top"]-render_bbox[1], bottom=w["bottom"]-render_bbox[1]))
    return sorted(out, key=lambda r: (r["top"], r["x0"]))


def strip_owner(labels, point, band=14.0):
    """Bu klemensin çubuk adı hangisi? Kanıt: aynı satır bandı + etiketin SAĞINDA olmak.

    Etiket bir kez yazılır ve kendi grubunu adlandırır. Bir sonraki çubuk etiketi yeni grubu
    başlatır; ad komşu gruba TAŞMAZ. Etiketin solunda kalan klemensin sahibi yoktur ve
    `None` döner: ad uydurulmaz.
    """
    x, y = point
    row = [q for q in labels if q["top"]-band <= y <= q["bottom"]+band]
    if not row:
        return None, "NO_STRIP_LABEL_IN_ROW"
    left = [q for q in row if q["x1"] <= x]
    if not left:
        return None, "TERMINAL_LEFT_OF_FIRST_STRIP_LABEL"
    owner = max(left, key=lambda q: q["x1"])
    later = [q for q in row if owner["x1"] < q["x0"] <= x]
    if later:                      # araya başka bir çubuk etiketi girmiş
        return None, "ANOTHER_STRIP_LABEL_BETWEEN"
    return owner["text"], "STRIP_LABEL_OWNERSHIP"


# --- PLC modülü: cihaz adının kendi pinlerine bağlanması ---------------------------------
#
# Klemens çubuğu yatay dizilir ve adı solunda bir kez yazılır (`strip_owner`). PLC modülü
# BÖYLE ÇİZİLMEZ: gövdesi tek bir uzun yatay çizgidir, pinler o çizgiye dik kısa uçlarla
# oturur, modül adı çizginin ÜSTÜNDEKİ başlık bloğunda bir kez yazılır. Bu yüzden satır
# bandı kuralı burada çalışmaz ve ayrı bir sahiplik kuralı gerekir.
MODULE_EPS = 0.1
MODULE_STUB_MAX = 12.0      # ölçülen pin ucu: 7,1 pt (sayfa 28/36, y 206,5 → 213,6)
MODULE_MIN_STUBS = 3        # tek bir dik çizgi modül yapmaz
MODULE_NAME_GAP = 6.0       # ölçülen pin adı uzaklığı: 1,1–1,2 pt
MODULE_NAME_BAND = 12.0     # pin adı çubuğun hemen üstündeki bantta basılır
MODULE_MARK_BAND = (8.0, 45.0)   # pin tanımı (`DO`, `DQ-M0`) çubuğun bu kadar üstünde
MODULE_MARK_TOL = 3.0       # tanım yazısının x merkezi pin ucuyla örtüşmeli


def _h(segment):
    return abs(segment["a"][1]-segment["b"][1]) < MODULE_EPS


def _v(segment):
    return abs(segment["a"][0]-segment["b"][0]) < MODULE_EPS


def _len(segment):
    return max(abs(segment["a"][0]-segment["b"][0]), abs(segment["a"][1]-segment["b"][1]))


def module_bars(segments, min_stubs=MODULE_MIN_STUBS):
    """Modül gövdesi: kendisine dik KISA uçlarla oturulmuş uzun yatay çizgi.

    Kanıt çizimin kendisidir: uzunluk eşiği değil, çizgiye oturan uç sayısı belirler.
    Başlık bloğunun altındaki uzun çizgilerde böyle uç yoktur; ölçüldü: sayfa 28 ve 36'da
    tam bir çubuk (y=213,6, x 86,0→1049,8, 28 uç), sayfa 2/4/5'te sıfır.
    """
    out = []
    for bar in segments:
        if not _h(bar) or _len(bar) < MODULE_STUB_MAX*4:
            continue
        y = bar["a"][1]
        x0, x1 = sorted((bar["a"][0], bar["b"][0]))
        above, below = [], []
        for s in segments:
            if not _v(s) or _len(s) > MODULE_STUB_MAX or _len(s) <= MODULE_EPS:
                continue
            if not (x0-MODULE_EPS <= s["a"][0] <= x1+MODULE_EPS):
                continue
            ys = sorted((s["a"][1], s["b"][1]))
            if abs(ys[1]-y) < MODULE_EPS:
                above.append(s["a"][0])
            elif abs(ys[0]-y) < MODULE_EPS:
                below.append(s["a"][0])
        for side, stubs in (("ABOVE", above), ("BELOW", below)):
            if len(set(stubs)) >= min_stubs:
                out.append(dict(id=bar["id"], y=y, x0=x0, x1=x1, side=side,
                                stubs=sorted({round(x, 2) for x in stubs})))
    return out


def module_header(bar, segments):
    """Başlık bandı: çubuğun üstü, üstteki ilk KAPSAYICI yatay çizgiye kadar; solda bandı
    kesen ilk dikey çizgiye kadar. Sınırlar çizimden okunur, sabit pay verilmez."""
    y, x0, x1 = bar["y"], bar["x0"], bar["x1"]
    tops = [s["a"][1] for s in segments if _h(s) and s["a"][1] < y-MODULE_EPS
            and min(s["a"][0], s["b"][0]) <= x0+MODULE_EPS and max(s["a"][0], s["b"][0]) >= x1-MODULE_EPS]
    if not tops:
        return None
    top = max(tops)
    lefts = [s["a"][0] for s in segments if _v(s) and s["a"][0] < x0-MODULE_EPS
             and min(s["a"][1], s["b"][1]) <= top+MODULE_EPS and max(s["a"][1], s["b"][1]) >= y-MODULE_EPS]
    return (max(lefts) if lefts else x0, top, x1, y)


def module_owner(bar, segments, words, render_bbox):
    """Bu modülün cihaz adı. Başlıkta TEK bir cihaz yazısı varsa sahiplik kurulur.

    Birden çok yazı varsa ad UYDURULMAZ: komşu modülün adını taşımaktansa çözümsüz kalır.
    """
    band = module_header(bar, segments)
    if band is None:
        return None, "NO_MODULE_HEADER_BAND", None, []
    hits = []
    for w in words:
        if classify_label(w["text"]) != "DEVICE_TAG":
            continue
        box = (w["x0"]-render_bbox[0], w["top"]-render_bbox[1],
               w["x1"]-render_bbox[0], w["bottom"]-render_bbox[1])
        if band[0] <= box[0] and box[2] <= band[2] and band[1] <= box[1] and box[3] <= band[3]:
            hits.append(w["text"])
    if not hits:
        return None, "NO_DEVICE_TAG_IN_MODULE_HEADER", band, []
    if len(hits) > 1:
        return None, "AMBIGUOUS_MODULE_HEADER_TAGS", band, hits
    return hits[0], "MODULE_HEADER_OWNERSHIP", band, hits


def module_pin_name(bar, stub_x, words, render_bbox):
    """Pin adı: çubuğun hemen üstünde, ucun SAĞINDA duran ilk düz yazı.

    Ölçülen uzaklık 1,1–1,2 pt'dir. Yazısı olmayan uç adlandırılmaz; `L+`, `M` ve `1..16`
    aynı kuralla okunur, hiçbiri şablondan kopyalanmaz.
    """
    best = None
    for w in words:
        if w.get("rotated"):
            continue
        x0, top = w["x0"]-render_bbox[0], w["top"]-render_bbox[1]
        bottom = w["bottom"]-render_bbox[1]
        if not (bar["y"]-MODULE_NAME_BAND <= (top+bottom)/2 <= bar["y"]):
            continue
        d = x0-stub_x
        if not (0 <= d <= MODULE_NAME_GAP):
            continue
        if best is None or d < best[0]:
            best = (d, w["text"])
    return None if best is None else best[1]


def module_pin_mark(bar, stub_x, words, render_bbox):
    """Pin TANIMI: ucun üstünde, aynı eksende basılı döndürülmüş yazı (`DO`, `DI`, `DQ-M0`).

    DO ile DI aynı şekilde çizilir; ayrımın kanıtı bu yazıdır, şekil değildir.
    """
    lo, hi = MODULE_MARK_BAND
    best = None
    for w in words:
        if not w.get("rotated"):
            continue
        cx = (w["x0"]+w["x1"])/2 - render_bbox[0]
        cy = (w["top"]+w["bottom"])/2 - render_bbox[1]
        if abs(cx-stub_x) > MODULE_MARK_TOL:
            continue
        d = bar["y"]-cy
        if not (lo <= d <= hi):
            continue
        if best is None or d < best[0]:
            best = (d, w["text"])
    return None if best is None else best[1]


def occurrences(device_name, index, doc_types=None):
    """Every page printing this device, with the exact printed text kept as evidence.

    All document types are searched by default: a device printed only on a parts list is
    still printed. Each row carries its own doc_type so the caller can separate them.
    """
    rows = []
    for page in index:
        if doc_types is not None and page["doc_type"] not in doc_types:
            continue
        for d in page["devices"]:
            name, inherited = full_device_name(d, page)
            if name == device_name:
                rows.append(dict(physical_page=page["physical_page"], text=d["text"], box=d["box"],
                                 inherited_address_parts=inherited, doc_type=page["doc_type"],
                                 scope=page["scope"], local_location=d.get("local_location"),
                                 location_uncertain=bool(d.get("location_uncertain"))))
    return rows


def terminal_table(index, doc_types=("Schaltplan",)):
    """Terminal strips seen per page. Built from evidence; this PDF has no Klemmenplan document."""
    table = {}
    for page in index:
        if page["doc_type"] not in doc_types or page["scope"] != "IN_SCOPE":
            continue
        for d in page["devices"]:
            if not re.fullmatch(r"X[0-9]+", d["tag"].split(":")[0].split(".")[0]):
                continue
            name, _ = full_device_name(d, page)
            table.setdefault(name, []).append(dict(physical_page=page["physical_page"], text=d["text"],
                                                   box=d["box"]))
    return table


def split_pin(printed, device):
    """Split the PRINTED name against the requested device, not at the last ':'.

    Pin names may themselves contain ':' (e.g. -4D27:X1:P1), so splitting from the right
    would move part of the pin into the device name and lose the record.
    """
    if printed == device:
        return device, None
    if printed.startswith(device + ":"):
        return device, printed[len(device) + 1:]
    head, separator, tail = printed.rpartition(":")
    return (head, tail) if separator else (printed, None)


def reconcile_endpoint(device, pin, index, doc_types=None):
    """Where this exact device+pin is printed. Same name on several sheets is not one point."""
    device, pin = normalized(device), normalized(pin)
    exact, other = [], []
    for page in index:
        if doc_types is not None and page["doc_type"] not in doc_types:
            continue
        for d in page["devices"]:
            name, inherited = full_device_name(d, page)
            base, printed_pin = split_pin(normalized(name), device)
            if base != device:
                continue
            row = dict(physical_page=page["physical_page"], text=d["text"], box=d["box"],
                       printed_pin=printed_pin, inherited_address_parts=inherited, scope=page["scope"],
                       doc_type=page["doc_type"], rotated=d.get("rotated", False),
                       local_location=d.get("local_location"),
                       location_uncertain=bool(d.get("location_uncertain")))
            (exact if printed_pin == pin else other).append(row)
    status = ("DEVICE_NOT_PRINTED_ON_ANY_PAGE" if not exact and not other else
              "EXACT_PIN_PRINTED" if exact else "DEVICE_PRINTED_PIN_NOT_PRINTED")
    pages = {r["physical_page"] for r in exact}
    return dict(device=device, pin=pin, status=status, exact=exact, other_occurrences=other,
                multiple_drawing_locations=len(exact) > 1,
                pages=sorted(pages), out_of_scope_pages=sorted({r["physical_page"] for r in exact + other
                                                               if r["scope"] != "IN_SCOPE"}),
                searched_doc_types=sorted({p["doc_type"] for p in index if p["doc_type"]}) if doc_types is None
                else sorted(doc_types),
                doc_types_found=sorted({r["doc_type"] for r in exact + other if r["doc_type"]}),
                note="Aynı ad birden fazla çizim konumunda olabilir; ad eşleşmesi fiziksel tel onayı değildir. "
                     "Pin metni yalnız cihaz yazısında ':' ile basılmışsa görülür; klemens sırasındaki ayrı "
                     "rakamlar burada aranmaz. Şema dışı belge türlerinde (ör. Stückliste) bulunan kayıtlar "
                     "cihazın basılı olduğunu gösterir, bağlantı göstermez.",
                production_ready=False)
