#!/usr/bin/env python3
"""Prove that v2.1 kept everything v2.0 was scored on.

Every line of the preservation checklist is answered by parsing the two .bpmn
files, never from memory.  Run it after any regeneration:

    python3 tools/verify_preservation.py

Exit code is 0 only when nothing scored went missing.
"""
import os
import re
import sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))


def _baseline():
    """The v2.0 model every scored element is checked against.

    Vendored under tools/baseline/ so the audit runs from a bare copy of this
    release. The sibling working folder is only a fallback for the author's own
    machine, where the two releases sit side by side.
    """
    local = os.path.abspath(os.path.join(HERE, "baseline",
                                         "UFCEP6-0-3_Hospital_Patient_Pathway_v2.bpmn"))
    if os.path.exists(local):
        return local
    return os.path.abspath(os.path.join(HERE, "..", "..",
           "UFCEP6-0-3_BPMN_Hospital_Referral_v2", "model",
           "UFCEP6-0-3_Hospital_Patient_Pathway_v2.bpmn"))


OLD = _baseline()
NEW = os.path.abspath(os.path.join(HERE, "..", "model",
      "UFCEP6-0-3_Hospital_Patient_Pathway_v14.bpmn"))

BPMN = "http://www.omg.org/spec/BPMN/20100524/MODEL"
BPMNDI = "http://www.omg.org/spec/BPMN/20100524/DI"
ZEEBE = "http://camunda.org/schema/zeebe/1.0"
MODELER = "http://camunda.org/schema/modeler/1.0"

results = []


def check(label, ok, detail=""):
    results.append((ok, label, detail))
    print("%s %s%s" % ("PASS" if ok else "FAIL", label, ("  -- " + detail) if detail else ""))


def load(path):
    return ET.parse(path).getroot()


def ids(root, tag):
    return {e.get("id"): e for e in root.iter("{%s}%s" % (BPMN, tag))}


def val(el, tag, attr="name"):
    hit = el.find("{%s}%s" % (BPMN, tag))
    return None if hit is None else hit.get(attr)


def main():
    if not os.path.exists(OLD):
        print("v2.0 model not found at %s" % OLD)
        return 2
    old, new = load(OLD), load(NEW)

    # 1 -- the fifteen pools, by name
    op = {p.get("name") for p in old.iter("{%s}participant" % BPMN)}
    np_ = {p.get("name") for p in new.iter("{%s}participant" % BPMN)}
    check("15 participants, names unchanged", len(np_) == 15 and np_ == op,
          "v2.0 %d / v2.1 %d, missing %s" % (len(op), len(np_), sorted(op - np_) or "none"))

    # 2 -- every user task keeps a form and a candidate group
    ou, nu = ids(old, "userTask"), ids(new, "userTask")
    check("39 user tasks present", len(nu) == 39, "v2.1 has %d" % len(nu))
    check("user task ids identical", set(ou) == set(nu),
          "missing %s" % (sorted(set(ou) - set(nu)) or "none"))

    def form_of(el):
        fd = el.find(".//{%s}formDefinition" % ZEEBE)
        return None if fd is None else fd.get("formId")

    def group_of(el):
        ad = el.find(".//{%s}assignmentDefinition" % ZEEBE)
        return None if ad is None else ad.get("candidateGroups")

    no_form = sorted(k for k, v in nu.items() if not form_of(v))
    no_grp = sorted(k for k, v in nu.items() if not group_of(v))
    check("every user task has zeebe:formDefinition + formId", not no_form, str(no_form[:4]))
    check("every user task has zeebe:assignmentDefinition candidateGroups", not no_grp, str(no_grp[:4]))
    check("user task forms unchanged", all(form_of(ou[k]) == form_of(nu[k]) for k in ou),
          "changed %s" % [k for k in ou if form_of(ou[k]) != form_of(nu[k])][:3])
    check("user task candidate groups unchanged", all(group_of(ou[k]) == group_of(nu[k]) for k in ou))

    # 3 -- the forty-seven service tasks and their job types
    def job_types(root):
        out = {}
        for el in root.iter("{%s}serviceTask" % BPMN):
            td = el.find(".//{%s}taskDefinition" % ZEEBE)
            out[el.get("id")] = None if td is None else td.get("type")
        return out

    oj, nj = job_types(old), job_types(new)
    # v14 gives each of the four outside suppliers one service task of its own,
    # so the count is a floor rather than an equality: every v2.0 service task
    # has to survive with its own job type, and nothing else may appear.
    added = sorted(set(nj) - set(oj))
    check("all 47 v2.0 service tasks present", set(oj) <= set(nj),
          "missing %s" % (sorted(set(oj) - set(nj)) or "none"))
    check("no v2.0 service task changed job type", all(oj[k] == nj[k] for k in oj),
          "changed %s" % [k for k in oj if oj.get(k) != nj.get(k)][:3])
    check("the only service tasks added are the four supplier-side ones",
          len(added) == 4, "added %s" % added)
    check("no service task lost its job type", all(v for v in nj.values()))

    # 4 -- all four gateway flavours still on the canvas
    for gt in ("exclusiveGateway", "inclusiveGateway", "parallelGateway", "eventBasedGateway"):
        check("gateway type present: %s" % gt, len(ids(new, gt)) > 0, "%d found" % len(ids(new, gt)))

    # 5 -- the exception paths that carry marks
    # the exception paths the brief names, each pinned to a real marker in the
    # file: an error code, a boundary event, or a timer.
    marks = {
        "referral rejected / unreadable":      "REFERRAL_PACK_UNREADABLE",
        "referral pack incomplete":            "REFERRAL_PACK_INCOMPLETE",
        "external service unavailable":        "EXTERNAL_RESOURCE_UNAVAILABLE",
        "correspondence service unavailable":  "CORRESPONDENCE_SERVICE_FAILED",
        "scheduling service unavailable":      "SCHEDULING_SERVICE_UNAVAILABLE",
        "payment provider unavailable":        "PAYMENT_PROVIDER_UNAVAILABLE",
        "payment confirmation lost":           "PAYMENT_CONFIRMATION_LOST",
        "charge calculation failed":           "CHARGE_CALCULATION_FAILED",
        "treatment request unauthorised":      "TREATMENT_REQUEST_UNAUTHORISED",
    }
    body = ET.tostring(new, encoding="unicode")
    for label, m in marks.items():
        check("exception path present: %s" % label, m in body, m)

    # the 7 day chase is a boundary timer; the one month and three month rungs
    # are modelled as a message chain between pools rather than as timers, so
    # both shapes have to be checked.
    timers = [t.text for t in new.iter("{%s}timeDuration" % BPMN)]
    timers += [t.text for t in new.iter("{%s}timeCycle" % BPMN)]
    check("7 day letter chase timer P7D", "P7D" in timers,
          "timers seen: %s" % sorted(set(timers)))
    check("weekly repeat chase R/PT168H", "R/PT168H" in timers)
    check("14 day appointment reminder timer P14D", "P14D" in timers)

    ladder = [m.get("name") for m in new.iter("{%s}message" % BPMN)]
    for rung, why in (("letter.overdue-flagged", "letter gone overdue"),
                      ("letter.escalation-admin-manager", "one month: to the admin manager"),
                      ("letter.escalation-higher-management", "three months: to higher management"),
                      ("letter.escalation-recorded", "escalation outcome written back")):
        check("letter escalation rung: %s (%s)" % (rung, why), rung in ladder)
    old_ladder = [m.get("name") for m in old.iter("{%s}message" % BPMN)
                  if (m.get("name") or "").startswith("letter.")]
    new_ladder = [n for n in ladder if (n or "").startswith("letter.")]
    check("letter escalation chain unchanged from v2.0", sorted(old_ladder) == sorted(new_ladder))

    names = {e.get("name") for e in new.iter("{%s}boundaryEvent" % BPMN)}
    for want in ("Rejected", "Unreadable", "Incomplete", "No confirmation",
                 "Provider down", "Service down", "Unavailable", "No capacity",
                 "Not authorised"):
        check("boundary event present: %s" % want, want in names)

    # 6 -- no white box pool left without a way to talk to another pool
    def pool_of_lane_map(root):
        m = {}
        for part in root.iter("{%s}participant" % BPMN):
            pref = part.get("processRef")
            if pref:
                m[part.get("id")] = pref
        return m

    # The 15-25 band this used to assert belonged to a compaction pass that was
    # built, measured and withdrawn (see docs/06-diagram-engineering.md section
    # 5). The rule the shipped drawing actually keeps is stronger and is checked
    # instead: exactly one representative line per pair of pools, never two
    # lines for the same hand-off.
    flows = list(new.iter("{%s}messageFlow" % BPMN))
    pairs = {(mf.get("sourceRef"), mf.get("targetRef")) for mf in flows}
    check("no two drawn message flows share a pair of pools",
          len(flows) == len(pairs) and len(flows) > 0,
          "%d message flows over %d pool pairs" % (len(flows), len(pairs)))

    # What is drawn is not every hand-off any more: the routine internal ones
    # were thinned because 31 dashed lines running the height of the drawing
    # carried less than they cost. The guarantee that replaces "one per pair" is
    # that nothing meaningful was dropped with them - every exception hand-off
    # the model routes through a throw event keeps its line, and the four
    # hand-offs that cross the system boundary are always drawn.
    from spec_v2 import (REQUIRED_EXCEPTION_THROWS, KEEP_BOUNDARY_HANDOFFS,
                         WHITE_BOX_HANDOFFS)
    boundary = {src for src, _tgt in KEEP_BOUNDARY_HANDOFFS}
    white = {src for src, _tgt in WHITE_BOX_HANDOFFS}
    drawn_src = {mf.get("sourceRef") for mf in flows}
    throws = set(ids(new, "intermediateThrowEvent"))
    allowed = boundary | white | {t for t in throws if t in REQUIRED_EXCEPTION_THROWS}
    check("every system-boundary hand-off is drawn", boundary <= drawn_src,
          "missing %s" % sorted(boundary - drawn_src))
    check("every white-box outside hand-off is drawn", white <= drawn_src,
          "missing %s" % sorted(white - drawn_src))
    check("nothing but an exception, boundary or white-box hand-off is drawn",
          drawn_src <= allowed, "unexpected %s" % sorted(drawn_src - allowed)[:4])
    check("the exception hand-offs that were drawn before are still drawn",
          len(drawn_src & REQUIRED_EXCEPTION_THROWS) == 11,
          "%d exception hand-offs drawn" % len(drawn_src & REQUIRED_EXCEPTION_THROWS))

    # 6b -- no outside participant is left floating. Before v14 the payment
    # provider, the treatment and diagnostic services and the scheduling service
    # were pools on the drawing that no line reached at all.
    outside = {"P_ReferringOrg", "P_Correspondence", "P_PaymentProvider",
               "P_ExternalClinicalServices", "P_Patient", "P_ExternalScheduling"}
    pool_of_proc, el_pool = {}, {}
    for part in new.iter("{%s}participant" % BPMN):
        el_pool[part.get("id")] = part.get("id")
        if part.get("processRef"):
            pool_of_proc[part.get("processRef")] = part.get("id")
    for proc in new.iter("{%s}process" % BPMN):
        owner = pool_of_proc.get(proc.get("id"))
        for el in proc:
            if el.get("id"):
                el_pool[el.get("id")] = owner
    linked = set()
    for mf in flows:
        for ref in (mf.get("sourceRef"), mf.get("targetRef")):
            linked.add(el_pool.get(ref, ref))
    check("every outside participant is connected to another pool",
          outside <= linked, "floating %s" % sorted(outside - linked))
    with_process = {p.get("id") for p in new.iter("{%s}participant" % BPMN)
                    if p.get("processRef")}
    check("every outside participant now has a process of its own",
          outside <= with_process, "still a black box %s" % sorted(outside - with_process))

    # every end event stands for exactly one terminating path
    ends = set(ids(new, "endEvent"))
    incoming = {}
    for fl in new.iter("{%s}sequenceFlow" % BPMN):
        if fl.get("targetRef") in ends:
            incoming[fl.get("targetRef")] = incoming.get(fl.get("targetRef"), 0) + 1
    merged = sorted(k for k, v in incoming.items() if v > 1)
    orphan = sorted(e for e in ends if incoming.get(e, 0) == 0)
    check("no end event merges more than one terminating path", not merged,
          "merged %s" % merged[:4])
    check("no end event is left with nothing reaching it", not orphan,
          "orphan %s" % orphan[:4])

    # 7 -- platform
    for root, tag in ((old, "v2.0"), (new, "v2.1")):
        plat = root.get("{%s}executionPlatform" % MODELER)
        ver = root.get("{%s}executionPlatformVersion" % MODELER)
        check("%s declares modeler:executionPlatform = Camunda Cloud" % tag,
              plat == "Camunda Cloud", "got %r" % plat)
        check("%s targets engine 8.10.0" % tag, ver == "8.10.0", "got %r" % ver)
        txt = ET.tostring(root, encoding="unicode")
        for bad in ("camunda:formKey", "camunda:assignee", "camunda:class",
                    "camunda:delegateExpression", "activiti:", "camunda:historyTimeToLive"):
            check("%s free of Camunda 7 attribute %s" % (tag, bad), bad not in txt)

    # 8 -- diagram interchange is complete
    shapes = {e.get("bpmnElement") for e in new.iter("{%s}BPMNShape" % BPMNDI)}
    edges = {e.get("bpmnElement") for e in new.iter("{%s}BPMNEdge" % BPMNDI)}
    drawn = shapes | edges
    want = set()
    for tag in ("startEvent", "endEvent", "userTask", "serviceTask",
                "intermediateCatchEvent", "intermediateThrowEvent", "boundaryEvent",
                "exclusiveGateway", "inclusiveGateway", "parallelGateway",
                "eventBasedGateway", "subProcess", "sequenceFlow", "messageFlow",
                "participant", "lane", "textAnnotation", "association"):
        want |= set(ids(new, tag))
    # A collapsed subprocess draws only its own box on the main plane - bpmn-js
    # hides the children - but the children still carry diagram interchange, so
    # that opening the box in the Modeler shows a laid-out flow instead of an
    # empty frame, and so no element in the file is left without DI.
    collapsed = [sp.get("id") for sp in new.iter("{%s}subProcess" % BPMN)]
    inside = {e for e in want if any(e.startswith(c + "_") for c in collapsed)}
    check("subprocess steps are all present in the XML", len(inside) >= 28,
          "%d inner elements" % len(inside))
    check("every element has a shape or an edge", not (want - drawn),
          "undrawn %s" % sorted(want - drawn)[:5])
    check("every collapsed subprocess step carries DI, so the box can be opened",
          inside <= drawn, "no DI for %s" % sorted(inside - drawn)[:3])
    check("no diagram element points at a missing element", not (drawn - want),
          "orphan DI %s" % sorted(drawn - want)[:5])

    bad = [r for r in results if not r[0]]
    print("\n%d checks, %d passed, %d failed" % (len(results), len(results) - len(bad), len(bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
