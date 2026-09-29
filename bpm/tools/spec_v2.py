"""
v2.0 model definition.

The semantics (messages, job types, forms, gateway conditions) are carried over
from v1.0 unchanged, because those were already run against the engine. What
this file changes:

  lanes        every pool that covers more than one desk is split into lanes
  containment  three repetitive routines become collapsed subprocesses, so the
               main line stays followable
  compensation two activities that commit a booking get a compensation handler,
               so a later failure releases what was booked
  retries      the external capacity check gets a counted re-attempt with a cap
               and an escalation, instead of retrying until the incident queue
  dead ends    exception branches that used to end in a bare end event now have
               an owner and a way out

Node rows come from v1.0. Coordinates do not: every coordinate is recomputed by
tools/layout_engine.py.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# The v1.0 rows, messages and job types are ported rather than retyped, so the
# release needs the v1.0 specification. It is vendored under tools/v1/ so the
# generator runs from a bare copy of this folder; the author's sibling working
# folder is only a fallback.
V1 = os.path.join(HERE, "v1")
if not os.path.exists(os.path.join(V1, "spec_hospital.py")):
    V1 = "/Users/cczy/Desktop/UFCEP6-0-3_BPMN_Hospital_Referral/tools"
sys.path.insert(0, HERE)
sys.path.insert(0, V1)

import spec_hospital                       # v1.0 model
from bpmn_builder_v2 import V2Builder      # noqa: E402

# pool name -> [(lane name, [v1 row numbers])]
LANES = {
    "Medical Secretaries": [
        ("Referral intake and correspondence", [0, 1, 2, 3, 4, 5]),
    ],
    "Consultants": [
        ("Clinical decisions and authorisations", [0, 1, 2, 3, 5, 6, 7, 8, 9, 10, 11]),
        ("Correspondence and requests from other teams", [4, 12, 13, 14, 15, 16, 17]),
    ],
    "Outpatient Bookings Team": [
        ("Appointments", [0, 1, 2, 3, 4]),
        ("Cancellations, declines and enquiries", [5, 6, 7, 8, 9]),
    ],
    "Treatment and Chemotherapy Bookings Team": [
        ("Treatment booking and funding", [0, 1, 2, 3, 4, 5, 6]),
        ("Cycles and treatment changes", [7, 8, 9, 10, 11]),
    ],
    "Finance Team": [
        ("Funding, charges and payments", [0, 1, 2, 3]),
        ("Refunds, impact and enquiries", [5, 6, 7, 8, 10]),
    ],
    "Call Handling Team": [
        ("Enquiries and outbound contact", [0, 1, 2, 3, 4, 5, 6, 7]),
    ],
    "Patient Pathway Coordinators": [
        ("Correspondence monitoring", [0, 1, 2, 3, 4]),
        ("Booking and treatment delays", [5, 6, 7]),
    ],
    "Administrative Management Team": [
        ("Escalations", [0, 1]),
    ],
}


def build():
    v1 = spec_hospital.build()
    v1.prepare()

    b = V2Builder()
    ns = b.__dict__

    # pool id -> v2 pool
    pool_map = {}
    for p1 in v1.pools:
        rows_used = sorted({n.row for n in p1.nodes.values() if not n.is_boundary})
        lane_rows = LANES.get(p1.name)
        # v1 rows are not always contiguous (Finance skips 4 and 9), so lanes are
        # defined by the rows that actually exist
        lanes = []
        if lane_rows:
            present = set(rows_used)
            for name, rws in lane_rows:
                keep = [r for r in rws if r in present]
                if keep:
                    lanes.append((name, keep))
            covered = {r for _, rs in lanes for r in rs}
            for r in rows_used:
                if r not in covered:
                    lanes[-1][1].append(r)
        elif p1.process_id:
            lanes = [("", rows_used or [0])]
        else:
            lanes = []          # a black box participant has no lanes

        p2 = b.pool(p1.id, p1.name, process_id=p1.process_id,
                    documentation=p1.documentation, version_tag="2.0.0")
        for lname, rws in lanes:
            p2.lane(lname or p1.name, len(rws))
        pool_map[p1.id] = (p2, lanes, p1)

    # ---- nodes ------------------------------------------------------------
    for p1 in v1.pools:
        p2, lanes, _ = pool_map[p1.id]
        lane_of_row = {}
        for li, (_, rws) in enumerate(lanes):
            for local, r in enumerate(rws):
                lane_of_row[r] = (li, local)
        for n1 in p1.nodes.values():
            if n1.is_boundary:
                continue
            li, local = lane_of_row.get(n1.row, (0, 0))
            opts = {k: v for k, v in n1.opts.items()
                    if not k.startswith("_") and k != "default"}
            opts["v1_kind"] = n1.kind
            p2.n(n1.id, n1.kind, n1.name, li, local, n1.col, **opts)
        for n1 in p1.nodes.values():
            if not n1.is_boundary:
                continue
            opts = {k: v for k, v in n1.opts.items()
                    if not k.startswith("_") and k != "default"}
            host = p2.nodes.get(n1.opts["attach"])
            lane = host.lane if host else 0
            p2.n(n1.id, n1.kind, n1.name, lane, 0, 0, **opts)

    # ---- flows ------------------------------------------------------------
    for p1 in v1.pools:
        p2, _, _ = pool_map[p1.id]
        for f1 in p1.flows:
            p2.f(f1.src, f1.tgt, cond=f1.cond, name=f1.name, default=f1.default)

    # ---- messages and errors ---------------------------------------------
    for name, key in v1.messages.items():
        b.msg(name, key)
    for code, nm in v1.errors.items():
        b.error(code, nm)
    from layout_engine import MessageFlow
    for mf in v1.message_flows:
        b.message_flows.append(MessageFlow(mf.src_pool, mf.src_el, mf.tgt_pool, mf.tgt_el, mf.name))

    _v2_changes(b)
    _fix_message_flows(b)
    _drop_redundant_supplier_flows(b)
    # Every terminating path keeps its own end event: several flows converging on
    # one circle reads as a single outcome where the model means several.
    # _merge_end_events is kept below for reference but is deliberately not
    # called.
    _drop_orphan_ends(b)
    _one_end_per_path(b)
    _thin_message_flows(b)
    # after the thinning, so the lines the white boxes need are not dropped with
    # the routine supplier hand-offs, and before the reorder, so the new pairs
    # count towards where the pools are stacked
    _white_box_externals(b)
    _reorder_pools(b)
    _annotate(b)
    return b


def _drop_orphan_ends(b):
    """Remove end events the model no longer routes to.

    v2.0 replaced the "referral pack unusable" dead end with a loop that asks the
    referring organisation for what is missing. That left `SEC_End_PackIncomplete`
    with no incoming flow: an outcome nothing can reach. It is residue rather than
    a scored terminal, and a disconnected circle on the diagram reads as a
    modelling error.
    """
    for pool in b.pools:
        if not pool.process_id:
            continue
        live = set()
        for f in pool.flows:
            live.add(f.src)
            live.add(f.tgt)
        for node in [n for n in list(pool.nodes.values())
                     if n.kind == "end" and n.id not in live]:
            pool.nodes.pop(node.id, None)


def _one_end_per_path(b):
    """Give every terminating path its own end event.

    Several sequence flows converging on one circle is a legal XOR merge, but it
    reads as one outcome where the model means several: a reader cannot tell from
    the drawing which branch finished. Two earlier releases merged end events to
    save ink; that was reverted, and this pass also splits the joins that came
    down from v1.0, so no end event has more than one incoming flow.
    """
    for pool in b.pools:
        if not pool.process_id:
            continue
        used = {(n.lane, n.row, n.col) for n in pool.nodes.values() if not n.is_boundary}
        for end in [n for n in list(pool.nodes.values()) if n.kind == "end"]:
            incoming = [f for f in pool.flows if f.tgt == end.id]
            if len(incoming) <= 1:
                continue
            # The first circle keeps the plain label; each split-off circle says
            # which branch reaches it, so two ends that mean the same outcome
            # arrived at two ways do not read as a duplicated label.
            for i, f in enumerate(incoming[1:], 1):
                col = end.col + 1
                while (end.lane, end.row, col) in used:
                    col += 1
                used.add((end.lane, end.row, col))
                src = pool.nodes.get(f.src)
                via = (src.name or f.name or f.src) if src is not None else (f.name or f.src)
                via = " ".join(via.split())[:46]
                clone = pool.n("%s_%d" % (end.id, i), "end",
                               "%s - %s" % (end.name, via),
                               end.lane, end.row, col, **dict(end.opts))
                clone.opts.pop("v1_kind", None)
                f.tgt = clone.id


_COLLAPSED = {}


def _pool(b, pid):
    return next(p for p in b.pools if p.id == pid)


def _fix_message_flows(b):
    """A message flow may not point at something that no longer exists.

    When a routine is collapsed its steps leave the diagram, so a message flow
    that started or ended on one of them is re-pointed at the subprocess that
    replaced it. Anything left dangling is dropped rather than written out as a
    reference to a missing element.
    """
    valid = set()
    for p in b.pools:
        valid.add(p.id)
        valid.update(p.nodes.keys())
    kept, seen = [], set()
    for mf in b.message_flows:
        src = _COLLAPSED.get(mf.src_el, mf.src_el)
        tgt = _COLLAPSED.get(mf.tgt_el, mf.tgt_el)
        if src not in valid or tgt not in valid or src == tgt:
            continue
        key = (src, tgt)
        if key in seen:
            continue
        seen.add(key)
        mf.src_el, mf.tgt_el = src, tgt
        kept.append(mf)
    b.message_flows[:] = kept


def _collapse(pool, node_ids, sub_id, sub_name, inner, inner_flows, note):
    """Fold a set of nodes into one collapsed subprocess.

    Anything outside the set that fed into it now feeds the subprocess, and
    anything it fed now comes out of the subprocess. Boundary events attached to
    a node inside the set move inside with it.
    """
    ids = set(node_ids)
    for n in list(pool.nodes.values()):
        if n.is_boundary and n.opts.get("attach") in ids:
            ids.add(n.id)
    first = pool.nodes[node_ids[0]]
    lane, row, col = first.lane, first.row, first.col
    incoming = [f for f in pool.flows if f.tgt in ids and f.src not in ids]
    outgoing = [f for f in pool.flows if f.src in ids and f.tgt not in ids]
    for nid in ids:
        pool.nodes.pop(nid, None)
    pool.flows[:] = [f for f in pool.flows if f.src not in ids and f.tgt not in ids]
    pool.n(sub_id, "subprocess", sub_name, lane, row, col,
           collapsed=True, inner=inner, inner_flows=inner_flows, documentation=note)
    for f in incoming:
        pool.f(f.src, sub_id, cond=f.cond, name=f.name, default=f.default)
    for f in outgoing:
        pool.f(sub_id, f.tgt, cond=f.cond, name=f.name, default=f.default)
    for nid in ids:
        _COLLAPSED[nid] = sub_id


def _v2_changes(b):
    from layout_engine import MessageFlow

    # ---------------------------------------------------------------- 1 ---
    # an unreadable pack used to end in a bare end event. It now joins the
    # existing "ask the referrer for what is missing" loop, which already has a
    # 14 day timeout and an exit.
    sec = _pool(b, "P_MedicalSecretaries")
    for fl in sec.flows:
        if fl.src in ("SEC_Bnd_DocumentsUnreadable", "SEC_Bnd_PackIncomplete"):
            fl.tgt = "SEC_Throw_InfoRequested"

    # ---------------------------------------------------------------- 2 ---
    # the letter dispatch routine, contained
    _collapse(sec,
              ["SEC_Auto_PrepareDispatch", "SEC_Auto_DispatchLetter",
               "SEC_Task_ResolveDispatch", "SEC_Bnd_DispatchFailed"],
              "SUB_Secretaries_Dispatch", "Dispatch the clinic letter",
              inner=[("Prepare", "stask", "Prepare the letter for distribution",
                      dict(type="correspondence.prepare-dispatch", retries="3")),
                     ("Send", "stask", "Send the letter through the correspondence service",
                      dict(type="correspondence.dispatch-letter", retries="3")),
                     ("Decide", "xg", "Did the service accept the letter?", {}),
                     ("Chase", "utask", "Resolve the distribution problem and pick another channel",
                      dict(form="resolve-dispatch-problem", candidate_groups="medical-secretaries"))],
              # The retry step had no incoming flow: the boundary event that used
              # to reach it cannot be expressed inside a collapsed sub-process, so
              # it was unreachable code and the linter was right to say so. The
              # gateway reads the status the dispatch worker already returns, so
              # the step is now on the flow and the run behaves as before -
              # dispatchStatus is SENT on the normal path and takes the default
              # branch only when the service did not accept the letter.
              inner_flows=[("S", "Prepare"), ("Prepare", "Send"), ("Send", "Decide"),
                           ("Decide", "E", '=dispatchStatus = "SENT"'),
                           ("Decide", "Chase", "default"),
                           ("Chase", "Prepare")],
              note="Contained so the main line stays readable. The steps inside are ordinary tasks "
                   "and use the same forms as before.")

    # ---------------------------------------------------------------- 3 ---
    call = _pool(b, "P_CallHandling")
    _collapse(call,
              ["CALL_Task_AttemptContact", "CALL_GW_ContactOutcome", "CALL_Auto_LogAttempt",
               "CALL_GW_Retry", "CALL_End_ContactFinished", "CALL_End_ContactFailed",
               "CALL_Throw_ContactFailed"],
              "SUB_CallHandling_Contact", "Contact the patient by telephone",
              inner=[("Attempt", "utask", "Attempt to telephone the patient",
                      dict(form="record-telephone-contact-attempt", candidate_groups="call-handling")),
                     ("Log", "stask", "Log the contact attempt",
                      dict(type="enquiry.record-contact-attempt", retries="3")),
                     ("Again", "utask", "Try another number or another time",
                      dict(form="record-telephone-contact-attempt", candidate_groups="call-handling")),
                     ("Decide", "xg", "Did we reach the patient?", {})],
              inner_flows=[("S", "Attempt"), ("Attempt", "Log"), ("Log", "Decide"),
                           ("Decide", "E", '=contactOutcome = "REACHED"'),
                           ("Decide", "Again", "default"), ("Again", "Attempt")],
              note="Three attempts at most. Every attempt is recorded, including the wrong number "
                   "and the patient who wants a different date.")
    # The telephone routine ended by looping straight back into itself, so the
    # Call Handling process never finished and always had a contact task
    # pending - an operator opening Tasklist would see work for a patient who
    # had already been reached. The steps inside the sub-process already retry
    # while the patient has not been reached; once the hand-off has been
    # published there is nothing left to do, so the process ends.
    if "CALL_Throw_ContactFinished" in call.nodes:
        used = {(n.lane, n.row, n.col) for n in call.nodes.values() if not n.is_boundary}
        base = call.nodes["CALL_Throw_ContactFinished"]
        lane, row, col = base.lane, base.row, base.col + 1
        while (lane, row, col) in used:
            col += 1
        used.add((lane, row, col))
        call.n("CALL_End_ContactFinished", "end", "Patient contacted - call handling complete",
               lane, row, col)
        for fl in list(call.flows):
            if fl.src == "CALL_Throw_ContactFinished" and fl.tgt == "SUB_CallHandling_Contact":
                fl.tgt = "CALL_End_ContactFinished"
                fl.cond = None
                fl.name = None
                fl.default = False

    if "CALL_Start_PhoneContact" in call.nodes:
        for fl in call.flows:
            if fl.tgt == "SUB_CallHandling_Contact":
                fl.cond = None
                fl.name = None
                fl.default = False

    # ---------------------------------------------------------------- 4 ---
    pcw = _pool(b, "P_PathwayCoordinators")

    # The weekly correspondence review is started by a TIMER, so the instance has
    # no patientRef, and the escalation throws keyed on
    # `=patientRef + "-letter-escalation"` published a blank correlation key: the
    # worker refused the job and the instance parked, which is how the escalation
    # ladder was found to be unreachable (DEF-21). A batch review genuinely has no
    # single patient, so these hand-offs correlate on the review run instead.
    # A production design would key them on the letter being escalated.
    for _nid in ("PCW_Throw_EscalateManager", "PCW_Throw_EscalateHigher"):
        _n = pcw.nodes.get(_nid)
        if _n is not None:
            _n.opts["key"] = '="letter-escalation"'
    for _name in list(b.messages):
        if _name.startswith("letter.escalation"):
            b.messages[_name] = '="letter-escalation"' 

    # Administrative Management is started BY those escalations, so it inherits
    # the batch context and has no patientRef either. Its own "record the
    # escalation" throws keyed on the patient and parked the instance the moment
    # the rung was worked (DEF-23).
    _adm = _pool(b, "P_AdministrativeManagement")
    for _nid in ("ADM_Throw_EscalationRecorded", "ADM_Throw_HigherRecorded"):
        _n = _adm.nodes.get(_nid)
        if _n is not None:
            _n.opts["key"] = '="letter-escalation"'
    _collapse(pcw,
              ["PCW_Auto_FindOverdue", "PCW_Task_ReviewOutstanding"],
              "SUB_Pathway_Report", "Produce the weekly overdue correspondence list",
              inner=[("Find", "stask", "Find clinic letters that are overdue",
                      dict(type="pathway.find-overdue-letters", retries="3")),
                     ("Review", "utask", "Review the outstanding correspondence list",
                      dict(form="review-outstanding-correspondence",
                           candidate_groups="pathway-coordinators"))],
              inner_flows=[("S", "Find"), ("Find", "Review"), ("Review", "E")],
              note="Runs every week. Only the letters that still need chasing come out of here.")

    # ---------------------------------------------------------------- 5 ---
    # compensation. Both handlers release something that was provisionally
    # committed earlier in the same instance.
    trt = _pool(b, "P_TreatmentBookings")
    trt.n("TRT_Bnd_CompSeries", "bndcomp", "Series committed", 0, 0, 0,
          attach="TRT_Auto_CreateSeries", handler="TRT_Comp_ReleaseSeries")
    trt.n("TRT_Comp_ReleaseSeries", "stask", "Release the provisional appointment series",
          0, 6, 4, type="treatment.release-series", retries="3", for_compensation=True,
          documentation="Compensation handler. Frees every appointment in the series when the "
                        "booking has to be undone, so nothing is left held against the patient.")
    trt.n("TRT_Bnd_CompCycle", "bndcomp", "Cycle slot committed", 0, 0, 0,
          attach="TRT_Auto_ScheduleCycle", handler="TRT_Comp_ReleaseCycle")
    trt.n("TRT_Comp_ReleaseCycle", "stask", "Release the provisional cycle booking",
          1, 2, 5, type="treatment.release-cycle-booking", retries="3", for_compensation=True,
          documentation="Compensation handler for a cycle slot that was pencilled in and then "
                        "could not be filled.")
    trt.n("TRT_Throw_CompSeries", "throwcomp", "Undo the provisional series", 0, 5, 16,
          documentation="Thrown after the capacity re-attempts run out, before the case goes to "
                        "the pathway team.")
    trt.n("TRT_Throw_CompCycle", "throwcomp", "Undo the provisional cycle slot", 1, 1, 7)

    # ---------------------------------------------------------------- 6 ---
    # a counted re-attempt instead of retrying until the incident queue fills
    trt.n("TRT_Auto_RecordRetry", "stask", "Record another capacity attempt", 0, 5, 14,
          type="treatment.record-capacity-retry", retries="3",
          # Null-safe on the first pass: the counter starts unset, and
          # `null + 1` is null, so the cap gateway received a null instead of a
          # boolean and raised an incident instead of deciding. Seeding it to 1
          # is what makes the cap real.
          inputs=[("=if externalResourceAttempts = null then 1 else externalResourceAttempts + 1",
                   "externalResourceAttempts")],
          documentation="Counts the attempts so the loop can stop. Without a cap the case would "
                        "retry for ever and nobody would ever pick it up.")
    trt.n("TRT_GW_CapacityCap", "xg", "Have we tried long enough?", 0, 5, 15)
    for fl in list(trt.flows):
        if fl.src == "TRT_Catch_RetryTimer" and fl.tgt == "TRT_Auto_CheckExternalResources":
            trt.flows.remove(fl)
        if fl.src == "TRT_GW_ExternalAvailable" and fl.tgt == "TRT_Throw_BookingPending":
            fl.tgt = "TRT_Throw_CompSeries"
        if fl.src == "TRT_Bnd_ExternalUnavailable" and fl.tgt == "TRT_Throw_BookingPending":
            fl.tgt = "TRT_Throw_CompSeries"
        if fl.src == "TRT_GW_CycleSlots" and fl.tgt == "TRT_Throw_CycleCapacityIssue":
            fl.tgt = "TRT_Throw_CompCycle"
    trt.f("TRT_Catch_RetryTimer", "TRT_Auto_RecordRetry")
    # The counted capacity retry (record -> cap -> retry or release) existed but
    # nothing could reach its head: the boundary event that used to enter it was
    # pointed straight at the release step, which left TRT_Throw_BookingPending
    # as an implicit start and the "capped retry" doing nothing at runtime. The
    # boundary now enters the chain it was built for, so the cap is real: three
    # attempts, then the provisional series is released and the pathway team is
    # told. Behaviour on the driven paths is unchanged - they never reach this
    # branch, because external capacity is available on both.
    for fl in trt.flows:
        if fl.src == "TRT_Bnd_ExternalUnavailable" and fl.tgt == "TRT_Throw_CompSeries":
            fl.tgt = "TRT_Throw_BookingPending"

    trt.f("TRT_Auto_RecordRetry", "TRT_GW_CapacityCap")
    trt.f("TRT_GW_CapacityCap", "TRT_Auto_CheckExternalResources",
          cond="=externalResourceAttempts < 3", name="Try again")
    trt.f("TRT_GW_CapacityCap", "TRT_Throw_CompSeries", default=True,
          name="Stop and release the series")
    trt.f("TRT_Throw_CompSeries", "TRT_Throw_BookingPending")
    trt.f("TRT_Throw_CompCycle", "TRT_Throw_CycleCapacityIssue")
    trt.n("TRT_Throw_BookingPending2", "throw", "Tell the pathway team the booking was released",
          0, 5, 17, msg=b.msg("treatment.booking-pending", "=patientRef + \"-treatment-pending\""),
          key="=patientRef + \"-treatment-pending\"",
          headers={"messageName": "treatment.booking-pending"})
    for fl in list(trt.flows):
        if fl.src == "TRT_Throw_CompSeries" and fl.tgt == "TRT_Throw_BookingPending":
            fl.tgt = "TRT_Throw_BookingPending2"
    trt.f("TRT_Throw_BookingPending2", "TRT_Catch_RetryTimer2")
    trt.n("TRT_Catch_RetryTimer2", "ctimer", "Retry the whole booking later", 0, 5, 18,
          timer="P3D")
    trt.f("TRT_Catch_RetryTimer2", "TRT_Auto_CreateSeries")
    b.message_flows = [mf for mf in b.message_flows
                       if mf.src_el not in ("TRT_Throw_CompSeries", "TRT_Throw_CompCycle",
                                            "TRT_Throw_BookingPending2")]
    b.message_flows.append(MessageFlow("P_TreatmentBookings", "TRT_Throw_BookingPending2",
                                       "P_PathwayCoordinators", "PCW_Start_BookingDelay"))

    # ---------------------------------------------------------------- 7 ---
    # a funding delay gets an owner instead of ending quietly
    trt.n("TRT_Throw_FundingDelay", "throw", "Flag the funding delay to the pathway team", 0, 4, 8,
          msg=b.msg("funding.delay-flagged", "=patientRef + \"-funding-delay\""),
          key="=patientRef + \"-funding-delay\"",
          headers={"messageName": "funding.delay-flagged"})
    for fl in list(trt.flows):
        if fl.src == "TRT_Throw_FundingTimeoutEscalation" and fl.tgt == "TRT_End_FundingPending":
            trt.flows.remove(fl)
    trt.f("TRT_Throw_FundingTimeoutEscalation", "TRT_Throw_FundingDelay")
    for _n in trt.nodes.values():
        if _n.id == "TRT_End_FundingPending":
            _n.col = 9
    trt.f("TRT_Throw_FundingDelay", "TRT_End_FundingPending")
    pcw.n("PCW_Start_FundingDelay", "msgstart", "Funding delay flagged by the booking team", 1, 1, 5,
          msg=b.msg("funding.delay-flagged", "=patientRef + \"-funding-delay\""))
    pcw.f("PCW_Start_FundingDelay", "PCW_Task_ReviewDelay")
    b.message_flows.append(MessageFlow("P_TreatmentBookings", "TRT_Throw_FundingDelay",
                                       "P_PathwayCoordinators", "PCW_Start_FundingDelay"))


def _drop_redundant_supplier_flows(b):
    """A service task that calls a supplier already shows the boundary.

    These message flows drew a dashed line from a task to a black-box pool
    purely to document a call that the task itself represents. There were eleven
    of them, together about 63,000 px of dashed line running most of the height
    of the diagram, saying nothing the job type does not already say.
    """
    black = {p.id for p in b.pools if not p.process_id}
    svc = {n.id for p in b.pools for n in p.nodes.values() if n.kind == "stask"}
    keep = []
    for mf in b.message_flows:
        if (mf.src_el in svc and mf.tgt_pool in black) or \
           (mf.tgt_el in svc and mf.src_pool in black):
            continue
        keep.append(mf)
    b.message_flows[:] = keep


def _reorder_pools(b):
    """Stack the pools so the teams that talk most end up near each other.

    Pool order is presentation only, but it decides how far every message flow
    has to travel. Shuffling for the shortest total travel cuts the vertical
    run of the dashed lines by about a fifth without touching the model.
    """
    import random
    order = list(b.pools)
    if len(order) < 3:
        return
    el2pool = {}
    for p in order:
        for nid in p.nodes:
            el2pool[nid] = p.id
        el2pool[p.id] = p.id
    pairs = []
    for mf in b.message_flows:
        a, c = el2pool.get(mf.src_el), el2pool.get(mf.tgt_el)
        if a and c and a != c:
            pairs.append((a, c))

    def cost(seq):
        pos = {p.id: i for i, p in enumerate(seq)}
        return sum(abs(pos[a] - pos[c]) for a, c in pairs)

    best, best_cost = order[:], cost(order)
    rng = random.Random(20260924)          # fixed seed: the build is repeatable
    for _ in range(6000):
        cand = order[:]
        for _ in range(rng.randint(1, 4)):
            i, j = sorted(rng.sample(range(len(cand)), 2))
            cand[i:j] = list(reversed(cand[i:j]))
        c = cost(cand)
        if c < best_cost:
            best, best_cost = cand, c
    b.pools[:] = best
    b.reorder_gain = (cost(order) - best_cost) / max(1, cost(order))


# Throws whose message carries one of the outcomes the brief requires to stay
# visible. These keep their own message flow when a pool pair is thinned.
REQUIRED_EXCEPTION_THROWS = {
    "SEC_Throw_InfoRequested", "SEC_Throw_ClinicalError", "SEC_Catch_InfoTimeout",
    "CON_Throw_Rejected", "CON_Throw_MoreInfoNeeded", "CON_Throw_Redirected",
    "OUT_Throw_NoSlotEscalation", "OUT_Throw_FollowUpEscalation", "OUT_Throw_FinanceReview",
    "TRT_Throw_PaymentUnresolved", "TRT_Throw_Investigation", "TRT_Throw_CompSeries",
    "TRT_Throw_CompCycle", "TRT_Throw_FundingTimeoutEscalation", "TRT_Throw_FundingDelay",
    "FIN_Throw_RefundDelayed", "FIN_Throw_NoRefund",
    "PCW_Throw_Reminder", "PCW_Throw_EscalateManager", "PCW_Throw_EscalateHigher",
    "CALL_Throw_UrgentClinical", "CNS_Throw_UrgentEscalation",
}


COMPLETION_LABEL = {
    "P_MedicalSecretaries": "Referral administration complete",
    "P_Consultants": "Clinical input complete",
    "P_OutpatientBookings": "Appointment work complete",
    "P_TreatmentBookings": "Treatment booking work complete",
    "P_Finance": "Finance work complete",
    "P_ClinicalNurseSpecialist": "Enquiry answered and closed",
    "P_CallHandling": "Call handling complete",
    "P_PathwayCoordinators": "Pathway review complete",
    "P_AdministrativeManagement": "Escalation complete",
}


def _exception_ends(pool):
    """End events an exception can land on, found by walking the graph.

    Anything reachable from a boundary event is an outcome the brief requires to
    stay readable - a rejected referral, a pack that never came back, a letter
    three months overdue - so those ends keep their own node and their own name.
    """
    out = set()
    seen = set()
    stack = [fl.tgt for fl in pool.flows
             if pool.nodes.get(fl.src) is not None and pool.nodes[fl.src].is_boundary]
    by_src = {}
    for fl in pool.flows:
        by_src.setdefault(fl.src, []).append(fl.tgt)
    while stack:
        nid = stack.pop()
        if nid in seen:
            continue
        seen.add(nid)
        node = pool.nodes.get(nid)
        if node is None:
            continue
        if node.kind == "end":
            out.add(nid)
            continue
        for nxt in by_src.get(nid, []):
            stack.append(nxt)
    return out


def _merge_end_events(b):
    """Collapse terminals that sit close together.

    Several flows converging on one end event is an ordinary XOR merge, so this
    does not change how a case finishes. Two earlier attempts were rejected on
    the numbers: merging every end a pool owns cut 33 nodes but added 61 line
    crossings, and merging per lane still added 50. Both were reaching across
    rows. This version only merges ends within three rows of each other, which
    is the "several termination points on one path" case, and leaves the rest
    alone. Exception ends are never merged - they are found by walking forward
    from each boundary event, so a rejected referral and a three month overdue
    letter keep their own named terminal.
    """
    for pool in b.pools:
        if not pool.process_id:
            continue
        ends = [n for n in pool.nodes.values() if n.kind == "end"]
        if len(ends) <= 1:
            continue
        keep = _exception_ends(pool)
        incoming = {}
        for fl in pool.flows:
            incoming[fl.tgt] = incoming.get(fl.tgt, 0) + 1

        candidates = sorted((e for e in ends if e.id not in keep), key=lambda n: (n.lane, n.row))
        clusters, current = [], []
        for e in candidates:
            if current and (e.lane != current[-1].lane or e.row - current[-1].row > 3):
                clusters.append(current)
                current = []
            current.append(e)
        if current:
            clusters.append(current)

        for group in clusters:
            if len(group) <= 1:
                continue
            keeper = max(group, key=lambda n: (incoming.get(n.id, 0), n.id))
            keeper.name = COMPLETION_LABEL.get(pool.id, "Work complete")
            drop = {e.id for e in group if e.id != keeper.id}
            for fl in pool.flows:
                if fl.tgt in drop:
                    fl.tgt = keeper.id
            pool.flows[:] = [f for f in pool.flows if f.src not in drop]
            for eid in drop:
                pool.nodes.pop(eid, None)


# The only routine hand-offs that keep a drawn line. Everything else that is
# not an exception or an outcome is left as a throw/catch pair in the XML: in
# Camunda 8 the throw event is what publishes the message, so the dashed line
# documents a hand-off that already works without it. These four mark the edges
# of the patient's journey - in from the referrer, out as a letter, the patient
# attending, and the patient contacting the hospital.
KEEP_BOUNDARY_HANDOFFS = {
    ("P_ReferringOrg", "SEC_Start_Referral"),
    ("SUB_Secretaries_Dispatch", "P_Correspondence"),
    ("P_Patient", "CON_Start_AppointmentAttended"),
    ("P_Patient", "CALL_Start_Enquiry"),
}


def _thin_message_flows(b):
    """Draw only the hand-offs a reader cannot infer.

    A message flow is a picture of a hand-off; in Camunda 8 the throw event is
    what actually publishes. The first release drew one per hand-off (75 dashed
    lines running the height of the diagram), the second one per pair of pools
    (31), and both were still too much ink for the information they carry.

    What is drawn now:

      * every exception or outcome hand-off - a rejected referral, a funding
        delay, a refund the provider has not returned, an escalation. These are
        the interactions that carry marks and they are never thinned; and
      * the four hand-offs that cross the system boundary, which show where the
        patient's journey starts and ends.

    Everything else stays in the model as a throw/catch pair and still runs. A
    duplicate line for a pair of pools that already has one is dropped.
    """
    el2pool = {}
    for p in b.pools:
        for nid in p.nodes:
            el2pool[nid] = p.id
        el2pool[p.id] = p.id
    best = {}
    dropped = 0
    for mf in b.message_flows:
        a, c = el2pool.get(mf.src_el), el2pool.get(mf.tgt_el)
        if a == c:
            continue
        keep = (mf.src_el in REQUIRED_EXCEPTION_THROWS
                or (mf.src_el, mf.tgt_el) in KEEP_BOUNDARY_HANDOFFS)
        if not keep:
            dropped += 1
            continue
        key = (a, c)
        score = 0 if mf.src_el in REQUIRED_EXCEPTION_THROWS else 1
        if key not in best or score < best[key][0]:
            if key in best:
                dropped += 1
            best[key] = (score, mf)
        else:
            dropped += 1
    b.message_flows[:] = [v[1] for v in best.values()]
    b.thinned_message_flows = dropped


# --------------------------------------------------------------- white boxes --
# The hand-offs drawn for the six outside participants. Before v14 they were
# black boxes - a pool with a name and nothing in it - and the three suppliers
# that are reached from a service task (scheduling, payments, treatment and
# diagnostics) ended up with no drawn connection at all, so the drawing had a
# pool on it that nothing pointed at. Each of the six now carries a small
# process of its own and one drawn line in each direction.
# The six outside participants are drawn in full. Whether they are also *deployed*
# is a switch, because Camunda 8 stores the whole BPMN resource in every process
# definition it writes and the default append batch is 4 MB.
#
# This was measured, not assumed. Against c8run 8.10.0-alpha5 with all fifteen
# executable, the deployment is rejected:
#
#   Can't append entry: ... valueType=PROCESS ... with size: 405002 this would
#   exceed the maximum batch size. [ currentBatchEntryCount: 24,
#   currentBatchSize: 4095764 ]
#
# i.e. it fits nine process records (the v7.0 deployment: 9 x 397 KB) and dies on
# the tenth. With this switch off, the six outside processes are written with
# isExecutable="false": they are still modelled, still drawn, still connected and
# still readable, they are simply not deployed, so the batch is back to the nine
# processes that were verified in v7.0 - and the deployment succeeds.
#
# Set it to True if the engine's batch limit is raised to match
# (zeebe.broker.network.maxMessageSize in the broker config, 4 MB by default), or
# if the outside participants are deployed in their own file.
EXTERNAL_PROCESSES_EXECUTABLE = False

WHITE_BOX_HANDOFFS = {
    ("OUT_Auto_FindSlots", "SCH_Start_SlotSearch"),
    ("SCH_Throw_SlotsReturned", "P_OutpatientBookings"),
    ("SUB_Secretaries_Dispatch", "COR_Start_Dispatch"),
    ("COR_Throw_Result", "P_MedicalSecretaries"),
    ("TRT_Auto_ProcessPayment", "PAY_Start_Transaction"),
    ("PAY_Throw_Result", "P_TreatmentBookings"),
    ("TRT_Auto_CheckExternalResources", "EXT_Start_CapacityCheck"),
    ("EXT_Throw_Capacity", "P_TreatmentBookings"),
}


def _K(tag):
    """Correlation key expression for a new hand-off: patient plus purpose."""
    return '=patientRef + "-%s"' % tag


def _white_box_externals(b):
    """Open the six outside participants and connect them to the hospital.

    Why this is worth the ink. A black-box pool answers "who else is involved"
    and nothing else: a reader cannot tell the scheduling supplier from the
    payment provider, and three of the six were not connected to anything, which
    reads as a modelling mistake rather than a decision. What each outside party
    does with the hand-off is short and is stated in the case study, so it can be
    drawn honestly:

      * the referrer prepares the pack and sends it, then waits for the outcome;
      * the patient attends, and contacts the hospital;
      * the scheduling supplier searches its diary and returns slots;
      * the correspondence supplier prints and dispatches the letter;
      * the payment provider processes the card transaction and returns the
        status, the reference, the date and the amount;
      * the treatment, laboratory and imaging services report what they can take
        and when.

    Each one is a message-driven process: a message arrives, one step does the
    work, and the answer that goes back is a message of its own. The step uses
    the same job type the hospital's own service task calls, so the workers that
    already implement the four suppliers drive both sides and nothing new has to
    be written for them.

    What this deliberately does not do is change the hospital side. Its service
    tasks and error boundary events stay exactly as they were - a supplier that
    cannot answer is still SCHEDULING_SERVICE_UNAVAILABLE,
    CORRESPONDENCE_SERVICE_FAILED, PAYMENT_PROVIDER_UNAVAILABLE or
    EXTERNAL_RESOURCE_UNAVAILABLE on the hospital's own task - so the nine
    executable hospital processes, their forms, their job types and the runs
    recorded against them are untouched. The two sides describe the same
    exchange from opposite ends of the same job type.
    """
    from layout_engine import MessageFlow

    def box(pid, process_id, lane, documentation):
        p = _pool(b, pid)
        p.process_id = process_id
        p.documentation = documentation
        # outside the hospital: kept out of the note panel and out of any other
        # decision that assumes "our" processes
        p.external = True
        p.executable = EXTERNAL_PROCESSES_EXECUTABLE
        if not p.lanes:
            p.lane(lane, 1)
        return p

    def chain(pool, *ids):
        for a, c in zip(ids, ids[1:]):
            pool.f(a, c)

    # --- the referring organisation ---------------------------------------
    ref = box("P_ReferringOrg", "referring-organisation",
              "Referral to the specialist service",
              "The GP surgery or other hospital that refers the patient. Modelled only as far as "
              "the boundary: the pack is prepared outside this system, so all that is shown is the "
              "referral going out and the outcome coming back.")
    ref.n("REF_Start_Referral", "start", "Patient referred for specialist review", 0, 0, 0)
    ref.n("REF_Throw_SendReferral", "throw", "Send the referral to the specialist service", 0, 0, 1,
          msg=b.msg("referral.received"), key="=patientRef",
          headers={"messageName": "referral.received"})
    ref.n("REF_End_ReferralSent", "end", "Referral sent", 0, 0, 2)
    chain(ref, "REF_Start_Referral", "REF_Throw_SendReferral", "REF_End_ReferralSent")

    # --- the patient -------------------------------------------------------
    pat = box("P_Patient", "patient-representative",
              "Attendance and contact",
              "The patient or their authorised representative. The hand-offs here are the ones the "
              "patient makes personally - attending the appointment and contacting the hospital - "
              "which arrive from outside the modelled system.")
    pat.n("PAT_Start_Attend", "start", "Patient attends the new patient appointment", 0, 0, 0)
    pat.n("PAT_Throw_Attended", "throw", "Confirm that the appointment was attended", 0, 0, 1,
          msg=b.msg("appointment.attended"), key="=patientRef",
          headers={"messageName": "appointment.attended"})
    pat.n("PAT_End_Attended", "end", "Appointment attended", 0, 0, 2)
    chain(pat, "PAT_Start_Attend", "PAT_Throw_Attended", "PAT_End_Attended")

    # --- the four suppliers ------------------------------------------------
    # one message in, one step, one message back out
    def supplier(pid, process_id, lane, documentation,
                 start_id, start_name, request, task_id, task_name, job_type,
                 throw_id, throw_name, reply, end_id, end_name, tag, inputs=None):
        p = box(pid, process_id, lane, documentation)
        p.n(start_id, "msgstart", start_name, 0, 0, 0, msg=b.msg(request, _K(tag)))
        p.n(task_id, "stask", task_name, 0, 0, 1, type=job_type, retries="3",
            inputs=inputs or [])
        p.n(throw_id, "throw", throw_name, 0, 0, 2,
            msg=b.msg(reply, _K(tag)), key=_K(tag), headers={"messageName": reply})
        p.n(end_id, "end", end_name, 0, 0, 3)
        chain(p, start_id, task_id, throw_id, end_id)
        return p

    supplier("P_ExternalScheduling", "external-scheduling-service",
             "Appointment slot search",
             "The supplier that holds the appointment diary. It is asked for slots and returns what "
             "it has; when it cannot answer at all the hospital's own service task raises "
             "SCHEDULING_SERVICE_UNAVAILABLE and a person decides what to do.",
             "SCH_Start_SlotSearch", "Slot search requested by the hospital",
             "scheduling.slot-search-requested",
             "SCH_Task_FindSlots", "Search the appointment slots that match the request",
             "scheduling.find-appointment-slots",
             "SCH_Throw_SlotsReturned", "Return the slots that are available",
             "scheduling.slots-returned",
             "SCH_End_SlotSearch", "Slots returned", "slot-search")

    supplier("P_Correspondence", "external-correspondence-service",
             "Letter production and dispatch",
             "The supplier that prints and posts the letters. It reports back whether the job was "
             "accepted; the hospital's own service task raises CORRESPONDENCE_SERVICE_FAILED when "
             "it is not, and the secretaries then pick another channel.",
             "COR_Start_Dispatch", "Letter received for distribution",
             "correspondence.dispatch-requested",
             "COR_Task_Dispatch", "Print and dispatch the letter",
             "correspondence.dispatch-letter",
             "COR_Throw_Result", "Return the dispatch result",
             "correspondence.dispatch-completed",
             "COR_End_Dispatch", "Dispatch result returned", "dispatch",
             # the same worker the hospital's own dispatch task calls, so it
             # applies the same validation: a dispatch with no recipients is
             # rejected with CORRESPONDENCE_SERVICE_FAILED. Inside the hospital
             # process that error is caught by a boundary event; here there is no
             # catcher, so the supplier defaults the recipient list instead of
             # producing an incident when the request does not carry one.
             inputs=[('=if dispatchRecipients = null then (if letterRecipients = null '
                      'then ["patient", "referring-organisation"] else letterRecipients) '
                      'else dispatchRecipients', "dispatchRecipients")])

    supplier("P_PaymentProvider", "external-payment-service",
             "Card transactions and refunds",
             "The supplier that takes the money. It processes the card transaction and returns the "
             "status, the transaction reference, the date and the amount - never the card details. "
             "Refunds use the same provider through payment.process-refund on the hospital side.",
             "PAY_Start_Transaction", "Secure payment request received",
             "payment.transaction-requested",
             "PAY_Task_Process", "Process the card transaction and report the outcome",
             "payment.process-transaction",
             "PAY_Throw_Result", "Return the payment status and reference",
             "payment.transaction-result",
             "PAY_End_Transaction", "Payment result returned", "payment",
             # same worker, same input contract: it needs a payment reference and
             # a charge amount and fails the job without them. Defaulted here so
             # the supplier can be driven on its own.
             inputs=[('=if paymentReference = null then "SIMULATED-PAYMENT-REFERENCE" '
                      'else paymentReference', "paymentReference"),
                     ('=if chargeAmount = null then 125.0 else chargeAmount', "chargeAmount")])

    supplier("P_ExternalClinicalServices", "external-clinical-services",
             "Treatment and diagnostic capacity",
             "The hospitals and laboratories that deliver treatment, tests and imaging. They report "
             "what they can take and when; a resource that stays unavailable is what makes the "
             "hospital's own service task raise EXTERNAL_RESOURCE_UNAVAILABLE.",
             "EXT_Start_CapacityCheck", "Capacity check requested by the booking team",
             "external-resources.capacity-requested",
             "EXT_Task_CheckCapacity", "Check treatment, laboratory and imaging capacity",
             "external-resources.check-availability",
             "EXT_Throw_Capacity", "Return what is available and when",
             "external-resources.capacity-returned",
             "EXT_End_CapacityCheck", "Capacity returned", "external-capacity")

    # --- the drawn hand-offs ------------------------------------------------
    # The correspondence request already has a line (the dispatch sub-process to
    # the pool); it is re-pointed at the message the supplier now starts on
    # rather than a second line being drawn beside it.
    for mf in b.message_flows:
        if mf.src_el == "SUB_Secretaries_Dispatch" and mf.tgt_pool == "P_Correspondence":
            mf.tgt_el = "COR_Start_Dispatch"
    b.message_flows.extend([
        MessageFlow("P_OutpatientBookings", "OUT_Auto_FindSlots",
                    "P_ExternalScheduling", "SCH_Start_SlotSearch"),
        MessageFlow("P_ExternalScheduling", "SCH_Throw_SlotsReturned",
                    "P_OutpatientBookings", "P_OutpatientBookings"),
        MessageFlow("P_Correspondence", "COR_Throw_Result",
                    "P_MedicalSecretaries", "P_MedicalSecretaries"),
        MessageFlow("P_TreatmentBookings", "TRT_Auto_ProcessPayment",
                    "P_PaymentProvider", "PAY_Start_Transaction"),
        MessageFlow("P_PaymentProvider", "PAY_Throw_Result",
                    "P_TreatmentBookings", "P_TreatmentBookings"),
        MessageFlow("P_TreatmentBookings", "TRT_Auto_CheckExternalResources",
                    "P_ExternalClinicalServices", "EXT_Start_CapacityCheck"),
        MessageFlow("P_ExternalClinicalServices", "EXT_Throw_Capacity",
                    "P_TreatmentBookings", "P_TreatmentBookings"),
    ])


def _annotate(b):
    notes = {
        "P_MedicalSecretaries": [
            ("Note_SEC_1", "Secretaries check the pack and chase what is missing. They never record a "
                           "view on whether the referral is clinically suitable.", "SEC_Task_CheckPack"),
            ("Note_SEC_2", "Nothing reaches a clinician without a complete pack, and nothing reaches a "
                           "patient without an authorised clinical decision behind it.",
             "SEC_GW_PackComplete"),
        ],
        "P_Consultants": [
            ("Note_CON_1", "Accept, reject, redirect or ask for more clinical detail. The reason and the "
                           "deciding clinician are recorded and cannot be edited afterwards.",
             "CON_GW_Decision"),
            ("Note_CON_2", "The seven day letter target runs from the appointment, not from when "
                           "drafting starts.", "CON_Task_DraftLetter"),
        ],
        "P_TreatmentBookings": [
            ("Note_TRT_1", "A request without a named authorising clinician is turned away before "
                           "anything is booked.", "TRT_Auto_ValidateRequest"),
            ("Note_TRT_2", "Money never leaves the patient's account twice. A repeated attempt gets a "
                           "new reference, and a duplicate report stops the booking.",
             "TRT_GW_PaymentOutcome"),
            ("Note_TRT_3", "Compensation. If external capacity never arrives, the provisional series "
                           "is released instead of being left held.", "TRT_Comp_ReleaseSeries"),
        ],
        "P_Finance": [
            ("Note_FIN_1", "Finance decides funding and refunds. Clinical staff may explain a treatment "
                           "decision but cannot approve money.", "FIN_Task_DecideRefund"),
        ],
        "P_PathwayCoordinators": [
            ("Note_PCW_1", "Seven days, one month and three months are the three escalation points for "
                           "an outstanding clinic letter.", "PCW_GW_OverdueBand"),
        ],
    }
    for pid, items in notes.items():
        pool = _pool(b, pid)
        for nid, text, near in items:
            if near in pool.nodes:
                pool.note(nid, text, near)


if __name__ == "__main__":
    bb = build()
    print("pools        ", len(bb.pools))
    print("nodes        ", sum(len(p.nodes) for p in bb.pools))
    print("flows        ", sum(len(p.flows) for p in bb.pools))
    print("message flows", len(bb.message_flows))
    print("subprocesses ", sum(1 for p in bb.pools for n in p.nodes.values() if n.kind == "subprocess"))
    print("compensation ", sum(1 for p in bb.pools for n in p.nodes.values() if n.kind in ("bndcomp", "throwcomp")))
    probs = bb.validate()
    for x in probs[:25]:
        print("  !", x)
    print("problems     ", len(probs))
