"""
Orthogonal channel router for the v2.0 collaboration.

Why this exists
---------------
The v1.0 diagram was drawn by a router that sent every sequence flow between the
same pair of columns down the same mid-x, and every message flow between the
same pair of pools down the same mid-y. Measured with tools/analyse_layout.py
that produced 142 overlapping sequence-flow segments (18,951 px of shared
length) and 448 overlapping message-flow segments. Every individual line was
straight and orthogonal; they simply all ran in the same corridors.

How this one is different
-------------------------
The drawing is treated as a channel routing problem.

  * Elements sit on a column / row grid. Columns are separated by vertical
    channels, rows by horizontal corridors.
  * Every flow leaves the right edge of its source and enters the left edge of
    its target, at a port offset unique to that flow, so two flows never start
    from the same point.
  * The vertical leg of a route runs inside a vertical channel on a track. Two
    segments share a track only when their y ranges are clear of each other by
    TRACK_SEP, so no two vertical segments are ever parallel-adjacent.
  * Horizontal legs are allocated the same way, on their own x ranges.
  * Backward flows go to a loop corridor below the pool instead of cutting back
    through the middle.
  * Message flows use their own risers plus a channel in the gap between pools,
    and are fed through the same allocator so they cannot land on top of a
    sequence flow either.

Order of work matters: rows fix the y coordinates, y coordinates fix the demand
on each vertical channel, channel width fixes the columns, and only then can the
horizontal spans be allocated. place() runs those phases in that order.
"""

# ------------------------------------------------------------------ geometry --
POOL_HEADER = 28
LANE_HEADER = 26
LANE_LABEL_W = 30
LANE_PAD = 28
POOL_GAP = 104
POOL_PAD_TOP = 16
POOL_PAD_LEFT = 96
POOL_PAD_RIGHT = 80
POOL_PAD_BOTTOM = 46          # the loop corridor lives in here

ROW_H = 142
ELEM_W, ELEM_H = 152, 92
EVT = 36
GW = 50
BND_DEPTH = 40                # extra row height when boundary events hang below it
BND_REACH = EVT / 2           # how far a boundary event pokes into the corridor
BND_PITCH = EVT + 6           # centre-to-centre gap between two boundary events

V_PITCH = 13
H_PITCH = 13
TRACK_SEP = 11
CHANNEL_MIN = 48
GAP_TRACK_PITCH = 15

TASK_KINDS = {"utask", "stask", "subprocess", "callactivity"}
GATEWAY_KINDS = {"xg", "ig", "pg", "eg"}
BOUNDARY_KINDS = {"bndtimer", "bnderror", "bndmsg", "bndcomp"}
EVENT_KINDS = {"start", "msgstart", "timerstart", "end", "endterminate",
               "catch", "ctimer", "throw", "throwcomp", "bndcomp"}


def size_of(kind):
    if kind in TASK_KINDS:
        return ELEM_W, ELEM_H
    if kind in GATEWAY_KINDS:
        return GW, GW
    return EVT, EVT


def _row_height(pool, lane_idx, row_idx, bnd_hosts=frozenset()):
    """Row height, grown when the row carries an expanded subprocess.

    A row that hosts boundary events is grown too. A boundary event straddles
    the bottom edge of its host and reaches BND_REACH px into the corridor
    underneath, which is exactly where that corridor's horizontal tracks want to
    run. Without the extra room a line is drawn across the circle.
    """
    tall = ROW_H
    for node in pool.nodes.values():
        if node.lane != lane_idx or node.row != row_idx:
            continue
        if node.kind == "subprocess" and node.opts.get("inner"):
            tall = max(tall, node.h + 44)
        if node.id in bnd_hosts:
            tall = max(tall, ROW_H + BND_DEPTH)
    return tall


class Node:
    def __init__(self, nid, kind, name, lane, row, col, **opts):
        self.id, self.kind, self.name = nid, kind, name
        self.lane, self.row, self.col = lane, row, col
        self.opts = opts
        self.w, self.h = size_of(kind)
        self.x = self.y = 0.0
        self.host = None
        self.exit_off, self.entry_off = {}, {}
        self.msg_entry_off = {}

    @property
    def is_boundary(self):
        return self.kind in BOUNDARY_KINDS

    @property
    def left(self):
        return self.x - self.w / 2

    @property
    def right(self):
        return self.x + self.w / 2

    @property
    def top(self):
        return self.y - self.h / 2

    @property
    def bottom(self):
        return self.y + self.h / 2


class Flow:
    def __init__(self, src, tgt, cond=None, name=None, default=False):
        self.src, self.tgt, self.cond, self.name, self.default = src, tgt, cond, name, default
        self.id = None
        self.owner = None
        self.points = []
        self.p = {}

    def __repr__(self):
        return "Flow(%s->%s)" % (self.src, self.tgt)


class MessageFlow:
    def __init__(self, src_pool, src_el, tgt_pool, tgt_el, name=None):
        self.src_pool, self.src_el = src_pool, src_el
        self.tgt_pool, self.tgt_el = tgt_pool, tgt_el
        self.name = name
        self.id = None
        self.points = []


class Lane:
    def __init__(self, name, rows):
        self.name, self.rows = name, rows
        self.y = self.h = 0.0


class Pool:
    def __init__(self, pid, name, process_id=None):
        self.id, self.name, self.process_id = pid, name, process_id
        self.lanes, self.nodes, self.flows = [], {}, []
        self.x = self.y = self.w = self.h = 0.0
        self.rows_y = {}
        self.index = 0

    def lane(self, name, rows):
        self.lanes.append(Lane(name, rows))
        return len(self.lanes) - 1

    def n(self, nid, kind, name, lane, row, col, **opts):
        node = Node(nid, kind, name, lane, row, col, **opts)
        self.nodes[nid] = node
        return node

    def f(self, src, tgt, cond=None, name=None, default=False):
        flow = Flow(src, tgt, cond, name, default)
        flow.owner = self
        self.flows.append(flow)
        return flow


class Router:
    def __init__(self, pools, message_flows):
        self.pools = pools
        self.message_flows = message_flows
        self.by_id = {p.id: p for p in pools}
        for i, p in enumerate(pools):
            p.index = i
        self.chan_w = CHANNEL_MIN
        self.col_x = {}
        self.v_track = {}          # (pool_id, channel) -> {flow_index: x}
        self.h_track = {}          # (pool_id, corridor) -> {flow_index: y}
        self.gap_track = {}        # gap index -> {msg_index: y}
        self.gaps = []
        self.problems = []

    # ===================================================================== --
    def place(self):
        self._rows()
        self._corridors()
        self._ports()
        self._plan_sequence()
        self._geometry()
        self._optimise_corridors()        # trade route length for fewer crossings
        self._check()

    def _geometry(self):
        """Everything that depends on the chosen corridors.

        Kept as its own phase because the crossing optimiser rewrites a flow's
        corridor and then asks for the whole drawing to be measured again.
        Nothing before `_geometry` depends on a coordinate, so this is the
        cheapest place to re-enter.
        """
        self._plan_message_columns()      # column indices only, no x yet
        self._size_channels()             # sequence and message risers together
        self._columns()
        self._alloc_vertical()
        self._alloc_message_tracks()
        self._alloc_horizontal()
        self._build_sequence_points()
        self._plan_message_gap()          # gap tracks need the columns
        self._build_message_points()
        self._resolve_collisions()        # last few stubs that still land together
        self._unclip()                    # and the last few runs drawn over a shape

    # ------------------------------------------------------------- phase 1 --
    def _rows(self):
        y = POOL_PAD_TOP
        for pool in self.pools:
            pool.x = 160.0
            pool.y = y
            cy = y + POOL_HEADER
            bnd_hosts = {n.opts.get("attach") for n in pool.nodes.values() if n.is_boundary}
            for li, lane in enumerate(pool.lanes):
                lane.y = cy
                # a row holding an embedded subprocess has to be tall enough for
                # the box to sit clear of the rows above and below it, otherwise
                # neighbouring runs cut straight through the subprocess
                lane.row_h = [_row_height(pool, li, r, bnd_hosts)
                              for r in range(lane.rows)]
                lane.h = LANE_HEADER + sum(lane.row_h)
                top = cy + LANE_HEADER
                for r in range(lane.rows):
                    pool.rows_y[(li, r)] = top + sum(lane.row_h[:r]) + lane.row_h[r] / 2
                cy += lane.h + (LANE_PAD if li < len(pool.lanes) - 1 else 0)
            pool.h = cy - y + POOL_PAD_BOTTOM
            # boundary events ride on their host's grid cell; without this their
            # outgoing flows are routed as if they started in column 0
            for node in pool.nodes.values():
                if node.is_boundary:
                    host = pool.nodes.get(node.opts.get("attach"))
                    if host is None:
                        raise ValueError("boundary %s has no host %r"
                                         % (node.id, node.opts.get("attach")))
                    node.host = host
                    node.lane, node.row, node.col = host.lane, host.row, host.col
            for node in pool.nodes.values():
                node.y = pool.rows_y[(node.lane, node.row)]
            for node in pool.nodes.values():
                if not node.is_boundary or node.host is None:
                    continue
                node.y = node.host.bottom
                sibs = [n for n in pool.nodes.values()
                        if n.is_boundary and n.opts.get("attach") == node.host.id]
                node.bnd_idx = sibs.index(node)
            y += pool.h + POOL_GAP

    def _corridors(self):
        """Horizontal channels inside a pool, top to bottom (list of y values)."""
        self.corridors = {}
        for pool in self.pools:
            rows = sorted(pool.rows_y.items(), key=lambda kv: kv[1])
            ys = [ry for _, ry in rows]
            if not ys:
                self.corridors[pool.id] = [pool.y + POOL_HEADER + 40]
                continue
            out = []
            for a, b in zip(ys, ys[1:]):
                out.append((a + b) / 2)
            last_lane, last_row = max(pool.rows_y, key=lambda k: pool.rows_y[k])
            last_h = pool.lanes[last_lane].row_h[last_row]
            out.append(ys[-1] + last_h / 2)                   # loop corridor
            for li, lane in enumerate(pool.lanes[:-1]):
                out.append(lane.y + lane.h + LANE_PAD / 2)    # lane boundary
            self.corridors[pool.id] = sorted(set(out))

        self.gaps = []
        for a, b in zip(self.pools, self.pools[1:]):
            top = a.y + a.h
            bottom = b.y
            self.gaps.append((top, bottom))

    def _ports(self):
        msg_in = {}
        for mf in self.message_flows:
            tgt = self.by_id[mf.tgt_pool].nodes.get(mf.tgt_el)
            if tgt is not None:
                msg_in[tgt.id] = msg_in.get(tgt.id, 0) + 1
        for pool in self.pools:
            out_n, in_n = {}, {}
            for fl in pool.flows:
                out_n[fl.src] = out_n.get(fl.src, 0) + 1
                in_n[fl.tgt] = in_n.get(fl.tgt, 0) + 1
            for nid, node in pool.nodes.items():
                self._spread(node, out_n.get(nid, 0), node.exit_off)
                seq_in, msg = in_n.get(nid, 0), msg_in.get(nid, 0)
                if msg == 0:
                    self._spread(node, seq_in, node.entry_off)
                    node.msg_entry_off = {}
                    continue
                slots = {}
                self._spread(node, seq_in + msg, slots)
                for i in range(seq_in):
                    node.entry_off[i] = slots[i]
                node.msg_entry_off = {k: slots[seq_in + k] for k in range(msg)}

    @staticmethod
    def _spread(node, count, table):
        if count <= 0:
            return
        if count == 1:
            table[0] = 0.0
            return
        usable = max(14.0, node.h - 26)
        pitch = max(9.5, min(14.0, usable / (count - 1)))
        for i in range(count):
            table[i] = (i - (count - 1) / 2.0) * pitch

    # ------------------------------------------------------------- phase 2 --
    def _is_straight(self, s, t):
        return (not s.is_boundary and not t.is_boundary
                and s.lane == t.lane and s.row == t.row and t.col == s.col + 1)

    def _plan_sequence(self, reuse=False):
        self._corridor_load = {}
        counters = {}
        for pool in self.pools:
            for fl in pool.flows:
                oi = counters.get(("o", fl.src), 0)
                counters[("o", fl.src)] = oi + 1
                ii = counters.get(("i", fl.tgt), 0)
                counters[("i", fl.tgt)] = ii + 1
                fl.p["oi"], fl.p["ii"] = oi, ii

        for pool in self.pools:
            corridors = self.corridors[pool.id]
            for fl in pool.flows:
                s, t = pool.nodes[fl.src], pool.nodes[fl.tgt]
                sy = s.y + s.exit_off.get(fl.p["oi"], 0.0)
                if s.is_boundary:
                    sy += getattr(s, "bnd_idx", 0.0) * 14.0
                ty = t.y + t.entry_off.get(fl.p["ii"], 0.0)
                p = fl.p
                p.update(s=s, t=t, pool=pool, sy=sy, ty=ty)
                if self._is_straight(s, t):
                    p["mode"] = "straight"
                    continue
                # a branch that drops straight down its own column is the most
                # common shape in the whole model, so it gets a single segment
                # rather than a trip around the loop corridor
                if t.col == s.col and not self._blocked_between(pool, s, t):
                    p["mode"] = "vertical"
                    continue
                p["back"] = t.col <= s.col
                if reuse and p.get("corridor") is not None:
                    # the crossing optimiser already decided this one; rebuilding
                    # the plan must not quietly move it back
                    p["chan_a"] = s.col
                    p["chan_b"] = t.col - 1
                    p["mode"] = "dogleg" if p["chan_a"] == p["chan_b"] else "channel"
                    continue
                if p["back"]:
                    corridor = corridors[-1]
                else:
                    lo, hi = sorted((s.y, t.y))
                    mid = (lo + hi) / 2
                    between = [c for c in corridors if lo + 8 < c < hi - 8]
                    pool_of = between or corridors
                    ranked = sorted(pool_of, key=lambda y: abs(y - mid))[:6]
                    load = self._corridor_load
                    corridor = min(ranked, key=lambda y: (load.get((pool.id, y), 0), abs(y - mid)))
                    load[(pool.id, corridor)] = load.get((pool.id, corridor), 0) + 1
                p["corridor"] = corridor
                p["chan_a"] = s.col                    # channel right of the source
                p["chan_b"] = t.col - 1                # channel left of the target
                p["mode"] = "dogleg" if p["chan_a"] == p["chan_b"] else "channel"

    @staticmethod
    def _blocked_between(pool, s, t):
        """Is there another box in this column between the two rows?"""
        lo, hi = sorted((s.y, t.y))
        for n in pool.nodes.values():
            if n is s or n is t or n.col != s.col or n.is_boundary:
                continue
            if lo + 4 < n.y < hi - 4:
                return True
        return False

    def _v_demand(self, pool, fl):
        """y ranges this flow occupies in each vertical channel."""
        p = fl.p
        out = []
        if p["mode"] in ("straight", "vertical"):
            return out
        if p["mode"] == "dogleg":
            out.append((p["chan_a"], p["sy"], p["ty"]))
        else:
            out.append((p["chan_a"], p["sy"], p["corridor"]))
            out.append((p["chan_b"], p["corridor"], p["ty"]))
        return out

    def _size_channels(self):
        spans = {}
        for pool in self.pools:
            for fl in pool.flows:
                for ch, y0, y1 in self._v_demand(pool, fl):
                    spans.setdefault((pool.id, ch), []).append((fl, min(y0, y1), max(y0, y1)))
        for key, items in self._msg_vspans.items():
            spans.setdefault(key, []).extend(items)
        for key in spans:
            spans[key].sort(key=lambda r: (r[1], str(r[0])))
        self.v_spans = spans
        # Sequence tracks and message risers get separate halves of the channel.
        # All pools share the same column grid, so a riser in pool A and one in
        # pool B land on the same x unless they are told apart globally.
        seq_tracks, msg_by_col = {}, {}
        for (pool_id, ch), items in spans.items():
            seq = [(lo, hi) for tag, lo, hi in items if not isinstance(tag, tuple)]
            if seq:
                seq_tracks[ch] = max(seq_tracks.get(ch, 0), self._tracks_needed(seq))
            for tag, lo, hi in items:
                if isinstance(tag, tuple):
                    # every pool shares the column grid, so risers must be told
                    # apart across the whole diagram, not pool by pool
                    msg_by_col.setdefault(ch, []).append((lo, hi))
        self.seq_band = max(list(seq_tracks.values()) or [1]) * V_PITCH
        self.msg_band = max([self._tracks_needed(v) for v in msg_by_col.values()] or [1]) * V_PITCH
        self.chan_w = max(CHANNEL_MIN, self.seq_band + self.msg_band + 20)

    def _columns(self):
        self.content_x0 = POOL_PAD_LEFT + 34 + ELEM_W / 2
        for pool in self.pools:
            max_col = max([n.col for n in pool.nodes.values()] or [0])
            pool.content_x0 = POOL_PAD_LEFT + 34 + ELEM_W / 2
            for c in range(-1, max_col + 1):
                self.col_x[(pool.id, c)] = pool.content_x0 + c * (ELEM_W + self.chan_w)
            for node in pool.nodes.values():
                node.x = self.col_x[(pool.id, node.col)]
            self._place_boundaries(pool)
            if not pool.nodes:
                pool.w = 900
                continue
            right = self.col_x[(pool.id, max_col)] + ELEM_W / 2
            pool.w = right + POOL_PAD_RIGHT + self.chan_w / 2 + 20

    def _place_boundaries(self, pool):
        for node in pool.nodes.values():
            if not node.is_boundary:
                continue
            host = pool.nodes.get(node.opts.get("attach"))
            if host is None:
                raise ValueError("boundary %s has no host %r" % (node.id, node.opts.get("attach")))
            node.host = host
            node.col = host.col
            node.row = host.row
            node.lane = host.lane
            sibs = [n for n in pool.nodes.values()
                    if n.is_boundary and n.opts.get("attach") == host.id]
            idx = sibs.index(node)
            node.x = host.left + 24 + idx * BND_PITCH

    # ------------------------------------------------------------- phase 3 --
    def _alloc_vertical(self):
        for key, spans in self.v_spans.items():
            pool_id, ch = key
            centre = self._channel_left(pool_id, ch) + 10 + self.seq_band / 2
            ends, track = [], {}
            for i, (_fl, lo, hi) in enumerate(spans):
                for ti, end in enumerate(ends):
                    if end + TRACK_SEP <= lo:
                        ends[ti] = hi
                        track[i] = ti
                        break
                else:
                    ends.append(hi)
                    track[i] = len(ends) - 1
            n = max(1, len(ends))
            self.v_track[key] = {i: centre + (ti - (n - 1) / 2.0) * V_PITCH
                                 for i, ti in track.items()}

    def _alloc_horizontal(self):
        self.h_spans = {}
        for pool in self.pools:
            for fl in pool.flows:
                p = fl.p
                if p["mode"] != "channel":
                    continue
                xa = self.col_x[(pool.id, p["chan_a"])] + ELEM_W / 2 + self.chan_w / 2
                xb = self.col_x[(pool.id, p["chan_b"])] + ELEM_W / 2 + self.chan_w / 2
                self.h_spans.setdefault((pool.id, p["corridor"]), []).append(
                    (fl, min(xa, xb), max(xa, xb)))
        for key, spans in self.h_spans.items():
            pool_id, corridor = key
            order = sorted(range(len(spans)), key=lambda i: spans[i][1])
            ends, track = [], {}
            for i in order:
                lo, hi = spans[i][1], spans[i][2]
                for ti, end in enumerate(ends):
                    if end + TRACK_SEP <= lo:
                        ends[ti] = hi
                        track[i] = ti
                        break
                else:
                    ends.append(hi)
                    track[i] = len(ends) - 1
            n = max(1, len(ends))
            room = ROW_H - ELEM_H - 12
            pitch = max(8.0, min(H_PITCH, room / n))
            centre = corridor
            self.h_track[key] = {i: centre + (ti - (n - 1) / 2.0) * pitch
                                 for i, ti in track.items()}

    def _clear_corridor(self, pool_id, corridor, spans, half):
        """Slide a track band off any boundary event it would run through.

        A boundary event hangs half in and half out of the bottom edge of its
        host, so it reaches into the corridor underneath. The band is centred on
        the corridor and grows upwards as tracks are added, which is how a line
        ends up drawn across the circle. Nudging the whole band clear costs a few
        pixels and removes the last 'line through a shape' defects.
        """
        pool = self.by_id[pool_id]
        lo_x = min(sp[1] for sp in spans)
        hi_x = max(sp[2] for sp in spans)
        obs_lo = obs_hi = None
        for node in pool.nodes.values():
            if not node.is_boundary:
                continue
            if node.right < lo_x or node.left > hi_x:
                continue
            # only the row this corridor actually belongs to: a circle six rows
            # away shares nothing with this band, and letting it vote moves the
            # band across half the pool
            if abs(node.y - corridor) > ROW_H:
                continue
            obs_lo = node.top if obs_lo is None else min(obs_lo, node.top)
            obs_hi = node.bottom if obs_hi is None else max(obs_hi, node.bottom)
        if obs_lo is None:
            return corridor
        band_lo, band_hi = corridor - half, corridor + half
        if band_hi < obs_lo - 2 or band_lo > obs_hi + 2:
            return corridor
        limit = ROW_H / 2.0
        below = obs_hi + 4 + half
        above = obs_lo - 4 - half
        if abs(below - corridor) <= abs(above - corridor):
            return min(below, corridor + limit)
        return max(above, corridor - limit)

    def _h_y(self, pool, corridor, fl):
        key = (pool.id, corridor)
        for i, (f, _, _) in enumerate(self.h_spans.get(key, [])):
            if f is fl:
                return self.h_track[key][i]
        return corridor

    def _v_x(self, pool, ch, fl):
        key = (pool.id, ch)
        for i, (f, _, _) in enumerate(self.v_spans.get(key, [])):
            if f is fl:
                return self.v_track[key][i]
        return self.col_x[(pool.id, ch)] + ELEM_W / 2 + self.chan_w / 2

    def _build_sequence_points(self):
        for pool in self.pools:
            for fl in pool.flows:
                p = fl.p
                s, t = p["s"], p["t"]
                if p["mode"] == "straight":
                    # One horizontal line, so both ends share a y. The level
                    # comes from the source's exit offset when the source has
                    # several branches, and from the target's entry offset when
                    # several flows converge on one target.
                    off = (s.exit_off.get(p["oi"], 0.0) if len(s.exit_off) > 1
                           else t.entry_off.get(p["ii"], 0.0))
                    ty = t.y + off
                    fl.points = [(s.right, ty), (t.left, ty)]
                    continue
                if p["mode"] == "vertical":
                    off = s.exit_off.get(p["oi"], 0.0)
                    lim = max(10.0, min(s.w, t.w) / 2 - 22)
                    off = max(-lim, min(lim, off))
                    x0 = s.x + off
                    x1 = t.x + off
                    fl.points = self._dedupe([(x0, s.bottom), (x0, t.top)] if abs(x0 - x1) < 1
                                             else [(x0, s.bottom), (x0, (s.bottom + t.top) / 2),
                                                   (x1, (s.bottom + t.top) / 2), (x1, t.top)])
                    continue
                xa = self._v_x(pool, p["chan_a"], fl)
                if p["mode"] == "dogleg":
                    fl.points = [(s.right, p["sy"]), (xa, p["sy"]),
                                 (xa, p["ty"]), (t.left, p["ty"])]
                    continue
                xb = self._v_x(pool, p["chan_b"], fl)
                hy = self._h_y(pool, p["corridor"], fl)
                fl.points = [(s.right, p["sy"]), (xa, p["sy"]), (xa, hy),
                             (xb, hy), (xb, p["ty"]), (t.left, p["ty"])]
                if p["back"]:
                    fl.points = [(s.right, p["sy"]), (xa, p["sy"]), (xa, hy),
                                 (xb, hy), (xb, p["ty"]), (t.left, p["ty"])]
                fl.points = self._dedupe(fl.points)

    @staticmethod
    def _dedupe(pts):
        out = [pts[0]]
        for q in pts[1:]:
            if abs(q[0] - out[-1][0]) > 0.6 or abs(q[1] - out[-1][1]) > 0.6:
                out.append(q)
        return out

    # ------------------------------------------------------------- messages --
    def _plan_message_columns(self):
        """Everything a message route needs except x coordinates."""
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
            sch = src.col if src else self._last_col(sp)
            tch = (tgt.col - 1) if tgt else self._last_col(tp)
            self._msg_plan[idx] = dict(sp=sp, tp=tp, gap=gap, downward=downward,
                                       src=src, tgt=tgt, sch=sch, tch=tch)
            self._msg_src_count[src.id if src else sp.id] = \
                self._msg_src_count.get(src.id if src else sp.id, 0) + 1
            self._msg_tgt_count[tgt.id if tgt else tp.id] = \
                self._msg_tgt_count.get(tgt.id if tgt else tp.id, 0) + 1
            gy = self.gaps[gap][0]
            self._msg_plan[idx]["k_src"] = k_src
            self._msg_plan[idx]["k_tgt"] = k_tgt
            if src is not None:
                d = 1 if downward else -1
                y0 = (src.bottom if downward else src.top) + d * (10 + k_src * 12)
            else:
                y0 = (sp.y + 14 + k_src * 13) if downward else (sp.y + sp.h - 14 - k_src * 13)
            self._msg_vspans.setdefault((sp.id, sch), []).append((("msg", idx, 0), y0, gy))
            if tgt is not None:
                ty = tgt.y + tgt.msg_entry_off.get(k_tgt, 0.0)
            else:
                # a black box participant has no element to attach to, so the
                # message lands on the pool edge. It still needs its own riser
                # track, otherwise every message to that supplier shares one
                # line down the whole diagram.
                ty = (tp.y + 14) if downward else (tp.y + tp.h - 14)
            self._msg_plan[idx]["ty"] = ty
            self._msg_vspans.setdefault((tp.id, tch), []).append((("msg", idx, 1), gy, ty))

    def _channel_left(self, pool_id, ch):
        return self.content_x0 + ch * (ELEM_W + self.chan_w) + ELEM_W / 2

    def _msg_x(self, pool, ch, tag):
        key = ("msgchan", ch)
        return self.msg_track.get(key, {}).get(
            tag, self._channel_left(None, ch) + 10 + self.seq_band + self.msg_band / 2)

    def _alloc_message_tracks(self):
        """One global set of tracks per column index, shared by every pool."""
        by_col = {}
        for (pool_id, ch), items in self.v_spans.items():
            for tag, lo, hi in items:
                if isinstance(tag, tuple):
                    by_col.setdefault(ch, []).append((tag, min(lo, hi), max(lo, hi)))
        self.msg_track = {}
        for ch, entries in by_col.items():
            # Risers share a track when their y ranges clear each other. Giving
            # every riser its own slot removes the last overlaps but pushes the
            # canvas past 14000 px wide, which is a worse drawing overall.
            entries.sort(key=lambda r: (r[1], r[0]))
            ends, track = [], {}
            for i, (_tag, lo, hi) in enumerate(entries):
                for ti, end in enumerate(ends):
                    if end + TRACK_SEP <= lo:
                        ends[ti] = hi
                        track[i] = ti
                        break
                else:
                    ends.append(hi)
                    track[i] = len(ends) - 1
            n = max(1, len(ends))
            base = self._channel_left(None, ch) + 10 + self.seq_band + self.msg_band / 2
            self.msg_track[("msgchan", ch)] = {
                entries[i][0]: base + (ti - (n - 1) / 2.0) * V_PITCH
                for i, ti in track.items()}

    def _plan_message_gap(self):
        spans = {}
        for idx, mp in self._msg_plan.items():
            sp, tp = mp["sp"], mp["tp"]
            xa = self._msg_x(sp, mp["sch"], ("msg", idx, 0))
            xb = self._msg_x(tp, mp["tch"], ("msg", idx, 1))
            mp["xa"], mp["xb"] = xa, xb
            spans.setdefault(mp["gap"], []).append((idx, min(xa, xb), max(xa, xb)))
        for gap, items in spans.items():
            top, bottom = self.gaps[gap]
            order = sorted(range(len(items)), key=lambda i: items[i][1])
            ends, track = [], {}
            for i in order:
                lo, hi = items[i][1], items[i][2]
                for ti, end in enumerate(ends):
                    if end + TRACK_SEP * 1.6 <= lo:
                        ends[ti] = hi
                        track[i] = ti
                        break
                else:
                    ends.append(hi)
                    track[i] = len(ends) - 1
            n = max(1, len(ends))
            band = bottom - top
            centre = top + band / 2
            self.gap_track[gap] = {}
            for i, ti in track.items():
                idx = items[i][0]
                # keep at least 10 px between two message lines crossing the same
                # gap; if that needs more room than the gap has, the outermost
                # tracks use the pool padding either side rather than being
                # squeezed until they read as one line
                pitch = max(10.0, min(GAP_TRACK_PITCH, (band - 16) / max(1, n)))
                y = centre + (ti - (n - 1) / 2.0) * pitch
                self.gap_track[gap][idx] = y


    @staticmethod
    def _last_col(pool):
        return max([n.col for n in pool.nodes.values()] or [0])

    def _build_message_points(self):
        for idx, mp in enumerate(self.message_flows):
            p = self._msg_plan[idx]
            src, tgt = p["src"], p["tgt"]
            gy = self.gap_track[p["gap"]][idx]
            xa, xb = p["xa"], p["xb"]
            d = 1 if p["downward"] else -1
            kk = p.get("k_src", 0)
            s_y = (((src.bottom if p["downward"] else src.top) + d * (10 + kk * 12)) if src
                   else ((p["sp"].y + 14 + kk * 13) if p["downward"]
                         else (p["sp"].y + p["sp"].h - 14 - kk * 13)))
            s_x = src.x if src else p["sp"].x + p["sp"].w / 2
            t_y = p.get("ty", tgt.y) if tgt else p["tp"].y + POOL_HEADER
            t_x = tgt.x if tgt else p["tp"].x + p["tp"].w / 2
            # down (or up) from the source through its channel, across the
            # gap on this message flow's own track, then into the target row
            pts = [(s_x, s_y), (xa, s_y), (xa, gy), (xb, gy), (xb, t_y)]
            if tgt is not None:
                pts.append((tgt.left, t_y))
            mp.points = self._dedupe(pts)

    # ------------------------------------------------------- clip removal --
    @staticmethod
    def _jog(pts, i, delta):
        """Redraw one horizontal run of a polyline `delta` px lower or higher.

        The run keeps its connection: when it is the first or last segment a
        short vertical stub is inserted at that end, so the line still leaves the
        shape edge it started from.
        """
        a, b = pts[i], pts[i + 1]
        yd = a[1] + delta
        if i == 0:
            out = [pts[0], (pts[0][0], yd), (b[0], yd)] + list(pts[2:])
        elif i + 1 == len(pts) - 1:
            out = list(pts[:i]) + [(a[0], yd), (b[0], yd), pts[-1]]
        else:
            out = list(pts)
            out[i] = (a[0], yd)
            out[i + 1] = (b[0], yd)
        return Router._dedupe(out)

    def _boxes(self):
        out = {}
        for pool in self.pools:
            for node in pool.nodes.values():
                out[node.id] = (node.left + 1, node.top + 1,
                                node.right - 1, node.bottom - 1)
        return out

    @staticmethod
    def _hits(a, b, boxes, skip):
        """Is any sample along this run inside a box it does not belong to?"""
        n = max(2, int(abs(b[0] - a[0]) / 4) + 1)
        for k in range(1, n):
            t = k / float(n)
            x = a[0] + (b[0] - a[0]) * t
            y = a[1] + (b[1] - a[1]) * t
            for sid, (x0, y0, x1, y1) in boxes.items():
                if sid in skip:
                    continue
                if x0 < x < x1 and y0 < y < y1:
                    return True
        return False

    @staticmethod
    def _parallel_overlap(m, o):
        """Two collinear segments closer than PARALLEL_TOL that share length."""
        mh = abs(m[0][1] - m[1][1]) < 0.6
        oh = abs(o[0][1] - o[1][1]) < 0.6
        if mh != oh:
            return False
        if mh:
            if abs(m[0][1] - o[0][1]) >= 6.0:
                return False
            a0, a1 = sorted((m[0][0], m[1][0]))
            b0, b1 = sorted((o[0][0], o[1][0]))
        else:
            if abs(m[0][0] - o[0][0]) >= 6.0:
                return False
            a0, a1 = sorted((m[0][1], m[1][1]))
            b0, b1 = sorted((o[0][1], o[1][1]))
        return min(a1, b1) - max(a0, b0) > 1.0

    def _unclip(self, rounds=3):
        """Move a horizontal run off a shape it is drawn across.

        Two boundary events on one host sit on the same edge a few pixels apart,
        so a line leaving the left one and heading right runs straight across the
        right one. Shifting that run by a few pixels and closing the gap with a
        short vertical stub fixes it and leaves the connection on the shape edge.
        Every candidate move is checked against the boxes and against every other
        segment before it is kept, so this can only remove a defect.
        """
        ends = {}
        for pool in self.pools:
            for fl in pool.flows:
                ends[fl] = {fl.src, fl.tgt}
        for mf in getattr(self, "msg_routes", []):
            ends[mf] = {mf.src_el, mf.tgt_el}
        boxes = self._boxes()
        for _ in range(rounds):
            fixed = 0
            for fl, skip in ends.items():
                pts = list(fl.points)
                if len(pts) < 2:
                    continue
                for i in range(len(pts) - 1):
                    a, b = pts[i], pts[i + 1]
                    if abs(a[1] - b[1]) > 0.6 or abs(a[0] - b[0]) < 1.0:
                        continue
                    if not self._hits(a, b, boxes, skip):
                        continue
                    segs = self._all_segments()
                    for delta in (18, -18, 26, -26, 36, -36):
                        cand = self._jog(pts, i, delta)
                        if len(cand) < 2:
                            continue
                        bad = False
                        for k in range(len(cand) - 1):
                            c, d = cand[k], cand[k + 1]
                            if abs(c[1] - d[1]) < 0.6 and self._hits(c, d, boxes, skip):
                                bad = True
                                break
                            if any(self._parallel_overlap((c, d), (o[1], o[2]))
                                   for o in segs if o[0] is not fl):
                                bad = True
                                break
                        if bad:
                            continue
                        fl.points = cand
                        pts = list(cand)
                        fixed += 1
                        break
            if not fixed:
                break

    # ------------------------------------------------- crossing optimiser --
    def _all_segments(self):
        """Every drawn segment, tagged with the flow that owns it."""
        out = []
        for pool in self.pools:
            for fl in pool.flows:
                pts = fl.points
                for a, b in zip(pts, pts[1:]):
                    out.append((fl, a, b))
        for mf in getattr(self, "msg_routes", []):
            pts = mf.points
            for a, b in zip(pts, pts[1:]):
                out.append((mf, a, b))
        return out

    @staticmethod
    def _crosses(a, b):
        """Do two axis-parallel segments cut each other in their interiors?"""
        ah = abs(a[0][1] - a[1][1]) < 0.6
        bh = abs(b[0][1] - b[1][1]) < 0.6
        if ah == bh:
            return False
        h, v = (a, b) if ah else (b, a)
        hy = h[0][1]
        hx0, hx1 = (h[0][0], h[1][0]) if h[0][0] < h[1][0] else (h[1][0], h[0][0])
        vx = v[0][0]
        vy0, vy1 = (v[0][1], v[1][1]) if v[0][1] < v[1][1] else (v[1][1], v[0][1])
        return hx0 + 0.8 < vx < hx1 - 0.8 and vy0 + 0.8 < hy < vy1 - 0.8

    def _count_crossings(self, fl, segs, pts):
        mine = [(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
        if not mine:
            return 0
        bx0 = min(min(a[0], b[0]) for a, b in mine)
        bx1 = max(max(a[0], b[0]) for a, b in mine)
        by0 = min(min(a[1], b[1]) for a, b in mine)
        by1 = max(max(a[1], b[1]) for a, b in mine)
        n = 0
        for other, a, b in segs:
            if other is fl:
                continue
            if (min(a[0], b[0]) > bx1 or max(a[0], b[0]) < bx0
                    or min(a[1], b[1]) > by1 or max(a[1], b[1]) < by0):
                continue
            for m in mine:
                if self._crosses(m, (a, b)):
                    n += 1
                    break
        return n

    def _candidate_points(self, pool, fl, corridor):
        p = fl.p
        s, t = p["s"], p["t"]
        xa = self._v_x(pool, p["chan_a"], fl)
        xb = self._v_x(pool, p["chan_b"], fl)
        pts = [(s.right, p["sy"]), (xa, p["sy"]), (xa, corridor),
               (xb, corridor), (xb, p["ty"]), (t.left, p["ty"])]
        return self._dedupe(pts)

    def _optimise_corridors(self, rounds=6, keep=20):
        """Move each horizontal run to the corridor that cuts fewest lines.

        The first pass picks the least-loaded corridor nearest the middle of the
        jump: it spreads the ink out but says nothing about crossings. This pass
        measures instead of guessing. For every dogleg it tries the corridors its
        own rows allow, counts how many other segments the resulting polyline
        would cut, keeps the best and redraws. It stops when a round changes
        nothing, which the numbers reach after two or three.
        """
        for _ in range(rounds):
            segs = self._all_segments()
            moved = 0
            for pool in self.pools:
                corridors = self.corridors[pool.id]
                for fl in pool.flows:
                    p = fl.p
                    if p.get("mode") != "channel" or len(fl.points) < 2:
                        continue
                    s, t = p["s"], p["t"]
                    lo, hi = sorted((s.y, t.y))
                    inside = [c for c in corridors if lo + 8 < c < hi - 8]
                    pool_of = inside or corridors
                    cur = p["corridor"]
                    ranked = sorted(pool_of, key=lambda y: abs(y - cur))[:keep]
                    best = cur
                    best_cost = self._count_crossings(fl, segs, fl.points)
                    for cand in ranked:
                        if cand == cur:
                            continue
                        cost = self._count_crossings(
                            fl, segs, self._candidate_points(pool, fl, cand))
                        if cost < best_cost:
                            best, best_cost = cand, cost
                    if best != cur:
                        p["corridor"] = best
                        moved += 1
            if not moved:
                break
            self._plan_sequence(reuse=True)
            self._geometry()

    # -------------------------------------------------------------- sanity --
    def _check(self):
        """The horizontal pitch adapts to the room available, so a corridor is
        only a problem if even the tightest readable pitch will not fit."""
        limit = ROW_H - ELEM_H
        for key, spans in getattr(self, "h_spans", {}).items():
            n = len(spans)
            if n * 8.0 > limit:
                self.problems.append(
                    "corridor %s needs %d px for %d horizontal runs but only %d px available"
                    % (key, n * 8, n, int(limit)))

    @staticmethod
    def _tracks_needed(spans):
        if not spans:
            return 1
        ends = []
        for lo, hi in sorted((min(a, b), max(a, b)) for a, b in spans):
            for i, end in enumerate(ends):
                if end + TRACK_SEP <= lo:
                    ends[i] = hi
                    break
            else:
                ends.append(hi)
        return len(ends)


    # ------------------------------------------------- last-resort tidy-up --
    @staticmethod
    def _flat(a, b):
        return abs(a[1] - b[1]) < 0.6, abs(a[0] - b[0]) < 0.6

    def _stubs(self):
        """The first and last segment of every routed flow, as line records."""
        out = []
        for pool in self.pools:
            for fl in pool.flows:
                self._collect_stubs(out, fl, fl.points)
        for mp in self.msg_routes:
            self._collect_stubs(out, mp, mp.points)
        return out

    @staticmethod
    def _collect_stubs(out, fl, pts):
        if len(pts) < 2:
            return
        for which, (a, b) in (("first", (pts[0], pts[1])), ("last", (pts[-2], pts[-1]))):
            horiz, vert = Router._flat(a, b)
            if horiz:
                out.append([fl, which, "h", a[1], min(a[0], b[0]), max(a[0], b[0])])
            elif vert:
                out.append([fl, which, "v", a[0], min(a[1], b[1]), max(a[1], b[1])])

    def _resolve_collisions(self):
        """Nudge stubs that still share a line.

        The allocators keep whole corridors apart, but the short first and last
        segments of a route leave the grid and can still land on each other.
        Moving one of them sideways by a few pixels is harmless - it only shifts
        where the line meets the shape edge - and it removes the last handful of
        overlaps the pitch rules cannot.
        """
        self.msg_routes = [mf for mf in self.message_flows]
        for _ in range(6):
            stubs = self._stubs()
            moved = 0
            for i in range(len(stubs)):
                for j in range(i + 1, len(stubs)):
                    a, b = stubs[i], stubs[j]
                    if a[0] is b[0] or a[2] != b[2]:
                        continue
                    if abs(a[3] - b[3]) > 6:
                        continue
                    if min(a[5], b[5]) - max(a[4], b[4]) <= 1:
                        continue
                    if self._nudge(b[0], b[1], b[2], 9.0):
                        moved += 1
            if not moved:
                break

    @staticmethod
    def _nudge(fl, which, orient, delta):
        pts = fl.points
        if len(pts) < 2:
            return False
        idx = (0, 1) if which == "first" else (-2, -1)
        p, q = pts[idx[0]], pts[idx[1]]
        if orient == "h":
            newp, newq = (p[0], p[1] + delta), (q[0], q[1] + delta)
        else:
            newp, newq = (p[0] + delta, p[1]), (q[0] + delta, q[1])
        if idx[0] == 0:
            pts[0], pts[1] = newp, newq
        else:
            pts[-2], pts[-1] = newp, newq
        return True
