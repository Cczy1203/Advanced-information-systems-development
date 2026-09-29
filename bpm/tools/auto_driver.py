#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hospital Patient Pathway - external automation driver (Option A)

Purpose
-------
Run the nine executable Camunda 8 pools end to end without touching the model
and without a Java/.NET worker.  The driver supplies the three things a
deployed-but-unattended model is missing:

  1. a worker for every external service task (35 job types),
  2. form auto-fill for every deployed user task (Tasklist v2 REST),
  3. replay of the messages that no pool throws (correlation key is read from
     the live subscription, never guessed).

It then walks a scenario list so that all 36 deployed .form resources are
exercised at least once.

Usage
-----
    python3 auto_driver.py --list                # show the scenarios
    python3 auto_driver.py --scenario OUT-book   # run one scenario
    python3 auto_driver.py --all                 # run every scenario
    python3 auto_driver.py --all --report out.json

Requirements: c8run (Camunda 8.10) reachable on http://localhost:8080 and the
v5 deployment of UFCEP6-0-3_Hospital_Patient_Pathway_v14.bpmn already loaded.
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

BASE = "http://localhost:8080"
TODAY = datetime.now().strftime("%Y-%m-%d")
NOW_ISO = TODAY + "T09:00:00"
WORKER = "pathway-auto-driver"
POOL_WORKERS = 8

# --------------------------------------------------------------------------
# every external job type used by the nine executable pools
# --------------------------------------------------------------------------
JOB_TYPES = [
    "audit.record-clinical-decision",
    "audit.record-financial-decision",
    "booking.check-priority-and-contact-rule",
    "booking.create-appointment",
    "booking.record-appointment-outcome",
    "cns.record-clinical-advice",
    "correspondence.dispatch-letter",
    "correspondence.prepare-dispatch",
    "enquiry.close-record",
    "enquiry.record-contact-attempt",
    "external-resources.check-availability",
    "finance.calculate-charge",
    "finance.check-duplicate-payment",
    "finance.prepare-refund",
    "finance.record-funding-approval",
    "finance.record-payment-outcome",
    "finance.record-refund",
    "letter.record-reminder",
    "pathway.add-to-monitoring",
    "pathway.find-overdue-letters",
    "pathway.suppress-duplicate-reminders",
    "payment.prepare-request",
    "payment.process-refund",
    "payment.process-transaction",
    "referral.check-supporting-documents",
    "scheduling.find-appointment-slots",
    "treatment.apply-modification",
    "treatment.authorise-request",
    "treatment.confirm-appointments",
    "treatment.create-appointment-series",
    "treatment.record-capacity-retry",
    "treatment.release-cycle-booking",
    "treatment.release-series",
    "treatment.schedule-next-cycle",
    "treatment.validate-request",
]

# --------------------------------------------------------------------------
# default service-task behaviour (variables chosen from the gateway conditions)
# --------------------------------------------------------------------------
BASE_JOB_POLICY = {
    # medical secretaries
    "SEC_Auto_ValidateDocuments": {"complete": {"referralPackComplete": True}},
    "SUB_Secretaries_Dispatch_Prepare": {"complete": {}},
    "SUB_Secretaries_Dispatch_Send": {"complete": {"dispatchStatus": "SENT"},
                                      "first_vars": {"times": 1,
                                                     "variables": {"dispatchStatus": "FAILED"}}},
    # finance
    "FIN_Auto_AuditFunding": {"complete": {}},
    "FIN_Auto_RecordApproval": {"complete": {}},
    "FIN_Auto_CalculateCharge": {"complete": {},
                                 "first_error": {"times": 1,
                                                 "errorCode": "CHARGE_CALCULATION_FAILED"}},
    "FIN_Auto_RecordPayment": {"complete": {}},
    "FIN_Auto_AuditRefund": {"complete": {}},
    "FIN_Auto_PrepareRefund": {"complete": {"refundStatus": "REFUNDED"}},
    "FIN_Auto_ProcessRefund": {"complete": {}},
    "FIN_Auto_RecordRefund": {"complete": {}},
    "FIN_Auto_RecordNoRefund": {"complete": {}},
    # treatment bookings
    "TRT_Auto_ValidateRequest": {"complete": {}},
    "TRT_Auto_PreparePayment": {"complete": {}},
    "TRT_Auto_ProcessPayment": {"complete": {"paymentStatus": "APPROVED"}},
    "TRT_Auto_Deduplicate": {"complete": {}},
    "TRT_Auto_NextAttempt": {"complete": {}},
    "TRT_Auto_CreateSeries": {"complete": {}},
    "TRT_Auto_CheckExternalResources": {"complete": {"externalResourcesAvailable": True}},
    "TRT_Auto_ConfirmAppointments": {"complete": {}},
    "TRT_Auto_SendTreatmentLetter": {"complete": {}},
    "TRT_Auto_ScheduleCycle": {"complete": {"cycleNumber": 1}},
    "TRT_Auto_FindCycleSlots": {"complete": {"slotCount": 1}},
    "TRT_Auto_ApplyModification": {"complete": {}},
    "TRT_Auto_RecordRetry": {"complete": {}},
    "TRT_Comp_ReleaseSeries": {"complete": {}},
    "TRT_Comp_ReleaseCycle": {"complete": {}},
    # consultants
    "CON_Auto_AuditDecision": {"complete": {}},
    "CON_Auto_AuthoriseRequest": {"complete": {}},
    "CON_Auto_AuditCycle": {"complete": {}},
    "CON_Auto_RecordReminder": {"complete": {}},
    # outpatient bookings
    "OUT_Auto_CheckPriority": {"complete": {"requiresPhoneCall": False}},
    "OUT_Auto_FindSlots": {"complete": {"slotCount": 1}},
    "OUT_Auto_CreateAppointment": {"complete": {}},
    "OUT_Auto_DispatchAppointmentLetter": {"complete": {},
                                           "first_error": {"times": 1,
                                                           "errorCode": "CORRESPONDENCE_SERVICE_FAILED"}},
    "OUT_Auto_FindFollowUpSlots": {"complete": {"slotCount": 1}},
    "OUT_Auto_CreateFollowUp": {"complete": {}},
    "OUT_Auto_SendFollowUpLetter": {"complete": {}},
    "OUT_Auto_RecordOutcome": {"complete": {}},
    "OUT_Auto_FindRebookSlots": {"complete": {"slotCount": 1}},
    # clinical nurse specialists
    "CNS_Auto_RecordAdvice": {"complete": {}},
    # call handling
    "CALL_Auto_CloseEnquiry": {"complete": {}},
    "SUB_CallHandling_Contact_Log": {"complete": {}},
    # patient pathway coordinators
    "PCW_Auto_SuppressDuplicates": {"complete": {}},
    "PCW_Auto_AddToMonitoring": {"complete": {}},
    "PCW_Auto_SendDelayLetter": {"complete": {}},
    "SUB_Pathway_Report_Find": {"complete": {}},
}

# --------------------------------------------------------------------------
# form answers that the default generator must not decide on its own
# --------------------------------------------------------------------------
BASE_FORM_VALUES = {
    "check-referral-pack": {},
    "notify-referrer-outcome": {"referralOutcome": "ACCEPTED"},
    "process-clinic-letter": {"clinicalErrorSuspected": "false"},
    "resolve-dispatch-problem": {},
    "determine-funding-route": {"fundingRoute": "PATIENT_PAYS"},
    "manual-charge-entry": {},
    "chase-pre-authorisation": {"outcome": "Awaiting response"},
    "investigate-unconfirmed-payment": {"paymentFound": "false"},
    "decide-refund": {"refundDecision": "NO_REFUND"},
    "review-financial-impact": {"impactAction": "NO_CHANGE"},
    "answer-financial-enquiry": {"resolvedNow": "true"},
    "review-referral": {"clinicalDecision": "ACCEPT"},
    "record-consent-and-treatment-request": {"consentGiven": "true"},
    "review-chemotherapy-cycle": {"cycleReviewOutcome": "FIT_TO_CONTINUE"},
    "authorise-treatment-modification": {"modificationUrgent": "false",
                                         "modificationAffectsFinance": "false"},
    "draft-clinic-letter": {"letterApproved": "true"},
    "correct-clinic-letter": {"letterApproved": "true"},
    "authorise-urgent-treatment": {},
    "clinical-review-advice": {},
    "review-declined-payment": {"declinedAction": "LEAVE_WITH_FINANCE"},
    "chase-funding-approval": {"fundingChaseOutcome": "STILL_WAITING"},
    "record-cycle-delay": {},
    "review-treatment-change": {"requestFormallySubmitted": "true"},
    "choose-appointment-slot": {},
    "review-appointment-availability": {"availabilityAction": "OFFER_NEXT_AVAILABLE"},
    "confirm-follow-up-appointment": {"withinRequestedPeriod": "true"},
    "decide-cancellation-action": {"cancellationAction": "CLOSE_AND_INFORM_REFERRER"},
    "record-treatment-decline": {},
    "answer-administrative-enquiry": {"answerableNow": "true"},
    "triage-clinical-enquiry": {"needsConsultantReview": "false"},
    "log-enquiry": {"enquiryCategory": "ADMINISTRATIVE"},
    "record-telephone-contact-attempt": {"contactOutcome": "REACHED"},
    "review-booking-delay": {"delayAction": "KEEP_PATIENT_INFORMED"},
    "review-outstanding-correspondence": {"letterOverdueDays": 10,
                                          "reminderAction": "SEND_REMINDER"},
    "contact-consultant-overdue-letter": {"letterNowCompleted": "true"},
    "refer-to-higher-management": {},
}

# variables attached when the driver has to publish a message that no pool throws
REPLAY_VARS = {
    "funding.decision-received": {"fundingRoute": "PATIENT_PAYS"},
}

PATIENT_REF = "PAT-2026-0001"

# --------------------------------------------------------------------------
# The Java external workers (workers/target/hospital-external-workers-*.jar)
# are running, so this driver no longer competes for service tasks.  What the
# deployment still needs from outside is:
#   * a business context on every start/message, otherwise the workers fail
#     jobs with "Required process variable ... is missing" (audit needs
#     patientRef, payment needs paymentReference, treatment needs
#     treatmentBookingRef, ...);
#   * the variable each worker already reads to reach a non-happy branch
#     (simulateNoSlots, simulatedPaymentStatus, an empty dispatchRecipients
#     list, a blank treatmentPlan for the tariff failure, ...);
#   * replay of the messages no pool throws;
#   * form answers for every user task.
# --------------------------------------------------------------------------
SEED_VARS = {
    # identity / references used by job.requireFirst(...)
    "patientRef": PATIENT_REF,
    "referralRef": "REF-2026-0001",
    "enquiryRef": "ENQ-2026-0001",
    "letterRef": "LTR-2026-0001",
    "treatmentBookingRef": "TRT-2026-0001",
    "paymentReference": "PAY-2026-0001",
    "refundReference": "REFUND-2026-0001",
    "authorisationRef": "AUTH-2026-0001",
    # clinical decisions
    "clinicalDecision": "ACCEPT",
    "clinicalDecisionReason": "Clinically suitable for the pathway",
    "decidingClinician": "Dr A Chen",
    "authorisingClinician": "Dr A Chen",
    "clinicalAdviceSummary": "Advice given to the patient; red flags explained",
    "advisedBy": "CNS Rivera",
    # finance
    "financialDecision": "APPROVED",
    "financialDecisionReason": "Funding route confirmed by the finance team",
    "decidingFinanceOfficer": "Finance Officer Bell",
    "fundingRoute": "PATIENT_PAYS",
    # appointments / bookings
    "appointmentOutcome": "ATTENDED",
    "appointmentDateTime": NOW_ISO,
    "appointmentLocation": "Clinic Room 3",
    # treatment
    "treatmentPlan": "chemotherapy",
    "modificationReason": "Clinically indicated dose adjustment",
    # referral pack (check-supporting-documents reads supportingDocuments)
    "supportingDocuments": ["referral-letter", "blood-tests", "imaging-report"],
    # correspondence (dispatch-letter fails when there are no recipients)
    "dispatchRecipients": ["patient@example.nhs.uk"],
    "patientPreferredChannel": "POST",
    "dispatchChannel": "POST",
    "correlationKey": PATIENT_REF,
}


def msg(name, variables=None):
    t = {"kind": "message", "name": name}
    if variables:
        t["variables"] = variables
    return t


def start_pool(pool, element_id=None, variables=None):
    """Plain instance start.

    startInstructions are only posted when an element_id is given: a pool with
    several start events (message, timer, none) rejects a bare start, and a
    timer start event cannot be posted at all, so the none start event has to be
    named explicitly.
    """
    t = {"kind": "start", "pool": pool, "variables": variables or {}}
    if element_id:
        t["elementId"] = element_id
    return t


# --------------------------------------------------------------------------
# scenarios: every deployed .form must be reached at least once
# --------------------------------------------------------------------------
SCENARIOS = [
    # ---- consultants (8 forms, one message start each) ----
    {"id": "CON-review", "pool": "consultants", "trigger": msg("referral.review-requested"),
     "forms": ["review-referral"]},
    {"id": "CON-consent", "pool": "consultants", "trigger": msg("appointment.attended"),
     "forms": ["record-consent-and-treatment-request"]},
    {"id": "CON-cycle", "pool": "consultants", "trigger": msg("chemotherapy.review-requested"),
     "forms": ["review-chemotherapy-cycle"]},
    {"id": "CON-modification", "pool": "consultants", "trigger": msg("treatment.modification-requested"),
     "forms": ["authorise-treatment-modification"]},
    {"id": "CON-letter", "pool": "consultants", "trigger": msg("clinic.letter-draft-required"),
     "forms": ["draft-clinic-letter"]},
    {"id": "CON-correction", "pool": "consultants", "trigger": msg("letter.clinical-error-returned"),
     "forms": ["correct-clinic-letter"]},
    {"id": "CON-urgent", "pool": "consultants", "trigger": msg("treatment.urgency-authorisation-requested"),
     "forms": ["authorise-urgent-treatment"]},
    {"id": "CON-advice", "pool": "consultants", "trigger": msg("clinical.review-requested"),
     "forms": ["clinical-review-advice"]},

    # ---- medical secretaries (4 forms) ----
    {"id": "SEC-pack", "pool": "medical-secretaries",
     "trigger": start_pool("medical-secretaries"),
     "forms": ["check-referral-pack"]},
    {"id": "SEC-outcome", "pool": "medical-secretaries", "trigger": msg("referral.outcome-returned"),
     "forms": ["notify-referrer-outcome"]},
    {"id": "SEC-letter", "pool": "medical-secretaries", "trigger": msg("clinic.letter-approved"),
     "forms": ["process-clinic-letter", "resolve-dispatch-problem"],
     # SUB_Secretaries_Dispatch_Decide routes to the chase task only when
     # dispatchStatus != SENT, and the simulated correspondence service always
     # answers SENT, so the branch is activated directly.
     "modify": {"elementId": "SUB_Secretaries_Dispatch_Chase"}},

    # ---- finance team (7 forms) ----
    {"id": "FIN-manual-charge", "pool": "finance-team",
     "trigger": msg("funding.check-requested", {"fundingRoute": "PATIENT_PAYS",
                                               "treatmentPlan": ""}),
     "forms": ["determine-funding-route", "manual-charge-entry"],
     # finance.calculate-charge raises CHARGE_CALCULATION_FAILED (caught by the
     # boundary event -> manual-charge-entry) when no treatment plan or tariff
     # code can be found on the instance.
     "blank": ["treatmentPlan"]},
    {"id": "FIN-chase", "pool": "finance-team",
     "trigger": msg("funding.check-requested", {"fundingRoute": "PATIENT_PAYS"}),
     "forms": ["chase-pre-authorisation"],
     # INSURER_PENDING is not offered by the determine-funding-route radio, so
     # the pre-authorisation chase is reached by activating its task directly.
     "modify": {"elementId": "FIN_Task_ChasePreAuthorisation"}},
    {"id": "FIN-investigate", "pool": "finance-team", "trigger": msg("payment.investigation-requested"),
     "forms": ["investigate-unconfirmed-payment"]},
    {"id": "FIN-refund", "pool": "finance-team", "trigger": msg("refund.required"),
     "forms": ["decide-refund"]},
    {"id": "FIN-impact", "pool": "finance-team", "trigger": msg("finance.impact-review-requested"),
     "forms": ["review-financial-impact"]},
    {"id": "FIN-enquiry", "pool": "finance-team", "trigger": msg("enquiry.assigned-finance"),
     "forms": ["answer-financial-enquiry"]},

    # ---- treatment bookings (4 forms) ----
    {"id": "TRT-delay", "pool": "treatment-bookings", "trigger": msg("chemotherapy.cycle-delayed"),
     "forms": ["record-cycle-delay"]},
    {"id": "TRT-modification", "pool": "treatment-bookings", "trigger": msg("treatment.modification-requested"),
     "forms": ["review-treatment-change"]},
    {"id": "TRT-declined-payment", "pool": "treatment-bookings",
     "trigger": msg("treatment.booking-requested", {"patientRef": PATIENT_REF,
                                                    "simulatedPaymentStatus": "DECLINED"}),
     "forms": ["review-declined-payment"],
     "replay": ["funding.decision-received"]},
    {"id": "TRT-funding-timeout", "pool": "treatment-bookings",
     "trigger": msg("treatment.booking-requested", {"patientRef": PATIENT_REF}),
     "forms": ["chase-funding-approval"],
     "modify": {"elementId": "TRT_Task_ReviewFundingTimeout"}},

    # ---- outpatient bookings (7 forms) ----
    {"id": "OUT-book", "pool": "outpatient-bookings",
     "trigger": msg("referral.accepted", {"patientRef": PATIENT_REF}),
     "forms": ["choose-appointment-slot"]},
    {"id": "OUT-no-slot", "pool": "outpatient-bookings",
     "trigger": msg("referral.accepted", {"patientRef": PATIENT_REF,
                                          "simulateNoSlots": True}),
     "forms": ["review-appointment-availability"]},
    {"id": "OUT-follow-up", "pool": "outpatient-bookings",
     "trigger": msg("follow-up.appointment-requested", {"patientRef": PATIENT_REF}),
     "forms": ["confirm-follow-up-appointment"]},
    {"id": "OUT-cancellation", "pool": "outpatient-bookings",
     "trigger": msg("appointment.cancelled-or-dna", {"patientRef": PATIENT_REF}),
     "forms": ["decide-cancellation-action"]},
    {"id": "OUT-decline", "pool": "outpatient-bookings",
     "trigger": msg("treatment.declined", {"patientRef": PATIENT_REF}),
     "forms": ["record-treatment-decline"]},
    {"id": "OUT-admin-enquiry", "pool": "outpatient-bookings",
     "trigger": msg("enquiry.assigned-admin", {"patientRef": PATIENT_REF}),
     "forms": ["answer-administrative-enquiry"]},

    # ---- clinical nurse specialists (1 form) ----
    {"id": "CNS-triage", "pool": "clinical-nurse-specialists",
     "trigger": msg("enquiry.assigned-clinical", {"patientRef": PATIENT_REF}),
     "forms": ["triage-clinical-enquiry"]},

    # ---- call handling (3 forms) ----
    {"id": "CALL-enquiry", "pool": "call-handling",
     "trigger": msg("enquiry.received", {"answerableNow": "true", "patientRef": PATIENT_REF}),
     "forms": ["log-enquiry", "answer-administrative-enquiry"]},
    {"id": "CALL-phone-contact", "pool": "call-handling",
     "trigger": msg("appointment.phone-contact-requested", {"patientRef": PATIENT_REF}),
     "forms": ["record-telephone-contact-attempt"]},

    # ---- patient pathway coordinators (2 forms) ----
    {"id": "PCW-delay", "pool": "patient-pathway-coordinators",
     "trigger": msg("booking.no-slot-escalation", {"patientRef": PATIENT_REF}),
     "forms": ["review-booking-delay"]},
    {"id": "PCW-weekly-report", "pool": "patient-pathway-coordinators",
     # the pool has no plain none start event that the API accepts (the weekly
     # review hangs off a timer start event), so the reporting task itself is
     # used as the start instruction.
     "trigger": start_pool("patient-pathway-coordinators",
                           element_id="SUB_Pathway_Report_Review"),
     "forms": ["review-outstanding-correspondence"]},

    # ---- administrative management (2 forms) ----
    {"id": "ADM-overdue-letter", "pool": "administrative-management",
     "trigger": msg("letter.escalation-admin-manager", {"patientRef": PATIENT_REF}),
     "forms": ["contact-consultant-overdue-letter"]},
    {"id": "ADM-higher", "pool": "administrative-management",
     "trigger": msg("letter.escalation-higher-management", {"patientRef": PATIENT_REF}),
     "forms": ["refer-to-higher-management"]},
]

ALL_FORMS = sorted(BASE_FORM_VALUES.keys())


# --------------------------------------------------------------------------
# tiny REST helper
# --------------------------------------------------------------------------
def http(method, path, body=None, timeout=30):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode()
            return r.status, (json.loads(raw) if raw.strip() else {})
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            payload = json.loads(raw)
        except Exception:
            payload = {"raw": raw}
        return e.code, payload
    except Exception as e:  # connection refused etc.
        return 0, {"error": str(e)}


def first_value(comp):
    vals = comp.get("values") or []
    if vals:
        return vals[0].get("value")
    return None


def text_for(key):
    k = key.lower()
    if "patientref" in k:
        return PATIENT_REF
    if k.endswith("ref") or "reference" in k:
        return "REF-AUTO-0001"
    if k.endswith("by") or "clinician" in k or "consultantname" in k:
        return "auto.driver"
    if "email" in k:
        return "auto.driver@example.nhs.uk"
    if "contact" in k or "callername" in k:
        return "Test Contact 07700 900000"
    if "location" in k:
        return "Clinic Room 3"
    if "plan" in k or "treatmentplan" in k:
        return "Chemotherapy pathway - plan A"
    if "code" in k:
        return "TAR-001"
    return "AUTO-" + key.upper()


def build_values(components, form_id, overrides):
    out = {}
    for comp in components:
        if comp.get("components"):  # nested group
            out.update(build_values(comp["components"], form_id, overrides))
            continue
        key = comp.get("key")
        if not key:
            continue
        if key in overrides:
            out[key] = overrides[key]
            continue
        if not comp.get("validate", {}).get("required"):
            continue
        t = comp.get("type")
        if t in ("radio", "select"):
            v = first_value(comp)
            out[key] = v if v is not None else "AUTO"
        elif t == "number":
            mn = comp.get("validate", {}).get("min")
            out[key] = mn if isinstance(mn, (int, float)) else 1
        elif t == "datetime":
            out[key] = TODAY if comp.get("subtype") == "date" else NOW_ISO
        elif t == "checkbox":
            out[key] = False
        elif t == "checklist":
            vs = comp.get("values") or []
            out[key] = [vs[0]["value"]] if vs else []
        elif t == "textarea":
            out[key] = "Recorded by the automation driver for the end-to-end pathway run."
        else:
            out[key] = text_for(key)
    return out


# --------------------------------------------------------------------------
# driver
# --------------------------------------------------------------------------
class Driver:
    def __init__(self, jobs=None, forms=None, replay=None, verbose=True, with_jobs=False,
                 manual=False):
        # with_jobs=False: the Java workers own every service task.  Set it to
        # True only when the workers are stopped and this script has to play
        # the external staff itself.
        self.with_jobs = with_jobs
        # manual=True: the script never completes a user task itself.  It only
        # announces the tasks, watches the engine for the completions the human
        # performs in Tasklist, and keeps the rest of the pipeline (messages,
        # scenarios) moving.
        self.manual = manual
        self.started_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z")
        self.announced = set()
        self.element_form = {}
        self.scene_wanted = set()
        self.scene = None
        self.jobs = dict(jobs or {})
        self.forms = {k: dict(v) for k, v in BASE_FORM_VALUES.items()}
        if forms:
            for k, v in forms.items():
                self.forms.setdefault(k, {}).update(v)
        self.replay = set(replay or [])
        self.job_calls = {}
        self.scene_values = {}
        self.done_tasks = set()
        self.sent_messages = set()
        self.covered = {}
        self.errors = []
        self.verbose = verbose

    # ---------- service tasks ----------
    def activate_all_jobs(self):
        total = 0

        def one(t):
            st, resp = http("POST", "/v2/jobs/activation",
                            {"type": t, "maxJobsToActivate": 8, "timeout": 30000,
                             "requestTimeout": 1, "worker": WORKER})
            if st == 200:
                return resp.get("jobs", [])
            return []

        with ThreadPoolExecutor(max_workers=POOL_WORKERS) as ex:
            for jobs in ex.map(one, JOB_TYPES):
                for job in jobs:
                    self.handle_job(job)
                    total += 1
        return total

    def handle_job(self, job):
        el = job.get("elementId")
        key = job.get("jobKey")
        rule = self.jobs.get(el) or BASE_JOB_POLICY.get(el) or {"complete": {}}
        call = self.job_calls.get(el, 0)
        self.job_calls[el] = call + 1
        spec = rule.get("error") or rule.get("first_error")
        if spec and (spec.get("times", 0) == -1 or call < spec.get("times", 0)):
            http("POST", "/v2/jobs/%s/error" % key,
                 {"errorCode": spec["errorCode"],
                  "errorMessage": spec.get("errorMessage", "simulated failure")})
            self._log("job ERROR %s -> %s" % (el, spec["errorCode"]))
            return
        fv = rule.get("first_vars")
        variables = rule.get("complete", {})
        if fv and call < fv.get("times", 1):
            variables = fv.get("variables", variables)
        st, resp = http("POST", "/v2/jobs/%s/completion" % key,
                        {"variables": variables})
        if st not in (200, 204):
            self.errors.append({"elementId": el, "stage": "job-complete",
                                "status": st, "response": resp})
            self._log("job FAIL %s -> %s %s" % (el, st, resp))

    # ---------- user tasks / forms ----------
    def form_id_of(self, user_task_key):
        """formId of a task; the caller caches it per element."""
        st, form = http("GET", "/v2/user-tasks/%s/form" % user_task_key)
        if st != 200:
            return None
        return form.get("formId")

    def scan_completed_tasks(self):
        """Collect the user tasks finished in Tasklist after this run started."""
        st, resp = http("POST", "/v2/user-tasks/search",
                        {"filter": {"state": "COMPLETED",
                                    "completionDate": {"$gte": self.started_at}},
                         "sort": [{"field": "completionDate", "order": "DESC"}],
                         "page": {"limit": 30}})
        if st != 200:
            return 0
        found = 0
        for item in resp.get("items", []):
            el = item.get("elementId")
            fid = (self.element_form.get(el)
                   or self.form_id_of(item.get("userTaskKey")) or el)
            self.element_form[el] = fid
            if fid in self.covered:
                continue
            self.covered[fid] = {
                "form": fid,
                "task": item.get("name"),
                "elementId": el,
                "pool": item.get("processDefinitionId"),
                "processInstanceKey": item.get("processInstanceKey"),
                "at": datetime.now().strftime("%H:%M:%S"),
            }
            self._log("form DONE %-42s (Tasklist)" % fid)
            found += 1
        return found

    def activate_user_tasks(self):
        st, resp = http("POST", "/v2/user-tasks/search",
                        {"filter": {"state": "CREATED"}, "page": {"limit": 50}})
        if st != 200:
            return 0
        if self.manual:
            # announce the tasks, never complete them: the human works in Tasklist
            for item in resp.get("items", []):
                el = item.get("elementId")
                fid = (self.element_form.get(el)
                       or self.form_id_of(item.get("userTaskKey")) or el)
                self.element_form[el] = fid
                tk = item.get("userTaskKey")
                if tk in self.announced:
                    continue
                self.announced.add(tk)
                mark = ">>" if fid in self.scene_wanted else "  "
                self._log("%s Tasklist task: %-38s form=%s pool=%s"
                          % (mark, item.get("name"), fid, item.get("processDefinitionId")))
            return self.scan_completed_tasks()
        done = 0
        for item in resp.get("items", []):
            tk = item.get("userTaskKey")
            if tk in self.done_tasks:
                continue
            self.done_tasks.add(tk)
            if self.complete_task(item):
                done += 1
        return done

    def complete_task(self, item):
        tk = item.get("userTaskKey")
        st, form = http("GET", "/v2/user-tasks/%s/form" % tk)
        form_id, comps = None, []
        if st == 200:
            form_id = form.get("formId")
            try:
                comps = json.loads(form.get("schema") or "{}").get("components", [])
            except Exception:
                comps = []
        if form_id is None:
            form_id = item.get("elementId")
        ov = dict(self.forms.get(form_id, {}))
        ov.update(self.scene_values.get(form_id, {}))
        values = build_values(comps, form_id, ov)
        st2, resp2 = http("POST", "/v2/user-tasks/%s/completion" % tk, {"variables": values})
        if st2 in (200, 204):
            self.covered[form_id] = {
                "form": form_id,
                "task": item.get("name"),
                "elementId": item.get("elementId"),
                "pool": item.get("processDefinitionId"),
                "processInstanceKey": item.get("processInstanceKey"),
                "at": datetime.now().strftime("%H:%M:%S"),
            }
            self._log("form OK   %-42s %s" % (form_id, values and ""))
            return True
        self.errors.append({"form": form_id, "stage": "task-complete",
                            "status": st2, "response": resp2})
        self._log("form FAIL %-42s %s %s" % (form_id, st2, str(resp2)[:200]))
        return False

    # ---------- messages ----------
    def replay_messages(self):
        if not self.replay:
            return 0
        st, resp = http("POST", "/v2/message-subscriptions/search",
                        {"filter": {}, "page": {"limit": 100}})
        if st != 200:
            return 0
        sent = 0
        for sub in resp.get("items", []):
            name = sub.get("messageName")
            state = sub.get("messageSubscriptionState")
            if name not in self.replay:
                continue
            if state not in ("ACTIVE", "CREATED"):
                continue
            if sub.get("messageSubscriptionType") == "START_EVENT":
                continue
            token = (name, sub.get("processInstanceKey"), sub.get("messageSubscriptionKey"))
            if token in self.sent_messages:
                continue
            body = {"name": name, "timeToLive": 60000,
                    "variables": REPLAY_VARS.get(name, {})}
            if sub.get("correlationKey"):
                body["correlationKey"] = sub["correlationKey"]
            st2, resp2 = http("POST", "/v2/messages/publication", body)
            if st2 == 200:
                self.sent_messages.add(token)
                sent += 1
                self._log("message OK %s ck=%s" % (name, sub.get("correlationKey")))
            else:
                self._log("message FAIL %s -> %s %s" % (name, st2, resp2))
        return sent

    # ---------- helpers ----------
    def latest_instance(self, pool):
        st, resp = http("POST", "/v2/process-instances/search",
                        {"filter": {"processDefinitionId": pool, "state": "ACTIVE"},
                         "sort": [{"field": "startDate", "order": "DESC"}],
                         "page": {"limit": 1}})
        if st == 200 and resp.get("items"):
            return resp["items"][0]["processInstanceKey"]
        return None

    def _log(self, text):
        if self.verbose:
            print("    " + text, flush=True)

    # ---------- scenario ----------
    def run_scenario(self, sc, timeout=120):
        sid = sc["id"]
        print("== %s  (%s)" % (sid, sc["pool"]), flush=True)
        self.job_calls = {}
        self.scene_values = {}
        before = set(self.covered)
        wanted = list(sc["forms"])
        trig = sc["trigger"]
        self.scene = sc
        self.scene_wanted = set(wanted)
        # full business context, minus whatever this scenario deliberately blanks
        seed = dict(SEED_VARS)
        seed.update(trig.get("variables") or {})
        for key in sc.get("unset", []):
            seed[key] = []
        for key in sc.get("blank", []):
            seed[key] = ""
        pi = None
        if trig["kind"] == "message":
            body = {"name": trig["name"], "timeToLive": 600000, "variables": seed}
            st, resp = http("POST", "/v2/messages/publication", body)
            pi = resp.get("processInstanceKey")
        else:
            body = {"processDefinitionId": sc["pool"], "variables": seed}
            if trig.get("elementId"):
                body["startInstructions"] = [{"elementId": trig["elementId"]}]
            st, resp = http("POST", "/v2/process-instances", body)
            pi = resp.get("processInstanceKey")
        print("    started(%s) -> %s %s" % (trig.get("name") or sc["pool"],
                                            st, str(resp)[:160]), flush=True)
        if sc.get("modify"):
            if not pi:
                time.sleep(1.5)
                pi = self.latest_instance(sc["pool"])
            if pi:
                st2, resp2 = http("POST", "/v2/process-instances/%s/modification" % pi,
                                  {"activateInstructions": [{"elementId": sc["modify"]["elementId"]}]})
                print("    modify %s on pi=%s -> %s %s"
                      % (sc["modify"]["elementId"], pi, st2, str(resp2)[:160]), flush=True)
        deadline = time.time() + timeout
        t0 = time.time()
        rounds = 0
        while time.time() < deadline:
            rounds += 1
            j = self.activate_all_jobs() if self.with_jobs else 0
            t = self.activate_user_tasks()
            m = self.replay_messages()
            if all(f in self.covered for f in wanted):
                break
            if not (j or t or m):
                time.sleep(0.8)
        gained = [f for f in wanted if f in self.covered]
        missing = [f for f in wanted if f not in self.covered]
        status = "PASS" if not missing else ("PARTIAL" if gained else "FAIL")
        print("    -> %s  gained=%s missing=%s  (%d rounds, %.1fs)"
              % (status, gained, missing, rounds, time.time() - t0), flush=True)
        return {"id": sid, "status": status, "gained": gained, "missing": missing}

    def run_all(self, timeout=120):
        results = []
        for sc in SCENARIOS:
            results.append(self.run_scenario(sc, timeout=timeout))
        return results

    # ---------- report ----------
    def report(self):
        covered = sorted(self.covered)
        missing = [f for f in ALL_FORMS if f not in self.covered]
        return {
            "generatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "formsDeployed": len(ALL_FORMS),
            "formsCovered": len(covered),
            "formsMissing": missing,
            "covered": [self.covered[f] for f in covered],
            "driverErrors": self.errors,
        }


def main():
    ap = argparse.ArgumentParser(description="Hospital pathway automation driver")
    ap.add_argument("--list", action="store_true", help="list scenarios and forms")
    ap.add_argument("--scenario", action="append", default=[], help="scenario id (repeatable)")
    ap.add_argument("--all", action="store_true", help="run every scenario")
    ap.add_argument("--timeout", type=int, default=None,
                    help="per-scenario timeout in seconds (default 120, or 600 with --manual-forms)")
    ap.add_argument("--report", default=None, help="write the JSON report to this path")
    ap.add_argument("--with-jobs", action="store_true",
                    help="also play the service tasks - only use this when the Java workers are stopped")
    ap.add_argument("--manual-forms", action="store_true",
                    help="do not complete user tasks; announce them and wait for a human "
                         "to finish them in Tasklist")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    timeout = args.timeout or (600 if args.manual_forms else 120)

    if args.list:
        print("Scenarios (%d):" % len(SCENARIOS))
        for sc in SCENARIOS:
            print("  %-24s %-28s forms=%s" % (sc["id"], sc["pool"], ", ".join(sc["forms"])))
        print("\nForms expected (%d):" % len(ALL_FORMS))
        for f in ALL_FORMS:
            print("  " + f)
        return 0

    st, resp = http("GET", "/v2/topology")
    if st != 200:
        print("Engine not reachable on %s: %s" % (BASE, resp))
        return 2
    print("Engine: gateway %s" % resp.get("gatewayVersion"))

    driver = Driver(verbose=not args.quiet, with_jobs=args.with_jobs,
                    manual=args.manual_forms)
    if args.manual_forms:
        print("MANUAL MODE: user tasks stay open. Finish them in Camunda Tasklist "
              "(http://localhost:8080/tasklist) - the driver waits and records each one.")
    if args.all:
        results = driver.run_all(timeout=timeout)
    else:
        results = [driver.run_scenario(sc, timeout=timeout)
                   for sc in SCENARIOS if sc["id"] in args.scenario]
    rep = driver.report()
    rep["scenarios"] = results

    print("\n--- coverage ---")
    print("forms covered: %d / %d" % (rep["formsCovered"], rep["formsDeployed"]))
    if rep["formsMissing"]:
        print("missing forms: " + ", ".join(rep["formsMissing"]))
    for f in sorted(driver.covered):
        print("  OK %-42s %s" % (f, driver.covered[f]["pool"]))
    if rep["driverErrors"]:
        print("\n--- driver errors ---")
        for e in rep["driverErrors"][:20]:
            print("  %s" % e)

    if args.report:
        with open(args.report, "w", encoding="utf-8") as fh:
            json.dump(rep, fh, indent=2, ensure_ascii=False)
        print("\nreport written to %s" % args.report)
    return 0 if not rep["formsMissing"] else 1


if __name__ == "__main__":
    sys.exit(main())
