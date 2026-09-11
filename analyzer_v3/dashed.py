"""Kesikli / kesikli-noktalı hatların ÖLÇÜMÜ ve birleştirme ÖNERİSİ.

Burada hiçbir bağlantı kurulmaz ve graf değiştirilmez. Modül yalnız çizimden okunabilen
olguları üretir:

  * eş doğrusal parçaların oluşturduğu **cetvel** ve cetvelin kendi desen ölçüleri,
  * cetvelin kesintisiz **koşu**ları; koşuyu ayıran her boşluğun NEDEN ayırdığı,
  * dört cetvelin **kapalı dikdörtgen** (bölge/cihaz kutusu) oluşturup oluşturmadığı,
  * çizimin kendi **birleşme noktaları** (eş merkezli halka kümesi).

İki farklı soru bilerek ayrı tutulur:

  1. *Süreklilik*: kesikli hat bu boşluğun ötesinde kendisi olarak devam ediyor mu?
     Hattı kesen başka bir tel bu soruyu etkilemez — üstünden geçer, kesmez.
  2. *Bağlantı*: kesikli hat, kendisini kesen tele bağlı mı? Bu ancak kesişme noktasında
     ÇİZİLMİŞ birleşme noktası varsa önerilir. Noktasız kesişme asla bağlanmaz.

Sembol boşluğu (klemens/cihaz maskesi) süreklilik boşluğu DEĞİLDİR: iletken cihazın
içine girer, köprülenirse cihaz atlanmış olur. Bu yüzden koşuyu kırar.
"""
from collections import Counter, defaultdict

from .geometry import EPS

MIN_PIECE = 0.3        # bundan kısa parça ölçüm gürültüsüdür; gerçek mürekkep bu eşiğin üstünde
MIN_PIECES = 4         # bir cetvel sayılmak için gereken en az parça
FILL_STACK = 10        # bu kadar hairline aynı sütunda üst üste ise dolu sembol gövdesidir
FILL_STEP = 0.4        # dolgu tarama satırları arasındaki en büyük adım
DOT_TOLERANCE = 0.15   # eş merkez sayılmak için merkezler arası en büyük fark
# Boşluk köprüleme FAIL-CLOSED'dur. Ölçüm: -X4:PE klemensini ayıran boşluk 5,67 pt idi ve
# 1,6 x medyan (6,80 pt) sınırının ALTINDA kalıyordu; klemensi yalnız tek bir eğri nesnesi
# kurtarıyordu. 1,25 kat, desenin kendi boşluğuna dar bir zarf bırakır: bundan geniş her boşluk,
# içinde görünür bir engel bulunmasa bile "sembol olabilir" gerekçesiyle koşuyu kırar.
GAP_SLACK = 1.25
DOT_GAP_SLACK = 2.0    # içinde çizilmiş birleşme noktası olan boşluk için üst sınır
# Kesikli hattı, cihazlarla bölünmüş DÜZ hattan ayıran iki ölçü. İkisi birden gerekir:
# desen en az 50 pt'de bir tekrar etmeli ve tipik boşluk küçük olmalı. Sayfa 4/2/5/28/36
# ölçümünde kesikli hatlar 0.033..0.132 parça/pt, düz hatlar 0.0066..0.0091 parça/pt çıkıyor.
MIN_DENSITY = 0.02     # parça / uzanım
MAX_TYPICAL_GAP = 12.0


def fill_scanlines(segments):
    """Dolu sembol gövdesi: aynı sütunda çok sayıda kısa hairline, 0.14 pt adımlarla yığılmış.

    Bu parçalar mürekkeptir ama HAT değildir. Desen ölçümüne girerlerse kesikli cetvel
    istatistiğini kirletirler (sayfa 4'te y=572.18 ekseninde 19 tanesi vardır).
    """
    columns = defaultdict(list)
    for s in segments:
        w, h = abs(s["b"][0]-s["a"][0]), abs(s["b"][1]-s["a"][1])
        if h <= EPS and 0.5 < w < 4.0:
            columns[round((s["a"][0]+s["b"][0])/2, 1)].append((s["a"][1], s["id"]))
        elif w <= EPS and 0.5 < h < 4.0:
            columns[round((s["a"][1]+s["b"][1])/2, 1)].append((s["a"][0], s["id"]))
    out = set()
    for rows in columns.values():
        rows.sort()
        run = [rows[0]]
        for value, sid in rows[1:]:
            # Yığın YEREL olmalı: 0,4 pt'den uzak bir parça aynı gövdenin satırı değildir.
            # Ölçüldü: yerellik olmadan PE düşüşünün ok başı "dolu sembol" sayılıp açık işten
            # düşüyordu.
            if value-run[-1][0] <= FILL_STEP:
                run.append((value, sid))
            else:
                if len(run) >= FILL_STACK:
                    out.update(i for _, i in run)
                run = [(value, sid)]
        if len(run) >= FILL_STACK:
            out.update(i for _, i in run)
    return out


def _pieces_by_axis(segments, skip=()):
    """Eksene paralel parçalar; cetvel kimliği (eksen, koordinat, KALEM KALINLIĞI).

    Kalınlık kimliğin parçasıdır: farklı kalemle çizilmiş iki nesne aynı eksende olsa bile
    aynı hat değildir (sayfa 4'te 0.71 pt'lik yazı bloğu çizgisi, 0.99 pt'lik PE düşüşüyle
    aynı x üzerindedir).
    """
    rows, cols = defaultdict(list), defaultdict(list)
    for s in segments:
        if s.get("dash") or s["id"] in skip:
            continue
        pen = round(s.get("linewidth") or 0.0, 2)
        dx, dy = abs(s["b"][0]-s["a"][0]), abs(s["b"][1]-s["a"][1])
        if dy <= EPS and dx > MIN_PIECE:
            rows[(round(s["a"][1], 2), pen)].append((min(s["a"][0], s["b"][0]),
                                                     max(s["a"][0], s["b"][0]), s["id"]))
        elif dx <= EPS and dy > MIN_PIECE:
            cols[(round(s["a"][0], 2), pen)].append((min(s["a"][1], s["b"][1]),
                                                     max(s["a"][1], s["b"][1]), s["id"]))
    return rows, cols


def junction_dots(curves, with_rejected=False):
    """Çizimin kendi birleşme noktaları: aynı merkezde iç içe en az iki kapalı daire.

    EPLAN dolu bağlantı noktasını iç içe çizili dairelerle basar. Tek daire (lamba, motor,
    delik, buton) nokta sayılmaz; eş merkezli halka kümesi gerekir. Bu bir ÖLÇÜMDÜR:
    noktanın gerçekten bağlantı anlamına gelip gelmediğine insan karar verir.
    """
    circles = []
    for c in curves:
        box = c["bbox"]
        w, h = box[2]-box[0], box[3]-box[1]
        if max(w, h) <= 0.0:
            continue
        if abs(w-h) > max(0.2, 0.15*max(w, h)):          # daire değil (elips, yay, kutu)
            continue
        circles.append(((box[0]+box[2])/2, (box[1]+box[3])/2, max(w, h)/2, c["id"]))
    # Ondalık yuvarlama aynı noktanın halkalarını ayrı gruplara düşürüyordu: toleranslı kümele.
    groups = []
    for x, y, r, cid in sorted(circles, key=lambda q: -q[2]):
        for g in groups:
            if abs(g["x"]-x) <= DOT_TOLERANCE and abs(g["y"]-y) <= DOT_TOLERANCE:
                g["rings"].append((r, cid))
                break
        else:
            groups.append(dict(x=x, y=y, rings=[(r, cid)]))
    dots, rejected = [], []
    for g in groups:
        radii = sorted({round(r, 2) for r, _ in g["rings"] if r > 0})
        if len(radii) < 2:
            # Tek halka: lamba, motor, klemens dairesi, telif işareti. Elenen küme RAPOR EDİLİR.
            rejected.append(dict(point=[round(g["x"], 2), round(g["y"], 2)], rings=radii,
                                 reason="SINGLE_RING_NOT_A_JUNCTION_MARK"))
            continue
        dots.append(dict(point=[round(g["x"], 2), round(g["y"], 2)], radius=max(radii),
                         rings=radii, curve_ids=sorted({i for _, i in g["rings"]}),
                         source="DRAWN_CONCENTRIC_RINGS", tolerance=DOT_TOLERANCE,
                         note="Çizimin kendi birleşme noktası işareti: eş merkezli %d halka. "
                              "Halka sayısı bir güç ölçüsü DEĞİLDİR (aynı nokta üst üste "
                              "çizilmiş olabilir). Bu bir ÇİZİM işaretidir; fiziksel tel "
                              "birleşmesi anlamına geldiği insan kararıdır." % len(radii)))
    dots.sort(key=lambda d: (d["point"][0], d["point"][1]))
    if with_rejected:
        return dots, sorted(rejected, key=lambda d: (d["point"][0], d["point"][1]))
    return dots


def measure_dots(dots, segments, boxes=()):
    """Her noktada kaç kol buluşuyor ve nokta hangi kutunun içinde? Ölçüm, iddia değil."""
    for d in dots:
        x, y = d["point"]
        arms, touching = 0, []
        for s in segments:
            for end in (s["a"], s["b"]):
                if abs(end[0]-x) <= EPS and abs(end[1]-y) <= EPS:
                    arms += 1
                    touching.append(s["id"])
                    break
            else:
                lo_x, hi_x = sorted((s["a"][0], s["b"][0]))
                lo_y, hi_y = sorted((s["a"][1], s["b"][1]))
                if lo_x-EPS <= x <= hi_x+EPS and lo_y-EPS <= y <= hi_y+EPS:
                    arms += 2                      # noktadan geçen hat iki kol sayılır
                    touching.append(s["id"])
        d["arms"] = arms
        d["segments"] = sorted(set(touching))
        inside = [b["bbox"] for b in boxes
                  if b["bbox"][0] <= x <= b["bbox"][2] and b["bbox"][1] <= y <= b["bbox"][3]]
        d["inside_zone_box"] = bool(inside)
        d["scope_note"] = ("Kapalı kesikli kutunun içinde: saha tarafı, pano kapsamı dışı."
                           if inside else "Kapalı kesikli kutunun dışında.")
    return dots


def _dot_curve_ids(dots):
    return {i for d in dots for i in d["curve_ids"]}


def _dot_near(dots, axis, coord, lo, hi):
    for d in dots:
        along, across = (d["point"][0], d["point"][1]) if axis == "y" else (d["point"][1], d["point"][0])
        if abs(across-coord) <= d["radius"]+EPS and lo-d["radius"] <= along <= hi+d["radius"]:
            return d
    return None


def _gap_contents(page, dots, axis, coord, lo, hi):
    """Boşluğun içinde ne var? Süreklilik kararını verecek kanıt burada toplanır."""
    dot_ids = _dot_curve_ids(dots)
    crossings, blockers = [], []
    for s in page["segments"]:
        dx, dy = abs(s["b"][0]-s["a"][0]), abs(s["b"][1]-s["a"][1])
        if axis == "y" and dx <= EPS:
            x = s["a"][0]
            if lo-EPS < x < hi+EPS and min(s["a"][1], s["b"][1])-EPS <= coord <= max(s["a"][1], s["b"][1])+EPS:
                crossings.append(s["id"])
        elif axis == "x" and dy <= EPS:
            y = s["a"][1]
            if lo-EPS < y < hi+EPS and min(s["a"][0], s["b"][0])-EPS <= coord <= max(s["a"][0], s["b"][0])+EPS:
                crossings.append(s["id"])
    for box in page.get("masks", []):
        b = box["bbox"]
        hit = (b[0] < hi and b[2] > lo and b[1]-EPS <= coord <= b[3]+EPS) if axis == "y" \
            else (b[1] < hi and b[3] > lo and b[0]-EPS <= coord <= b[2]+EPS)
        if hit:
            blockers.append(("SYMBOL_MASK", box.get("id", "?")))
    for w in page.get("word_boxes", []):
        hit = (w[0] < hi and w[2] > lo and w[1] <= coord <= w[3]) if axis == "y" \
            else (w[1] < hi and w[3] > lo and w[0] <= coord <= w[2])
        if hit:
            blockers.append(("TEXT_BOX", w[4]))
    for c in page.get("curves", []):
        if c["id"] in dot_ids:
            continue                                     # birleşme noktası engel değil, kanıttır
        pts = c.get("points") or []
        if len(pts) < 2:
            continue                                     # sıfır uzunluklu eğri asla engel değil
        # Engel, eğrinin SINIRLAYICI KUTUSU değil KENDİ NOKTA YOLUDUR: ölçümde 31 eğri
        # engelinin 23'ü yalnız kutu artefaktıydı ve sahte kırılma üretiyordu.
        hit = False
        for q, r in zip(pts, pts[1:]):
            lo_a, hi_a = sorted((q[0], r[0]))
            lo_b, hi_b = sorted((q[1], r[1]))
            if axis == "y":
                if lo_a < hi and hi_a > lo and lo_b-EPS <= coord <= hi_b+EPS:
                    hit = True
                    break
            elif lo_b < hi and hi_b > lo and lo_a-EPS <= coord <= hi_a+EPS:
                hit = True
                break
        if hit:
            blockers.append(("SYMBOL_CURVE", c["id"]))
    return sorted(set(crossings)), sorted(set(blockers))


def rulings(page, dots=None):
    """Cetveller: tam uzanım, desen ölçüleri, kesintisiz koşular ve her kırılmanın gerekçesi."""
    dots = junction_dots(page.get("curves", [])) if dots is None else dots
    fills = fill_scanlines(page["segments"])
    rows, cols = _pieces_by_axis(page["segments"], skip=fills)
    out, dropped, thin = [], [], []
    for axis, store in (("y", rows), ("x", cols)):
        for (coord, pen), raw in sorted(store.items()):
            pieces = sorted(raw)
            if len(pieces) < MIN_PIECES:
                thin.append(dict(ruling="%s=%.2f" % (axis, coord), pen=pen, pieces=len(pieces),
                                 reason="PARCA_SAYISI_MIN_PIECES_ALTINDA"))
                continue
            spaces = [pieces[i+1][0]-pieces[i][1] for i in range(len(pieces)-1)]
            positive = sorted(g for g in spaces if g > EPS)
            # Tipik boşluk MEDYANDIR. Yuvarlama kovasıyla alınan "en sık" değer, çizgi-nokta
            # deseninde tire uzunluğunu ikiye bölüp ölçüyü kaydırıyordu.
            typical = round(positive[len(positive)//2], 2) if positive else 0.0
            dash = Counter(round(b-a, 1) for a, b, _ in pieces).most_common(1)[0][0]
            # Desenin gerçek tekrar birimi: bir sonraki-bir sonraki parçanın başlangıcı.
            starts = [a for a, _, _ in pieces]
            repeats = sorted(starts[i+2]-starts[i] for i in range(len(starts)-2))
            repeat_unit = round(repeats[len(repeats)//2], 2) if repeats else 0.0
            runs, current, breaks, crossings_on_run = [], [pieces[0]], [], []
            all_crossings, all_dots = [], []
            for i, space in enumerate(spaces):
                lo, hi = pieces[i][1], pieces[i+1][0]
                crossings, blockers = _gap_contents(page, dots, axis, coord, lo, hi) \
                    if space > EPS else ([], [])
                dot = _dot_near(dots, axis, coord, lo, hi) if space > EPS else None
                limit = typical*(DOT_GAP_SLACK if dot else GAP_SLACK)
                too_wide = space > max(limit, EPS)
                reason = None
                if blockers:
                    reason = "SEMBOL_BOSLUGU:" + ",".join(sorted({k for k, _ in blockers}))
                elif too_wide:
                    # Görünür engel yok ama boşluk desenin kendi boşluğundan geniş: köprülenirse
                    # arada duran bir cihaz atlanabilir. Fail-closed: koşu kırılır.
                    reason = "SEMBOL_OLABILIR_BOSLUK_DESENDEN_GENIS"
                if reason:
                    breaks.append(dict(gap=round(space, 2), between=[round(lo, 2), round(hi, 2)],
                                       reason=reason, blockers=blockers, crossings=crossings,
                                       dot=dot and dot["point"]))
                    runs.append((current, crossings_on_run))
                    current, crossings_on_run = [pieces[i+1]], []
                else:
                    # Süreklilik korunur. Kesişen tel hattı kesmez; ayrı kanıt olarak saklanır.
                    crossings_on_run += crossings
                    if dot:
                        all_dots.append(dot["point"])
                    current.append(pieces[i+1])
                all_crossings += crossings
            runs.append((current, crossings_on_run))
            extent = (round(pieces[0][0], 2), round(max(b for _, b, _ in pieces), 2))
            span = extent[1]-extent[0]
            density = round(len(pieces)/span, 4) if span > 0 else 0.0
            regularity = round(sum(1 for g in positive if abs(g-typical) <= 0.3)/len(positive), 2)                 if positive else 0.0
            if density < MIN_DENSITY or typical > MAX_TYPICAL_GAP:
                # Cihazlarla bölünmüş DÜZ iletken: grafın zaten izlediği hat, kesikli değil.
                # Sessizce düşmez: elenen her cetvel gerekçesiyle raporlanır.
                dropped.append(dict(ruling="%s=%.2f" % (axis, coord), axis=axis, coord=coord,
                                    pen=pen, pieces=len(pieces), extent=list(extent),
                                    dash_density=density, typical_gap=typical,
                                    reason=("YOGUNLUK_DUSUK" if density < MIN_DENSITY
                                            else "TIPIK_BOSLUK_BUYUK"),
                                    note="Kesikli hat sayılmadı; grafın zaten izlediği düz hat "
                                         "olarak değerlendirilir."))
                continue
            for index, (run, crossed) in enumerate(runs):
                lengths = sorted({round(b-a, 1) for a, b, _ in run})
                out.append(dict(
                    ruling="%s=%.2f" % (axis, coord), axis=axis, coord=coord, index=index,
                    pen=pen, piece_lengths=lengths,
                    mixed_style=bool(lengths and max(lengths) > 3*max(dash, 0.1)),
                    start=round(run[0][0], 2), end=round(run[-1][1], 2),
                    ruling_extent=list(extent), pieces=len(run),
                    segment_ids=[i for _, _, i in run],
                    raw_pieces=[[round(a, 2), round(b, 2)] for a, b, _ in run],
                    typical_gap=typical, typical_dash=dash, repeat_unit=repeat_unit,
                    dash_density=density, gap_regularity=regularity,
                    crossings_without_dot=sorted(set(crossed)),
                    dots_on_run=[d["point"] for d in dots
                                 if _dot_near([d], axis, coord, run[0][0], run[-1][1])],
                    breaks=breaks, total_pieces_on_ruling=len(pieces)))
    for row in out:
        row["dropped_rulings"] = dropped
        row["thin_axis_groups"] = len(thin)
    return out


def path_corners(curves, tolerance=0.2):
    """Çizimin kendi yol-köşesi izleri: sıfır uzunluklu eğri nesneleri.

    EPLAN bir yol köşesinde sıfır uzunluklu bir nesne bırakır. Köşe kanıtı budur;
    "iki kenarın ucu birbirine yakın" DEĞİLDİR (MAIN.md yakınlıktan ilişki kurmayı yasaklar).
    """
    return [((c["bbox"][0]+c["bbox"][2])/2, (c["bbox"][1]+c["bbox"][3])/2)
            for c in curves
            if abs(c["bbox"][2]-c["bbox"][0]) <= tolerance
            and abs(c["bbox"][3]-c["bbox"][1]) <= tolerance]


def closed_boxes(runs, corners=(), tolerance=0.3):
    """Dört CETVELİN oluşturduğu kapalı dikdörtgen: bölge/cihaz kutusu, iletken değil.

    Kutu, koşulardan değil cetvellerin tam uzanımından aranır: iç semboller koşuyu böler
    ama cetvel yine de kutunun kenarıdır. Dört köşenin de çizimde kendi köşe izi olmalıdır;
    kesik deseninin köşeye kaç pt kala bittiği yalnızca rapor edilir, kanıt sayılmaz.
    """
    def marked(x, y):
        return any(abs(cx-x) <= tolerance and abs(cy-y) <= tolerance for cx, cy in corners)
    by_ruling = {}
    for r in runs:
        by_ruling.setdefault(r["ruling"], r)
    horiz = [r for r in by_ruling.values() if r["axis"] == "y"]
    vert = [r for r in by_ruling.values() if r["axis"] == "x"]
    boxes, member = [], set()
    for top in horiz:
        for bottom in horiz:
            if bottom["coord"] <= top["coord"] + 1.0:
                continue
            for left in vert:
                for right in vert:
                    if right["coord"] <= left["coord"] + 1.0:
                        continue
                    box = (left["coord"], top["coord"], right["coord"], bottom["coord"])
                    if not all(marked(x, y) for x, y in
                               ((box[0], box[1]), (box[2], box[1]),
                                (box[0], box[3]), (box[2], box[3]))):
                        continue
                    reach = [
                        abs(top["ruling_extent"][0]-left["coord"]),
                        abs(top["ruling_extent"][1]-right["coord"]),
                        abs(bottom["ruling_extent"][0]-left["coord"]),
                        abs(bottom["ruling_extent"][1]-right["coord"]),
                        abs(left["ruling_extent"][0]-top["coord"]),
                        abs(left["ruling_extent"][1]-bottom["coord"]),
                        abs(right["ruling_extent"][0]-top["coord"]),
                        abs(right["ruling_extent"][1]-bottom["coord"])]
                    period = max(r["typical_dash"] + r["typical_gap"]
                                 for r in (top, bottom, left, right))
                    if max(reach) > period:
                        continue          # kenar mürekkebi köşeden bir desen periyodundan fazla uzak
                    edges = sorted(r["ruling"] for r in (top, bottom, left, right))
                    box_rect = list(box)
                    boxes.append(dict(bbox=box_rect, edges=edges,
                                      corner_marks="DRAWN_PATH_CORNERS",
                                      ink_short_of_corner=round(max(reach), 2),
                                      pattern_period=round(period, 2),
                                      note="Dört kesikli cetvel kapalı dikdörtgen oluşturuyor ve "
                                           "dört köşede de çizimin kendi köşe izi var: bölge/cihaz "
                                           "kutusu, iletken değil. Köşeler yakınlıkla değil, çizim "
                                           "işaretiyle doğrulandı."))
                    member.update(edges)
    return boxes, member


def _ends(run):
    axis = run["axis"]
    a = (run["start"], run["coord"]) if axis == "y" else (run["coord"], run["start"])
    b = (run["end"], run["coord"]) if axis == "y" else (run["coord"], run["end"])
    return [list(a), list(b)]


def _span(run):
    return (run["start"], run["end"])


def _run_on_rect(run, rect, tol=0.3):
    """Koşu bu dikdörtgenin bir kenarı üzerinde mi (uzanımı da kenarın içinde)?"""
    lo, hi = _span(run)
    if run["axis"] == "y":
        return (abs(run["coord"]-rect[1]) <= tol or abs(run["coord"]-rect[3]) <= tol) \
            and lo >= rect[0]-tol and hi <= rect[2]+tol
    return (abs(run["coord"]-rect[0]) <= tol or abs(run["coord"]-rect[2]) <= tol) \
        and lo >= rect[1]-tol and hi <= rect[3]+tol


def _run_inside_rect(run, rect, tol=0.3):
    """Koşunun TAMAMI dikdörtgenin içinde mi (kenarında değil)?"""
    if _run_on_rect(run, rect, tol):
        return False
    lo, hi = _span(run)
    if run["axis"] == "y":
        return rect[0]-tol <= lo and hi <= rect[2]+tol and rect[1]+tol < run["coord"] < rect[3]-tol
    return rect[1]-tol <= lo and hi <= rect[3]+tol and rect[0]+tol < run["coord"] < rect[2]-tol


def _run_crosses_rect(run, rect, tol=0.3):
    """Koşunun bir ucu içeride, diğeri dışarıda mı? Sınır geçişi işaretlenir."""
    if _run_on_rect(run, rect, tol) or _run_inside_rect(run, rect, tol):
        return False
    lo, hi = _span(run)
    if run["axis"] == "y":
        if not (rect[1] < run["coord"] < rect[3]):
            return False
        return (lo < rect[0] < hi) or (lo < rect[2] < hi)
    if not (rect[0] < run["coord"] < rect[2]):
        return False
    return (lo < rect[1] < hi) or (lo < rect[3] < hi)


def _on_run(run, point, slack=0.4):
    """Nokta bu koşunun üzerinde mi (eksende ve uzanım içinde)?"""
    axis = run["axis"]
    along, across = (point[0], point[1]) if axis == "y" else (point[1], point[0])
    return abs(across-run["coord"]) <= slack and run["start"]-slack <= along <= run["end"]+slack


def proposals(page, runs=None, dots=None, pins=(), labels_at=None):
    """Kesikli koşular için SINIF ve birleştirme ÖNERİSİ. Hiçbir şey otomatik bağlanmaz.

    `labels_at(point)` -> o uçta basılı potansiyel/sayfa referansı yazıları.

    Not: "düz iletkene değiyor" kanıtı ÖLÇÜLDÜĞÜNDE asılsız çıktı (34/34 örneği 1,15 pt'lik
    sembol kontur çizgisiyle destekleniyordu) ve kaldırıldı.
    """
    dots = junction_dots(page.get("curves", [])) if dots is None else dots
    runs = rulings(page, dots) if runs is None else runs
    boxes, _ = closed_boxes(runs, path_corners(page.get("curves", [])))
    labels_at = labels_at or (lambda point: dict(potentials=[], sheet_references=[]))
    rows = []
    for run in runs:
        ends = _ends(run)
        texts = [labels_at(p) for p in ends]
        # Uç yazısı yalnız TEK ve en yakın olduğunda kanıttır. Ölçüldü: PE düşüşünün ucunda
        # komşu klemensin "N24.30" adı da toplanıyordu — iki ayrı potansiyel tek kayıtta.
        potentials, ambiguous = [], []
        for x in texts:
            names = x.get("potentials", [])
            if len(names) == 1:
                potentials += names
            elif names:
                ambiguous += names
        potentials = sorted(set(potentials))
        ambiguous = sorted(set(ambiguous) - set(potentials))
        sheets = sorted({t for x in texts for t in x.get("sheet_references", [])})
        touching = [p for p in pins if _on_run(run, p["point"])]
        # Kanıtlar SINIFLANDIRILIR: iki kanıt aynı sınıftan gelirse tek kanıt sayılır.
        #   YAZI   — uçtaki potansiyel adı ve/veya sayfa referansı (ikisi birlikte tek sınıf)
        #   CIZIM  — koşunun üzerinde çizilmiş birleşme noktası
        #   ISARET — koşuya bağlı, işaretlenmiş kapsam içi uç
        evidence = []
        if potentials:
            evidence.append(dict(kind="END_POTENTIAL_LABEL", klass="YAZI", detail=potentials,
                                 strength=("GUCLU" if len(
                                     {t for x in texts for t in x.get("potentials", [])}) and
                                     all(x.get("potentials") for x in texts) else "ZAYIF")))
        if sheets:
            evidence.append(dict(kind="END_SHEET_REFERENCE", klass="YAZI", detail=sheets))
        if run["dots_on_run"]:
            evidence.append(dict(kind="DRAWN_JUNCTION_DOT", klass="CIZIM",
                                 detail=run["dots_on_run"]))
        for q in touching:
            # Kendi ürettiğim aday işaret bağımsız kanıt SAYILMAZ: döngüsel kanıt olurdu.
            confirmed_mark = q.get("method", "MANUAL") != "P04_CANDIDATE"
            evidence.append(dict(kind="MARKED_PIN_ON_RUN",
                                 klass="ISARET" if confirmed_mark else "ISARET_ONAYSIZ_ADAY",
                                 method=q.get("method", "MANUAL"),
                                 detail=["%s:%s" % (q["device"], q["pin"])]))
        classes = sorted({e["klass"] for e in evidence if e["klass"] != "ISARET_ONAYSIZ_ADAY"})
        # Kutu kenarı sınıfı KOŞU bazındadır: kutunun dışına taşan koşu kendi kanıtıyla sınıflanır.
        on_edge = any(run["ruling"] in b["edges"] and _run_on_rect(run, b["bbox"])
                      for b in boxes)
        inside = [b for b in boxes if _run_inside_rect(run, b["bbox"])]
        crossing = [b for b in boxes if _run_crosses_rect(run, b["bbox"])]
        # Kapsam bir NOT'tur, sınıf değil: geometrik konum, insanın işaretlediği kanıtı EZEMEZ.
        # (Ölçüldü: kapsam dalı kanıt sayımından önce gelince kutu içindeki her koşu, elle
        # işaretlenmiş kapsam içi ucu olsa bile "iş değil" kovasına düşüyordu.)
        scope = ("KAPALI_KUTU_ICI" if inside else
                 "KUTU_SINIRINI_GECIYOR" if crossing else "KUTU_DISI")
        if on_edge:
            kind, why = ("ZONE_BOX_EDGE",
                         "Dört kesikli cetvelin oluşturduğu kapalı kutunun kenarı: bölge/cihaz "
                         "çerçevesi, iletken değil.")
        elif len(classes) >= 2:
            kind, why = ("CONDUCTOR_CANDIDATE",
                         "Kapalı kutunun parçası değil ve birbirinden bağımsız %d KANIT SINIFI "
                         "taşıyor (%s)." % (len(classes), ", ".join(classes)))
        else:
            kind, why = ("UNDECIDED",
                         "Yeterli kanıt yok: %d kanıt sınıfı (%s). Açık işte kalır."
                         % (len(classes), ", ".join(classes) or "yok"))
        if kind != "ZONE_BOX_EDGE" and inside:
            why += (" Koşunun tamamı kapsam dışı bir cihaz/bölge kutusunun içinde "
                    "(MAIN.md pano sınırı): üretim listesine giremez, ama AÇIK İŞ olarak "
                    "görünür kalır.")
        rows.append(dict(run, kind=kind, reason=why, evidence=evidence,
                         evidence_classes=classes, scope=scope,
                         inside_zone_box=[b["bbox"] for b in inside],
                         crosses_zone_box=[b["bbox"] for b in crossing],
                         ends=ends, potentials=potentials, ambiguous_end_text=ambiguous,
                         sheet_references=sheets,
                         marked_pins=["%s:%s" % (p["device"], p["pin"]) for p in touching],
                         decision="ONAY_BEKLIYOR", decided_by=None,
                         merge_proposal=dict(
                             status="PROPOSED",
                             from_point=ends[0], to_point=ends[1],
                             bridged_gaps=len(run["raw_pieces"])-1,
                             raw_pieces_kept=len(run["raw_pieces"]),
                             note="Ham parçalar korunur; graf değişmez. Onay insana aittir.")))
    # Kesikli koşuların birbirine veya düz iletkene bağlanması: YALNIZ çizilmiş nokta ile.
    links = []
    for dot in dots:
        on = [r for r in rows if _on_run(r, dot["point"], dot["radius"])]
        if len(on) < 2:
            continue
        if any(r["kind"] == "ZONE_BOX_EDGE" for r in on):
            continue                       # kutu kenarı bağlantı ucu değildir
        links.append(dict(point=dot["point"], rings=dot["rings"],
                          runs=["%s#%d" % (r["ruling"], r["index"]) for r in on],
                          evidence="DRAWN_JUNCTION_DOT",
                          relation="COMMON_POTENTIAL_NETWORK_ONLY",
                          decision="ONAY_BEKLIYOR",
                          note="Çizilmiş birleşme noktası iki kesikli koşuyu buluşturuyor. "
                               "Bu ORTAK POTANSİYEL ilişkisidir; buradan fiziksel tel çifti "
                               "türetilmez (MAIN.md: ortak potansiyelden daisy-chain yasak)."))
    return dict(runs=rows, links=links, boxes=boxes, dots=dots,
                dropped_rulings=(runs[0]["dropped_rulings"] if runs else []),
                thin_axis_groups=(runs[0]["thin_axis_groups"] if runs else 0),
                production_ready=False,
                limitation="Kesikli hat desteği ÖNERİ düzeyindedir: ham parçalar korunur, graf "
                           "değiştirilmez, hiçbir satır üretim listesine girmez. Aynı çizgi stili "
                           "veya aynı potansiyel adı TEK BAŞINA bağlantı kanıtı sayılmaz; en az iki "
                           "bağımsız kanıt aranır. Noktasız kesişme ve sembol boşluğu birleştirilmez.")
