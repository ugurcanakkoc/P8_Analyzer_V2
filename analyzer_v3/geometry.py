"""Conservative drawn-path graph. Reachability is NOT a physical wire list.

Every edge retains raw segment IDs. Interior X crossings remain separate without
an explicit filled dot. T endpoints connect graphically, not as a wiring-order claim.
No nearest-neighbour chains, no internal-contact traversal, no short-line filter.
"""
from collections import defaultdict, deque
from math import hypot

EPS = 0.015
PIN_ATTACH = 0.35   # how close a marked pin must sit to a drawn line to attach to it
CELL = 24.0         # spatial index cell for pair search; it changes speed, never the result


def pt(p):
    return (round(p[0], 4), round(p[1], 4))


def distance(a, b):
    return hypot(a[0] - b[0], a[1] - b[1])


def projection(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    div = dx * dx + dy * dy
    t = max(0, min(1, ((p[0]-a[0])*dx + (p[1]-a[1])*dy)/div)) if div else 0
    q = (a[0] + t*dx, a[1] + t*dy)
    return pt(q), distance(p, q)


def axis(s):
    a, b = s["a"], s["b"]
    if distance(a, b) < EPS:
        return None
    if abs(a[1]-b[1]) <= EPS:
        return "h"
    if abs(a[0]-b[0]) <= EPS:
        return "v"
    return None


def intersect(a, b):
    """Return shared points. End-on-line Ts join; interior crosses need a dot."""
    aa, bb = axis(a), axis(b)
    if aa == bb:
        dim, fixed = (0, 1) if aa == "h" else (1, 0)
        if abs(a["a"][fixed]-b["a"][fixed]) > EPS:
            return []
        lo = max(min(a["a"][dim], a["b"][dim]), min(b["a"][dim], b["b"][dim]))
        hi = min(max(a["a"][dim], a["b"][dim]), max(b["a"][dim], b["b"][dim]))
        if lo > hi + EPS:
            return []
        return [(pt((v, a["a"][1]) if dim == 0 else (a["a"][0], v)), "COLLINEAR") for v in {lo, hi}]
    h, v = (a, b) if aa == "h" else (b, a)
    q = pt((v["a"][0], h["a"][1]))
    if all(projection(q, s["a"], s["b"])[1] <= EPS for s in (a, b)):
        endpoint = any(distance(q, p) <= EPS for s in (a, b) for p in (s["a"], s["b"]))
        return [(q, "T_OR_END" if endpoint else "X")]
    return []


def clip_outside_boxes(segment, boxes):
    """Keep outside portions; record the removed interior instead of deleting raw data."""
    pieces = [segment]
    excluded = []
    for box in boxes:
        new = []
        x0, y0, x1, y1 = box["bbox"]
        for s in pieces:
            orient = axis(s)
            d, f = (0, 1) if orient == "h" else (1, 0)
            low, high = (x0, x1) if d == 0 else (y0, y1)
            flow, fhigh = (y0, y1) if d == 0 else (x0, x1)
            if not (flow + EPS < s["a"][f] < fhigh - EPS):
                new.append(s)
                continue
            a, b = sorted([s["a"], s["b"]], key=lambda p: p[d])
            lo, hi = max(a[d], low), min(b[d], high)
            if hi - lo <= EPS:
                new.append(s)
                continue
            excluded.append({"segment_id": s["id"], "reason": "DEVICE_INTERIOR", "box_id": box["id"]})
            for start, end in ((a[d], lo), (hi, b[d])):
                if end - start > EPS:
                    p, q = list(a), list(a)
                    p[d], q[d] = start, end
                    new.append({**s, "a": pt(p), "b": pt(q)})
        pieces = new
    return pieces, excluded


def ends_near(segments, point, dx=45.0, dy=8.0):
    """Dangling line ends inside a window: exactly one segment ends there and none passes through."""
    hits = {}
    for s in segments:
        if axis(s) is None or s.get("dash"):
            continue
        for e in (s["a"], s["b"]):
            if abs(e[0]-point[0]) <= dx and abs(e[1]-point[1]) <= dy:
                hits.setdefault(pt(e), []).append(s["id"])
    out = []
    for p, ids in sorted(hits.items()):
        if len(ids) != 1:
            continue
        through = [s["id"] for s in segments
                   if axis(s) and s["id"] != ids[0] and projection(p, s["a"], s["b"])[1] <= EPS]
        if not through:
            out.append({"point": list(p), "segment_id": ids[0]})
    return out


class PathGraph:
    def __init__(self, raw_segments, dots, pins, boxes=()):
        self.raw_count = len(raw_segments)
        self.excluded, self.segments = [], []
        self.pins = {p["id"]: p for p in pins}
        self.dots = dots
        for s in raw_segments:
            reason = "DASHED_STYLE_UNSUPPORTED" if s.get("dash") else ("NON_AXIS_OR_DEGENERATE" if not axis(s) else None)
            if reason:
                self.excluded.append({"segment_id": s["id"], "reason": reason})
                continue
            pieces, excluded = clip_outside_boxes(s, boxes)
            self.segments.extend(pieces)
            self.excluded.extend(excluded)
        segments = self.segments
        # Only segments sharing a grid cell can touch: the same result as the full pairwise scan,
        # without walking every pair on a sheet with thousands of lines.
        cells = defaultdict(list)
        for i, s in enumerate(segments):
            x0, x1 = sorted((s["a"][0], s["b"][0]))
            y0, y1 = sorted((s["a"][1], s["b"][1]))
            for cx in range(int((x0-EPS)//CELL), int((x1+EPS)//CELL)+1):
                for cy in range(int((y0-EPS)//CELL), int((y1+EPS)//CELL)+1):
                    cells[(cx, cy)].append(i)

        def around(q):
            return {i for cx in (int((q[0]-EPS)//CELL), int((q[0]+EPS)//CELL))
                    for cy in (int((q[1]-EPS)//CELL), int((q[1]+EPS)//CELL))
                    for i in cells.get((cx, cy), ())}

        def four_way(q):
            # A PDF exporter may split an unjoined X into four line objects.
            # Segment endpoints alone are NOT proof of a four-way junction.
            rays=set()
            for i in around(q):
                s=segments[i]
                if projection(q,s['a'],s['b'])[1]<=EPS:
                    d=0 if axis(s)=='h' else 1
                    for end in (s['a'],s['b']):
                        if abs(end[d]-q[d])>EPS:
                            rays.add((d,1 if end[d]>q[d] else -1))
            return len(rays)==4
        four_way_cache={}
        cuts = [{pt(s["a"]), pt(s["b"])} for s in segments]
        joins, self.crossings = [], []
        pairs = set()
        for bucket in cells.values():
            for position, i in enumerate(bucket):
                for j in bucket[position+1:]:
                    pairs.add((i, j) if i < j else (j, i))
        for i, j in sorted(pairs):
            a, b = segments[i], segments[j]
            aminx, amaxx = sorted((a["a"][0], a["b"][0]))
            aminy, amaxy = sorted((a["a"][1], a["b"][1]))
            if (min(b["a"][0], b["b"][0]) > amaxx+EPS or max(b["a"][0], b["b"][0]) < aminx-EPS
                or min(b["a"][1], b["b"][1]) > amaxy+EPS or max(b["a"][1], b["b"][1]) < aminy-EPS):
                continue
            for p, kind in intersect(a, b):
                dotted = any(distance(p, d["point"]) <= max(EPS, d["radius"] * .35) for d in dots)
                if kind!='COLLINEAR' and not dotted and p not in four_way_cache:
                    four_way_cache[p]=four_way(p)
                if kind!='COLLINEAR' and not dotted and (kind=='X' or four_way_cache.get(p)):
                    self.crossings.append({"point": p, "segments": [a["id"], b["id"]], "kind": "UNJOINED_X"})
                    continue
                cuts[i].add(p)
                cuts[j].add(p)
                joins.append((i, j, p))
        # A pin is attached only if its nearby projections resolve to ONE graph node.
        pin_candidates = {}
        for pid, pin in self.pins.items():
            candidates = []
            near = {i for cx in (int((pin["point"][0]-PIN_ATTACH)//CELL), int((pin["point"][0]+PIN_ATTACH)//CELL))
                    for cy in (int((pin["point"][1]-PIN_ATTACH)//CELL), int((pin["point"][1]+PIN_ATTACH)//CELL))
                    for i in cells.get((cx, cy), ())}
            for i in sorted(near):
                s = segments[i]
                q, dist = projection(pin["point"], s["a"], s["b"])
                if dist <= PIN_ATTACH:
                    cuts[i].add(q)
                    candidates.append((i, q, dist))
            pin_candidates[pid] = candidates
        parent = {(i, p): (i, p) for i, points in enumerate(cuts) for p in points}

        def root(n):
            while parent[n] != n:
                parent[n] = parent[parent[n]]
                n = parent[n]
            return n

        def union(a, b):
            a, b = root(a), root(b)
            if a != b:
                parent[b] = a

        for i, j, p in joins:
            union((i, p), (j, p))
        # Merge near-identical cuts on each single segment only, not separate wires.
        for i, points in enumerate(cuts):
            ordered = sorted(points, key=lambda p: distance(p, segments[i]["a"]))
            for a, b in zip(ordered, ordered[1:]):
                if distance(a, b) <= EPS:
                    union((i, a), (i, b))
        self.adj = defaultdict(list)
        self.coords = {}
        for i, points in enumerate(cuts):
            ordered = sorted(points, key=lambda p: distance(p, segments[i]["a"]))
            for a, b in zip(ordered, ordered[1:]):
                na, nb = root((i, a)), root((i, b))
                self.coords[na], self.coords[nb] = a, b
                if na == nb:
                    continue
                edge = {"segment_id": segments[i]["id"], "a": a, "b": b}
                self.adj[na].append((nb, edge))
                self.adj[nb].append((na, edge))
        self.pin_nodes, self.pin_issues = {}, {}
        self.node_pins = defaultdict(list)
        # A pin that failed to attach still marks its candidate nodes: tracing must not
        # slip through a marked terminal just because its attachment was inconclusive.
        self.node_unattached = defaultdict(list)
        for pid, candidates in pin_candidates.items():
            nodes = {root((i, q)) for i, q, dist in candidates}
            if len(nodes) == 1:
                n = next(iter(nodes))
                self.pin_nodes[pid] = n
                self.node_pins[n].append(pid)
            else:
                self.pin_issues[pid] = "NO_LINE_AT_PIN" if not nodes else "AMBIGUOUS_PIN_ATTACHMENT"
                for n in nodes:
                    self.node_unattached[n].append(pid)

    def trace(self, pin_id):
        if pin_id not in self.pins:
            raise ValueError("Pin bulunamadı.")
        start = self.pin_nodes.get(pin_id)
        result = {"source_id": pin_id, "targets": [], "edges": [], "open_ends": [], "branch_points": [],
                  "unattached_pins": [], "issues": []}
        if start is None:
            result["issues"].append(self.pin_issues[pin_id])
            return result
        return self._reach(start, pin_id, result)

    def trace_from_point(self, point, tolerance=PIN_ATTACH):
        """Follow the drawn lines from a bare coordinate: the far side of a sheet continuation."""
        result = {"source_id": None, "source_point": list(point), "targets": [], "edges": [],
                  "open_ends": [], "branch_points": [], "unattached_pins": [], "issues": []}
        nodes = {n for n, p in self.coords.items() if distance(p, point) <= tolerance}
        if len(nodes) != 1:
            result["issues"].append("NO_NODE_AT_POINT" if not nodes else "AMBIGUOUS_NODE_AT_POINT")
            return result
        return self._reach(next(iter(nodes)), None, result)

    def _reach(self, start, pin_id, result):
        queue, paths, visited_edges = deque([start]), {start: []}, set()  # noqa: E501
        while queue:
            n = queue.popleft()
            other_pins = [p for p in self.node_pins[n] if p != pin_id]
            if other_pins:
                for other in other_pins:
                    result["targets"].append({"pin_id": other, "path": paths[n], "relation": "DRAWN_REACHABILITY_ONLY"})
                if n != start:
                    continue  # Never traverse a device/terminal through a pin.
            blocked = [p for p in self.node_unattached[n] if p != pin_id]
            if blocked and n != start:
                # Fail closed: an inconclusive marked terminal ends the trace instead of
                # letting the far end look directly reachable.
                for p in blocked:
                    if p not in result["unattached_pins"]:
                        result["unattached_pins"].append(p)
                continue
            neighbours = {m for m, edge in self.adj[n]}
            if len(neighbours) > 2:
                result["branch_points"].append(self.coords[n])
            if len(neighbours) == 1 and n != start and not other_pins:
                result["open_ends"].append({"point": self.coords[n], "reason": "UNMARKED_END_OR_CONTINUATION"})
            for m, edge in self.adj[n]:
                key = (edge["segment_id"], pt(edge["a"]), pt(edge["b"]))
                if key not in visited_edges:
                    visited_edges.add(key)
                    result["edges"].append(edge)
                if m not in paths:
                    paths[m] = paths[n] + [edge]
                    queue.append(m)
        if result["unattached_pins"]:
            result["issues"].append("UNATTACHED_PIN_ON_PATH")
        if result["branch_points"]:
            result["issues"].append("BRANCH_ORDER_NOT_INFERRED")
        if result["open_ends"]:
            result["issues"].append("UNRESOLVED_OPEN_ENDS")
        return result
