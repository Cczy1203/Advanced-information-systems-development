"""
Small builder that turns a declarative description of a BPMN collaboration into
Camunda 8 (Zeebe) flavoured BPMN 2.0 XML, including the diagram interchange
section, so the file opens straight away in Camunda Modeler.

Written for UFCEP6-0-3 (Hospital Patient Referral, Treatment and Administration
System). Kept deliberately plain: one collaboration, one BPMNPlane, one diagram.

Layout model
------------
Every pool is a horizontal band. Inside a band each node sits on a (col, row)
grid. Column 0 is the left-most node of a fragment, row 0 the top row of that
pool. Absolute coordinates are derived from the grid so the whole diagram stays
aligned without hand-tuning hundreds of numbers.
"""

from collections import OrderedDict

# ---------------------------------------------------------------- geometry ---
POOL_HEADER = 30          # the strip at the top of a pool that carries its name
PAD_TOP = 45              # gap between the pool header and the first row
PAD_LEFT = 70
COL_W = 300
ROW_H = 155
TASK_W, TASK_H = 165, 96
EVT_W = EVT_H = 36
GW_W = GW_H = 50
POOL_PAD_RIGHT = 130
POOL_PAD_BOTTOM = 40

XSI = "http://www.w3.org/2001/XMLSchema-instance"
NS = {
    "bpmn": "http://www.omg.org/spec/BPMN/20100524/MODEL",
    "bpmndi": "http://www.omg.org/spec/BPMN/20100524/DI",
    "dc": "http://www.omg.org/spec/DD/20100524/DC",
    "di": "http://www.omg.org/spec/DD/20100524/DI",
    "zeebe": "http://camunda.org/schema/zeebe/1.0",
    "modeler": "http://camunda.org/schema/modeler/1.0",
}

EVENT_KINDS = {"start", "msgstart", "timerstart", "end", "endterminate",
               "catch", "ctimer", "throw", "bndtimer", "bnderror", "bndmsg"}
TASK_KINDS = {"utask", "stask", "subprocess"}
GATEWAY_KINDS = {"xg", "ig", "pg", "eg"}


def esc(text):
    """Escape text for use in XML character data or a double quoted attribute."""
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def feel(expr):
    """Escape a FEEL expression for an attribute value."""
    return esc(expr)


class Node:
    def __init__(self, nid, kind, name, col, row, **kw):
        self.id = nid
        self.kind = kind
        self.name = name
        self.col = col
        self.row = row
        self.opts = kw
        self.x = 0
        self.y = 0

    # -- size helpers ------------------------------------------------------
    @property
    def size(self):
        if self.kind in EVENT_KINDS:
            return EVT_W, EVT_H
        if self.kind in GATEWAY_KINDS:
            return GW_W, GW_H
        return TASK_W, TASK_H

    @property
    def is_boundary(self):
        return self.kind in {"bndtimer", "bnderror", "bndmsg"}

    @property
    def left(self):
        return self.x - self.size[0] / 2

    @property
    def right(self):
        return self.x + self.size[0] / 2

    @property
    def top(self):
        return self.y - self.size[1] / 2

    @property
    def bottom(self):
        return self.y + self.size[1] / 2


class Flow:
    def __init__(self, src, tgt, cond=None, name=None, default=False):
        self.src = src
        self.tgt = tgt
        self.cond = cond
        self.name = name
        self.default = default
        self.id = None


class MessageFlow:
    def __init__(self, src_pool, src_el, tgt_pool, tgt_el, name=None):
        self.src_pool = src_pool
        self.src_el = src_el
        self.tgt_pool = tgt_pool
        self.tgt_el = tgt_el
        self.name = name
        self.id = None


class Pool:
    def __init__(self, pid, name, builder, process_id=None, process_name=None,
                 documentation=None, version_tag="1.0.0"):
        self.id = pid
        self.name = name
        self.builder = builder
        self.process_id = process_id      # None -> black box pool
        self.process_name = process_name
        self.documentation = documentation
        self.version_tag = version_tag
        self.nodes = OrderedDict()
        self.flows = []
        self.x = 0
        self.y = 0
        self.width = 0
        self.height = 0
        self.row_count = 1

    # -- building ----------------------------------------------------------
    def n(self, nid, kind, name, col, row, **kw):
        if nid in self.builder.nodes:
            raise ValueError("duplicate node id: %s" % nid)
        node = Node(nid, kind, name, col, row, **kw)
        self.nodes[nid] = node
        self.builder.nodes[nid] = node
        self.row_count = max(self.row_count, row + 1)
        return node

    def f(self, src, tgt, cond=None, name=None, default=False):
        self.flows.append(Flow(src, tgt, cond, name, default))
        return self.flows[-1]

    def mf(self, src_el, tgt_pool, tgt_el, name=None):
        """Message flow from an element of this pool to an element of tgt_pool."""
        self.builder.message_flows.append(
            MessageFlow(self.id, src_el, tgt_pool, tgt_el, name))

    def mf_in(self, src_pool, src_el, tgt_el, name=None):
        """Message flow arriving from src_pool into an element of this pool."""
        self.builder.message_flows.append(
            MessageFlow(src_pool, src_el, self.id, tgt_el, name))

    # -- layout ------------------------------------------------------------
    def layout(self, x, y):
        self.x, self.y = x, y
        if not self.nodes:
            self.width = 900
            self.height = 110
            return
        main = [n for n in self.nodes.values() if not n.is_boundary]
        max_col = 0
        for node in main:
            max_col = max(max_col, node.col)
            node.x = x + PAD_LEFT + node.col * COL_W + TASK_W / 2
            node.y = y + POOL_HEADER + PAD_TOP + node.row * ROW_H
        # boundary events sit on the bottom edge of the activity they are
        # attached to; siblings are nudged apart so the icons stay readable
        per_host = {}
        for node in self.nodes.values():
            if not node.is_boundary:
                continue
            host = self.nodes.get(node.opts.get("attach"))
            if host is None:
                raise ValueError("boundary %s has no host %r" % (node.id, node.opts.get("attach")))
            idx = per_host.get(host.id, 0)
            per_host[host.id] = idx + 1
            node.x = host.x - host.size[0] / 2 + 30 + idx * 70
            node.y = host.bottom
            max_col = max(max_col, int(round((node.x - x - PAD_LEFT - TASK_W / 2) / COL_W)))
        self.width = PAD_LEFT + max_col * COL_W + TASK_W + POOL_PAD_RIGHT
        self.height = POOL_HEADER + PAD_TOP + self.row_count * ROW_H + POOL_PAD_BOTTOM


class Builder:
    def __init__(self, collaboration_id, collaboration_name=None):
        self.collaboration_id = collaboration_id
        self.collaboration_name = collaboration_name
        self.pools = []
        self.nodes = {}
        self.messages = OrderedDict()   # message name -> correlation key or None
        self.errors = OrderedDict()     # error code -> error name
        self.message_flows = []
        self.definitions_id = "Definitions_hospital_pathway"
        self.target_namespace = "http://bpmn.io/schema/bpmn"
        self.execution_platform = "Camunda Cloud"
        self.execution_platform_version = "8.10.0"
        self.exporter = "Camunda Modeler"
        self.exporter_version = "5.51.0"
        self._ids = {}
        self._prepared = False

    # -- registries --------------------------------------------------------
    def msg(self, name, key=None):
        if name not in self.messages:
            self.messages[name] = key
        elif key is not None and self.messages[name] is None:
            self.messages[name] = key
        elif key is not None and self.messages[name] != key:
            raise ValueError("message %r used with two correlation keys" % name)
        return name

    def error(self, code, name=None):
        self.errors.setdefault(code, name or code)
        return code

    def pool(self, pid, name, **kw):
        p = Pool(pid, name, self, **kw)
        self.pools.append(p)
        return p

    def uid(self, prefix):
        self._ids[prefix] = self._ids.get(prefix, 0) + 1
        return "%s_%02d" % (prefix, self._ids[prefix])

    # -- layout ------------------------------------------------------------
    # -- layout ------------------------------------------------------------
    def prepare(self):
        """Run layout and id assignment exactly once."""
        if self._prepared:
            return
        self.layout()
        for pool in self.pools:
            self._sequence_flows(pool)
        for i, mf in enumerate(self.message_flows):
            mf.id = "MessageFlow_%02d" % (i + 1)
        self._prepared = True

    def layout(self, origin_x=160, origin_y=80, gap=60):
        y = origin_y
        for p in self.pools:
            p.layout(origin_x, y)
            y += p.height + gap
        # Each pool keeps the width its own content needs. Stretching every
        # pool to the widest one leaves a lot of dead space in a collaboration
        # this size.

    # ------------------------------------------------------------- emit ---
    def _ext(self, lines, indent):
        pad = "  " * indent
        if not lines:
            return []
        out = [pad + "<bpmn:extensionElements>"]
        for ln in lines:
            out.append(pad + "  " + ln)
        out.append(pad + "</bpmn:extensionElements>")
        return out

    def _io_mapping(self, node):
        inputs = node.opts.get("inputs") or []
        outputs = node.opts.get("outputs") or []
        if not inputs and not outputs:
            return []
        out = ["<zeebe:ioMapping>"]
        for src, tgt in inputs:
            out.append('<zeebe:input source="%s" target="%s" />' % (feel(src), esc(tgt)))
        for src, tgt in outputs:
            out.append('<zeebe:output source="%s" target="%s" />' % (feel(src), esc(tgt)))
        out.append("</zeebe:ioMapping>")
        return out

    def _headers(self, node):
        headers = node.opts.get("headers")
        if not headers:
            return []
        out = ["<zeebe:taskHeaders>"]
        for k, v in headers.items():
            out.append('<zeebe:header key="%s" value="%s" />' % (esc(k), esc(v)))
        out.append("</zeebe:taskHeaders>")
        return out

    def _message_ref(self, name):
        return "Message_" + name.replace(".", "_").replace("-", "_")

    def _error_ref(self, code):
        return "Error_" + code.replace(".", "_").replace("-", "_")

    def _event_definition_xml(self, node, indent):
        pad = "  " * indent
        kind = node.kind
        out = []
        if kind in ("msgstart", "catch", "throw", "bndmsg"):
            out.append('%s<bpmn:messageEventDefinition id="%s" messageRef="%s" />'
                       % (pad, self.uid("MessageEventDefinition"), self._message_ref(node.opts["msg"])))
        if kind in ("timerstart", "ctimer", "bndtimer"):
            out.append('%s<bpmn:timerEventDefinition id="%s">' % (pad, self.uid("TimerEventDefinition")))
            timer = node.opts["timer"]
            if timer.startswith("="):
                out.append('%s  <bpmn:timeDate xsi:type="bpmn:tFormalExpression">%s</bpmn:timeDate>'
                           % (pad, esc(timer)))
            elif timer.startswith("R"):
                out.append('%s  <bpmn:timeCycle xsi:type="bpmn:tFormalExpression">%s</bpmn:timeCycle>'
                           % (pad, esc(timer)))
            else:
                out.append('%s  <bpmn:timeDuration xsi:type="bpmn:tFormalExpression">%s</bpmn:timeDuration>'
                           % (pad, esc(timer)))
            out.append("%s</bpmn:timerEventDefinition>" % pad)
        if kind == "bnderror":
            out.append('%s<bpmn:errorEventDefinition id="%s" errorRef="%s" />'
                       % (pad, self.uid("ErrorEventDefinition"), self._error_ref(node.opts["error"])))
        if kind == "endterminate":
            out.append('%s<bpmn:terminateEventDefinition id="%s" />' % (pad, self.uid("TerminateEventDefinition")))
        return out

    def _node_xml(self, node, indent):
        pad = "  " * indent
        kind = node.kind
        opts = node.opts
        tag = {
            "start": "bpmn:startEvent", "msgstart": "bpmn:startEvent",
            "timerstart": "bpmn:startEvent", "end": "bpmn:endEvent",
            "endterminate": "bpmn:endEvent", "catch": "bpmn:intermediateCatchEvent",
            "ctimer": "bpmn:intermediateCatchEvent", "throw": "bpmn:intermediateThrowEvent",
            "utask": "bpmn:userTask", "stask": "bpmn:serviceTask",
            "subprocess": "bpmn:subProcess",
        }.get(kind)
        if kind in GATEWAY_KINDS:
            tag = {"xg": "bpmn:exclusiveGateway", "ig": "bpmn:inclusiveGateway",
                   "pg": "bpmn:parallelGateway", "eg": "bpmn:eventBasedGateway"}[kind]
        if kind in ("bndtimer", "bnderror", "bndmsg"):
            tag = "bpmn:boundaryEvent"

        attrs = ['id="%s"' % node.id]
        if node.name:
            attrs.append('name="%s"' % esc(node.name))
        if kind.startswith("bnd"):
            attrs.append('attachedToRef="%s"' % opts["attach"])
            if kind == "bndtimer":
                attrs.append('cancelActivity="%s"' % ("false" if opts.get("non_interrupting") else "true"))
            elif kind == "bndmsg":
                attrs.append('cancelActivity="%s"' % ("false" if opts.get("non_interrupting") else "true"))
        if kind == "xg" and opts.get("default"):
            attrs.append('default="%s"' % opts["default"])
        if kind == "ig" and opts.get("default"):
            attrs.append('default="%s"' % opts["default"])
        out = ["%s<%s %s>" % (pad, tag, " ".join(attrs))]

        if opts.get("documentation"):
            out.append("%s  <bpmn:documentation>%s</bpmn:documentation>" % (pad, esc(opts["documentation"])))

        ext = []
        if kind == "utask":
            ext.append("<zeebe:userTask />")
            if opts.get("candidate_groups") or opts.get("assignee"):
                a = []
                if opts.get("assignee"):
                    a.append('assignee="%s"' % esc(opts["assignee"]))
                if opts.get("candidate_groups"):
                    a.append('candidateGroups="%s"' % esc(opts["candidate_groups"]))
                ext.append("<zeebe:assignmentDefinition %s />" % " ".join(a))
            if opts.get("form"):
                ext.append('<zeebe:formDefinition formId="%s" bindingType="deployment" />' % esc(opts["form"]))
        if kind == "stask":
            retries = opts.get("retries")
            if retries is not None:
                ext.append('<zeebe:taskDefinition type="%s" retries="%s" />' % (esc(opts["type"]), retries))
            else:
                ext.append('<zeebe:taskDefinition type="%s" />' % esc(opts["type"]))
        if kind == "throw":
            ext.append('<zeebe:taskDefinition type="publish-message" />')
            # The dispatcher worker needs the correlation key as a process
            # variable. Setting it here keeps the key next to the message it
            # belongs to instead of hiding it in the worker.
            opts.setdefault("inputs", [])
            opts["inputs"] = [(opts.get("key") or "=patientRef", "correlationKey")] + list(opts["inputs"])
        ext.extend(self._headers(node))
        ext.extend(self._io_mapping(node))
        out.extend(self._ext(ext, indent + 1))

        for incoming in opts.get("_incoming", []):
            out.append('%s  <bpmn:incoming>%s</bpmn:incoming>' % (pad, incoming))
        for outgoing in opts.get("_outgoing", []):
            out.append('%s  <bpmn:outgoing>%s</bpmn:outgoing>' % (pad, outgoing))
        out.extend(self._event_definition_xml(node, indent + 1))
        out.append("%s</%s>" % (pad, tag))
        return out

    def _sequence_flows(self, pool):
        for flow in pool.flows:
            flow.id = self.uid("Flow")
        # attach incoming/outgoing lists to nodes so the XML carries them
        for node in pool.nodes.values():
            node.opts["_incoming"] = []
            node.opts["_outgoing"] = []
        for flow in pool.flows:
            if flow.src not in pool.nodes:
                raise ValueError("%s: flow source %s is not in pool %s" % (flow.id, flow.src, pool.id))
            if flow.tgt not in pool.nodes:
                raise ValueError("%s: flow target %s is not in pool %s" % (flow.id, flow.tgt, pool.id))
            pool.nodes[flow.src].opts["_outgoing"].append(flow.id)
            pool.nodes[flow.tgt].opts["_incoming"].append(flow.id)
            if flow.default:
                src = pool.nodes[flow.src]
                if src.opts.get("default"):
                    raise ValueError("%s has two default flows" % src.id)
                src.opts["default"] = flow.id

    def to_xml(self):
        self.prepare()
        ns = " ".join('xmlns:%s="%s"' % (k, v) for k, v in NS.items())
        out = ['<?xml version="1.0" encoding="UTF-8"?>']
        out.append('<bpmn:definitions %s xmlns:xsi="%s" id="%s" targetNamespace="%s" '
                   'exporter="%s" exporterVersion="%s" modeler:executionPlatform="%s" '
                   'modeler:executionPlatformVersion="%s">'
                   % (ns, XSI, self.definitions_id, self.target_namespace,
                      self.exporter, self.exporter_version,
                      self.execution_platform, self.execution_platform_version))

        # ---- messages ----------------------------------------------------
        for name, key in self.messages.items():
            key = key or "=patientRef"
            if key:
                out.append('  <bpmn:message id="%s" name="%s">' % (self._message_ref(name), esc(name)))
                out.append("    <bpmn:extensionElements>")
                out.append('      <zeebe:subscription correlationKey="%s" />' % feel(key))
                out.append("    </bpmn:extensionElements>")
                out.append("  </bpmn:message>")
            else:
                out.append('  <bpmn:message id="%s" name="%s" />' % (self._message_ref(name), esc(name)))


        # ---- errors ------------------------------------------------------
        for code, ename in self.errors.items():
            out.append('  <bpmn:error id="%s" name="%s" errorCode="%s" />'
                       % (self._error_ref(code), esc(ename), esc(code)))

        # ---- collaboration ----------------------------------------------
        out.append('  <bpmn:collaboration id="%s">' % self.collaboration_id)
        for p in self.pools:
            if p.process_id:
                out.append('    <bpmn:participant id="%s" name="%s" processRef="%s" />'
                           % (p.id, esc(p.name), p.process_id))
            else:
                out.append('    <bpmn:participant id="%s" name="%s" />' % (p.id, esc(p.name)))
        for mf in self.message_flows:
            out.append('    <bpmn:messageFlow id="%s" sourceRef="%s" targetRef="%s" />'
                       % (mf.id, mf.src_el, mf.tgt_el))
        out.append("  </bpmn:collaboration>")

        # ---- processes ---------------------------------------------------
        for p in self.pools:
            if not p.process_id:
                continue
            out.append('  <bpmn:process id="%s" name="%s" isExecutable="true">'
                       % (p.process_id, esc(p.process_name or p.name)))
            ext = []
            if p.version_tag:
                ext.append('<zeebe:versionTag value="%s" />' % esc(p.version_tag))
            out.extend(self._ext(ext, 2))
            if p.documentation:
                out.append("    <bpmn:documentation>%s</bpmn:documentation>" % esc(p.documentation))
            for node in p.nodes.values():
                out.extend(self._node_xml(node, 2))
            for flow in p.flows:
                cattrs = ' id="%s" sourceRef="%s" targetRef="%s"' % (flow.id, flow.src, flow.tgt)
                if flow.name and p.nodes[flow.src].kind in GATEWAY_KINDS:
                    cattrs += ' name="%s"' % esc(flow.name)
                if flow.cond:
                    out.append("    <bpmn:sequenceFlow%s>" % cattrs)
                    out.append('      <bpmn:conditionExpression xsi:type="bpmn:tFormalExpression">%s</bpmn:conditionExpression>'
                               % esc(flow.cond))
                    out.append("    </bpmn:sequenceFlow>")
                else:
                    out.append("    <bpmn:sequenceFlow%s />" % cattrs)
            out.append("  </bpmn:process>")

        # ---- diagram interchange ----------------------------------------
        out.append('  <bpmndi:BPMNDiagram id="BPMNDiagram_1">')
        out.append('    <bpmndi:BPMNPlane id="BPMNPlane_1" bpmnElement="%s">' % self.collaboration_id)
        for p in self.pools:
            out.append('      <bpmndi:BPMNShape id="%s_di" bpmnElement="%s" isHorizontal="true">'
                       % (p.id, p.id))
            out.append('        <dc:Bounds x="%d" y="%d" width="%d" height="%d" />'
                       % (p.x, p.y, p.width, p.height))
            out.append("      </bpmndi:BPMNShape>")
        for p in self.pools:
            for node in p.nodes.values():
                w, h = node.size
                out.append('      <bpmndi:BPMNShape id="%s_di" bpmnElement="%s">' % (node.id, node.id))
                out.append('        <dc:Bounds x="%d" y="%d" width="%d" height="%d" />'
                           % (node.left, node.top, w, h))
                if node.kind == "utask":
                    out.append('        <bpmndi:BPMNLabel />')
                if node.kind == "eg":
                    out.append('        <bpmndi:BPMNLabel />')
                out.append("      </bpmndi:BPMNShape>")

        # sequence flow edges
        for p in self.pools:
            for flow in p.flows:
                out.append('      <bpmndi:BPMNEdge id="%s_di" bpmnElement="%s">' % (flow.id, flow.id))
                for (wx, wy) in self._route(p, flow):
                    out.append('        <di:waypoint x="%d" y="%d" />' % (wx, wy))
                out.append("      </bpmndi:BPMNEdge>")

        # message flow edges
        for mf in self.message_flows:
            out.append('      <bpmndi:BPMNEdge id="%s_di" bpmnElement="%s">' % (mf.id, mf.id))
            for (wx, wy) in self._route_message(mf):
                out.append('        <di:waypoint x="%d" y="%d" />' % (wx, wy))
            out.append("      </bpmndi:BPMNEdge>")

        out.append("    </bpmndi:BPMNPlane>")
        out.append("  </bpmndi:BPMNDiagram>")
        out.append("</bpmn:definitions>")
        return "\n".join(out) + "\n"

    # ------------------------------------------------------------ routes --
    def _node_anchor(self, pool, node, side):
        if side == "l":
            return (node.left, node.y)
        if side == "r":
            return (node.right, node.y)
        if side == "t":
            return (node.x, node.top)
        return (node.x, node.bottom)

    def _route(self, pool, flow):
        src = pool.nodes[flow.src]
        tgt = pool.nodes[flow.tgt]
        if src.is_boundary:
            sx, sy = src.x, src.bottom
        else:
            sx, sy = src.right, src.y
        tx, ty = tgt.left, tgt.y
        if tgt.is_boundary:
            tx, ty = tgt.x, tgt.top
        if abs(sy - ty) < 4:
            return [(sx, sy), (tx, ty)]
        if tx > sx:
            mid = sx + max(30, (tx - sx) / 2)
            return [(sx, sy), (mid, sy), (mid, ty), (tx, ty)]
        # backward edge (a loop back): dip below both rows
        dip = max(sy, ty) + 55
        return [(sx, sy), (sx + 35, sy), (sx + 35, dip), (tx - 35, dip), (tx - 35, ty), (tx, ty)]

    def _pool_by_id(self, pid):
        for p in self.pools:
            if p.id == pid:
                return p
        raise KeyError(pid)

    def _element_point(self, pool_id, el_id):
        pool = self._pool_by_id(pool_id)
        if el_id in pool.nodes:
            node = pool.nodes[el_id]
            return node.x, node.top, node.bottom, node.left, node.right
        return pool.x + pool.width / 2, pool.y, pool.y + POOL_HEADER, pool.x, pool.x + pool.width

    def _route_message(self, mf):
        sp = self._pool_by_id(mf.src_pool)
        tp = self._pool_by_id(mf.tgt_pool)
        sx, stop, sbot, sl, sr = self._element_point(mf.src_pool, mf.src_el)
        tx, ttop, tbot, tl, tr = self._element_point(mf.tgt_pool, mf.tgt_el)
        if sp is tp:
            return [(int(sx), int(sbot)), (int(tx), int(ttop))]
        if sp.y < tp.y:      # downward
            start = (int(sx), int(sbot))
            end = (int(tx), int(ttop))
        else:                # upward
            start = (int(sx), int(stop))
            end = (int(tx), int(tbot))
        if abs(start[1] - end[1]) < 40:
            return [start, end]
        midy = int((start[1] + end[1]) / 2)
        return [start, (start[0], midy), (end[0], midy), end]
