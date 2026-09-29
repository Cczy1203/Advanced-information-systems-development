"""
v2.0 builder: same semantics as v1.0, new drawing.

Responsibilities split:
  * layout_engine.py decides where everything goes.
  * this file holds the model and writes BPMN 2.0 with the Zeebe extensions.

The v1.0 model is loaded from its own spec rather than being retyped, so the
messages, job types, forms and gateway conditions that were already verified on
the engine carry over unchanged. What changes for v2.0 is structure (lanes and
collapsed subprocesses), behaviour (compensation, a capped retry loop, and an
owner and an exit for every exception branch) and the drawing.
"""

from collections import OrderedDict

from layout_engine import Router, Pool, MessageFlow, POOL_HEADER, LANE_HEADER, LANE_LABEL_W

NS = OrderedDict([
    ("bpmn", "http://www.omg.org/spec/BPMN/20100524/MODEL"),
    ("bpmndi", "http://www.omg.org/spec/BPMN/20100524/DI"),
    ("dc", "http://www.omg.org/spec/DD/20100524/DC"),
    ("di", "http://www.omg.org/spec/DD/20100524/DI"),
    ("zeebe", "http://camunda.org/schema/zeebe/1.0"),
    ("modeler", "http://camunda.org/schema/modeler/1.0"),
])
XSI = "http://www.w3.org/2001/XMLSchema-instance"

TAG = {
    "start": "bpmn:startEvent", "msgstart": "bpmn:startEvent", "timerstart": "bpmn:startEvent",
    "end": "bpmn:endEvent", "endterminate": "bpmn:endEvent",
    "catch": "bpmn:intermediateCatchEvent", "ctimer": "bpmn:intermediateCatchEvent",
    "throw": "bpmn:intermediateThrowEvent", "throwcomp": "bpmn:intermediateThrowEvent",
    "utask": "bpmn:userTask", "stask": "bpmn:serviceTask",
    "subprocess": "bpmn:subProcess", "callactivity": "bpmn:callActivity",
    "xg": "bpmn:exclusiveGateway", "ig": "bpmn:inclusiveGateway",
    "pg": "bpmn:parallelGateway", "eg": "bpmn:eventBasedGateway",
    "bndtimer": "bpmn:boundaryEvent", "bnderror": "bpmn:boundaryEvent",
    "bndmsg": "bpmn:boundaryEvent", "bndcomp": "bpmn:boundaryEvent",
}


def esc(t):
    return (str(t).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


class V2Pool(Pool):
    """A pool that also knows how to write itself out."""

    def __init__(self, pid, name, process_id=None, documentation=None, version_tag=None):
        super().__init__(pid, name, process_id)
        self.documentation = documentation
        self.version_tag = version_tag
        self.annotations = []      # (id, text, node_id_or_None)

    def note(self, nid, text, near=None):
        self.annotations.append((nid, text, near))


class V2Builder:
    def __init__(self):
        self.pools = []
        self.message_flows = []
        self.messages = OrderedDict()
        self.errors = OrderedDict()
        self.collaboration_id = "Collaboration_HospitalPatientPathway"
        self.definitions_id = "Definitions_hospital_pathway_v2"
        self.target_ns = "http://bpmn.io/schema/bpmn"
        self.platform = "Camunda Cloud"
        self.platform_version = "8.10.0"
        self.exporter = "Camunda Modeler"
        self.exporter_version = "5.51.0"
        self._ids = {}
        self.router = None

    # ---------------------------------------------------------------- model --
    def pool(self, pid, name, **kw):
        p = V2Pool(pid, name, **kw)
        self.pools.append(p)
        return p

    def msg(self, name, key=None):
        if name not in self.messages:
            self.messages[name] = key
        elif key and not self.messages[name]:
            self.messages[name] = key
        return name

    def error(self, code, name=None):
        self.errors.setdefault(code, name or code)
        return code

    def uid(self, prefix):
        self._ids[prefix] = self._ids.get(prefix, 0) + 1
        return "%s_%03d" % (prefix, self._ids[prefix])

    def mref(self, name):
        return "Message_" + name.replace(".", "_").replace("-", "_")

    def eref(self, code):
        return "Error_" + code.replace(".", "_").replace("-", "_")

    # ------------------------------------------------------------- validate --
    def validate(self):
        problems = []
        for pool in self.pools:
            for fl in pool.flows:
                if fl.src not in pool.nodes:
                    problems.append("%s: flow source %s missing" % (pool.id, fl.src))
                if fl.tgt not in pool.nodes:
                    problems.append("%s: flow target %s missing" % (pool.id, fl.tgt))
            for node in pool.nodes.values():
                if node.kind == "xg":
                    outs = [f for f in pool.flows if f.src == node.id]
                    defaults = [f for f in outs if f.default]
                    if len(outs) > 1 and len(defaults) != 1:
                        problems.append("%s: exclusive gateway %s needs exactly one default flow"
                                        % (pool.name, node.id))
                if node.kind == "xg":
                    for f in pool.flows:
                        if f.src == node.id and not f.cond and not f.default:
                            problems.append("%s: exclusive gateway %s has an unconditional flow"
                                            % (pool.name, node.id))
                if node.kind == "utask" and not node.opts.get("form"):
                    problems.append("%s: user task %s has no form" % (pool.name, node.id))
                if node.kind == "stask" and not node.opts.get("type"):
                    problems.append("%s: service task %s has no job type" % (pool.name, node.id))
        return problems

    # ------------------------------------------------------------- geometry --
    INNER_PITCH = 176
    INNER_PAD = 46

    # Drawing a subprocess open costs five columns of width.  The router lays
    # nodes on a 165 px pitch, so an open box overlaps whatever sits beside it
    # and neighbouring runs end up cutting through it - measured at 21 lines
    # through an unrelated shape against 4 when the box stays closed.  The steps
    # are still in the file and still execute; only the box is drawn closed.
    EXPAND_SUBPROCESSES = False

    def _size_subprocesses(self):
        for pool in self.pools:
            for node in pool.nodes.values():
                node.close_box = not self.EXPAND_SUBPROCESSES

    def place(self):
        self._size_subprocesses()
        for pool in self.pools:
            for fl in pool.flows:
                fl.id = self.uid("Flow")
        for i, mf in enumerate(self.message_flows):
            mf.id = "MessageFlow_%02d" % (i + 1)
        self.router = Router(self.pools, self.message_flows)
        self.router.place()
        self._place_annotations()
        return self.router

    NOTE_W, NOTE_H = 520, 64
    NOTE_COLS = 3

    def _place_annotations(self):
        """Every note goes in one panel under the collaboration.

        Notes used to sit at the foot of their own pool, which put them straight
        in the path of the message risers running down the diagram. Collecting
        them into one panel below the pools keeps them off every line, and each
        note names the step it refers to so the link is still clear.
        """
        self.notes = []
        for pool in self.pools:
            for (nid, text, near) in pool.annotations:
                label = pool.nodes[near].name if near in pool.nodes else ""
                shown = ("%s - %s" % (label, text)) if label else text
                self.notes.append((nid, shown))
        bottom = max((p.y + p.h) for p in self.pools)
        rows = (len(self.notes) + self.NOTE_COLS - 1) // self.NOTE_COLS
        self.notes_y0 = bottom + 70
        self.notes_bottom = self.notes_y0 + rows * (self.NOTE_H + 18)

    def _annotation_geometry(self, pool=None):
        out = []
        for i, (nid, text) in enumerate(self.notes):
            col, row = i % self.NOTE_COLS, i // self.NOTE_COLS
            out.append((nid, text,
                        190 + col * (self.NOTE_W + 30),
                        self.notes_y0 + row * (self.NOTE_H + 18),
                        self.NOTE_W, self.NOTE_H))
        return out

    # ------------------------------------------------------------------ xml --
    def to_xml(self):
        self.place()
        out = ['<?xml version="1.0" encoding="UTF-8"?>']
        ns = " ".join('xmlns:%s="%s"' % (k, v) for k, v in NS.items())
        out.append('<bpmn:definitions %s xmlns:xsi="%s" id="%s" targetNamespace="%s" '
                   'exporter="%s" exporterVersion="%s" modeler:executionPlatform="%s" '
                   'modeler:executionPlatformVersion="%s">'
                   % (ns, XSI, self.definitions_id, self.target_ns, self.exporter,
                      self.exporter_version, self.platform, self.platform_version))

        for name, key in self.messages.items():
            out.append('  <bpmn:message id="%s" name="%s">' % (self.mref(name), esc(name)))
            out.append("    <bpmn:extensionElements>")
            out.append('      <zeebe:subscription correlationKey="%s" />' % esc(key or "=patientRef"))
            out.append("    </bpmn:extensionElements>")
            out.append("  </bpmn:message>")
        for code, nm in self.errors.items():
            out.append('  <bpmn:error id="%s" name="%s" errorCode="%s" />'
                       % (self.eref(code), esc(nm), esc(code)))

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

        for p in self.pools:
            if p.process_id:
                out.extend(self._process_xml(p))
        out.extend(self._di_xml())
        out.append("</bpmn:definitions>")
        return "\n".join(out) + "\n"

    def _first_executable(self):
        """The pool that carries the note panel.

        A textAnnotation is a process artifact, so the notes have to live inside
        one process. They are hospital notes, so an outside participant is
        skipped even when the router has stacked it first.
        """
        for p in self.pools:
            if p.process_id and not getattr(p, "external", False):
                return p
        for p in self.pools:
            if p.process_id:
                return p
        return None

    def _process_xml(self, pool):
        # A pool can be marked non-executable, which is how an outside
        # participant can be drawn in full without adding another deployable
        # process definition to the batch. See EXTERNAL_PROCESSES_EXECUTABLE in
        # spec_v2.py.
        executable = "true" if getattr(pool, "executable", True) else "false"
        out = ['  <bpmn:process id="%s" name="%s" isExecutable="%s">'
               % (pool.process_id, esc(pool.name), executable)]
        # bpmn:tBaseElement wants documentation before extensionElements, and the
        # engine validates the file against the XSD before it deploys it. Only a
        # pool that carries process-level documentation can expose the order, and
        # until the outside participants were opened up no pool did, so this was
        # latent: bpmn-moddle accepts either order, the Camunda 8 deployer does
        # not, and it rejected the whole collaboration with
        # "cvc-complex-type.2.4.a ... expected supportedInterfaceRef, ioSpecification,
        # ... , laneSet, flowElement, ...".
        if pool.documentation:
            out.append("    <bpmn:documentation>%s</bpmn:documentation>" % esc(pool.documentation))
        ext = []
        if pool.version_tag:
            ext.append('<zeebe:versionTag value="%s" />' % esc(pool.version_tag))
        if ext:
            out.append("    <bpmn:extensionElements>")
            out.extend("      " + e for e in ext)
            out.append("    </bpmn:extensionElements>")

        if pool.lanes and pool.process_id:
            out.append('    <bpmn:laneSet id="%s_lanes">' % pool.process_id)
            for i, lane in enumerate(pool.lanes):
                out.append('      <bpmn:lane id="%s_L%d" name="%s">' % (pool.process_id, i, esc(lane.name)))
                for node in pool.nodes.values():
                    if node.lane == i and not node.is_boundary:
                        out.append("        <bpmn:flowNodeRef>%s</bpmn:flowNodeRef>" % node.id)

                out.append("      </bpmn:lane>")
            out.append("    </bpmn:laneSet>")

        for node in pool.nodes.values():
            out.extend(self._node_xml(pool, node))
        for fl in pool.flows:
            attrs = ' id="%s" sourceRef="%s" targetRef="%s"' % (fl.id, fl.src, fl.tgt)
            if fl.name and pool.nodes[fl.src].kind in ("xg", "ig", "pg", "eg", "eg"):
                attrs += ' name="%s"' % esc(fl.name)
            if fl.cond:
                out.append("    <bpmn:sequenceFlow%s>" % attrs)
                out.append('      <bpmn:conditionExpression xsi:type="bpmn:tFormalExpression">%s'
                           "</bpmn:conditionExpression>" % esc(fl.cond))
                out.append("    </bpmn:sequenceFlow>")
            else:
                out.append("    <bpmn:sequenceFlow%s />" % attrs)

        # artifacts last: the BPMN schema wants them after the flow elements
        for node in pool.nodes.values():
            if node.kind == "bndcomp":
                out.append('    <bpmn:association id="%s_assoc" associationDirection="One" '
                           'sourceRef="%s" targetRef="%s" />' % (node.id, node.id, node.opts["handler"]))
        if pool is self._first_executable():
            # a textAnnotation is a process artifact, so it has to live inside a
            # process; the first executable pool carries the whole note panel
            for nid, text, _x, _y, _w, _h in self._annotation_geometry():
                out.append('    <bpmn:textAnnotation id="%s"><bpmn:text>%s</bpmn:text>'
                           "</bpmn:textAnnotation>" % (nid, esc(text)))
        out.append("  </bpmn:process>")
        return out

    def _node_xml(self, pool, node):
        kind, opts = node.kind, node.opts
        tag = TAG[kind]
        attrs = ['id="%s"' % node.id]
        if node.name:
            attrs.append('name="%s"' % esc(node.name))
        if node.is_boundary:
            attrs.append('attachedToRef="%s"' % opts["attach"])
            if kind in ("bndtimer", "bndmsg"):
                attrs.append('cancelActivity="%s"' % ("false" if opts.get("non_interrupting") else "true"))
        if kind in ("xg", "ig") and any(f.default for f in pool.flows if f.src == node.id):
            dflt = next(f for f in pool.flows if f.src == node.id and f.default)
            attrs.append('default="%s"' % dflt.id)
        if kind == "subprocess" and opts.get("collapsed", True):
            pass  # collapsed is a DI property, handled below
        if kind == "stask" and opts.get("for_compensation"):
            attrs.append('isForCompensation="true"')
        if kind == "callactivity":
            pass

        out = ["    <%s %s>" % (tag, " ".join(attrs))]
        if opts.get("documentation"):
            out.append("      <bpmn:documentation>%s</bpmn:documentation>" % esc(opts["documentation"]))

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
            ext.append('<zeebe:formDefinition formId="%s" bindingType="deployment" />' % esc(opts["form"]))
        if kind == "stask":
            r = opts.get("retries")
            ext.append('<zeebe:taskDefinition type="%s"%s />'
                       % (esc(opts["type"]), ' retries="%s"' % r if r is not None else ""))
        if kind == "throw":
            ext.append('<zeebe:taskDefinition type="publish-message" />')
        if kind == "callactivity":
            ext.append('<zeebe:calledElement processId="%s" propagateAllChildVariables="true" />'
                       % esc(opts["called_element"]))
        for k, v in (opts.get("headers") or {}).items():
            ext.append('<zeebe:header key="%s" value="%s" />' % (esc(k), esc(v)))
        if kind == "throw":
            opts["inputs"] = [(opts.get("key") or "=patientRef", "correlationKey")] + list(opts.get("inputs") or [])
        io = []
        for src, tgt in (opts.get("inputs") or []):
            io.append('<zeebe:input source="%s" target="%s" />' % (esc(src), esc(tgt)))
        for src, tgt in (opts.get("outputs") or []):
            io.append('<zeebe:output source="%s" target="%s" />' % (esc(src), esc(tgt)))
        inner = []
        if any(e.startswith("<zeebe:header") for e in ext):
            heads = [e for e in ext if e.startswith("<zeebe:header")]
            ext = [e for e in ext if not e.startswith("<zeebe:header")]
            inner = ext + ["<zeebe:taskHeaders>"] + heads + ["</zeebe:taskHeaders>"]
        else:
            inner = ext
        if io:
            inner = inner + ["<zeebe:ioMapping>"] + io + ["</zeebe:ioMapping>"]
        if inner:
            out.append("      <bpmn:extensionElements>")
            out.extend("        " + e for e in inner)
            out.append("      </bpmn:extensionElements>")

        for f in pool.flows:
            if f.tgt == node.id:
                out.append("      <bpmn:incoming>%s</bpmn:incoming>" % f.id)
        for f in pool.flows:
            if f.src == node.id:
                out.append("      <bpmn:outgoing>%s</bpmn:outgoing>" % f.id)

        out.extend(self._event_def_xml(node))
        if kind == "subprocess" and opts.get("inner"):
            out.extend(self._subprocess_body(node))
        out.append("    </%s>" % tag)
        return out

    def _subprocess_body(self, node):
        """A collapsed subprocess still carries its steps; only the DI is hidden."""
        sid = node.id
        opts = node.opts
        pad = "      "
        fid = lambda a, b: "%s_f_%s_%s" % (sid, a, b)
        flows = [(f[0], f[1], f[2] if len(f) > 2 else None) for f in opts["inner_flows"]]
        opts = dict(opts, inner_flows=flows)
        start_out = next((fid(a, b) for (a, b, _c) in flows if a == "S"), None)
        end_in = next((fid(a, b) for (a, b, _c) in flows if b == "E"), None)
        out = ['%s<bpmn:startEvent id="%s_Start" name="%s - start">'
               '<bpmn:outgoing>%s</bpmn:outgoing></bpmn:startEvent>'
               % (pad, sid, esc(node.name), start_out)]
        for (kid, kind, name, kopts) in opts["inner"]:
            nid = "%s_%s" % (sid, kid)
            tag = TAG.get(kind)
            if tag is None:
                raise ValueError("subprocess element kind %r is not supported" % kind)
            attrs = 'id="%s" name="%s"' % (nid, esc(name))
            if kind == "xg":
                dflt = next((f for f in opts["inner_flows"]
                             if f[0] == kid and f[2] == "default"), None)
                if dflt:
                    attrs += ' default="%s"' % fid(dflt[0], dflt[1])
            out.append('%s<%s %s>' % (pad, tag, attrs))
            if kopts.get("documentation"):
                out.append('%s  <bpmn:documentation>%s</bpmn:documentation>' % (pad, esc(kopts["documentation"])))
            ext = []
            if kind == "utask":
                ext.append("<zeebe:userTask />")
                if kopts.get("candidate_groups"):
                    ext.append('<zeebe:assignmentDefinition candidateGroups="%s" />'
                               % esc(kopts["candidate_groups"]))
                ext.append('<zeebe:formDefinition formId="%s" bindingType="deployment" />'
                           % esc(kopts["form"]))
            elif kind == "stask":
                ext.append('<zeebe:taskDefinition type="%s"%s />'
                           % (esc(kopts["type"]),
                              ' retries="%s"' % kopts["retries"] if kopts.get("retries") else ""))
            if ext:
                out.append('%s  <bpmn:extensionElements>' % pad)
                out.extend('%s    %s' % (pad, e) for e in ext)
                out.append('%s  </bpmn:extensionElements>' % pad)
            # the schema wants every incoming before any outgoing
            for (a, b, _c) in opts["inner_flows"]:
                if self._inner_id(sid, b) == nid:
                    out.append('%s  <bpmn:incoming>%s</bpmn:incoming>' % (pad, fid(a, b)))
            for (a, b, _c) in opts["inner_flows"]:
                if self._inner_id(sid, a) == nid:
                    out.append('%s  <bpmn:outgoing>%s</bpmn:outgoing>' % (pad, fid(a, b)))
            out.append('%s</%s>' % (pad, tag))
        out.append('%s<bpmn:endEvent id="%s_End" name="%s - end">'
                   '<bpmn:incoming>%s</bpmn:incoming></bpmn:endEvent>'
                   % (pad, sid, esc(node.name), end_in))
        for (a, b, cond) in opts["inner_flows"]:
            if cond and cond != "default":
                out.append('%s<bpmn:sequenceFlow id="%s" name="%s" sourceRef="%s" targetRef="%s">'
                           % (pad, fid(a, b), esc(cond.lstrip("= ").strip()),
                              self._inner_id(sid, a), self._inner_id(sid, b)))
                out.append('%s  <bpmn:conditionExpression xsi:type="bpmn:tFormalExpression">%s'
                           "</bpmn:conditionExpression>" % (pad, esc(cond)))
                out.append("%s</bpmn:sequenceFlow>" % pad)
            else:
                out.append('%s<bpmn:sequenceFlow id="%s" sourceRef="%s" targetRef="%s" />'
                           % (pad, fid(a, b), self._inner_id(sid, a), self._inner_id(sid, b)))
        return out

    @staticmethod
    def _inner_id(sid, key):
        return "%s_Start" % sid if key == "S" else ("%s_End" % sid if key == "E" else "%s_%s" % (sid, key))

    def _event_def_xml(self, node):
        kind, opts = node.kind, node.opts
        pad = "      "
        out = []
        if kind in ("msgstart", "catch", "throw", "bndmsg"):
            out.append('%s<bpmn:messageEventDefinition id="%s" messageRef="%s" />'
                       % (pad, self.uid("MessageEventDefinition"), self.mref(opts["msg"])))
        if kind in ("timerstart", "ctimer", "bndtimer"):
            t = opts["timer"]
            body = ("timeDate" if t.startswith("=") else
                    "timeCycle" if t.startswith("R") else "timeDuration")
            out.append('%s<bpmn:timerEventDefinition id="%s">' % (pad, self.uid("TimerEventDefinition")))
            out.append('%s  <bpmn:%s xsi:type="bpmn:tFormalExpression">%s</bpmn:%s>'
                       % (pad, body, esc(t), body))
            out.append("%s</bpmn:timerEventDefinition>" % pad)
        if kind == "bnderror":
            out.append('%s<bpmn:errorEventDefinition id="%s" errorRef="%s" />'
                       % (pad, self.uid("ErrorEventDefinition"), self.eref(opts["error"])))
        if kind == "bndcomp":
            out.append('%s<bpmn:compensateEventDefinition id="%s" />'
                       % (pad, self.uid("CompensateEventDefinition")))
        if kind == "throwcomp":
            out.append('%s<bpmn:compensateEventDefinition id="%s" />'
                       % (pad, self.uid("CompensateEventDefinition")))
        if kind == "endterminate":
            out.append('%s<bpmn:terminateEventDefinition id="%s" />'
                       % (pad, self.uid("TerminateEventDefinition")))
        return out

    def _inner_order(self, node):
        """Walk the subprocess' own flows so the row reads left to right.

        Listing the steps in declaration order puts a node between two others it
        does not sit between in the flow, which drags a line straight through it.
        A breadth first walk from the inner start event, then the end event, then
        anything only reachable by a loop back, keeps the main chain straight.
        """
        seen, queue = set(), ["S"]
        order = []
        while queue:
            cur = queue.pop(0)
            if cur in seen or cur == "E":
                continue
            seen.add(cur)
            if cur != "S":
                order.append(cur)
            for f in node.opts["inner_flows"]:
                if f[0] == cur and f[1] not in seen and f[1] != "E":
                    queue.append(f[1])
        for (kid, _kind, _name, _o) in node.opts["inner"]:
            if kid not in seen:
                order.append(kid)
        return order

    def _inner_child_positions(self, node):
        """Centre points for a subprocess' own steps, in execution order."""
        order = self._inner_order(node)
        kids = [("__start__", "startEvent")]
        kids += [(k, dict((c[0], c[1]) for c in node.opts["inner"])[k]) for k in order]
        kids += [("__end__", "endEvent")]
        span = (len(kids) - 1) * self.INNER_PITCH
        x0 = node.x - span / 2
        out = []
        for i, (kid, kind) in enumerate(kids):
            if kid == "__start__":
                cid, shape = "%s_Start" % node.id, "startEvent"
            elif kid == "__end__":
                cid, shape = "%s_End" % node.id, "endEvent"
            else:
                cid, shape = "%s_%s" % (node.id, kid), TAG.get(kind, "task").replace("bpmn:", "")
            out.append((cid, shape, x0 + i * self.INNER_PITCH, node.y))
        return out

    def _inner_edge_waypoints(self, node, a, b, pos, depth):
        """A straight run when nothing sits between the two steps, else a dip.

        A loop back to an earlier step, or any flow that would pass over a step
        it does not connect, is dropped below the row on its own line so it does
        not sit on top of the straight ones.
        """
        sx, sy = pos["%s_%s" % (node.id, "Start" if a == "S" else a)]
        tx, ty = pos["%s_%s" % (node.id, "End" if b == "E" else b)]
        lo, hi = min(sx, tx), max(sx, tx)
        blocked = any(lo + 1 < px < hi - 1 for (px, _py) in pos.values())
        if tx > sx and not blocked:
            return [(sx, sy), (tx, ty)]
        dy = sy + 64 + depth * 22
        return [(sx, sy), (sx, dy), (tx, dy), (tx, ty)]

    @staticmethod
    def _inner_box(shape):
        if shape in ("startEvent", "endEvent"):
            return 36, 36
        if shape == "exclusiveGateway":
            return 50, 50
        return 152, 92

    def _inner_shape_xml(self, node):
        out = []
        for (cid, shape, cx, cy) in self._inner_child_positions(node):
            w, h = self._inner_box(shape)
            out.append('      <bpmndi:BPMNShape id="%s_di" bpmnElement="%s">' % (cid, cid))
            out.append('        <dc:Bounds x="%.0f" y="%.0f" width="%d" height="%d" />'
                       % (cx - w / 2.0, cy - h / 2.0, w, h))
            out.append("      </bpmndi:BPMNShape>")
        return out

    # ------------------------------------------------------------ diagram ---
    def _di_xml(self):
        out = ['  <bpmndi:BPMNDiagram id="BPMNDiagram_1">',
               '    <bpmndi:BPMNPlane id="BPMNPlane_1" bpmnElement="%s">' % self.collaboration_id]
        for p in self.pools:
            out.append('      <bpmndi:BPMNShape id="%s_di" bpmnElement="%s" isHorizontal="true">'
                       % (p.id, p.id))
            out.append('        <dc:Bounds x="%.0f" y="%.0f" width="%.0f" height="%.0f" />'
                       % (p.x, p.y, p.w, p.h))
            out.append("      </bpmndi:BPMNShape>")
            for i, lane in enumerate(p.lanes if p.process_id else []):
                out.append('      <bpmndi:BPMNShape id="%s_L%d_di" bpmnElement="%s_L%d" '
                           'isHorizontal="true">' % (p.process_id, i, p.process_id, i))
                out.append('        <dc:Bounds x="%.0f" y="%.0f" width="%.0f" height="%.0f" />'
                           % (p.x + LANE_LABEL_W, lane.y, p.w - LANE_LABEL_W, lane.h))
                out.append("      </bpmndi:BPMNShape>")
        for p in self.pools:
            for node in p.nodes.values():
                if node.kind == "subprocess" and node.opts.get("collapsed", True):
                    out.append('      <bpmndi:BPMNShape id="%s_di" bpmnElement="%s" isExpanded="%s">'
                               % (node.id, node.id,
                                  "true" if self.EXPAND_SUBPROCESSES else "false"))
                else:
                    out.append('      <bpmndi:BPMNShape id="%s_di" bpmnElement="%s">'
                               % (node.id, node.id))
                out.append('        <dc:Bounds x="%.0f" y="%.0f" width="%.0f" height="%.0f" />'
                           % (node.left, node.top, node.w, node.h))
                out.append("      </bpmndi:BPMNShape>")
                if node.kind == "subprocess" and node.opts.get("inner"):
                    # The DI for the steps is written whether or not the box is
                    # drawn expanded. bpmn-js hides children of a collapsed
                    # subprocess, so the main plane is unaffected, but the box
                    # can be opened in the Modeler and no element is left
                    # without diagram interchange.
                    out.extend(self._inner_shape_xml(node))

        for p in self.pools:
            for node in p.nodes.values():
                if node.kind != "subprocess" or not node.opts.get("inner"):
                    continue
                pos = {cid: (cx, cy) for cid, _sh, cx, cy in self._inner_child_positions(node)}
                depth = 0
                for f in node.opts["inner_flows"]:
                    a, b = f[0], f[1]
                    if ("%s_%s" % (node.id, "Start" if a == "S" else a)) not in pos:
                        continue
                    if ("%s_%s" % (node.id, "End" if b == "E" else b)) not in pos:
                        continue
                    pts = self._inner_edge_waypoints(node, a, b, pos, depth)
                    if len(pts) > 2:
                        depth += 1
                    out.append('      <bpmndi:BPMNEdge id="%s_f_%s_%s_di" bpmnElement="%s_f_%s_%s">'
                               % (node.id, a, b, node.id, a, b))
                    for (px, py) in pts:
                        out.append('        <di:waypoint x="%.0f" y="%.0f" />' % (px, py))
                    out.append("      </bpmndi:BPMNEdge>")
        for (nid, _text, x, y, w, h) in self._annotation_geometry():
            out.append('      <bpmndi:BPMNShape id="%s_di" bpmnElement="%s">' % (nid, nid))
            out.append('        <dc:Bounds x="%.0f" y="%.0f" width="%.0f" height="%.0f" />' % (x, y, w, h))
            out.append("      </bpmndi:BPMNShape>")
        for p in self.pools:
            for node in p.nodes.values():
                if node.kind != "bndcomp":
                    continue
                handler = p.nodes.get(node.opts["handler"])
                if handler is None:
                    continue
                aid = "%s_assoc" % node.id
                out.append('      <bpmndi:BPMNEdge id="%s_di" bpmnElement="%s">' % (aid, aid))
                out.append('        <di:waypoint x="%.0f" y="%.0f" />' % (node.x, node.bottom))
                out.append('        <di:waypoint x="%.0f" y="%.0f" />' % (handler.x, handler.y))
                out.append("      </bpmndi:BPMNEdge>")
        for p in self.pools:
            for fl in p.flows:
                if len(fl.points) < 2:
                    continue
                out.append('      <bpmndi:BPMNEdge id="%s_di" bpmnElement="%s">' % (fl.id, fl.id))
                for (x, y) in fl.points:
                    out.append('        <di:waypoint x="%.0f" y="%.0f" />' % (x, y))
                out.append("      </bpmndi:BPMNEdge>")
        for mf in self.message_flows:
            if len(mf.points) < 2:
                continue
            out.append('      <bpmndi:BPMNEdge id="%s_di" bpmnElement="%s">' % (mf.id, mf.id))
            for (x, y) in mf.points:
                out.append('        <di:waypoint x="%.0f" y="%.0f" />' % (x, y))
            out.append("      </bpmndi:BPMNEdge>")
            for node in p.nodes.values():
                if node.kind != "bndcomp":
                    continue
                host = p.nodes[node.opts["handler"]]
                out.append('      <bpmndi:BPMNEdge id="%s_assoc_di" bpmnElement="%s_assoc">'
                           % (node.id, node.id))
                out.append('        <di:waypoint x="%.0f" y="%.0f" />' % (node.x, node.bottom))
                out.append('        <di:waypoint x="%.0f" y="%.0f" />' % (host.x, host.top))
                out.append("      </bpmndi:BPMNEdge>")

        out.append("    </bpmndi:BPMNPlane>")
        out.append("  </bpmndi:BPMNDiagram>")
        return out
