"""
v3.0 builder: one hospital pool, the outside participants in a single row beneath it.

What changed against v2.0
-------------------------
v2.0 drew the collaboration as fourteen pools stacked down the page, one per
desk, with the hospital's own teams talking to each other by message flow. That
is not how the case study reads: the nine desks are one organisation sharing one
process, and a message flow between two desks of the same organisation claims a
hand-off that does not exist. This builder draws the operational model the way
the strategic model reads - one hospital pool, responsibilities as lanes, and a
message flow only where an independent participant is really on the other end.

Two things therefore needed new code.

  lanes   The hospital pool carries three responsibility lanes, each holding the
          teams that answer for that responsibility. The router still lays out
          only the leaf lanes; the parent lanes are derived from them, and the
          BPMN writes them as a childLaneSet because that is what the schema and
          the Modeler expect.

  bus     The outside participants sit side by side in one row under the pool.
          The router's own message routing assumes a vertical stack where two
          participants that exchange a message are neighbours, which is not this
          shape, so the supplier row and the message geometry are supplied here.
          Every message leaves the hospital pool downwards, runs along its own
          track in a dedicated band, and lands on the supplier it belongs to.
"""

import re

from layout_engine import (Router, ELEM_W, V_PITCH, LANE_LABEL_W, POOL_HEADER)
from bpmn_builder_v2 import V2Builder, V2Pool
import layout_engine

# ------------------------------------------------------------- air, please --
# The v2.0 grid was cut for a collaboration of fourteen short pools, where each
# pool's lines had only its own row to cross. One pool nineteen rows deep and
# seventy-four columns wide has to be read as a drawing, not skimmed, so every
# one of the pitches below is opened up from the value that was tuned for v14.
layout_engine.V_PITCH = 14        # gap between two parallel vertical runs (was 11)
layout_engine.TRACK_SEP = 14      # minimum gap two tracks may share (was 11)
layout_engine.H_PITCH = 16        # gap between two horizontal runs (was 13)
layout_engine.GAP_TRACK_PITCH = 24
layout_engine.ROW_H = 168         # a row band, so two rows of tasks visibly differ (was 142)
layout_engine.LANE_PAD = 34       # gap between two team lanes (was 28)
# Task boxes carry sentences. At 152 x 92 the wrap was four lines in a box with
# no margin left; 164 x 108 gives the text room and still fits 74 columns.
layout_engine.ELEM_W = 164
layout_engine.ELEM_H = 108
layout_engine.GW = 56
layout_engine.EVT = 40
layout_engine.CHANNEL_MIN = 78    # and never let two columns close up (was 48)
# A pool whose lanes are nested needs three label strips - the pool's own, the
# responsibility lane's and the team's - before the first column of elements.
# v2.0 allowed 96 px, which was enough for one flat lane and puts a column-0
# event straight on top of the labels here.
layout_engine.POOL_PAD_LEFT = 250
# Two boundary events on one host sit 42 px apart in v2.0, which is less than
# the width of either label, so the two captions are drawn over each other.
layout_engine.BND_PITCH = 64

# ---------------------------------------------------------------- bus band --
BUS_TOP_PAD = 56          # hospital pool bottom -> first message track
BUS_BOTTOM_PAD = 44       # last message track -> supplier row
BUS_TRACK_PITCH = 26
SUPPLIER_H = 74
SUPPLIER_GAP = 64
SUPPLIER_MARGIN = 40


class V3Pool(V2Pool):
    """A pool that can group its leaf lanes under responsibility lanes."""

    def __init__(self, pid, name, process_id=None, **kw):
        super().__init__(pid, name, process_id, **kw)
        self.lane_groups = None       # [(parent name, [leaf lane index, ...])]

    def group_lanes(self, groups):
        self.lane_groups = groups
        return self

    @property
    def black_box(self):
        return not self.process_id


class V3Router(Router):
    """The v2.0 channel router plus a message bus for a horizontal supplier row."""

    def __init__(self, pools, message_flows):
        super().__init__(pools, message_flows)
        self.bus_h = BUS_TOP_PAD + BUS_BOTTOM_PAD + max(
            0, len(message_flows) - 1) * BUS_TRACK_PITCH

    # ------------------------------------------------------------- supplier --
    def _supplier_order(self):
        """Suppliers left to right, by the mean column of the messages they carry.

        It puts each supplier under the part of the pool that talks to it, which
        is what keeps the bus runs short.
        """
        seen = {}
        for mf in self.message_flows:
            for pool_id, el_id, other_id in ((mf.src_pool, mf.src_el, mf.tgt_pool),
                                             (mf.tgt_pool, mf.tgt_el, mf.src_pool)):
                pool = self.by_id[pool_id]
                if not getattr(pool, "black_box", False):
                    continue
                node = self.by_id[other_id].nodes.get(el_id)
                if node is None:
                    continue
                seen.setdefault(pool.id, []).append(node.col)
        rest = [p for p in self.pools[1:] if p.id not in seen]
        ranked = sorted(seen, key=lambda pid: sum(seen[pid]) / float(len(seen[pid])))
        out = [self.by_id[pid] for pid in ranked]
        out.extend(rest)
        return out

    def _plan_sequence(self, reuse=False):
        super()._plan_sequence(reuse=reuse)
        if reuse:
            return
        # v2.0 sends every backward run to the foot of the pool. That is right for
        # a pool three rows deep and wrong for one nineteen rows deep: a loop back
        # from the booking lane to the booking lane would be a round trip through
        # the whole hospital. A backward run is re-seated in the corridor just
        # below the lower of its two rows, and the crossing optimiser is then free
        # to move it again.
        for pool in self.pools:
            corridors = self.corridors[pool.id]
            for fl in pool.flows:
                p = fl.p
                if p.get("mode") != "channel" or not p.get("back"):
                    continue
                lo = max(p["s"].y, p["t"].y)
                # a host with a boundary event hanging off it has already taken
                # the corridor directly underneath, so the return leg goes below
                # the boundary marker rather than through its caption
                for node in (p["s"], p["t"]):
                    if any(b.is_boundary and b.opts.get("attach") == node.id
                           for b in pool.nodes.values()):
                        lo = max(lo, node.bottom + 46)
                below = [c for c in corridors if c > lo - 4]
                if below:
                    p["corridor"] = min(below)

    def _corridors(self):
        """Supplier row on top, hospital pool below it, one bus band between.

        The row goes above rather than below because twelve of the fifteen
        messages start or end in the top four lanes. Under the pool every one of
        those lines would run the full height of a 3,500 px drawing; above it,
        only the three payment and refund lines do.
        """
        super()._corridors()
        hosp = self.pools[0]
        dy = SUPPLIER_H + self.bus_h + BUS_TOP_PAD
        hosp.y += dy
        for lane in hosp.lanes:
            lane.y += dy
        for key in list(hosp.rows_y):
            hosp.rows_y[key] += dy
        for node in hosp.nodes.values():
            node.y += dy
        self.corridors[hosp.id] = [c + dy for c in self.corridors[hosp.id]]
        ext_y = SUPPLIER_MARGIN
        for pool in self.pools[1:]:
            pool.y = ext_y
            pool.h = SUPPLIER_H
        # one gap only, and it is above the pool: (upper bottom, lower top)
        self.gaps = [(ext_y + SUPPLIER_H, hosp.y)]

    def _columns(self):
        super()._columns()
        row = self._supplier_order()
        if not row:
            return
        hosp = self.pools[0]
        n = len(row)
        usable = hosp.w - 2 * SUPPLIER_MARGIN - SUPPLIER_GAP * (n - 1)
        w = max(320.0, usable / n)
        x0 = hosp.x + SUPPLIER_MARGIN
        for i, pool in enumerate(row):
            pool.x = x0 + i * (w + SUPPLIER_GAP)
            pool.w = w

    # -------------------------------------------------------------- messages --
    def _supplier_x(self, pool, k):
        """Where the k-th message lands on a supplier box."""
        return pool.x + 46 + k * 30

    def _plan_message_columns(self):
        """As v2.0, except that a supplier stub reserves no channel width.

        v2.0 reserves a riser track for both ends of every message and keys them
        by column index across the whole diagram. The supplier ends here are
        drawn at the supplier's own x, so reserving tracks for them only widens
        the busiest column - by 15 tracks in this model, which is 195 px on every
        one of the 72 columns.
        """
        self._msg_plan = {}
        self._msg_vspans = {}
        self._msg_src_count = {}
        self._msg_tgt_count = {}
        for idx, mf in enumerate(self.message_flows):
            sp, tp = self.by_id[mf.src_pool], self.by_id[mf.tgt_pool]
            downward = sp.index < tp.index
            gap = sp.index if downward else tp.index
            gap = max(0, min(gap, len(self.gaps) - 1))
            src = sp.nodes.get(mf.src_el)
            tgt = tp.nodes.get(mf.tgt_el)
            k_src = self._msg_src_count.get(src.id if src else sp.id, 0)
            k_tgt = self._msg_tgt_count.get(tgt.id if tgt else tp.id, 0)
            sch = src.col if src else 0
            tch = (tgt.col - 1) if tgt else 0
            ty = (tgt.y + tgt.msg_entry_off.get(k_tgt, 0.0) if tgt is not None
                  else (tp.y + 14 if downward else tp.y + tp.h - 14))
            self._msg_plan[idx] = dict(sp=sp, tp=tp, gap=gap, downward=downward,
                                       src=src, tgt=tgt, sch=sch, tch=tch,
                                       k_src=k_src, k_tgt=k_tgt, ty=ty)
            self._msg_src_count[src.id if src else sp.id] = k_src + 1
            self._msg_tgt_count[tgt.id if tgt else tp.id] = k_tgt + 1
            gy = self.gaps[gap][0]
            if src is not None:
                d = 1 if downward else -1
                y0 = (src.bottom if downward else src.top) + d * (10 + k_src * 12)
                self._msg_vspans.setdefault((sp.id, sch), []).append(
                    (("msg", idx, 0), y0, gy))
            if tgt is not None:
                self._msg_vspans.setdefault((tp.id, tch), []).append(
                    (("msg", idx, 1), gy, ty))

    def _build_message_points(self):
        """Hospital stubs leave the top edge; supplier stubs leave the bottom.

        The v2.0 routine routes a black box message through a channel it picks
        from the box's column index, which for a box with no elements is always
        the first one, and it starts the line 14 px inside the box. Both are wrong
        once the suppliers share a row: the runs would all converge on the left
        and the stubs would be drawn through the pool header.
        """
        for idx, mp in enumerate(self.message_flows):
            p = self._msg_plan[idx]
            src, tgt = p["src"], p["tgt"]
            gy = self.gap_track[p["gap"]][idx]
            pts = []
            if src is not None:
                s_y = src.top - (6 + p.get("k_src", 0) * 12)
                pts += [(src.x, s_y), (p["xa"], s_y), (p["xa"], gy)]
            else:
                x = self._supplier_x(p["sp"], p.get("k_src", 0))
                pts += [(x, p["sp"].y + p["sp"].h), (x, gy)]
            if tgt is not None:
                t_y = tgt.y + tgt.msg_entry_off.get(p.get("k_tgt", 0), 0.0)
                xb = p["xb"]
                pts += [(xb, gy), (xb, t_y), (tgt.left, t_y)]
            else:
                x = self._supplier_x(p["tp"], p.get("k_tgt", 0))
                pts += [(x, gy), (x, p["tp"].y + p["tp"].h)]
            mp.points = self._dedupe(pts)


class V3Builder(V2Builder):
    """v2.0 builder, one hospital pool, nested responsibility lanes."""

    def pool(self, pid, name, **kw):
        p = V3Pool(pid, name, **kw)
        self.pools.append(p)
        return p

    def place(self):
        for pool in self.pools:
            for fl in pool.flows:
                fl.id = self.uid("Flow")
        for i, mf in enumerate(self.message_flows):
            mf.id = "MessageFlow_%02d" % (i + 1)
        self.router = V3Router(self.pools, self.message_flows)
        self.router.place()
        self._place_annotations()
        return self.router

    # ------------------------------------------------------------ validation --
    def validate(self):
        problems = super().validate()
        for pool in self.pools:
            if getattr(pool, "black_box", False):
                continue
            if pool.lane_groups:
                covered = [i for _n, idxs in pool.lane_groups for i in idxs]
                if sorted(covered) != list(range(len(pool.lanes))):
                    problems.append("%s: lane groups must cover every leaf lane once"
                                    % pool.name)
            for node in pool.nodes.values():
                if node.is_boundary:
                    continue
                # a compensation handler is deliberately unreachable by sequence
                # flow in both directions: the engine enters it through the
                # compensation boundary and it ends when the job completes
                if node.opts.get("for_compensation"):
                    continue
                kind = node.kind
                outs = [f for f in pool.flows if f.src == node.id]
                ins = [f for f in pool.flows if f.tgt == node.id]
                if not outs and not kind.startswith("end"):
                    problems.append("%s: %s has no outgoing flow" % (pool.name, node.id))
                if not ins and not kind.endswith("start"):
                    problems.append("%s: %s has no incoming flow" % (pool.name, node.id))
            # a start event is reached by message flow, not by a sequence flow
            for node in pool.nodes.values():
                if node.kind in ("msgstart", "timerstart"):
                    if [f for f in pool.flows if f.tgt == node.id]:
                        problems.append("%s: start event %s has a sequence flow in"
                                        % (pool.name, node.id))
        for mf in self.message_flows:
            for pool_id, el_id in ((mf.src_pool, mf.src_el), (mf.tgt_pool, mf.tgt_el)):
                pool = next(p for p in self.pools if p.id == pool_id)
                # a black box participant has no elements, so its own id is the
                # endpoint the message flow names
                if getattr(pool, "black_box", False):
                    if el_id != pool.id:
                        problems.append("message flow %s: black box %s cannot carry %s"
                                        % (mf.id, pool_id, el_id))
                    continue
                if el_id not in pool.nodes:
                    problems.append("message flow %s: %s is not an element of %s"
                                    % (mf.id, el_id, pool_id))
        return problems

    # ------------------------------------------------------------------ xml --
    def _lane_xml(self, pool, indent="      "):
        if not pool.lane_groups:
            out = []
            for i, lane in enumerate(pool.lanes):
                out.append('%s<bpmn:lane id="%s_L%d" name="%s">'
                           % (indent, pool.process_id, i, self._esc_lane(lane.name)))
                out.extend(self._lane_refs(pool, i, indent + "  "))
                out.append("%s</bpmn:lane>" % indent)
            return out
        out = []
        for gi, (group_name, idxs) in enumerate(pool.lane_groups):
            out.append('%s<bpmn:lane id="%s_P%d" name="%s">'
                       % (indent, pool.process_id, gi, self._esc_lane(group_name)))
            out.append('%s  <bpmn:childLaneSet id="%s_P%d_child">'
                       % (indent, pool.process_id, gi))
            for i in idxs:
                out.append('%s    <bpmn:lane id="%s_L%d" name="%s">'
                           % (indent, pool.process_id, i, self._esc_lane(pool.lanes[i].name)))
                out.extend(self._lane_refs(pool, i, indent + "      "))
                out.append("%s    </bpmn:lane>" % indent)
            out.append("%s  </bpmn:childLaneSet>" % indent)
            out.append("%s</bpmn:lane>" % indent)
        return out

    @staticmethod
    def _esc_lane(name):
        return (str(name).replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace('"', "&quot;"))

    def _lane_refs(self, pool, lane_idx, indent):
        out = []
        for node in pool.nodes.values():
            if node.lane == lane_idx and not node.is_boundary:
                out.append("%s<bpmn:flowNodeRef>%s</bpmn:flowNodeRef>"
                           % (indent, node.id))
        return out

    def _process_xml(self, pool):
        """As v2.0, but the lanes inside the laneSet are written by _lane_xml."""
        src = super()._process_xml(pool)
        out, i = [], 0
        while i < len(src):
            if "<bpmn:laneSet" in src[i]:
                out.append(src[i])                     # keep the laneSet element
                while i < len(src) and "</bpmn:laneSet>" not in src[i]:
                    i += 1
                out.extend(self._lane_xml(pool))
                out.append(src[i])                     # keep its close tag
                i += 1
                continue
            out.append(src[i])
            i += 1
        return out

    def _lane_geometry(self, pool):
        """Leaf and parent lane rectangles, parents derived from their children."""
        leaves, parents = {}, {}
        for i, lane in enumerate(pool.lanes):
            leaves[i] = (pool.x + LANE_LABEL_W, lane.y,
                         pool.w - LANE_LABEL_W, lane.h)
        if pool.lane_groups:
            for gi, (_name, idxs) in enumerate(pool.lane_groups):
                top = pool.lanes[idxs[0]].y
                bottom = pool.lanes[idxs[-1]].y + pool.lanes[idxs[-1]].h
                parents[gi] = (pool.x + LANE_LABEL_W, top,
                               pool.w - LANE_LABEL_W, bottom - top)
        return leaves, parents

    def _di_xml(self):
        out = ['  <bpmndi:BPMNDiagram id="BPMNDiagram_1">',
               '    <bpmndi:BPMNPlane id="BPMNPlane_1" bpmnElement="%s">'
               % self.collaboration_id]
        for p in self.pools:
            out.append('      <bpmndi:BPMNShape id="%s_di" bpmnElement="%s" isHorizontal="true">'
                       % (p.id, p.id))
            out.append('        <dc:Bounds x="%.0f" y="%.0f" width="%.0f" height="%.0f" />'
                       % (p.x, p.y, p.w, p.h))
            out.append("      </bpmndi:BPMNShape>")
            if not p.lanes or not p.process_id:
                continue
            leaves, parents = self._lane_geometry(p)
            for gi in sorted(parents):
                x, y, w, h = parents[gi]
                out.append('      <bpmndi:BPMNShape id="%s_P%d_di" bpmnElement="%s_P%d" '
                           'isHorizontal="true">' % (p.process_id, gi, p.process_id, gi))
                out.append('        <dc:Bounds x="%.0f" y="%.0f" width="%.0f" height="%.0f" />'
                           % (x, y, w, h))
                out.append("      </bpmndi:BPMNShape>")
            for i in sorted(leaves):
                x, y, w, h = leaves[i]
                if p.lane_groups:
                    x += LANE_LABEL_W
                    w -= LANE_LABEL_W
                out.append('      <bpmndi:BPMNShape id="%s_L%d_di" bpmnElement="%s_L%d" '
                           'isHorizontal="true">' % (p.process_id, i, p.process_id, i))
                out.append('        <dc:Bounds x="%.0f" y="%.0f" width="%.0f" height="%.0f" />'
                           % (x, y, w, h))
                out.append("      </bpmndi:BPMNShape>")

        body = self._di_body()
        out.extend(body)
        return out

    # ---------------------------------------------------------- edge labels --
    LABEL_PT = 7.2          # px per character at the renderer's 12 px label font
    LABEL_MAX = 250.0

    def _flow_label_bounds(self, name, pts):
        """Where a sequence-flow caption goes: centred on its own line.

        bpmn-js places a label at the middle of the connection by arc length,
        which for a route with three bends is quite often a point on a vertical
        run, or on top of the neighbour's caption. The bounds written here put it
        2 px above the longest horizontal run of the flow it belongs to, so a
        caption is always sitting on the line it explains.
        """
        best = None
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            if abs(y1 - y0) < 0.6 and abs(x1 - x0) > 20:
                if best is None or abs(x1 - x0) > best[2]:
                    best = (min(x0, x1), y0, abs(x1 - x0))
        if best is None:
            (x0, y0), (x1, y1) = pts[0], pts[1]
            best = (min(x0, x1), (y0 + y1) / 2.0, abs(x1 - x0))
        sx, sy, sw = best
        text = self.LABEL_PT * len(name) + 8
        w = max(44.0, min(text, self.LABEL_MAX))
        lines = 1 if text <= w else min(3, int(text / w) + 1)
        h = 15.0 * lines
        return sx + sw / 2.0 - w / 2.0, sy - h - 2.0, w, h

    def _di_body(self):
        """Everything v2.0 writes after the shapes and lanes: elements and edges."""
        src = super()._di_xml()
        cut = len(src) - 2
        for i, line in enumerate(src):
            if "BPMNShape" in line and "bpmnElement=" in line:
                el = line.split('bpmnElement="')[1].split('"')[0]
                if el not in [p.id for p in self.pools] and "_L" not in el:
                    cut = i
                    break
        named = {}
        for pool in self.pools:
            for fl in pool.flows:
                if fl.name and len(fl.points) >= 2:
                    named[fl.id] = (fl.name, fl.points)
        out, cur = [], None
        for line in src[cut:]:
            if "<bpmndi:BPMNEdge" in line:
                m = re.search(r'bpmnElement="([^"]+)"', line)
                cur = m.group(1) if m else None
            # the label is the last child of the edge, so it has to be written
            # before the close tag and not after it
            if "</bpmndi:BPMNEdge>" in line and cur in named:
                name, pts = named[cur]
                x, y, w, h = self._flow_label_bounds(name, pts)
                out.append("        <bpmndi:BPMNLabel>")
                out.append('          <dc:Bounds x="%.0f" y="%.0f" width="%.0f" '
                           'height="%.0f" />' % (x, y, w, h))
                out.append("        </bpmndi:BPMNLabel>")
                cur = None
            out.append(line)
        return out
