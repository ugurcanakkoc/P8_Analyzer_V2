"""Similar-symbol candidates from ONE confirmed example. Proposals, never approvals.

A candidate is accepted only when the drawn core geometry matches 1:1 under pure
translation. Labels are re-read from this instance's own page words; template text is
never copied into a candidate. NO/NC blade differences and mirrored/rotated instances
therefore fail to match and stay visible as rejected reports instead of silent drops.
"""
from .geometry import EPS, PIN_ATTACH, axis, projection, pt
from .models import address_context, device_tail, normalized

TOL = 0.05          # drawn-geometry match tolerance in PDF points
LABEL_TOL = 2.0     # word must repeat at the same relative offset
CONTEXT_RADIUS = 45.0
MEMBER_RADIUS = 6.0    # a template owns only the pins on its own symbol, not the neighbour's
MARKED_TOL = 1.0    # an existing annotation this close is the same physical spot


def clip(segment, box):
    """Portion of an axis-parallel segment inside box, or None. Raw data is not modified."""
    orient = axis(segment)
    if orient is None:
        a, b = segment["a"], segment["b"]
        inside = [box[0]-EPS <= p[0] <= box[2]+EPS and box[1]-EPS <= p[1] <= box[3]+EPS for p in (a, b)]
        # Diagonals are kept whole or dropped whole: partial diagonal clipping is not implemented.
        return dict(segment, a=pt(a), b=pt(b)) if all(inside) else None
    d, f = (0, 1) if orient == "h" else (1, 0)
    low, high = (box[0], box[2]) if d == 0 else (box[1], box[3])
    flow, fhigh = (box[1], box[3]) if d == 0 else (box[0], box[2])
    if not (flow - EPS <= segment["a"][f] <= fhigh + EPS):
        return None
    a, b = sorted([segment["a"], segment["b"]], key=lambda p: p[d])
    lo, hi = max(a[d], low), min(b[d], high)
    if hi - lo <= EPS:
        return None
    p, q = list(a), list(a)
    p[d], q[d] = lo, hi
    return dict(segment, a=pt(p), b=pt(q))


def canonical(segment):
    """Endpoint order in the PDF is arbitrary; sort so mirrored shapes stay distinguishable."""
    return tuple(sorted((pt(segment["a"]), pt(segment["b"]))))


def curve_inside(curve, box):
    """Curves are matched as whole shapes: terminals and fuse bodies are drawn with them."""
    x0, y0, x1, y1 = curve["bbox"]
    return box[0]-EPS <= x0 and x1 <= box[2]+EPS and box[1]-EPS <= y0 and y1 <= box[3]+EPS


def curve_shape(curve):
    """Point path relative to the curve's first point. A shared bounding box is NOT a shared shape.

    A curve without a point list keeps only its box; such a match is reported as unverified
    instead of being accepted silently.
    """
    points = curve.get("points") or []
    if not points:
        x0, y0, x1, y1 = curve["bbox"]
        return ("BBOX_ONLY", round(x1-x0, 2), round(y1-y0, 2)), False
    first = points[0]
    return tuple((round(p[0]-first[0], 2), round(p[1]-first[1], 2)) for p in points), True


def signature(segments, box, origin, curves=()):
    rows, unverified = [], []
    for s in segments:
        piece = clip(s, box)
        if piece is None:
            continue
        (ax, ay), (bx, by) = canonical(piece)
        rows.append(("line", round(ax-origin[0], 2), round(ay-origin[1], 2),
                     round(bx-origin[0], 2), round(by-origin[1], 2), bool(s.get("dash"))))
    for c in curves:
        if not curve_inside(c, box):
            continue
        shape, verified = curve_shape(c)
        if not verified:
            unverified.append(c["id"])
        x0, y0, x1, y1 = c["bbox"]
        rows.append(("curve", round(x0-origin[0], 2), round(y0-origin[1], 2), shape, bool(c.get("fill"))))
    members = [s for s in segments if clip(s, box) is not None]
    members += [c for c in curves if curve_inside(c, box)]
    return sorted(rows, key=repr), members, unverified


def shifted(box, dx, dy):
    return [box[0]+dx, box[1]+dy, box[2]+dx, box[3]+dy]


def word_point(word, render_bbox):
    return (round((word["x0"]+word["x1"])/2 - render_bbox[0], 4),
            round((word["top"]+word["bottom"])/2 - render_bbox[1], 4))


def word_box_at(word, render_bbox):
    return (round(word["x0"]-render_bbox[0], 4), round(word["top"]-render_bbox[1], 4),
            round(word["x1"]-render_bbox[0], 4), round(word["bottom"]-render_bbox[1], 4))


def words_at(words, render_bbox, point, tol=LABEL_TOL):
    """Beklenen noktadaki yazı. Uzun/döndürülmüş etiketler için KUTU da sınanır.

    Kısa yatay etiketlerde merkez testi yeterlidir. Ama klemens adları döndürülmüş basıldığında
    (örn. `X3:15`, `N24.30`) yazı 18–29 pt uzar; merkezi beklenen noktadan uzağa düşer ve
    yalnız merkeze bakan bir test onları KAÇIRIR. Bu yüzden beklenen nokta yazının kendi
    kutusunun içindeyse de eşleşme sayılır. Gevşetme yalnız yazının kendi uzunluğu kadardır.
    """
    out = []
    for w in words:
        centre = word_point(w, render_bbox)
        if abs(centre[0]-point[0]) <= tol and abs(centre[1]-point[1]) <= tol:
            out.append(w)
            continue
        box = word_box_at(w, render_bbox)
        # Kutu testi YALNIZ döndürülmüş (enden uzun) etiketler içindir. Yatay bir cihaz yazısı
        # geniş olduğu için pin noktasını kutusuna alır ve pin adı sanılırdı; o yüzden yatay
        # yazılarda sıkı merkez testi korunur.
        if (box[3]-box[1]) <= (box[2]-box[0]):
            continue
        if (box[0]-tol <= point[0] <= box[2]+tol) and (box[1]-tol <= point[1] <= box[3]+tol):
            out.append(w)
    return out


def nearest_word(words, render_bbox, point, radius, others=(), reach=0.0, lateral=4.0):
    """Bu noktanın kendi yazısı. Başka bir işaretli uca daha yakın yazı ONUN etiketidir.

    `others` verilirse sahiplik sınanır: aynı sayfadaki diğer işaretli uçlardan birine bu
    noktadan daha yakın duran yazı atlanır. Böylece bitişik klemens dizilerinde bir sembol
    komşusunun adını kendi adı sanmaz.

    `reach` verilirse kare pencerenin dışına, YALNIZ bir eksen boyunca bakılır: uç adı
    telin uzandığı yönde biraz uzağa basılmış olabilir, ama yana kaymaz. Ölçüm (sayfa 38,
    PLC modülü `-27D22`): kanal adı `1` uçtan yanal 2.6 pt, boyuna 12.05 pt uzakta; 11 pt'lik
    kare pencere onu kaçırıyordu. Yana açılmadığı için komşu kanalın adı çalınmaz.
    """
    best = None
    for w in words:
        wp = word_point(w, render_bbox)
        dx, dy = abs(wp[0]-point[0]), abs(wp[1]-point[1])
        d = max(dx, dy)
        if d > radius and not (reach and ((dx <= lateral and dy <= reach)
                                          or (dy <= lateral and dx <= reach))):
            continue
        if any(max(abs(wp[0]-o[0]), abs(wp[1]-o[1])) < d for o in others):
            continue                      # yazının sahibi başka bir uç
        if best is None or d < best[0]:
            best = (d, w, wp)
    return best


def attached(segments, point, box=None):
    """Drawn lines that actually reach this point, ignoring the symbol's own interior."""
    ids = set()
    for s in segments:
        if box is not None and clip(s, box) is not None:
            continue
        if axis(s) and projection(point, s["a"], s["b"])[1] <= PIN_ATTACH:
            ids.add(s["id"])
    return sorted(ids)


def template(box, pins, segments, words, render_bbox, label_radius=11.0, curves=()):
    """Describe one user-marked instance: core geometry plus the label offsets it actually has."""
    origin = (box["bbox"][0], box["bbox"][1])
    core, raw, unverified = signature(segments, box["bbox"], origin, curves)
    if not core:
        raise ValueError("Şablon kutusunda çizim yok; benzer arama yapılamaz.")
    members = []
    for p in pins:
        x, y = p["point"]
        if box["bbox"][0]-MEMBER_RADIUS <= x <= box["bbox"][2]+MEMBER_RADIUS and \
           box["bbox"][1]-MEMBER_RADIUS <= y <= box["bbox"][3]+MEMBER_RADIUS:
            rivals = [tuple(q["point"]) for q in pins
                      if tuple(q["point"]) != (x, y)]
            hit = nearest_word(words, render_bbox, (x, y), label_radius, others=rivals)
            members.append(dict(pin_id=p["id"], device=p["device"], pin=p["pin"], kind=p["kind"],
                                offset=(round(x-origin[0], 4), round(y-origin[1], 4)),
                                pin_label_offset=None if hit is None else
                                (round(hit[2][0]-origin[0], 4), round(hit[2][1]-origin[1], 4)),
                                pin_label_text=None if hit is None else hit[1]["text"],
                                external_lines=len(attached(segments, (x, y), box["bbox"]))))
    # The device word is located from the template's OWN device name, never from proximity alone.
    names = {p["device"] for p in members if p["device"].strip()}
    tails = {t for t in (device_tail(n) for n in names) if t}
    device_word, device_issue = None, None
    if len(tails) != 1:
        device_issue = "TEMPLATE_DEVICE_AMBIGUOUS" if tails else "TEMPLATE_DEVICE_UNKNOWN"
    else:
        tail = next(iter(tails))
        hits = [(max(abs(word_point(w, render_bbox)[0]-origin[0]), abs(word_point(w, render_bbox)[1]-origin[1])), w)
                for w in words if device_tail(w["text"]) == tail]
        hits = [h for h in hits if h[0] <= CONTEXT_RADIUS]
        if not hits:
            device_issue = "TEMPLATE_DEVICE_WORD_NOT_ON_PAGE"
        else:
            device_word = min(hits, key=lambda h: h[0])[1]
    return dict(box_id=box["id"], bbox=box["bbox"], origin=origin, core=core, core_segments=raw,
                unverified_curves=unverified, pins=members, device_issue=device_issue,
                device_label_text=None if device_word is None else device_word["text"],
                device_label_offset=None if device_word is None else
                (round(word_point(device_word, render_bbox)[0]-origin[0], 4),
                 round(word_point(device_word, render_bbox)[1]-origin[1], 4)))


def anchor_of(member):
    """Anchor point and shape key of one core object: a line's vector or a curve's point path."""
    if "bbox" in member:
        shape, _ = curve_shape(member)
        first = (member.get("points") or [member["bbox"][:2]])[0]
        return (round(first[0], 4), round(first[1], 4)), shape, "curve"
    (ax, ay), (bx, by) = canonical(member)
    return (ax, ay), (round(bx-ax, 4), round(by-ay, 4)), "line"


def deep_tuple(value):
    """JSON turns tuples into lists; compare shapes on one normalised form."""
    return tuple(deep_tuple(v) for v in value) if isinstance(value, (list, tuple)) else value


def same_shape(a, b, tol=TOL):
    """Point paths (or the bbox-only fallback) match within drawing tolerance, not by luck.

    Length must match too: a circle and a rectangle in the same box have different paths, and a
    scaled or rotated copy fails here instead of being accepted silently.
    """
    a, b = deep_tuple(a), deep_tuple(b)
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        if isinstance(x, tuple) != isinstance(y, tuple):
            return False
        if isinstance(x, tuple):
            if not same_shape(x, y, tol):
                return False
        elif isinstance(x, str) or isinstance(y, str):
            if x != y:
                return False
        elif abs(x - y) > tol:
            return False
    return True


def same_object(a, b):
    """Two signature rows describe the same drawn object: kind, position and shape must agree."""
    a, b = deep_tuple(a), deep_tuple(b)
    if a[0] != b[0]:
        return False
    if a[0] == "line":
        return all(abs(a[i]-b[i]) <= TOL for i in range(1, 5)) and a[5] == b[5]
    return (abs(a[1]-b[1]) <= TOL and abs(a[2]-b[2]) <= TOL and same_shape(a[3], b[3]) and a[4] == b[4])


def edge_row(row, size, tol=EPS):
    """Bu imza satırı kutunun KENARINA değiyor mu? Değiyorsa sembolün kendi çizgisi değildir.

    `pick_anchor` ile aynı ilke: kutu kenarını sıyıran çizgi, sembolün değil, ÇEVRE
    TESİSATININ kırpılmış ucudur. Bir klemensin altına saha teli çizilmemişse sembol aynı
    klemenstir; eksik olan tel ucudur. Bu ayrım olmadan "kaç tel bağlı" sembolün kimliğine
    karışır ve tek telli aynı klemens eşleşmez.

    Eğriler yalnız bütün olarak alınır (`curve_inside`), bu yüzden hiçbir eğri kenar parçası
    değildir. Sembolün kendi çizgisi kutu kenarına tam denk gelirse bu kural onu da çevre
    sayar; sonuç sessiz bir kabul değil, kayıtta görünen `DIS_HAT_SAYISI_FARKLI` notudur.
    """
    if row[0] != "line":
        return False
    xs, ys = (row[1], row[3]), (row[2], row[4])
    return (min(xs) <= tol or max(xs) >= size[0]-tol
            or min(ys) <= tol or max(ys) >= size[1]-tol)


def split_core(rows, size):
    """İmzayı ikiye ayır: sembolün kendi çizgileri ve kutu kenarındaki tel uçları."""
    inside = [r for r in rows if not edge_row(r, size)]
    edge = [r for r in rows if edge_row(r, size)]
    return inside, edge


def has_extent(row, tol=TOL):
    """Bu parçanın ölçülebilir bir boyu var mı? Tek bir sıfır boyutlu nokta AYIRT ETMEZ."""
    if row[0] == "line":
        return abs(row[3]-row[1]) > tol or abs(row[4]-row[2]) > tol
    path = deep_tuple(row[3])
    if path and isinstance(path[0], str):        # BBOX_ONLY fallback: kutu ölçüsü taşır
        return any(abs(v) > tol for v in path[1:] if isinstance(v, (int, float)))
    xs = [p[0] for p in path if isinstance(p, tuple)]
    ys = [p[1] for p in path if isinstance(p, tuple)]
    return bool(xs) and (max(xs)-min(xs) > tol or max(ys)-min(ys) > tol)


def distinctive(inside):
    """Gevşetme yalnız sembolün AYIRT EDİCİ kendi şekli varsa yapılır.

    Tek bir sıfır boyutlu nokta (birleşme noktası, uç işareti) her yerde bulunur; onun
    üzerinden gevşetmek sayfadaki bütün noktaları aday yapardı. Ölçülen: sayfa 4'te
    "yalnız daire" ailesi 1 → 20 adaya çıkıyordu; bu kural onu 1'de tutar.
    """
    return bool(inside) and any(has_extent(r) for r in inside)


def same_rows(a, b):
    return len(a) == len(b) and all(same_object(x, y) for x, y in zip(a, b))


def pick_anchor(members, box):
    """Anchor on the symbol itself: a curve, else a line lying wholly inside the mask.

    A line that only grazes the box edge belongs to the surrounding wiring, and anchoring on it
    would hide instances whose feeding wires have a different length.
    """
    curves = [m for m in members if "bbox" in m]
    if curves:
        return curves[0]
    inside = [m for m in members if "bbox" not in m
              and all(box[0]-EPS <= p[0] <= box[2]+EPS and box[1]-EPS <= p[1] <= box[3]+EPS
                      for p in (m["a"], m["b"]))]
    return (inside or members)[0]


def descriptor(tpl):
    """Source-independent match recipe: signature, anchor, size, pin offsets, label offsets.

    The same recipe comes either from a box in this run or from the persistent library, so a
    library entry can be matched without needing the pins of the run it was captured in.
    """
    point, shape, kind = anchor_of(pick_anchor(tpl["core_segments"], tpl["bbox"]))
    origin = tpl["origin"]
    return dict(core=tpl["core"], size=(round(tpl["bbox"][2]-tpl["bbox"][0], 4),
                                        round(tpl["bbox"][3]-tpl["bbox"][1], 4)),
                anchor=dict(kind=kind, shape=shape,
                            offset=(round(point[0]-origin[0], 4), round(point[1]-origin[1], 4))),
                pins=[dict(offset=m["offset"], kind=m["kind"], pin_label_offset=m["pin_label_offset"],
                           source_pin_label=m["pin_label_text"], external_lines=m["external_lines"],
                           source_pin=m["pin"], source_device=m["device"], pin_id=m.get("pin_id"))
                      for m in tpl["pins"]],
                device_label_offset=tpl["device_label_offset"], source_device_label=tpl["device_label_text"],
                device_issue=tpl["device_issue"], unverified_curves=tpl.get("unverified_curves", []))


def search(desc, segments, words, render_bbox, marked=(), curves=()):
    """Translation-only search for one descriptor. Rejections are reported, not dropped."""
    anchor = desc["anchor"]
    shape = deep_tuple(anchor["shape"]) if anchor["kind"] == "curve" else anchor["shape"]
    candidates, rejected, seen = [], [], set()
    for obj in (curves if anchor["kind"] == "curve" else segments):
        point, found, _ = anchor_of(obj)
        if anchor["kind"] == "curve":
            if not same_shape(found, shape):
                continue
        elif abs(found[0]-shape[0]) > TOL or abs(found[1]-shape[1]) > TOL:
            continue
        origin = (round(point[0]-anchor["offset"][0], 4), round(point[1]-anchor["offset"][1], 4))
        key = (round(origin[0], 1), round(origin[1], 1))
        if key in seen:
            continue
        seen.add(key)
        bbox = [origin[0], origin[1], round(origin[0]+desc["size"][0], 4), round(origin[1]+desc["size"][1], 4)]
        core, _, unverified = signature(segments, bbox, (bbox[0], bbox[1]), curves)
        edge_issue = None
        if not same_rows(core, desc["core"]):
            inside_t, edge_t = split_core(desc["core"], desc["size"])
            inside_c, edge_c = split_core(core, desc["size"])
            # Sembolün KENDİ çizgileri birebir aynı olmalı. Yalnız kenardaki tel uçları
            # farklıysa bu aynı semboldür; fark elenmez, adayın üstünde not olarak görünür.
            # Şablonun kendi çizgisi yoksa (imza tamamen tel ucundan ibaretse) gevşetme
            # yapılmaz: orada ayırt edecek bir şekil yoktur.
            if not distinctive(inside_t) or not same_rows(inside_c, inside_t):
                rejected.append(dict(bbox=bbox, origin=list(origin), reason="CORE_GEOMETRY_DIFFERS",
                                     template_parts=len(desc["core"]), candidate_parts=len(core),
                                     template_symbol_parts=len(inside_t),
                                     candidate_symbol_parts=len(inside_c)))
                continue
            edge_issue = dict(reason="EXTERNAL_LINE_COUNT_DIFFERS_FROM_TEMPLATE",
                              template_edge_parts=len(edge_t), candidate_edge_parts=len(edge_c),
                              note="Sembol aynı; kutu kenarındaki tel ucu sayısı farklı. "
                                   "Bağlantı sayısı sembolün kimliği değildir; bu fark "
                                   "eleme değil, incelenecek nottur.")
        candidates.append(describe(desc, bbox, segments, words, render_bbox, marked, unverified,
                                   edge_issue))
    candidates.sort(key=lambda c: (c["bbox"][1], c["bbox"][0]))
    return dict(candidates=candidates, rejected=rejected, translation_only=True, production_ready=False,
                limitation="Aday öneridir. Yalnız öteleme desteklenir: aynalanmış, döndürülmüş veya "
                           "ölçeklenmiş yerleşim eşleşmez ve eşleşmemesi yokluk kanıtı değildir. "
                           "NO/NC ve PE farkı şekil farkı olarak elenir. Etiketler kopyalanmaz; "
                           "cihaz ve pin adları her örnek için sayfadan okunur.")


def find(box, pins, segments, words, render_bbox, all_pins=None, curves=()):
    tpl = template(box, pins, segments, words, render_bbox, curves=curves)
    desc = descriptor(tpl)
    marked = all_pins if all_pins is not None else pins
    result = search(desc, segments, words, render_bbox, marked, curves)
    for candidate in result["candidates"]:
        candidate["offset"] = [round(candidate["bbox"][0]-tpl["bbox"][0], 2),
                               round(candidate["bbox"][1]-tpl["bbox"][1], 2)]
        candidate["is_template"] = abs(candidate["offset"][0]) <= TOL and abs(candidate["offset"][1]) <= TOL
    for row in result["rejected"]:
        row["offset"] = [round(row["bbox"][0]-tpl["bbox"][0], 2), round(row["bbox"][1]-tpl["bbox"][1], 2)]
    return dict(result, template=dict(tpl, core_segments=len(tpl["core_segments"])), descriptor=desc)


def describe(desc, bbox, segments, words, render_bbox, marked, unverified_curves=(), edge_issue=None):
    pins = []
    for m in desc["pins"]:
        point = (round(bbox[0]+m["offset"][0], 4), round(bbox[1]+m["offset"][1], 4))
        existing = [p for p in marked
                    if abs(p["point"][0]-point[0]) <= MARKED_TOL and abs(p["point"][1]-point[1]) <= MARKED_TOL]
        found = [] if m["pin_label_offset"] is None else words_at(
            words, render_bbox, (bbox[0]+m["pin_label_offset"][0], bbox[1]+m["pin_label_offset"][1]))
        texts = [w["text"] for w in found]
        issues = []
        if m["pin_label_offset"] is None:
            issues.append("TEMPLATE_PIN_LABEL_UNKNOWN")
        elif not texts:
            issues.append("PIN_LABEL_NOT_FOUND_AT_SAME_OFFSET")
        elif len(texts) > 1:
            issues.append("PIN_LABEL_AMBIGUOUS")
        elif m["source_pin_label"] is not None and texts[0] != m["source_pin_label"]:
            issues.append("PIN_LABEL_DIFFERS_FROM_TEMPLATE")
        # External wiring is re-checked per instance: a matching symbol is not a matching circuit.
        lines = attached(segments, point, bbox)
        if not lines:
            issues.append("NO_EXTERNAL_LINE_AT_POINT")
        elif len(lines) != m["external_lines"]:
            issues.append("EXTERNAL_LINE_COUNT_DIFFERS_FROM_TEMPLATE")
        pins.append(dict(template_pin_id=m.get("pin_id"), template_device=m["source_device"],
                         template_pin=m["source_pin"], kind=m["kind"], point=list(point),
                         page_pin_texts=texts, template_pin_label_text=m["source_pin_label"],
                         external_lines=len(lines), template_external_lines=m["external_lines"],
                         already_marked=[p["id"] for p in existing], issues=issues))
    device_texts = [] if desc["device_label_offset"] is None else [
        w["text"] for w in words_at(words, render_bbox,
                                    (bbox[0]+desc["device_label_offset"][0], bbox[1]+desc["device_label_offset"][1]))]
    context = len([s for s in segments if clip(s, [bbox[0]-CONTEXT_RADIUS, bbox[1]-CONTEXT_RADIUS,
                                                  bbox[2]+CONTEXT_RADIUS, bbox[3]+CONTEXT_RADIUS]) is not None])
    issues = []
    if desc["device_issue"]:
        issues.append(desc["device_issue"])
    elif not device_texts:
        issues.append("DEVICE_LABEL_NOT_FOUND_AT_SAME_OFFSET")
    elif len(device_texts) > 1:
        issues.append("DEVICE_LABEL_AMBIGUOUS")
    elif desc["source_device_label"] is not None and device_texts[0] != desc["source_device_label"]:
        issues.append("DEVICE_LABEL_DIFFERS_FROM_TEMPLATE")
    if unverified_curves:
        issues.append("CURVE_SHAPE_UNVERIFIED_BBOX_ONLY")
    if edge_issue:
        issues.append(edge_issue["reason"])
    return dict(id="cand:%.2f:%.2f" % (bbox[0], bbox[1]), bbox=bbox, is_template=False,
                edge_difference=edge_issue,
                page_device_texts=device_texts, template_device_label_text=desc["source_device_label"],
                unverified_curves=list(unverified_curves),
                context_segments=context, pins=pins, issues=issues,
                status="CANDIDATE_REQUIRES_USER_CONFIRMATION", requires_user_confirmation=True,
                production_ready=False,
                note="Yalnız çizim şekli eşleşti. Cihaz/pin adı sayfadan okundu, şablondan kopyalanmadı; "
                     "kullanıcı doğrulamadan pin oluşturulmaz.")
