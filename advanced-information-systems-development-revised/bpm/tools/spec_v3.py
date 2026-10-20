"""
v16.0 operational model - one hospital pool, responsibilities as lanes.

Why the shape changed
---------------------
v14.0 was a collaboration of fourteen pools: nine hospital desks modelled as
nine independent deployable processes that reached each other by message flow,
plus five outside participants. That reads as a federation of organisations
rather than one hospital running one pathway. A message flow asserts an
agreement between independent participants; between the referral desk and the
consultant there is no such agreement, only a hand-off, and a hand-off is a
sequence flow. The model also had no single process that could be pointed at and
called "the pathway": the journey only existed as a chain of messages.

v16.0 redraws it the way the strategic model reads. One pool - the hospital - and
inside it three responsibility lanes, each carrying the teams that answer for
that responsibility:

    Clinical responsibility      Consultants, Clinical Nurse Specialist Team
    Administrative responsibility Medical Secretaries, Outpatient Bookings,
                                  Treatment and Chemotherapy Bookings,
                                  Call Handling, Patient Pathway Coordinators,
                                  Administrative Management
    Financial responsibility     Finance Team

Message flows are kept only where an independent participant is genuinely on the
other end: the referring organisation, the patient, and the four outside services
the hospital buys capacity or distribution from. They are drawn as black boxes in
a row under the pool.

What a reader can follow without leaving the diagram
-----------------------------------------------------
    referral in -> pack checked -> clinically reviewed -> accepted or not
    -> new patient appointment booked -> attended -> consent and treatment
       request -> clinic letter drafted, approved, processed, dispatched
    -> funding route, charge, payment, or an urgent-treatment authorisation
    -> treatment series planned against external capacity -> cycle scheduled ->
       clinically reviewed -> continued, delayed or changed -> follow-up ->
       outcome -> rebook, settle the account, or close the pathway

and, running alongside it, the enquiry path (administrative, financial or
clinical, urgent or routine) and the weekly correspondence sweep with its
one-month and three-month escalations.

Every user task carries a Camunda Form and a candidate group; every service task
carries a job type an external worker subscribes to.
"""

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from layout_engine import MessageFlow                      # noqa: E402
from bpmn_builder_v3 import V3Builder                      # noqa: E402

PROCESS_ID = "hospital-patient-pathway"

# --------------------------------------------------------------- lanes -----
# (lane name, rows, responsibility lane)
LANES = [
    ("Medical Secretaries", 2, "Administrative responsibility"),
    ("Outpatient Bookings Team", 2, "Administrative responsibility"),
    ("Treatment and Chemotherapy Bookings Team", 2, "Administrative responsibility"),
    ("Call Handling Team", 2, "Administrative responsibility"),
    ("Patient Pathway Coordinators", 2, "Administrative responsibility"),
    ("Administrative Management Team", 1, "Administrative responsibility"),
    ("Consultants", 2, "Clinical responsibility"),
    ("Clinical Nurse Specialist Team", 1, "Clinical responsibility"),
    # the last row of the last lane is deliberately empty: the router sends every
    # backward flow down the bottom-most corridor, and an empty row gives it one
    # that runs through no element
    ("Finance Team", 5, "Financial responsibility"),
]
RESPONSIBILITY_ORDER = ["Clinical responsibility",
                        "Administrative responsibility",
                        "Financial responsibility"]

MS, OB, TB, CH, PC, AM, CO, CNS, FI = range(9)

# ---------------------------------------------------------------- pools -----
POOL_DOC = (
    "The hospital's operational patient pathway, drawn as one pool because one "
    "organisation owns it end to end. Lanes separate responsibility, not "
    "ownership: clinical decisions belong to Consultants and the Clinical Nurse "
    "Specialist Team, administrative work to Medical Secretaries, the booking "
    "teams, Call Handling, the Patient Pathway Coordinators and the "
    "Administrative Management Team, and money to the Finance Team. An activity "
    "in one lane may not be performed by another: clinical staff do not approve "
    "refunds, administrative staff do not judge clinical suitability, and the "
    "Finance Team does not decide clinical need. Steps that an external worker "
    "performs are service tasks; steps that need a person and a form are user "
    "tasks."
)

EXTERNAL_PARTICIPANTS = [
    ("P_Referrer", "Referring organisation (GP or other hospital)"),
    ("P_Patient", "Patient or authorised representative"),
    ("P_Scheduling", "External scheduling service"),
    ("P_Correspondence", "External correspondence service"),
    ("P_Payment", "External payment service provider"),
    ("P_ClinicalServices", "External treatment, laboratory and imaging services"),
]

ERRORS = [
    ("REFERRAL_PACK_INCOMPLETE", "Referral pack failed the document checklist"),
    ("REFERRAL_PACK_UNREADABLE", "Referral documents could not be read"),
    ("SCHEDULING_SERVICE_UNAVAILABLE", "External scheduling service unavailable"),
    ("CORRESPONDENCE_SERVICE_FAILED", "External correspondence service rejected the job"),
    ("PAYMENT_PROVIDER_UNAVAILABLE", "External payment provider unavailable"),
    ("PAYMENT_CONFIRMATION_LOST", "Payment taken but no confirmation returned"),
    ("EXTERNAL_RESOURCE_UNAVAILABLE", "External treatment or diagnostic resource unavailable"),
    ("TREATMENT_REQUEST_UNAUTHORISED", "Treatment booking request is not authorised"),
    ("CHARGE_CALCULATION_FAILED", "Applicable charge could not be calculated"),
    ("INVALID_DATE", "A recorded date is not allowed by the shared date rules"),
]


# ------------------------------------------------------- build-time checks --
# DEF-02 was a real defect: the form submits a radio value as a string, the model
# compared it against a boolean literal, and FEEL does not consider "true" and
# true equal - so the condition was false for every patient who consented and the
# gateway took its default branch. Nine of the ten form-backed booleans were
# written correctly and one was not, which is exactly the sort of thing a person
# reading the file will not catch. This check is the promise in docs/01 section C4
# kept in the generator rather than in a deleted script.

# Variables a worker writes as a real JSON boolean. Everything else that a form
# collects is a string, because form-js always submits one.
WORKER_BOOLEANS = {"referralPackComplete", "externalResourcesAvailable"}

FORM_TYPES = ("radio", "select", "checkbox", "checklist", "textfield", "textarea",
              "number", "datetime", "taglist", "table")


def form_keys():
    """key -> component type, for every field in every form in model/forms."""
    import glob
    import json as _json
    out = {}
    here = os.path.dirname(os.path.abspath(__file__))
    for path in glob.glob(os.path.join(here, "..", "model", "forms", "*.form")):
        data = _json.load(open(path, encoding="utf-8"))

        def walk(comps):
            for comp in comps:
                if comp.get("key"):
                    out[comp["key"]] = comp.get("type")
                if comp.get("components"):
                    walk(comp["components"])
        walk(data.get("components", []))
    return out


def check_conditions(flows, keys=None):
    """Reject a condition that compared the wrong type. Returns problem strings."""
    keys = form_keys() if keys is None else keys
    problems = []
    for row in flows:
        cond = row[3] if len(row) > 3 else None
        if not cond:
            continue
        for var, literal in re.findall(
                r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(\"(?:true|false)\"|true|false)", cond):
            quoted = literal.startswith('"')
            if var in WORKER_BOOLEANS:
                if quoted:
                    problems.append(
                        "%s compares worker boolean %s against the string %s"
                        % (cond, var, literal))
                continue
            if keys.get(var) in FORM_TYPES and not quoted:
                problems.append(
                    "%s compares form field %s (%s, so a string) against the boolean %s"
                    % (cond, var, keys[var], literal))
    return problems


def check_gateway_variables(flows, keys=None, worker_variables=None):
    """Every variable a gateway tests must be set by a form or by a worker.

    The consentGiven defect was one of three of the same shape: a condition that
    read a variable nothing ever wrote, so the gateway quietly took its default
    branch and no test noticed because the driver was posting variables the form
    never submits. This is the general form of that check.
    """
    keys = form_keys() if keys is None else keys
    if worker_variables is None:
        worker_variables = WorkerVariables()
    problems = []
    for row in flows:
        cond = row[3] if len(row) > 3 else None
        if not cond:
            continue
        for var in set(re.findall(r"([A-Za-z_][A-Za-z0-9_]*)\s*=", cond)):
            if var in keys or var in worker_variables:
                continue
            problems.append("%s tests %s, which no form field and no worker sets"
                            % (cond, var))
    return sorted(set(problems))


class WorkerVariables(set):
    """The variables the Java workers write, read out of their own source."""

    def __init__(self, root=None):
        here = os.path.dirname(os.path.abspath(__file__))
        root = root or os.path.join(here, "..", "workers", "src", "main", "java")
        found = set()
        for base, _dirs, files in os.walk(root):
            for name in files:
                if not name.endswith(".java"):
                    continue
                text = open(os.path.join(base, name), encoding="utf-8",
                            errors="replace").read()
                found.update(re.findall(r'\.put\("([^"]+)"', text))
                found.update(re.findall(r'\.require(?:OneOf|First)?\(\s*"([^"]+)"', text))
        super().__init__(found)


# Variables that arrive with the case rather than being set anywhere in the
# process: the correlation key the referral is opened under, and the values the
# driver seeds so a worker is never handed a blank. Anything else a gateway tests
# has to be written by a form or by a worker that runs before it.
EXTERNAL_VARIABLES = {"patientRef"}


def _worker_outputs():
    """job type -> the variables its worker writes, read out of the Java source."""
    import collections
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.join(here, "..", "workers", "src", "main", "java")
    out = collections.defaultdict(set)
    for base, _dirs, files in os.walk(root):
        for name in files:
            if not name.endswith("Worker.java"):
                continue
            text = open(os.path.join(base, name), encoding="utf-8",
                        errors="replace").read()
            jt = re.search(r'JOB_TYPE\s*=\s*"([^"]+)"', text)
            if not jt:
                continue
            out[jt.group(1)].update(re.findall(r'output\.put\("([^"]+)"', text))
    return out


def check_gateway_sources(nodes, flows, keys=None, outputs=None):
    """A gateway must not test a variable nothing upstream of it writes.

    This is the check that would have caught the three of these that were really
    there: consentGiven compared against the wrong type, and modificationAuthorised
    and outcomeAction, which no form and no worker set at all - so the gateway
    took its default branch every time and looked fine.
    """
    keys = form_keys() if keys is None else keys
    outputs = _worker_outputs() if outputs is None else outputs

    sets_here = {}
    for nid, kind, name, lane, row, col, opts in nodes:
        written = set()
        if kind == "utask" and opts.get("form"):
            written |= set(_form_fields(opts["form"]))
        if kind == "stask" and opts.get("type"):
            written |= set(outputs.get(opts["type"], ()))
        sets_here[nid] = written

    upstream = {}
    incoming = {}
    for src, tgt, _n, _c, _d in flows:
        incoming.setdefault(tgt, set()).add(src)

    def walk(node, seen):
        for src in incoming.get(node, ()):
            if src in seen:
                continue
            seen.add(src)
            walk(src, seen)
        return seen

    problems = []
    for nid, kind, name, lane, row, col, opts in nodes:
        if kind not in ("xg", "ig"):
            continue
        for src, tgt, _n, cond, _d in flows:
            if src != nid or not cond:
                continue
            available = set(EXTERNAL_VARIABLES) | sets_here.get(nid, set())
            for up in walk(nid, set()):
                available |= sets_here.get(up, set())
            for var in set(re.findall(r"([A-Za-z_][A-Za-z0-9_]*)\s*=", cond)):
                if var not in available:
                    problems.append(
                        "%s tests %s, but nothing upstream of %s writes it (%s)"
                        % (cond, var, nid, name))
    return sorted(set(problems))


def _form_fields(form_id):
    here = os.path.dirname(os.path.abspath(__file__))
    import json as _json
    path = os.path.join(here, "..", "model", "forms", form_id + ".form")
    if not os.path.exists(path):
        return set()
    data = _json.load(open(path, encoding="utf-8"))
    out = set()

    def walk(comps):
        for comp in comps:
            if comp.get("key"):
                out.add(comp["key"])
            if comp.get("components"):
                walk(comp["components"])
    walk(data.get("components", []))
    return out


# Date-capturing user tasks with no service task after them. The rule can never fire,
# because no worker runs to validate the date. Listed explicitly so the gap is stated
# rather than hidden; see docs/20 section "Date rules".
DATE_RULES_WITHOUT_A_CHECK = {
    "ADM_Task_ContactConsultant":
        "followed only by end events, so no service task runs to validate contactedOn or "
        "expectedCompletionDate",
    "ADM_Task_ReferHigher":
        "followed only by end events, so no service task runs to validate referralDate",
}


def check_date_repair_points():
    """Every date rule must be enforced at a service task that can hand it back.

    A date that breaks the shared table is raised as the BPMN error INVALID_DATE, so the
    service task that raises it needs a matching boundary event. This check ties the three
    moving parts together - the rule table, the form the rule names, and the wiring in this
    file - and fails the build when a new rule is added without the boundary that catches it.
    The previous defect this guards against is real: an uncaught BPMN error raises an
    unhandled-error incident, which is worse than the retry loop it replaces.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    import json as _json
    table_path = os.path.join(here, "..", "workers", "src", "main", "resources",
                              "date-rules.json")
    if not os.path.exists(table_path):
        return ["date-rules.json not found at " + table_path]
    table = _json.load(open(table_path, encoding="utf-8"))

    forms = {opts.get("form"): nid for nid, kind, _n, _l, _r, _c, opts in NODES
             if kind == "utask"}
    wired = {ut for _host, ut in DATE_REPAIR_POINTS}
    declared_host = {ut: host for host, ut in DATE_REPAIR_POINTS}

    # first service task reached from each user task, walking through gateways and events
    outgoing = {}
    for src, tgt, _n, _c, _d in FLOWS:
        outgoing.setdefault(src, []).append(tgt)
    kinds = {n[0]: n[1] for n in NODES}

    def first_services(start):
        seen, queue, found = set(), list(outgoing.get(start, ())), []
        while queue:
            nid = queue.pop(0)
            if nid in seen:
                continue
            seen.add(nid)
            kind = kinds.get(nid)
            if kind == "stask":
                found.append(nid)
            elif kind in ("utask", "end", "endterminate"):
                continue
            else:
                queue.extend(outgoing.get(nid, ()))
        return sorted(set(found))

    problems = []
    for kind in ("futureDates", "pastOnlyDates"):
        for entry in table.get(kind, []):
            form, field = entry["form"], entry["field"]
            ut = forms.get(form)
            if ut is None:
                problems.append("date rule %s.%s names a form no user task binds" % (form, field))
                continue
            if ut in DATE_RULES_WITHOUT_A_CHECK:
                continue
            if ut not in wired:
                problems.append("%s.%s is captured by %s, which has no INVALID_DATE repair "
                                "point" % (form, field, ut))
                continue
            host = declared_host[ut]
            expected = first_services(ut)
            if host not in expected:
                problems.append("%s.%s: repair boundary is on %s but the first service task "
                                "after %s is %s" % (form, field, host, ut, expected or "none"))
    return sorted(set(problems))


def check_form_worker_types(keys=None):
    """A variable a worker reads as a list must not come from a free-text field.

    finance.record-funding-approval read `fundingLimitations` with `optStringList`,
    and the field on determine-funding-route is a **textarea** - so the funding
    approval failed with "must be a list but was String (111)" the first time a
    person typed in that optional field. No automated run caught it: the driver fills
    only the fields a form marks required, and never submits the rest.

    A checklist or taglist submits a JSON list; anything else submits a string.
    """
    keys = form_keys() if keys is None else keys
    list_types = ("checklist", "taglist")
    problems = []
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.join(here, "..", "workers", "src", "main", "java")
    for base, _dirs, files in os.walk(root):
        for name in files:
            if not name.endswith("Worker.java"):
                continue
            text = open(os.path.join(base, name), encoding="utf-8",
                        errors="replace").read()
            job = re.search(r'JOB_TYPE\s*=\s*"([^"]+)"', text)
            job_type = job.group(1) if job else name
            for call, var in re.findall(
                    r'job\.(optStringList|optList|requireStringList|requireList)'
                    r'\(\s*"([^"]+)"', text):
                kind = keys.get(var)
                if kind and kind not in list_types:
                    problems.append(
                        "%s reads %s as a list with %s(), but the form field is a %s, "
                        "which submits a string" % (job_type, var, call, kind))
    return sorted(set(problems))


def check_option_values(flows, keys=None):
    """A condition must compare a choice field against one of its own options.

    appointmentOutcome, declinedAction and paymentStatus each had a form offering
    values the step downstream refuses, or a model testing a value the form never
    offers - so a branch was unreachable or a worker failed the job. Neither is
    visible by reading one file.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    import glob as _glob
    import json as _json
    options = {}
    for path in _glob.glob(os.path.join(here, "..", "model", "forms", "*.form")):
        data = _json.load(open(path, encoding="utf-8"))

        def walk(comps):
            for comp in comps:
                if comp.get("key") and comp.get("values"):
                    options.setdefault(comp["key"], set()).update(
                        str(v.get("value")) for v in comp["values"])
                if comp.get("components"):
                    walk(comp["components"])
        walk(data.get("components", []))

    problems = []
    for row in flows:
        cond = row[3] if len(row) > 3 else None
        if not cond:
            continue
        for var, value in re.findall(r'([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"([^"]*)"', cond):
            if var in options and value not in options[var]:
                problems.append('%s tests %s = "%s", but the form offers %s'
                                % (cond, var, value, sorted(options[var])))
    return sorted(set(problems))

# ---------------------------------------------------------------- nodes -----
# (id, kind, name, lane, row, col, opts)
NODES = [
    # -- referral intake and the missing-information loop (Medical Secretaries)
    # A none start event, so the pathway begins at a plain start circle. The
    # referral is still what opens a case; it arrives as the trigger that creates
    # the instance (CreateProcessInstance with the case variables) rather than as
    # a message the engine subscribes to. The referring organisation keeps its
    # hand-off into the model: it is now drawn against the reply it sends to the
    # missing-information request, which was previously not drawn at all.
    # Camunda 8 allows one none start event alongside message start events.
    ("Start_Referral", "start", "Referral received", MS, 0, 0, {}),
    ("SEC_Task_CheckPack", "utask", "Check the referral pack against the document checklist",
     MS, 0, 1, {"form": "check-referral-pack", "candidate_groups": "medical-secretaries",
                "documentation": "Captures what arrived and what is missing. The task never records "
                                 "a view on whether the referral is clinically appropriate."}),
    ("SEC_Auto_ValidateDocuments", "stask", "Validate the supporting documents",
     MS, 0, 2, {"type": "referral.check-supporting-documents",
                "documentation": "Checks the pack against the document checklist and raises "
                                 "REFERRAL_PACK_INCOMPLETE rather than letting an incomplete pack "
                                 "reach a Consultant."}),
    # the worker raises two distinct codes from this one activity, and an
    # uncaught BPMN error stops the instance wherever it happens to be. Found by
    # running the model: the first draft caught only the incomplete pack and the
    # unreadable one produced UNHANDLED_ERROR_EVENT at run time.
    ("SEC_Bnd_PackIncomplete", "bnderror", "incomplete",
     MS, 0, 2, {"attach": "SEC_Auto_ValidateDocuments", "error": "REFERRAL_PACK_INCOMPLETE"}),
    ("SEC_Bnd_PackUnreadable", "bnderror", "unreadable",
     MS, 0, 2, {"attach": "SEC_Auto_ValidateDocuments", "error": "REFERRAL_PACK_UNREADABLE"}),
    ("SEC_GW_PackComplete", "xg", "Is the referral pack complete?", MS, 0, 3,
     {"documentation": "The only route to a clinical decision is a complete pack."}),
    ("SEC_Throw_InfoRequested", "throw", "Ask the referring organisation for what is missing",
     MS, 1, 4, {"msg": "referral.info-requested",
                "headers": {"messageName": "referral.info-requested"}}),
    ("SEC_EGW_InfoRequest", "eg", "Waiting for the missing information", MS, 1, 5, {}),
    ("SEC_Catch_InfoReceived", "catch", "Information received", MS, 1, 6,
     {"msg": "referral.info-received"}),
    ("SEC_Catch_InfoTimeout", "ctimer", "No response after 14 days", MS, 1, 7,
     {"timer": "P14D"}),
    ("End_InfoNotReceived", "end", "Referral closed - information not received", MS, 1, 8, {}),

    # -- clinical decision on the referral (Consultants)
    ("CON_Task_ReviewReferral", "utask", "Review the referral and record the clinical decision",
     CO, 0, 4, {"form": "review-referral", "candidate_groups": "consultants",
                "documentation": "The decision is accept, reject, redirect or request further "
                                 "detail. Only an authorised Consultant may accept a referral, and "
                                 "an appointment may not be arranged before that acceptance."}),
    ("CON_Auto_AuditDecision", "stask", "Write the clinical decision to the audit trail",
     CO, 0, 5, {"type": "audit.record-clinical-decision"}),
    ("SEC_Task_NotifyReferrer", "utask", "Record the decision and notify the referring organisation",
     MS, 0, 6, {"form": "notify-referrer-outcome", "candidate_groups": "medical-secretaries"}),
    ("SEC_Throw_OutcomeToReferrer", "throw", "Return the decision and the reason",
     MS, 0, 7, {"msg": "referral.outcome-sent",
                "headers": {"messageName": "referral.outcome-sent"}}),
    ("SEC_GW_Outcome", "xg", "Was the referral accepted?", MS, 0, 8, {}),
    ("End_ReferralNotAccepted", "end", "Referral not accepted or redirected; referrer informed",
     MS, 0, 9, {}),

    # -- new patient appointment (Outpatient Bookings)
    ("OUT_Auto_CheckPriority", "stask", "Work out the speciality, priority and contact rule",
     OB, 0, 10, {"type": "booking.check-priority-and-contact-rule"}),
    ("OUT_Auto_FindSlots", "stask", "Search the external scheduling service",
     OB, 0, 11, {"type": "scheduling.find-appointment-slots"}),
    ("OUT_Bnd_SchedulingUnavailable", "bnderror", "Scheduling service unavailable",
     OB, 0, 11, {"attach": "OUT_Auto_FindSlots", "error": "SCHEDULING_SERVICE_UNAVAILABLE"}),
    ("OUT_GW_SlotsFound", "xg", "Did the service return anything usable?", OB, 0, 12, {}),
    ("OUT_Task_ReviewAvailability", "utask", "Decide what to do without a suitable slot",
     OB, 1, 12, {"form": "review-appointment-availability",
                 "candidate_groups": "outpatient-bookings",
                 "documentation": "Urgent referrals that cannot wait for the normal administrative "
                                  "timescale, and requests with no slot in the clinically requested "
                                  "period, are escalated rather than booked outside the window."}),
    ("OUT_GW_AvailabilityAction", "xg", "How should the booking gap be handled?", OB, 1, 13, {}),
    ("OUT_Task_ChooseSlot", "utask", "Choose and confirm the appointment",
     OB, 0, 13, {"form": "choose-appointment-slot", "candidate_groups": "outpatient-bookings"}),
    ("OUT_Auto_CreateAppointment", "stask", "Create the appointment record",
     OB, 0, 14, {"type": "booking.create-appointment"}),
    ("OUT_GW_NotifyChannels", "ig", "Which contacts does this patient need?", OB, 0, 15,
     {"documentation": "The letter always goes; a telephone call is added when the appointment is "
                       "inside two weeks."}),
    ("OUT_Auto_DispatchAppointmentLetter", "stask", "Send the appointment letter",
     OB, 0, 16, {"type": "correspondence.dispatch-letter"}),
    ("OUT_Bnd_LetterFailed", "bnderror", "Rejected by the correspondence service",
     OB, 0, 16, {"attach": "OUT_Auto_DispatchAppointmentLetter",
                 "error": "CORRESPONDENCE_SERVICE_FAILED"}),
    ("OUT_Task_ChaseLetter", "utask", "Resolve the distribution problem and pick another channel",
     OB, 1, 16, {"form": "resolve-dispatch-problem", "candidate_groups": "outpatient-bookings"}),
    ("CALL_Task_ContactPatient", "utask", "Telephone the patient about the appointment",
     CH, 1, 16, {"form": "record-telephone-contact-attempt",
                 "candidate_groups": "call-handling"}),
    ("CALL_Auto_RecordContactAttempt", "stask", "Record the contact attempt and its outcome",
     CH, 1, 17, {"type": "enquiry.record-contact-attempt",
                 "documentation": "Every attempt and its outcome is recorded, so a patient who "
                                  "cannot be reached is visible on the pathway rather than silently "
                                  "un-notified."}),
    ("OUT_GW_NotifyJoin", "ig", "Patient notification complete", OB, 0, 17, {}),
    # A person, not a message. v16.0 waited here for an `appointment.attended`
    # message from the patient pool, which meant the pathway could only move if
    # something outside the engine published it - so a demonstration could not be
    # driven from Tasklist alone. The bookings team marking the patient in is the
    # same business step, and it is the form the next task already assumes.
    ("OUT_Task_RecordAttendance", "utask",
     "Record the patient's attendance at the new patient appointment",
     OB, 0, 18, {"form": "record-attendance",
                 "candidate_groups": "outpatient-bookings",
                 "documentation": "The patient came in. This records when and who marked them in, "
                                  "so the consultant on the next task is recording consent for an "
                                  "appointment that demonstrably took place. No clinical view is "
                                  "taken here."}),

    # -- consultation, consent and the treatment booking request (Consultants)
    ("CON_Task_RecordConsent", "utask", "Record consent and complete the treatment booking request",
     CO, 0, 19, {"form": "record-consent-and-treatment-request",
                 "candidate_groups": "consultants",
                 "documentation": "Records the proposed treatment, the start date, the number and "
                                  "frequency of cycles, the reviews between cycles and any special "
                                  "resource the treatment needs."}),
    ("CON_GW_Consent", "xg", "Has the patient agreed to proceed?", CO, 0, 20, {}),
    ("CON_Auto_AuthoriseRequest", "stask", "Authorise the treatment booking request",
     CO, 0, 21, {"type": "treatment.authorise-request",
                 "documentation": "A request that an appropriate clinical professional has not "
                                  "authorised must not be processed by administrative staff."}),
    ("OUT_Task_RecordDecline", "utask", "Record the decline and arrange clinical follow-up",
     OB, 1, 21, {"form": "record-treatment-decline", "candidate_groups": "outpatient-bookings"}),
    ("End_TreatmentDeclined", "end", "Patient does not proceed with treatment", OB, 1, 22, {}),

    # -- clinic letter (Consultants draft, Medical Secretaries process)
    ("CON_Task_DraftLetter", "utask", "Draft and approve the clinic letter",
     CO, 0, 22, {"form": "draft-clinic-letter", "candidate_groups": "consultants",
                 "documentation": "Every consultation produces a clinic letter. The first is the "
                                  "New Patient Clinic Letter and it must be completed, approved, "
                                  "processed and sent within seven days."}),
    ("CON_Bnd_LetterReminder", "bndmsg", "reminder", CO, 0, 22,
     {"attach": "CON_Task_DraftLetter", "msg": "letter.reminder", "non_interrupting": True}),
    ("CON_Bnd_LetterOverdue", "bndtimer", "day 7", CO, 0, 22,
     {"attach": "CON_Task_DraftLetter", "timer": "P7D", "non_interrupting": True}),
    ("CON_Auto_RecordReminder", "stask", "Record the reminder against the letter",
     CO, 1, 23, {"type": "letter.record-reminder"}),
    ("End_ReminderRecorded", "end", "Reminder recorded", CO, 1, 24, {}),
    ("PCW_Auto_AddToMonitoring", "stask", "Add the letter to pathway monitoring",
     PC, 0, 23, {"type": "pathway.add-to-monitoring"}),
    ("End_LetterMonitoring", "end", "Letter under pathway monitoring", PC, 0, 24, {}),
    ("CON_GW_LetterApproved", "xg", "Has the Consultant approved the letter?", CO, 0, 23, {}),
    ("SEC_Task_ProcessLetter", "utask", "Check and process the approved clinic letter",
     MS, 0, 24, {"form": "process-clinic-letter", "candidate_groups": "medical-secretaries",
                 "documentation": "Confirms the recipients and arranges distribution, may correct "
                                  "formatting and clear administrative errors, and must not change "
                                  "the clinical meaning."}),
    ("SEC_GW_LetterCheck", "xg", "Does the letter need a clinical correction?", MS, 0, 25,
     {"documentation": "A suspected clinical error goes back to the Consultant rather than being "
                       "corrected administratively."}),
    ("CON_Task_CorrectLetter", "utask", "Correct and re-approve the clinic letter",
     CO, 0, 26, {"form": "correct-clinic-letter", "candidate_groups": "consultants"}),
    ("SEC_Auto_PrepareDispatch", "stask", "Prepare the letter for dispatch",
     MS, 1, 26, {"type": "correspondence.prepare-dispatch"}),
    ("SEC_Auto_DispatchClinicLetter", "stask", "Dispatch the approved clinic letter",
     MS, 1, 27, {"type": "correspondence.dispatch-letter",
                 "documentation": "Records the drafting, approval, processing and distribution "
                                  "dates for the letter."}),

    # -- funding, charge and payment (Finance Team)
    ("FIN_Task_DetermineFunding", "utask",
     "Establish the funding route and record the authorisation",
     FI, 0, 28, {"form": "determine-funding-route", "candidate_groups": "finance",
                 "documentation": "Records the funding organisation, the authorisation reference, "
                                  "the approved amount and any limitation. The Finance Team does "
                                  "not decide clinical need."}),
    ("FIN_Bnd_FundingOverdue", "bndtimer", "Authorisation still outstanding", FI, 0, 28,
     {"attach": "FIN_Task_DetermineFunding", "timer": "P2D", "non_interrupting": True}),
    ("FIN_Auto_AuditFunding", "stask", "Record the funding decision for audit",
     FI, 0, 29, {"type": "audit.record-financial-decision"}),
    ("TRT_Task_ReviewFundingTimeout", "utask", "Chase the outstanding funding approval",
     TB, 1, 29, {"form": "chase-funding-approval", "candidate_groups": "treatment-bookings"}),
    ("FIN_GW_FundingRoute", "xg", "Which funding route applies?", FI, 0, 30, {}),
    ("FIN_Task_ChasePreAuthorisation", "utask", "Chase the insurer for pre-authorisation",
     FI, 1, 31, {"form": "chase-pre-authorisation", "candidate_groups": "finance"}),
    ("FIN_Auto_CalculateCharge", "stask", "Work out the charge payable",
     FI, 2, 31, {"type": "finance.calculate-charge"}),
    ("FIN_Bnd_ChargeFailed", "bnderror", "Pricing failed", FI, 2, 31,
     {"attach": "FIN_Auto_CalculateCharge", "error": "CHARGE_CALCULATION_FAILED"}),
    ("FIN_Auto_RecordApproval", "stask", "Record the funding approval",
     FI, 0, 32, {"type": "finance.record-funding-approval"}),
    ("FIN_Auto_PreparePayment", "stask", "Prepare the secure payment request",
     FI, 1, 32, {"type": "payment.prepare-request",
                 "documentation": "Complete card details are never stored by the hospital."}),
    ("FIN_Task_ManualCharge", "utask", "Price the treatment manually",
     FI, 2, 32, {"form": "manual-charge-entry", "candidate_groups": "finance"}),
    ("FIN_Auto_ProcessPayment", "stask", "Take the payment through the provider",
     FI, 1, 33, {"type": "payment.process-transaction"}),
    ("FIN_Bnd_ConfirmationLost", "bnderror", "No confirmation returned",
     FI, 1, 33, {"attach": "FIN_Auto_ProcessPayment", "error": "PAYMENT_CONFIRMATION_LOST"}),
    ("FIN_GW_PaymentOutcome", "xg", "What did the provider report?", FI, 1, 34, {}),
    ("FIN_Auto_RecordPayment", "stask", "Record the payment against the account",
     FI, 0, 35, {"type": "finance.record-payment-outcome"}),
    ("FIN_Auto_Deduplicate", "stask", "Check the charge has not already been taken",
     FI, 2, 35, {"type": "finance.check-duplicate-payment"}),
    ("TRT_Task_ReviewDeclinedPayment", "utask", "Decide how to handle the failed payment",
     TB, 1, 35, {"form": "review-declined-payment", "candidate_groups": "treatment-bookings"}),
    ("FIN_Task_InvestigatePayment", "utask", "Investigate the unconfirmed payment",
     FI, 3, 35, {"form": "investigate-unconfirmed-payment", "candidate_groups": "finance"}),
    ("TRT_GW_DeclinedAction", "xg", "Try again, ask a clinician, or leave it with Finance?",
     TB, 1, 36, {}),
    ("FIN_GW_InvestigationOutcome", "xg", "Was the money actually taken?", FI, 3, 36, {}),
    ("CON_Task_AuthoriseUrgentTreatment", "utask",
     "Authorise urgent treatment without confirmed payment",
     CO, 1, 36, {"form": "authorise-urgent-treatment", "candidate_groups": "consultants",
                 "documentation": "The only way treatment may start without a recorded payment, "
                                  "funding approval or exemption."}),
    ("CON_GW_UrgentAuthorised", "xg", "May treatment go ahead unconfirmed?", CO, 1, 37, {}),
    ("End_PaymentUnresolved", "end", "Payment unresolved; booking not confirmed", FI, 3, 38, {}),

    # -- treatment series (Treatment and Chemotherapy Bookings Team)
    ("TRT_Auto_ValidateRequest", "stask", "Check the request is complete and authorised",
     TB, 0, 37, {"type": "treatment.validate-request"}),
    ("TRT_Bnd_NotAuthorised", "bnderror", "Not authorised",
     TB, 0, 37, {"attach": "TRT_Auto_ValidateRequest",
                 "error": "TREATMENT_REQUEST_UNAUTHORISED"}),
    ("End_RequestNotAuthorised", "end", "Request returned to the clinical team for authorisation",
     TB, 1, 38, {}),
    ("TRT_Auto_CreateSeries", "stask", "Create the provisional appointment series",
     TB, 0, 38, {"type": "treatment.create-appointment-series"}),
    ("TRT_Auto_CheckExternalResources", "stask", "Check external treatment and diagnostic capacity",
     TB, 0, 39, {"type": "external-resources.check-availability"}),
    ("TRT_Bnd_ExternalUnavailable", "bnderror", "Capacity unavailable",
     TB, 0, 39, {"attach": "TRT_Auto_CheckExternalResources",
                 "error": "EXTERNAL_RESOURCE_UNAVAILABLE"}),
    ("TRT_Auto_RecordRetry", "stask", "Record another capacity attempt",
     TB, 1, 39, {"type": "treatment.record-capacity-retry"}),
    ("TRT_GW_CapacityCap", "xg", "Have we tried long enough?", TB, 1, 40,
     {"documentation": "A capped retry: three attempts, then release what was provisionally held "
                       "rather than leaving it committed."}),
    ("TRT_GW_ExternalAvailable", "xg", "Is everything available?", TB, 0, 41, {}),
    ("TRT_Auto_ConfirmAppointments", "stask", "Confirm the treatment appointments",
     TB, 0, 42, {"type": "treatment.confirm-appointments",
                 "documentation": "Committing the series is the point of no return: from here the "
                                  "appointments are held against the hospital's capacity, so the "
                                  "activity carries a compensation handler that gives them back."}),
    # Compensation, not a plain undo step. The series is committed here and only
    # here; if the plan changes later the confirmed appointments have to be
    # released, and compensation is the BPMN construct that ties the release to
    # the commitment instead of hoping nobody forgets it.
    ("TRT_Bnd_CompSeries", "bndcomp", "series committed",
     TB, 0, 42, {"attach": "TRT_Auto_ConfirmAppointments",
                 "handler": "TRT_Comp_ReleaseSeries"}),
    ("TRT_Comp_ReleaseSeries", "stask", "Release the confirmed series (compensation)",
     TB, 1, 42, {"type": "treatment.release-series", "for_compensation": True,
                 "documentation": "Compensation handler. Has no incoming sequence flow: the engine "
                                  "reaches it only when something throws compensation for the "
                                  "confirmed series."}),
    ("TRT_Throw_Compensate", "throwcomp", "Give back the appointments already held",
     TB, 1, 51, {}),
    ("TRT_Auto_ReleaseSeries", "stask", "Release the provisional series",
     TB, 1, 43, {"type": "treatment.release-series"}),
    ("End_BookingReleased", "end", "Provisional series released; no capacity held",
     TB, 1, 44, {}),
    ("TRT_Auto_SendTreatmentLetter", "stask", "Send the treatment confirmation letter",
     TB, 0, 44, {"type": "correspondence.dispatch-letter"}),
    ("TRT_Auto_ScheduleCycle", "stask", "Schedule the next cycle",
     TB, 0, 45, {"type": "treatment.schedule-next-cycle",
                 # the worker returns nextCycleNumber; the model's own counter is
                 # cycleNumber, because that is what the "are there further cycles"
                 # gateway below tests. Found by running: without the mapping the
                 # gateway evaluated a missing variable and the instance stopped.
                 "outputs": [("=nextCycleNumber", "cycleNumber")]}),
    ("TRT_Auto_FindCycleSlots", "stask", "Look for a slot for the next cycle",
     TB, 0, 46, {"type": "scheduling.find-appointment-slots"}),
    ("TRT_GW_CycleSlots", "xg", "Was a cycle slot found?", TB, 0, 47, {}),
    ("TRT_Auto_ReleaseCycle", "stask", "Release the provisional cycle slot",
     TB, 1, 48, {"type": "treatment.release-cycle-booking"}),
    ("TRT_Task_RecordDelay", "utask", "Record the delay and re-plan the cycle",
     TB, 1, 49, {"form": "record-cycle-delay", "candidate_groups": "treatment-bookings"}),

    # -- cycle review (Consultants)
    ("CON_Task_ReviewCycle", "utask", "Review the blood results and decide on the next cycle",
     CO, 0, 48, {"form": "review-chemotherapy-cycle", "candidate_groups": "consultants",
                 "documentation": "A patient receiving several cycles is reviewed before each "
                                  "subsequent cycle to decide whether to continue, delay or change "
                                  "the plan."}),
    ("CON_Auto_AuditCycle", "stask", "Record the cycle review decision",
     CO, 0, 49, {"type": "audit.record-clinical-decision"}),
    ("CON_GW_CycleOutcome", "xg", "Is the patient fit to continue?", CO, 0, 50, {}),
    ("TRT_GW_MoreCycles", "xg", "Are there further cycles in this course?", TB, 0, 51, {}),

    # -- treatment change (bookings team raises, Consultant authorises)
    ("TRT_Task_ReviewModification", "utask", "Review the treatment change request",
     TB, 0, 52, {"form": "review-treatment-change", "candidate_groups": "treatment-bookings"}),
    ("CON_Task_AuthoriseModification", "utask", "Authorise the treatment modification",
     CO, 0, 53, {"form": "authorise-treatment-modification", "candidate_groups": "consultants"}),
    ("CON_GW_ModificationAuthorised", "xg", "Has the Consultant authorised the change?",
     CO, 0, 54, {}),
    ("End_ModificationRefused", "end", "Change not authorised; schedule unchanged", TB, 1, 54, {}),
    ("TRT_Auto_ApplyModification", "stask", "Apply the treatment change to the schedule",
     TB, 0, 55, {"type": "treatment.apply-modification"}),
    ("TRT_GW_ModificationFinancial", "xg", "Does the change affect money already handled?",
     TB, 0, 56, {}),
    ("End_ModificationApplied", "end", "Treatment change applied", TB, 0, 57, {}),

    # -- follow-up (Outpatient Bookings)
    ("OUT_Auto_FindFollowUpSlots", "stask", "Look for a follow-up slot",
     OB, 0, 52, {"type": "scheduling.find-appointment-slots"}),
    ("OUT_Bnd_FollowUpNoSlots", "bnderror", "No slot in the clinical window",
     OB, 0, 52, {"attach": "OUT_Auto_FindFollowUpSlots",
                 "error": "SCHEDULING_SERVICE_UNAVAILABLE"}),
    ("OUT_GW_FollowUpSlots", "xg", "Was a follow-up slot found inside the window?", OB, 0, 53, {}),
    ("OUT_Task_ConfirmFollowUp", "utask", "Confirm the follow-up appointment",
     OB, 0, 54, {"form": "confirm-follow-up-appointment",
                 "candidate_groups": "outpatient-bookings"}),
    ("OUT_Auto_CreateFollowUp", "stask", "Create the follow-up appointment",
     OB, 0, 55, {"type": "booking.create-appointment"}),
    ("OUT_Auto_SendFollowUpLetter", "stask", "Tell the patient about the follow-up",
     OB, 0, 56, {"type": "correspondence.dispatch-letter"}),
    # v16.0 waited here for an `appointment.outcome` message and then asked the very
    # next task to enter the outcome again, because `decide-cancellation-action`
    # already captures `appointmentOutcome` - the value `booking.record-appointment-
    # outcome` validates two steps later. The wait was redundant with the form, so
    # it is gone and the outcome is recorded once, by the person who knows it.
    ("OUT_Task_DecideNextAction", "utask", "Decide whether another appointment is offered",
     OB, 0, 58, {"form": "decide-cancellation-action", "candidate_groups": "outpatient-bookings",
                 "documentation": "Cancellations, declines and non-attendance are recorded and a "
                                  "decision is taken on offering another appointment, reviewing the "
                                  "pathway or informing the referring organisation. Continuing, "
                                  "delaying or ending treatment stays with authorised clinical "
                                  "professionals."}),
    ("OUT_Auto_RecordOutcome", "stask", "Record the appointment outcome",
     OB, 0, 59, {"type": "booking.record-appointment-outcome"}),
    ("OUT_GW_OutcomeAction", "xg", "What happens after the appointment?", OB, 0, 60, {}),
    ("OUT_Auto_FindRebookSlots", "stask", "Look for a replacement appointment",
     OB, 0, 61, {"type": "scheduling.find-appointment-slots"}),
    ("OUT_Bnd_RebookNoSlots", "bnderror", "No replacement slot",
     OB, 0, 61, {"attach": "OUT_Auto_FindRebookSlots",
                 "error": "SCHEDULING_SERVICE_UNAVAILABLE"}),
    ("End_Reoffered", "end", "Replacement appointment offered", OB, 0, 62, {}),
    ("OUT_Throw_ReferrerNotified", "throw", "Inform the referring organisation",
     OB, 1, 63, {"msg": "pathway.closed",
                 "headers": {"messageName": "pathway.closed"}}),
    ("End_CancellationHandled", "end", "Cancellation handled; no replacement offered",
     OB, 1, 64, {}),
    ("End_PathwayComplete", "end", "Pathway complete", OB, 1, 65, {}),

    # -- weekly correspondence sweep and escalation (Patient Pathway Coordinators)
    ("PCW_Start_WeeklyReview", "timerstart", "Weekly correspondence review", PC, 0, 2,
     {"timer": "R/PT168H"}),
    ("PCW_Auto_FindOverdueLetters", "stask", "Find the letters that are overdue",
     PC, 0, 3, {"type": "pathway.find-overdue-clinic-letters"}),
    ("PCW_Task_ReviewOverdueList", "utask", "Review the outstanding correspondence list",
     PC, 0, 4, {"form": "review-outstanding-correspondence",
                "candidate_groups": "pathway-coordinators",
                "documentation": "The sweep produces the management view of referral volumes, "
                                 "outstanding referrals, waiting times, unsuccessful contact "
                                 "attempts, delayed letters, unresolved enquiries, booking delays, "
                                 "outstanding funding approvals, failed payments and refunds "
                                 "awaiting processing."}),
    ("PCW_GW_OverdueBand", "xg", "How far overdue is the letter?", PC, 0, 5, {}),
    ("PCW_Auto_SuppressDuplicates", "stask", "Drop letters that no longer need chasing",
     PC, 0, 6, {"type": "pathway.suppress-duplicate-reminders"}),
    ("PCW_Auto_SendReminder", "stask", "Send the weekly reminder to the Consultant",
     PC, 0, 7, {"type": "letter.record-reminder"}),
    ("End_ReminderIssued", "end", "Reminder issued", PC, 0, 8, {}),
    ("ADM_Task_ContactConsultant", "utask", "Contact the responsible Consultant",
     AM, 0, 6, {"form": "contact-consultant-overdue-letter",
                "candidate_groups": "administrative-management"}),
    ("ADM_GW_ManagerOutcome", "xg", "Has the letter been completed?", AM, 0, 7, {}),
    ("End_EscalationClosed", "end", "Escalation closed", AM, 0, 8, {}),
    ("ADM_Task_ReferHigher", "utask", "Refer the case to higher management",
     AM, 0, 9, {"form": "refer-to-higher-management",
                "candidate_groups": "administrative-management"}),
    ("End_HigherEscalation", "end", "Referred to higher management", AM, 0, 10, {}),
    ("PCW_Task_ReviewDelay", "utask", "Review the delay and agree the next step",
     PC, 1, 16, {"form": "review-booking-delay", "candidate_groups": "pathway-coordinators"}),
    ("PCW_GW_DelayAction", "xg", "What does the delay need?", PC, 1, 17, {}),
    ("PCW_Auto_SendDelayLetter", "stask", "Write to the patient about the delay",
     PC, 1, 18, {"type": "correspondence.dispatch-letter"}),
    ("End_PatientInformed", "end", "Patient informed and delay recorded", PC, 1, 19, {}),

    # -- enquiries (Call Handling, Clinical Nurse Specialists, Finance)
    ("Start_Enquiry", "msgstart", "Enquiry or contact received", CH, 0, 4,
     {"msg": "enquiry.received"}),
    ("CALL_Task_LogEnquiry", "utask", "Log the enquiry, classify it and set a priority",
     CH, 0, 5, {"form": "log-enquiry", "candidate_groups": "call-handling",
                "documentation": "Records when it was received, who handled it, which team owns it, "
                                 "the response given and whether the matter is resolved."}),
    ("CALL_GW_Category", "xg", "What kind of enquiry is this?", CH, 0, 6,
     {"documentation": "A call handler may answer straightforward administrative questions and "
                       "transfer other administrative matters, but must not diagnose a condition, "
                       "interpret test results, recommend treatment or give clinical advice."}),
    ("CALL_GW_Answerable", "xg", "Can this be answered with the information available?",
     CH, 0, 7, {}),
    ("CALL_Task_AnswerAdmin", "utask", "Answer the administrative question",
     CH, 0, 8, {"form": "answer-administrative-enquiry", "candidate_groups": "call-handling"}),
    ("OUT_Task_AnswerAdminEnquiry", "utask", "Answer the administrative enquiry",
     OB, 1, 8, {"form": "answer-administrative-enquiry",
                "candidate_groups": "outpatient-bookings"}),
    ("FIN_Task_AnswerEnquiry", "utask", "Answer the payment or funding enquiry",
     FI, 3, 8, {"form": "answer-financial-enquiry", "candidate_groups": "finance",
                "documentation": "Payment and funding enquiries that cannot be answered from "
                                 "authorised information are answered by the Finance Team."}),
    ("CNS_Task_TriageEnquiry", "utask", "Triage the clinical enquiry and respond",
     CNS, 0, 6, {"form": "triage-clinical-enquiry",
                 "candidate_groups": "clinical-nurse-specialists",
                 "documentation": "Urgent clinical concerns must be highlighted immediately; the "
                                  "rules for determining urgency are still to be agreed with the "
                                  "stakeholders."}),
    ("CNS_Bnd_UrgentOverdue", "bndtimer", "One hour", CNS, 0, 6,
     {"attach": "CNS_Task_TriageEnquiry", "timer": "PT1H", "non_interrupting": True}),
    ("CNS_GW_NeedsConsultant", "xg", "Does this need a Consultant?", CNS, 0, 7, {}),
    ("CNS_Auto_RecordAdvice", "stask", "Record the advice given",
     CNS, 0, 9, {"type": "cns.record-clinical-advice"}),
    ("CNS_Throw_UrgentEscalation", "throw", "Escalate the unanswered urgent concern",
     CNS, 0, 10, {"msg": "enquiry.urgent-escalated",
                  "headers": {"messageName": "enquiry.urgent-escalated"}}),
    ("End_UrgentEscalated", "end", "Urgent concern escalated", CNS, 0, 11, {}),
    ("CON_Task_ClinicalReview", "utask", "Provide the clinical review outcome",
     CO, 1, 8, {"form": "clinical-review-advice", "candidate_groups": "consultants"}),
    ("CALL_Auto_CloseEnquiry", "stask", "Close the enquiry record",
     CH, 0, 10, {"type": "enquiry.close-record"}),
    ("End_EnquiryResolved", "end", "Enquiry answered and recorded", CH, 0, 11, {}),

    # -- financial impact and refunds (Finance Team)
    ("FIN_Task_ReviewImpact", "utask", "Review the financial impact of the treatment change",
     FI, 0, 64, {"form": "review-financial-impact", "candidate_groups": "finance",
                 "documentation": "A change that affects a charge, a funding approval or a "
                                  "completed payment is referred here before the schedule moves on."}),
    ("FIN_GW_ImpactAction", "xg", "What does the change require?", FI, 0, 65, {}),
    ("FIN_Task_DecideRefund", "utask", "Decide whether a refund is due",
     FI, 0, 66, {"form": "decide-refund", "candidate_groups": "finance",
                 "documentation": "Where treatment is cancelled, postponed or changed after "
                                  "payment, Finance records whether a full or partial refund is due. "
                                  "Clinical staff must not approve refunds."}),
    ("FIN_Auto_AuditRefund", "stask", "Record the refund decision for audit",
     FI, 1, 67, {"type": "audit.record-financial-decision"}),
    ("FIN_GW_RefundDecision", "xg", "What did Finance decide?", FI, 1, 68, {}),
    ("FIN_Auto_PrepareRefund", "stask", "Prepare the approved refund",
     FI, 1, 69, {"type": "finance.prepare-refund"}),
    ("FIN_Auto_ProcessRefund", "stask", "Send the refund to the payment provider",
     FI, 1, 70, {"type": "payment.process-refund"}),
    ("FIN_Bnd_RefundFailed", "bnderror", "Provider rejected the refund",
     FI, 1, 70, {"attach": "FIN_Auto_ProcessRefund", "error": "PAYMENT_PROVIDER_UNAVAILABLE"}),
    ("FIN_Auto_RecordNoRefund", "stask", "Record that no refund is due",
     FI, 2, 69, {"type": "finance.record-refund"}),
    ("End_RefundPending", "end", "Refund still with the provider; patient informed",
     FI, 3, 71, {}),
    ("FIN_Auto_RecordRefund", "stask", "Record the refund against the patient account",
     FI, 1, 71, {"type": "finance.record-refund"}),
    ("End_NoRefundDue", "end", "No refund due; decision recorded", FI, 2, 70, {}),
    ("End_RefundRecorded", "end", "Refund recorded", FI, 1, 72, {}),
]

# ---------------------------------------------------------------- flows -----
# (source, target, name, condition, is_default)
FLOWS = [
    # referral intake
    ("Start_Referral", "SEC_Task_CheckPack", None, None, False),
    ("SEC_Task_CheckPack", "SEC_Auto_ValidateDocuments", None, None, False),
    ("SEC_Auto_ValidateDocuments", "SEC_GW_PackComplete", None, None, False),
    ("SEC_GW_PackComplete", "CON_Task_ReviewReferral", "pack complete",
     '= referralPackComplete = true', False),
    ("SEC_GW_PackComplete", "SEC_Throw_InfoRequested", "pack incomplete", None, True),
    ("SEC_Bnd_PackIncomplete", "SEC_Throw_InfoRequested", None, None, False),
    ("SEC_Bnd_PackUnreadable", "SEC_Throw_InfoRequested", None, None, False),
    ("SEC_Throw_InfoRequested", "SEC_EGW_InfoRequest", None, None, False),
    ("SEC_EGW_InfoRequest", "SEC_Catch_InfoReceived", None, None, False),
    ("SEC_EGW_InfoRequest", "SEC_Catch_InfoTimeout", None, None, False),
    ("SEC_Catch_InfoReceived", "SEC_Task_CheckPack", None, None, False),
    ("SEC_Catch_InfoTimeout", "End_InfoNotReceived", None, None, False),

    # clinical decision and referral outcome
    ("CON_Task_ReviewReferral", "CON_Auto_AuditDecision", None, None, False),
    ("CON_Auto_AuditDecision", "SEC_Task_NotifyReferrer", None, None, False),
    ("SEC_Task_NotifyReferrer", "SEC_Throw_OutcomeToReferrer", None, None, False),
    ("SEC_Throw_OutcomeToReferrer", "SEC_GW_Outcome", None, None, False),
    ("SEC_GW_Outcome", "OUT_Auto_CheckPriority", "accepted",
     '= clinicalDecision = "ACCEPT"', False),
    ("SEC_GW_Outcome", "End_ReferralNotAccepted", "not accepted", None, True),

    # new patient appointment
    ("OUT_Auto_CheckPriority", "OUT_Auto_FindSlots", None, None, False),
    ("OUT_Auto_FindSlots", "OUT_GW_SlotsFound", None, None, False),
    ("OUT_GW_SlotsFound", "OUT_Task_ChooseSlot", "options available",
     '= slotCount > 0', False),
    ("OUT_GW_SlotsFound", "OUT_Task_ReviewAvailability", "nothing suitable", None, True),
    ("OUT_Bnd_SchedulingUnavailable", "OUT_Task_ReviewAvailability", None, None, False),
    ("OUT_Task_ReviewAvailability", "OUT_GW_AvailabilityAction", None, None, False),
    ("OUT_GW_AvailabilityAction", "OUT_Auto_CheckPriority", "search wider",
     '= availabilityAction = "WIDEN_SEARCH"', False),
    ("OUT_GW_AvailabilityAction", "PCW_Task_ReviewDelay", "escalate",
     None, True),
    ("OUT_Task_ChooseSlot", "OUT_Auto_CreateAppointment", None, None, False),
    ("OUT_Auto_CreateAppointment", "OUT_GW_NotifyChannels", None, None, False),
    ("OUT_GW_NotifyChannels", "OUT_Auto_DispatchAppointmentLetter", "letter always",
     '= true', False),
    ("OUT_GW_NotifyChannels", "CALL_Task_ContactPatient",
     "call as well", '= requiresPhoneCall = "true"', False),
    ("OUT_Auto_DispatchAppointmentLetter", "OUT_GW_NotifyJoin", None, None, False),
    ("OUT_Bnd_LetterFailed", "OUT_Task_ChaseLetter", None, None, False),
    ("OUT_Task_ChaseLetter", "OUT_Auto_DispatchAppointmentLetter", None, None, False),
    ("CALL_Task_ContactPatient", "CALL_Auto_RecordContactAttempt", None, None, False),
    ("CALL_Auto_RecordContactAttempt", "OUT_GW_NotifyJoin", None, None, False),
    ("OUT_GW_NotifyJoin", "OUT_Task_RecordAttendance", None, None, False),

    # consultation and consent
    ("OUT_Task_RecordAttendance", "CON_Task_RecordConsent", None, None, False),
    ("CON_Task_RecordConsent", "CON_GW_Consent", None, None, False),
    ("CON_GW_Consent", "CON_Auto_AuthoriseRequest", "consent recorded",
     '= consentGiven = "true"', False),
    ("CON_GW_Consent", "OUT_Task_RecordDecline", "not proceeding", None, True),
    ("OUT_Task_RecordDecline", "End_TreatmentDeclined", None, None, False),
    ("CON_Auto_AuthoriseRequest", "CON_Task_DraftLetter", None, None, False),

    # clinic letter
    ("CON_Task_DraftLetter", "CON_GW_LetterApproved", None, None, False),
    ("CON_GW_LetterApproved", "SEC_Task_ProcessLetter", "approved",
     '= letterApproved = "true"', False),
    ("CON_GW_LetterApproved", "CON_Task_DraftLetter", "not yet", None, True),
    ("CON_Bnd_LetterReminder", "CON_Auto_RecordReminder", None, None, False),
    ("CON_Auto_RecordReminder", "End_ReminderRecorded", None, None, False),
    ("CON_Bnd_LetterOverdue", "PCW_Auto_AddToMonitoring", None, None, False),
    ("PCW_Auto_AddToMonitoring", "End_LetterMonitoring", None, None, False),
    ("SEC_Task_ProcessLetter", "SEC_GW_LetterCheck", None, None, False),
    ("SEC_GW_LetterCheck", "CON_Task_CorrectLetter", "suspected clinical error",
     '= clinicalErrorSuspected = "true"', False),
    ("SEC_GW_LetterCheck", "SEC_Auto_PrepareDispatch", "checks passed", None, True),
    ("SEC_Auto_PrepareDispatch", "SEC_Auto_DispatchClinicLetter", None, None, False),
    ("CON_Task_CorrectLetter", "SEC_Task_ProcessLetter", None, None, False),
    ("SEC_Auto_DispatchClinicLetter", "FIN_Task_DetermineFunding", None, None, False),

    # funding, charge and payment
    ("FIN_Task_DetermineFunding", "FIN_Auto_AuditFunding", None, None, False),
    ("FIN_Auto_AuditFunding", "FIN_GW_FundingRoute", None, None, False),
    ("FIN_GW_FundingRoute", "FIN_Auto_RecordApproval", "funded or exempt",
     '= fundingRoute = "HOSPITAL_FUNDED" or fundingRoute = "INSURER_APPROVED" '
     'or fundingRoute = "EXEMPTION"', False),
    ("FIN_GW_FundingRoute", "FIN_Auto_CalculateCharge", "patient pays",
     '= fundingRoute = "PATIENT_PAYS"', False),
    ("FIN_GW_FundingRoute", "FIN_Task_ChasePreAuthorisation", "pre-auth outstanding",
     None, True),
    ("FIN_Task_ChasePreAuthorisation", "FIN_Auto_RecordApproval", None, None, False),
    ("FIN_Bnd_FundingOverdue", "TRT_Task_ReviewFundingTimeout", None, None, False),
    ("TRT_Task_ReviewFundingTimeout", "FIN_Task_ChasePreAuthorisation", None, None, False),
    ("FIN_Auto_CalculateCharge", "FIN_Auto_PreparePayment", None, None, False),
    ("FIN_Bnd_ChargeFailed", "FIN_Task_ManualCharge", None, None, False),
    ("FIN_Task_ManualCharge", "FIN_Auto_PreparePayment", None, None, False),
    ("FIN_Auto_PreparePayment", "FIN_Auto_ProcessPayment", None, None, False),
    ("FIN_Auto_RecordApproval", "TRT_Auto_ValidateRequest", None, None, False),
    ("FIN_Auto_ProcessPayment", "FIN_GW_PaymentOutcome", None, None, False),
    ("FIN_Bnd_ConfirmationLost", "FIN_Task_InvestigatePayment", None, None, False),
    ("FIN_GW_PaymentOutcome", "FIN_Auto_RecordPayment", "approved",
     '= paymentStatus = "APPROVED"', False),
    ("FIN_GW_PaymentOutcome", "FIN_Auto_Deduplicate", "duplicate charge",
     '= paymentStatus = "DUPLICATE"', False),
    ("FIN_GW_PaymentOutcome", "TRT_Task_ReviewDeclinedPayment", "declined or cancelled",
     None, True),
    ("FIN_Auto_RecordPayment", "TRT_Auto_ValidateRequest", None, None, False),
    ("FIN_Auto_Deduplicate", "TRT_Auto_ValidateRequest", None, None, False),
    ("TRT_Task_ReviewDeclinedPayment", "TRT_GW_DeclinedAction", None, None, False),
    ("TRT_GW_DeclinedAction", "FIN_Auto_PreparePayment", "try another payment",
     '= declinedAction = "RETRY_PAYMENT"', False),
    ("TRT_GW_DeclinedAction", "CON_Task_AuthoriseUrgentTreatment",
     "ask a clinician", '= declinedAction = "SEEK_AUTHORISATION"', False),
    ("TRT_GW_DeclinedAction", "FIN_Task_InvestigatePayment", "leave with Finance",
     None, True),
    ("CON_Task_AuthoriseUrgentTreatment", "CON_GW_UrgentAuthorised", None, None, False),
    ("CON_GW_UrgentAuthorised", "TRT_Auto_ValidateRequest", "clinician authorised",
     '= urgentTreatmentAuthorised = "true"', False),
    ("CON_GW_UrgentAuthorised", "FIN_Task_InvestigatePayment", "not authorised", None, True),
    ("FIN_Task_InvestigatePayment", "FIN_GW_InvestigationOutcome", None, None, False),
    ("FIN_GW_InvestigationOutcome", "FIN_Auto_RecordPayment", "money taken",
     '= paymentFound = "true"', False),
    ("FIN_GW_InvestigationOutcome", "End_PaymentUnresolved", "nothing was taken", None, True),

    # treatment series
    ("TRT_Auto_ValidateRequest", "TRT_Auto_CreateSeries", None, None, False),
    ("TRT_Bnd_NotAuthorised", "End_RequestNotAuthorised", None, None, False),
    ("TRT_Auto_CreateSeries", "TRT_Auto_CheckExternalResources", None, None, False),
    ("TRT_Auto_CheckExternalResources", "TRT_GW_ExternalAvailable", None, None, False),
    ("TRT_Bnd_ExternalUnavailable", "TRT_Auto_RecordRetry", None, None, False),
    ("TRT_Auto_RecordRetry", "TRT_GW_CapacityCap", None, None, False),
    ("TRT_GW_CapacityCap", "TRT_Auto_CheckExternalResources", "try again",
     '= externalResourceAttempts < 3', False),
    ("TRT_GW_CapacityCap", "TRT_Auto_ReleaseSeries", "release the series",
     None, True),
    ("TRT_Auto_ReleaseSeries", "End_BookingReleased", None, None, False),
    ("TRT_GW_ExternalAvailable", "TRT_Auto_ConfirmAppointments", "all resources held",
     '= externalResourcesAvailable = true', False),
    ("TRT_GW_ExternalAvailable", "TRT_Auto_ReleaseSeries", "unavailable",
     None, True),
    ("TRT_Auto_ConfirmAppointments", "TRT_Auto_SendTreatmentLetter", None, None, False),
    ("TRT_Auto_SendTreatmentLetter", "TRT_Auto_ScheduleCycle", None, None, False),
    ("TRT_Auto_ScheduleCycle", "TRT_Auto_FindCycleSlots", None, None, False),
    ("TRT_Auto_FindCycleSlots", "TRT_GW_CycleSlots", None, None, False),
    ("TRT_GW_CycleSlots", "CON_Task_ReviewCycle", "slot found", '= slotCount > 0', False),
    ("TRT_GW_CycleSlots", "TRT_Auto_ReleaseCycle", "nothing available", None, True),
    ("TRT_Auto_ReleaseCycle", "TRT_Task_RecordDelay", None, None, False),
    ("TRT_Task_RecordDelay", "TRT_Auto_ScheduleCycle", None, None, False),

    # cycle review
    ("CON_Task_ReviewCycle", "CON_Auto_AuditCycle", None, None, False),
    ("CON_Auto_AuditCycle", "CON_GW_CycleOutcome", None, None, False),
    ("CON_GW_CycleOutcome", "TRT_GW_MoreCycles", "fit to continue",
     '= cycleReviewOutcome = "FIT_TO_CONTINUE"', False),
    ("CON_GW_CycleOutcome", "TRT_Task_RecordDelay", "delay the cycle",
     '= cycleReviewOutcome = "DELAY"', False),
    ("CON_GW_CycleOutcome", "TRT_Throw_Compensate", "change the plan", None, True),
    ("TRT_Throw_Compensate", "TRT_Task_ReviewModification", None, None, False),
    ("TRT_GW_MoreCycles", "TRT_Auto_ScheduleCycle", "more cycles",
     '= cycleNumber < cycleCount', False),
    ("TRT_GW_MoreCycles", "OUT_Auto_FindFollowUpSlots", "course complete",
     None, True),

    # treatment change
    ("TRT_Task_ReviewModification", "CON_Task_AuthoriseModification", None, None, False),
    ("CON_Task_AuthoriseModification", "CON_GW_ModificationAuthorised", None, None, False),
    ("CON_GW_ModificationAuthorised", "TRT_Auto_ApplyModification", "authorised",
     '= modificationAuthorised = "true"', False),
    ("CON_GW_ModificationAuthorised", "End_ModificationRefused", "not authorised", None, True),
    ("TRT_Auto_ApplyModification", "TRT_GW_ModificationFinancial", None, None, False),
    ("TRT_GW_ModificationFinancial", "FIN_Task_ReviewImpact",
     "money affected", '= modificationAffectsFinance = "true"', False),
    ("TRT_GW_ModificationFinancial", "End_ModificationApplied", "no financial impact",
     None, True),
    ("FIN_Task_ReviewImpact", "FIN_GW_ImpactAction", None, None, False),
    ("FIN_GW_ImpactAction", "FIN_Task_DecideRefund", "refund required",
     '= impactAction = "REFUND_REQUIRED"', False),
    ("FIN_GW_ImpactAction", "TRT_GW_MoreCycles", "no refund", None, True),

    # follow-up
    ("OUT_Auto_FindFollowUpSlots", "OUT_GW_FollowUpSlots", None, None, False),
    ("OUT_Bnd_FollowUpNoSlots", "OUT_GW_FollowUpSlots", None, None, False),
    ("OUT_GW_FollowUpSlots", "OUT_Task_ConfirmFollowUp", "inside the window",
     '= slotCount > 0', False),
    ("OUT_GW_FollowUpSlots", "PCW_Task_ReviewDelay",
     "outside the window", None, True),
    ("OUT_Task_ConfirmFollowUp", "OUT_Auto_CreateFollowUp", None, None, False),
    ("OUT_Auto_CreateFollowUp", "OUT_Auto_SendFollowUpLetter", None, None, False),
    ("OUT_Auto_SendFollowUpLetter", "OUT_Task_DecideNextAction", None, None, False),
    ("OUT_Task_DecideNextAction", "OUT_Auto_RecordOutcome", None, None, False),
    ("OUT_Auto_RecordOutcome", "OUT_GW_OutcomeAction", None, None, False),
    # the values here are the ones decide-cancellation-action.form actually offers.
    # The draft tested a variable called outcomeAction that no form and no worker
    # ever set, so the gateway silently took its default branch every time.
    ("OUT_GW_OutcomeAction", "OUT_Auto_FindRebookSlots", "offer another",
     '= cancellationAction = "REBOOK"', False),
    ("OUT_GW_OutcomeAction", "PCW_Task_ReviewDelay", "clinical review of the pathway",
     '= cancellationAction = "CLINICAL_REVIEW"', False),
    ("OUT_GW_OutcomeAction", "OUT_Throw_ReferrerNotified", "close pathway", None, True),
    ("OUT_Throw_ReferrerNotified", "End_PathwayComplete", None, None, False),
    ("OUT_Bnd_RebookNoSlots", "End_CancellationHandled", None, None, False),
    ("OUT_Auto_FindRebookSlots", "End_Reoffered", None, None, False),

    # weekly correspondence sweep and escalation
    ("PCW_Start_WeeklyReview", "PCW_Auto_FindOverdueLetters", None, None, False),
    ("PCW_Auto_FindOverdueLetters", "PCW_Task_ReviewOverdueList", None, None, False),
    ("PCW_Task_ReviewOverdueList", "PCW_GW_OverdueBand", None, None, False),
    ("PCW_GW_OverdueBand", "PCW_Auto_SuppressDuplicates", "1 week to 1 month",
     '= letterOverdueDays <= 30', False),
    ("PCW_GW_OverdueBand", "ADM_Task_ContactConsultant", "over one month",
     '= letterOverdueDays > 30 and letterOverdueDays <= 90', False),
    ("PCW_GW_OverdueBand", "ADM_Task_ReferHigher", "over 3 months", None, True),
    ("PCW_Auto_SuppressDuplicates", "PCW_Auto_SendReminder", None, None, False),
    ("PCW_Auto_SendReminder", "End_ReminderIssued", None, None, False),
    ("ADM_Task_ContactConsultant", "ADM_GW_ManagerOutcome", None, None, False),
    ("ADM_GW_ManagerOutcome", "End_EscalationClosed", "completed - close",
     '= letterNowCompleted = "true"', False),
    ("ADM_GW_ManagerOutcome", "ADM_Task_ReferHigher", "still outstanding", None, True),
    ("ADM_Task_ReferHigher", "End_HigherEscalation", None, None, False),
    ("PCW_Task_ReviewDelay", "PCW_GW_DelayAction", None, None, False),
    ("PCW_GW_DelayAction", "OUT_Auto_CheckPriority", "search again",
     '= delayAction = "WIDEN_SEARCH"', False),
    ("PCW_GW_DelayAction", "PCW_Auto_SendDelayLetter", "inform the patient",
     None, True),
    ("PCW_Auto_SendDelayLetter", "End_PatientInformed", None, None, False),

    # enquiries
    ("Start_Enquiry", "CALL_Task_LogEnquiry", None, None, False),
    ("CALL_Task_LogEnquiry", "CALL_GW_Category", None, None, False),
    ("CALL_GW_Category", "CNS_Task_TriageEnquiry", "clinical",
     '= enquiryCategory = "CLINICAL"', False),
    ("CALL_GW_Category", "FIN_Task_AnswerEnquiry", "payment or funding",
     '= enquiryCategory = "FINANCIAL"', False),
    ("CALL_GW_Category", "CALL_GW_Answerable", "administrative", None, True),
    ("CALL_GW_Answerable", "CALL_Task_AnswerAdmin", "answered now",
     '= answerableNow = "true"', False),
    ("CALL_GW_Answerable", "OUT_Task_AnswerAdminEnquiry", "needs another team", None, True),
    ("CALL_Task_AnswerAdmin", "CALL_Auto_CloseEnquiry", None, None, False),
    ("OUT_Task_AnswerAdminEnquiry", "CALL_Auto_CloseEnquiry", None, None, False),
    ("FIN_Task_AnswerEnquiry", "CALL_Auto_CloseEnquiry", None, None, False),
    ("CNS_Task_TriageEnquiry", "CNS_GW_NeedsConsultant", None, None, False),
    ("CNS_Bnd_UrgentOverdue", "CNS_Throw_UrgentEscalation", None, None, False),
    ("CNS_Throw_UrgentEscalation", "End_UrgentEscalated", None, None, False),
    ("CNS_GW_NeedsConsultant", "CON_Task_ClinicalReview", "needs a Consultant",
     '= needsConsultantReview = "true"', False),
    ("CNS_GW_NeedsConsultant", "CNS_Auto_RecordAdvice", "answered directly", None, True),
    ("CON_Task_ClinicalReview", "CNS_Auto_RecordAdvice", None, None, False),
    ("CNS_Auto_RecordAdvice", "CALL_Auto_CloseEnquiry", None, None, False),
    ("CALL_Auto_CloseEnquiry", "End_EnquiryResolved", None, None, False),

    # refunds
    ("FIN_Task_DecideRefund", "FIN_Auto_AuditRefund", None, None, False),
    ("FIN_Auto_AuditRefund", "FIN_GW_RefundDecision", None, None, False),
    ("FIN_GW_RefundDecision", "FIN_Auto_PrepareRefund", "refund approved",
     '= refundDecision = "FULL_REFUND" or refundDecision = "PARTIAL_REFUND"', False),
    ("FIN_Auto_PrepareRefund", "FIN_Auto_ProcessRefund", None, None, False),
    ("FIN_GW_RefundDecision", "FIN_Auto_RecordNoRefund", "no refund due", None, True),
    ("FIN_Auto_ProcessRefund", "FIN_Auto_RecordRefund", None, None, False),
    ("FIN_Bnd_RefundFailed", "End_RefundPending", None, None, False),
    ("FIN_Auto_RecordRefund", "End_RefundRecorded", None, None, False),
    ("FIN_Auto_RecordNoRefund", "End_NoRefundDue", None, None, False),
]

# -------------------------------------------------- date rules on the model --
# A date that breaks date-rules.json is bad input, not a transient fault, so the worker
# raises INVALID_DATE and the token has to leave the service task through a boundary
# event instead of being retried. The boundary sits on the first service task reached
# after the user task that captures the date, and routes straight back to that user
# task, so the person corrects the date in the same form and submits again.
#
# (host service task, user task that captures the date)
DATE_REPAIR_POINTS = [
    ("SEC_Auto_ValidateDocuments",  "SEC_Task_CheckPack"),           # referralDate
    ("CON_Auto_AuditDecision",      "CON_Task_ReviewReferral"),      # decisionDate
    ("CNS_Auto_RecordAdvice",       "CON_Task_ClinicalReview"),      # reviewDate
    ("CON_Auto_AuditCycle",         "CON_Task_ReviewCycle"),         # reviewDate
    ("FIN_Auto_AuditRefund",        "FIN_Task_DecideRefund"),        # decisionDate
    ("FIN_Auto_AuditFunding",       "FIN_Task_DetermineFunding"),    # approvalDate
    ("TRT_Auto_ApplyModification",  "CON_Task_AuthoriseModification"),  # modificationDate
    ("CON_Auto_AuthoriseRequest",   "CON_Task_RecordConsent"),       # treatmentStartDate
    ("OUT_Auto_CreateAppointment",  "OUT_Task_ChooseSlot"),          # appointmentDateTime
    ("OUT_Auto_CreateFollowUp",     "OUT_Task_ConfirmFollowUp"),     # appointmentDateTime
    ("OUT_Auto_CheckPriority",      "OUT_Task_ReviewAvailability"),  # preferred window
    ("TRT_Auto_ScheduleCycle",      "TRT_Task_RecordDelay"),         # newProposedStartDate
    ("CALL_Auto_RecordContactAttempt", "CALL_Task_ContactPatient"),  # preferredAlternativeDate
]

def _date_repair_wiring():
    """Boundary events and return flows for DATE_REPAIR_POINTS, placed in the host's cell."""
    index = {n[0]: n for n in NODES}
    nodes, flows = [], []
    for host, utask in DATE_REPAIR_POINTS:
        if host not in index:
            raise SystemExit("date repair: unknown service task " + host)
        if utask not in index or index[utask][1] != "utask":
            raise SystemExit("date repair: unknown user task " + utask)
        h = index[host]
        bid = host + "_Bnd_InvalidDate"
        nodes.append((bid, "bnderror", "a recorded date is not allowed",
                      h[3], h[4], h[5], {"attach": host, "error": "INVALID_DATE"}))
        flows.append((bid, utask, "correct the date and submit again", None, False))
    return nodes, flows


DATE_REPAIR_NODES, DATE_REPAIR_FLOWS = _date_repair_wiring()

# ------------------------------------------------------- message flows ------
# (source pool or None, source element or None, target pool or None,
#  target element or None, name)
MESSAGE_FLOWS = [
    ("P_Referrer", None, None, "SEC_Catch_InfoReceived",
     "Missing information supplied by the referring organisation"),
    (None, "SEC_Throw_InfoRequested", "P_Referrer", None,
     "Request for the missing information"),
    (None, "SEC_Throw_OutcomeToReferrer", "P_Referrer", None,
     "Referral decision and the reason for it"),
    ("P_Patient", None, None, "Start_Enquiry", "Enquiry or concern"),
    # The patient pool keeps its hand-offs, but they are now the hospital telling
    # the patient, not the patient telling the engine: the attendance and the
    # outcome are recorded by the bookings team on the two user tasks above.
    (None, "OUT_Auto_DispatchAppointmentLetter", "P_Patient", None,
     "Appointment details to the patient"),
    (None, "OUT_Auto_SendFollowUpLetter", "P_Patient", None,
     "Follow-up details to the patient"),
    (None, "OUT_Auto_FindSlots", "P_Scheduling", None, "Appointment slot search"),
    ("P_Scheduling", None, None, "OUT_Auto_FindSlots", "Available appointment slots"),
    (None, "OUT_Auto_DispatchAppointmentLetter", "P_Correspondence", None,
     "Appointment letter to dispatch"),
    (None, "SEC_Auto_DispatchClinicLetter", "P_Correspondence", None,
     "Clinic letter to dispatch"),
    (None, "FIN_Auto_PreparePayment", "P_Payment", None, "Secure payment request"),
    ("P_Payment", None, None, "FIN_Auto_ProcessPayment",
     "Payment status, reference, date and amount"),
    (None, "FIN_Auto_ProcessRefund", "P_Payment", None, "Refund request"),
    (None, "TRT_Auto_CheckExternalResources", "P_ClinicalServices", None,
     "Treatment, laboratory and imaging capacity request"),
    ("P_ClinicalServices", None, None, "TRT_Auto_CheckExternalResources",
     "Capacity available, and when"),
]

HOSPITAL_POOL = "P_Hospital"
HOSPITAL_NAME = "Hospital Patient Referral, Treatment and Administration Service"


def build():
    """Assemble the model. Returns a V3Builder ready to write out."""
    b = V3Builder()
    b.definitions_id = "Definitions_hospital_pathway_v16"
    pool = b.pool(HOSPITAL_POOL, HOSPITAL_NAME, process_id=PROCESS_ID,
                  documentation=POOL_DOC, version_tag="16.0.0")
    # leaf lanes, in layout order
    for name, rows, _resp in LANES:
        pool.lane(name, rows)
    # responsibility lanes, written as a childLaneSet
    groups, order = {}, []
    for i, (name, _rows, resp) in enumerate(LANES):
        if resp not in groups:
            groups[resp] = []
            order.append(resp)
        groups[resp].append(i)
    pool.group_lanes([(r, groups[r]) for r in RESPONSIBILITY_ORDER if r in groups])

    # `referral.received` is no longer declared: the pathway opens at a none start
    # event, so nothing subscribes to that message. Declaring it would leave an
    # orphan <bpmn:message> in the file.
    for name, key in (("referral.info-requested", '=patientRef + "-referral-info"'),
                      ("referral.info-received", '=patientRef + "-referral-info"'),
                      ("referral.outcome-sent", '=patientRef + "-referral-outcome"'),
                      ("letter.reminder", '=patientRef + "-letter-reminder"'),
                      ("pathway.closed", '=patientRef + "-pathway"'),
                      ("enquiry.received", "=patientRef"),
                      ("enquiry.urgent-escalated", '=patientRef + "-enquiry-escalation"')):
        b.msg(name, key)
    for code, label in ERRORS:
        b.error(code, label)

    for pid, pname in EXTERNAL_PARTICIPANTS:
        b.pool(pid, pname)

    for nid, kind, name, lane, row, col, opts in NODES + DATE_REPAIR_NODES:
        pool.n(nid, kind, name, lane, row, col, **opts)
    for src, tgt, name, cond, default in FLOWS + DATE_REPAIR_FLOWS:
        pool.f(src, tgt, cond=cond, name=name, default=default)

    problems = (check_conditions(FLOWS) + check_gateway_variables(FLOWS)
                + check_gateway_sources(NODES, FLOWS) + check_option_values(FLOWS)
                + check_form_worker_types() + check_date_repair_points())
    if problems:
        raise SystemExit("build check failed:\n  " + "\n  ".join(problems))

    def endpoint(pool_id, el_id):
        """A hospital endpoint names an element; a black box names itself."""
        return (HOSPITAL_POOL, el_id) if pool_id is None else (pool_id, pool_id)

    for src_pool, src_el, tgt_pool, tgt_el, name in MESSAGE_FLOWS:
        sp, se = endpoint(src_pool, src_el)
        tp, te = endpoint(tgt_pool, tgt_el)
        b.message_flows.append(MessageFlow(sp, se, tp, te, name))
    return b


if __name__ == "__main__":
    builder = build()
    problems = builder.validate()
    for p in problems:
        print("PROBLEM:", p)
    print("%d problems" % len(problems))
