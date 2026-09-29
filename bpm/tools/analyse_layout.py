#!/usr/bin/env python3
"""
Measure the drawing quality of a BPMN file's diagram interchange section.

This exists because "the lines look tangled" is not something you can act on.
The analyser turns that into counts: how many flow segments run on top of each
other, how many are diagonal, how many cross, how many pass through a shape
they are not connected to, and how much clear space there is around each pool.

Usage:  python3 analyse_layout.py <file.bpmn>
"""

import math
import re
import sys
from collections import defaultdict

PARALLEL_TOL = 6.0      # px; closer than this and two parallel lines read as one
CROSS_TOL = 1.0


def parse(xml):
    shapes = {}
    for m in re.finditer(
            r'<bpmndi:BPMNShape id="([^"]+)" bpmnElement="([^"]+)"([^>]*)>\s*'
            r'<dc:Bounds x="(-?[\d.]+)" y="(-?[\d.]+)" width="([\d.]+)" height="([\d.]+)"',
            xml):
        sid, el, attrs, x, y, w, h = m.groups()
        shapes[el] = dict(id=el, kind="participant" if "isHorizontal" in attrs else "node",
                          x=float(x), y=float(y), w=float(w), h=float(h))

    edges = {}
    for m in re.finditer(r'<bpmndi:BPMNEdge id="[^"]+" bpmnElement="([^"]+)">(.*?)</bpmndi:BPMNEdge>',
                         xml, re.S):
        eid, body = m.groups()
        pts = [(float(a), float(b)) for a, b in
               re.findall(r'<di:waypoint x="(-?[\d.]+)" y="(-?[\d.]+)"', body)]
        edges[eid] = pts

    flow_ids = set(re.findall(r'<bpmn:sequenceFlow id="([^"]+)"', xml))
    msg_ids = set(re.findall(r'<bpmn:messageFlow id="([^"]+)"', xml))
    pool_of = {}
    for m in re.finditer(r'<bpmndi:BPMNShape id="(P_\w+)_di" bpmnElement="(P_\w+)" isHorizontal="true">\s*'
                         r'<dc:Bounds x="(-?[\d.]+)" y="(-?[\d.]+)" width="([\d.]+)" height="([\d.]+)"', xml):
        pool_of[m.group(2)] = (float(m.group(3)), float(m.group(4)), float(m.group(5)), float(m.group(6)))
    return shapes, edges, flow_ids, msg_ids, pool_of


def segments(points):
    return [(points[i], points[i + 1]) for i in range(len(points) - 1)]


def seg_kind(a, b):
    if abs(a[0] - b[0]) < 0.5:
        return "v"
    if abs(a[1] - b[1]) < 0.5:
        return "h"
    return "d"


def overlap_len(s1, s2, kind):
    """Length of collinear overlap between two same-orientation segments."""
    if kind == "h":
        if abs(s1[0][1] - s2[0][1]) > PARALLEL_TOL:
            return 0.0
        lo = max(min(s1[0][0], s1[1][0]), min(s2[0][0], s2[1][0]))
        hi = min(max(s1[0][0], s1[1][0]), max(s2[0][0], s2[1][0]))
        return max(0.0, hi - lo)
    if abs(s1[0][0] - s2[0][0]) > PARALLEL_TOL:
        return 0.0
    lo = max(min(s1[0][1], s1[1][1]), min(s2[0][1], s2[1][1]))
    hi = min(max(s1[0][1], s1[1][1]), max(s2[0][1], s2[1][1]))
    return max(0.0, hi - lo)


def crosses(a1, a2, b1, b2):
    """Do two axis-aligned segments properly cross (not merely touch)?"""
    ka, kb = seg_kind(a1, a2), seg_kind(b1, b2)
    if ka == kb or "d" in (ka, kb):
        return False
    h1, h2, v1, v2 = (a1, a2, b1, b2) if ka == "h" else (b1, b2, a1, a2)
    hx0, hx1 = sorted((h1[0], h2[0]))
    vx = v1[0]
    vy0, vy1 = sorted((v1[1], v2[1]))
    hy = h1[1]
    return hx0 + CROSS_TOL < vx < hx1 - CROSS_TOL and vy0 + CROSS_TOL < hy < vy1 - CROSS_TOL


def bbox_hit(p, shapes, skip_ids):
    for sid, s in shapes.items():
        if sid in skip_ids or s["kind"] == "participant":
            continue
        if s["x"] + 1 < p[0] < s["x"] + s["w"] - 1 and s["y"] + 1 < p[1] < s["y"] + s["h"] - 1:
            return sid
    return None


def sample(points, step=4.0):
    out = []
    for a, b in segments(points):
        d = math.dist(a, b)
        n = max(2, int(d / step))
        for i in range(n + 1):
            t = i / n
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    return out


def hidden_children(xml):
    """Ids that live inside a collapsed sub-process.

    Those steps carry diagram interchange so the box can be opened in the
    Modeler, but a collapsed box draws none of it. Measuring them would report
    overlaps between two lines that are never on the page together, so they are
    left out of every count below.
    """
    out = set()
    for m in re.finditer(r'<bpmndi:BPMNShape id="[^"]+" bpmnElement="([^"]+)" '
                         r'isExpanded="false"', xml):
        sid = m.group(1)
        for mm in re.finditer(r'id="(%s_[^"]+)"' % re.escape(sid), xml):
            out.add(mm.group(1))
    return out


def main(path):
    xml = open(path, encoding="utf-8").read()
    shapes, edges, flow_ids, msg_ids, pools = parse(xml)
    hidden = hidden_children(xml)
    shapes = {k: v for k, v in shapes.items() if k not in hidden}
    edges = {k: v for k, v in edges.items() if k not in hidden}

    seq = {k: v for k, v in edges.items() if k in flow_ids}
    msg = {k: v for k, v in edges.items() if k in msg_ids}

    print("=" * 74)
    print("LAYOUT REPORT  %s" % path.split("/")[-1])
    print("=" * 74)
    print("shapes %d | sequence flows %d | message flows %d | pools %d"
          % (len(shapes), len(seq), len(msg), len(pools)))

    # ---------- 1. collinear overlap between different flows ----------
    for label, group in (("sequence", seq), ("message", msg)):
        segs = []
        for eid, pts in group.items():
            for s in segments(pts):
                k = seg_kind(*s)
                if k != "d":
                    segs.append((eid, s, k))
        worst = []
        n_ov = 0
        total_ov = 0.0
        for i in range(len(segs)):
            for j in range(i + 1, len(segs)):
                if segs[i][0] == segs[j][0]:
                    continue
                if segs[i][2] != segs[j][2]:
                    continue
                L = overlap_len(segs[i][1], segs[j][1], segs[i][2])
                if L > 1.0:
                    n_ov += 1
                    total_ov += L
                    worst.append((L, segs[i][0], segs[j][0]))
        worst.sort(reverse=True)
        print("\n[%s flows] overlapping/parallel-adjacent segment pairs: %d "
              "(total overlap %.0f px)" % (label, n_ov, total_ov))
        for L, a, b in worst[:5]:
            print("    %.0f px  %s  <->  %s" % (L, a, b))

    # ---------- 2. diagonal segments ----------
    diag = defaultdict(float)
    for label, group in (("sequence", seq), ("message", msg)):
        for eid, pts in group.items():
            for a, b in segments(pts):
                if seg_kind(a, b) == "d":
                    diag[label] += math.dist(a, b)
    print("\n[diagonals] sequence %.0f px total, message %.0f px total"
          % (diag["sequence"], diag["message"]))

    # ---------- 3. crossings ----------
    seq_segs = [(e, s) for e, p in seq.items() for s in segments(p) if seg_kind(*s) != "d"]
    n_cross = 0
    for i in range(len(seq_segs)):
        for j in range(i + 1, len(seq_segs)):
            if seq_segs[i][0] == seq_segs[j][0]:
                continue
            if crosses(*seq_segs[i][1], *seq_segs[j][1]):
                n_cross += 1
    print("[crossings] sequence-flow segment crossings: %d" % n_cross)

    # ---------- 4. flows passing through unrelated shapes ----------
    # a line legitimately starts and ends inside its own source/target shape,
    # so those two are excluded; anything else it passes through is a defect
    endpoints = {}
    for m in re.finditer(r'<bpmn:sequenceFlow id="([^"]+)" sourceRef="([^"]+)" targetRef="([^"]+)"', xml):
        endpoints[m.group(1)] = {m.group(2), m.group(3)}
    for m in re.finditer(r'<bpmn:messageFlow id="([^"]+)" sourceRef="([^"]+)" targetRef="([^"]+)"', xml):
        endpoints[m.group(1)] = {m.group(2), m.group(3)}

    hits = defaultdict(int)
    for eid, pts in list(seq.items()) + list(msg.items()):
        skip = endpoints.get(eid, set())
        # a step inside a subprocess runs within its own subprocess box, so the
        # box is a container, not an obstruction
        if "_f_" in eid:
            skip = set(skip) | {eid.split("_f_")[0]}
        for p in sample(pts):
            hit = bbox_hit(p, shapes, skip)
            if hit:
                hits[(eid, hit)] += 1
    print("[through-shapes] (flow, shape) pairs where a line runs inside an unrelated shape: %d"
          % len(hits))
    for (e, s), c in list(hits.items())[:5]:
        print("    %s passes through %s" % (e, s))

    # ---------- 5. bends per flow ----------
    bends = [len(p) - 2 for p in seq.values()]
    if bends:
        import statistics
        print("\n[bends] sequence flows: mean %.1f, max %d, flows with >4 bends: %d"
              % (statistics.mean(bends), max(bends), sum(1 for b in bends if b > 4)))

    # ---------- 6. pool gaps and lane presence ----------
    ordered = sorted(pools.items(), key=lambda kv: kv[1][1])
    gaps = []
    for (n1, a), (n2, b) in zip(ordered, ordered[1:]):
        gaps.append(b[1] - (a[1] + a[3]))
    lanes = len(re.findall(r"<bpmn:lane ", xml))
    print("\n[pools] %d pools, %d lanes; clear gap between pools: min %d px, mean %d px"
          % (len(pools), lanes, min(gaps) if gaps else 0,
             sum(gaps) / len(gaps) if gaps else 0))

    # ---------- 7. node alignment ----------
    cols = defaultdict(int)
    for sid, s in shapes.items():
        if s["kind"] == "node":
            cols[round(s["x"])] += 1
    print("[alignment] distinct node left-edges: %d for %d nodes"
          % (len(cols), sum(1 for s in shapes.values() if s["kind"] == "node")))

    # ---------- 8. collapsed subprocesses / call activities ----------
    print("[containment] subProcess elements: %d | callActivity elements: %d"
          % (len(re.findall(r"<bpmn:subProcess ", xml)), len(re.findall(r"<bpmn:callActivity ", xml))))
    print("=" * 74)


if __name__ == "__main__":
    main(sys.argv[1])
