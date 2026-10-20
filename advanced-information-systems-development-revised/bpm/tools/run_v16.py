#!/usr/bin/env python3
"""
Drive the v16.0 single-pool pathway through a running cluster.

One process, so the driver is one loop: look at what the instance is waiting on,
do that, repeat. A user task is completed the way Tasklist completes it; a message
catch event is fed the message it subscribes to. Nothing is stubbed and nothing is
skipped - if the model is wrong, the loop stops on an incident and says so.

    python3 tools/run_v16.py                 # the normal path
    python3 tools/run_v16.py --max-steps 80
    python3 tools/run_v16.py --scenario decline

Prerequisites: the engine is up, the model and forms are deployed, and the Java
workers are running.
"""

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "http://localhost:8080"
PROCESS_ID = "hospital-patient-pathway"
PATIENT = "P-1001"

# Variables every service task can ask for. Seeded on the start message and
# carried through the instance, so a worker is never waiting for a blank.
BASE_VARS = {
    "patientRef": PATIENT,
    "patientName": "A. Patient",
    "referralPackComplete": True,
    "decidingClinician": "Dr O. Okafor",
    "decidingFinanceOfficer": "F. Adeyemi",
    "treatmentBookingRef": "TBR-1001",
    "fundingRoute": "PATIENT_PAYS",
    "paymentReference": "PAY-1001",
    "refundReference": "REF-1001",
    "letterRef": "LTR-1001",
    "enquiryRef": "ENQ-1001",
    "appointmentOutcome": "ATTENDED",
    "clinicalAdviceSummary": "Advised rest and a review in two weeks",
    "advisedBy": "CNS R. Adeyemi",
    "financialDecision": "CHARGE_RAISED",
    "modificationReason": "Blood count below the threshold for this cycle",
    "treatmentModificationRef": "TMR-1001",
    # the correspondence worker refuses to dispatch to nobody, and it is right to
    "dispatchRecipients": ["patient", "referring GP"],
    "treatmentPlan": "chemotherapy",
    "patientCategory": "SELF_PAYING",
    "chargeAmount": 2450.00,
    "currency": "GBP",
}

# What the person at each user task enters.
#
# Every key below is a real field in the form bound to that task, and every value
# is the type that form submits: a radio or a select submits a string, a checkbox
# submits a boolean, a number submits a number. The draft of this driver posted
# its own variable names and a real JSON boolean for consentGiven, which is why a
# run could be green while a person using Tasklist took the other branch. Whatever
# is not listed here is filled from the form itself, so a task is never submitted
# with a field the form would not have asked for.
TASK_VARS = {
    "SEC_Task_CheckPack": {
        "referralSpeciality": "Medical oncology",
        "referralPriority": "Urgent",
        # exactly the oncology checklist, so the worker finds the pack complete
        "supportingDocuments": ["referral-letter", "histology-report",
                                "imaging-report", "blood-tests", "consent-form"],
        "packChecked": True,
        "referralSource": "GP surgery",
        "receivedBy": "M. Secretary",
    },
    "CON_Task_ReviewReferral": {"clinicalDecision": "ACCEPT",
                                "clinicalDecisionReason": "Meets the referral criteria",
                                "clinicalPriorityConfirmed": "Urgent",
                                "decidingClinician": "Dr O. Okafor"},
    "SEC_Task_NotifyReferrer": {"referralOutcome": "ACCEPTED",
                                "referralOutcomeReason": "Accepted for a new patient appointment",
                                "notificationMethod": "Secure email",
                                "outcomeRecordedBy": "M. Secretary"},
    "OUT_Task_ChooseSlot": {"appointmentDateTime": "2026-11-04T09:30",
                            "appointmentLocation": "Oncology day unit, level 2",
                            "appointmentPriority": "Urgent",
                            "chosenSlotRef": "SLOT-2026-11-04-0930",
                            "requiresPhoneCall": "true",
                            "chosenBy": "R. Booker"},
    "OUT_Task_ReviewAvailability": {"availabilityAction": "WIDEN_SEARCH"},
    "OUT_Task_ChaseLetter": {"alternativeChannel": "Secure email",
                             "dispatchFailureReason": "Channel unavailable",
                             "resolvedBy": "R. Booker"},
    "CALL_Task_ContactPatient": {"contactOutcome": "REACHED",
                                 "contactAttempts": 1,
                                 "attemptedBy": "C. Handler",
                                 "contactNotes": "Patient confirmed attendance."},
    "CON_Task_RecordConsent": {"consentGiven": "true",
                               "treatmentPlan": "Chemotherapy",
                               "cycleCount": 6,
                               "cycleIntervalDays": 21,
                               "treatmentBookingRef": "TBR-1001",
                               "authorisingClinician": "Dr O. Okafor",
                               "reviewsBetweenCycles": True,
                               "specialResources": ["Laboratory", "Day unit chair"]},
    "OUT_Task_RecordDecline": {"declineReason": "Patient choice"},
    "CON_Task_DraftLetter": {"letterApproved": "true",
                             "letterType": "New patient clinic letter",
                             "letterRecipients": ["patient", "gp"],
                             "diagnosisSummary": "Colorectal carcinoma",
                             "treatmentDecisions": "FOLFOX, six cycles",
                             "followUpArrangements": "Review before each cycle",
                             "approvingClinician": "Dr O. Okafor"},
    "CON_Task_CorrectLetter": {"letterApproved": "true",
                               "correctionReason": "Diagnosis transposed in the first draft",
                               "correctedSections": ["Diagnosis"],
                               "approvingClinician": "Dr O. Okafor"},
    "SEC_Task_ProcessLetter": {"clinicalErrorSuspected": "false",
                               "letterRecipients": ["patient", "gp"],
                               "adminChecksCarriedOut": ["Patient identifiers correct",
                                                         "Recipient list confirmed"],
                               "processedBy": "M. Secretary"},
    "FIN_Task_DetermineFunding": {"fundingRoute": "PATIENT_PAYS",
                                  "funderName": "Self funding",
                                  "authorisationRef": "FA-1001",
                                  "approvedAmount": 2450,
                                  "currency": "GBP",
                                  "decidedBy": "F. Adeyemi"},
    "FIN_Task_ChasePreAuthorisation": {"outcome": "Awaiting response",
                                       "payerContactName": "Insurer pre-authorisation desk",
                                       "payerReference": "INS-7781",
                                       "chasedBy": "F. Adeyemi"},
    "FIN_Task_ManualCharge": {"chargeAmount": 2450,
                              "treatmentPlan": "Chemotherapy",
                              "tariffCode": "CHEMO-6",
                              "overrideReason": "Tariff lookup failed",
                              "pricedBy": "F. Adeyemi"},
    "FIN_Task_InvestigatePayment": {"paymentFound": "true",
                                    "investigationNotes": "Provider ledger checked",
                                    "providerStatementChecked": True,
                                    "amountTaken": 2450,
                                    "investigatedBy": "F. Adeyemi"},
    "FIN_Task_DecideRefund": {"refundDecision": "FULL_REFUND",
                              "refundAmount": 2450,
                              "paidAmount": 2450,
                              "refundReason": "Treatment cancelled after payment",
                              "refundMethod": "Original card",
                              "decidedBy": "F. Adeyemi"},
    "FIN_Task_ReviewImpact": {"impactAction": "ADJUST_CHARGE",
                              "impactAmount": 2450,
                              "impactNotes": "One cycle removed",
                              "reviewedBy": "F. Adeyemi"},
    "FIN_Task_AnswerEnquiry": {"responseGiven": "The charge is 2,450 and was taken on 11 November.",
                               "resolvedNow": "true", "answeredBy": "F. Adeyemi"},
    "TRT_Task_ReviewDeclinedPayment": {"declinedAction": "RETRY_PAYMENT",
                                       "paymentStatus": "DECLINED"},
    "TRT_Task_ReviewFundingTimeout": {"fundingChaseOutcome": "RECHECK"},
    "TRT_Task_RecordDelay": {"cycleNumber": 2,
                             "delayReason": "Patient bloods below threshold",
                             "newProposedStartDate": "2026-12-02",
                             "patientInformed": True,
                             "recordedBy": "T. Booker"},
    "TRT_Task_ReviewModification": {"requestFormallySubmitted": "true",
                                    "changeCategory": "Dose change",
                                    "requestedBy": "Dr O. Okafor",
                                    "notes": "Reduce the dose by 20 per cent"},
    "CON_Task_ReviewCycle": {"cycleReviewOutcome": "FIT_TO_CONTINUE",
                             "bloodResultsReviewed": True,
                             "cycleReviewNotes": "Bloods acceptable",
                             "reviewClinician": "Dr O. Okafor"},
    "CON_Task_AuthoriseModification": {"modificationAuthorised": "true",
                                       "modificationUrgent": "false",
                                       "modificationAffectsFinance": "false",
                                       "modificationReason": "Patient safety",
                                       "modificationAuthorisedBy": "Dr O. Okafor"},
    "CON_Task_AuthoriseUrgentTreatment": {"urgentTreatmentAuthorised": "true"},
    "CON_Task_ClinicalReview": {"clinicalReviewOutcome": "Reviewed and continued",
                                "clinicalAdviceSummary": "Continue as planned",
                                "needsConsultantReview": "false",
                                "reviewedBy": "Dr O. Okafor"},
    "OUT_Task_ConfirmFollowUp": {"appointmentDateTime": "2027-01-08T10:00",
                                 "appointmentLocation": "Oncology clinic",
                                 "requestedReviewPeriod": "3 months",
                                 "withinRequestedPeriod": "true",
                                 "confirmedBy": "R. Booker"},
    "OUT_Task_DecideNextAction": {"appointmentOutcome": "CANCELLED",
                                  "cancellationAction": "CLOSE_AND_INFORM_REFERRER",
                                  "cancellationReason": "Patient no longer needs the appointment",
                                  "communicationChannel": "Letter",
                                  "patientInformedOfOptions": True,
                                  "recordedBy": "R. Booker"},
    "OUT_Task_AnswerAdminEnquiry": {"responseGiven": "The appointment is on 4 November at 09:30.",
                                    "answerableNow": "true", "answeredBy": "R. Booker"},
    "CNS_Task_TriageEnquiry": {"needsConsultantReview": "false",
                               "clinicalAdviceSummary": "Advised rest and a review in two weeks",
                               "advisedBy": "CNS R. Adeyemi",
                               "enquiryRef": "ENQ-1001"},
    "CALL_Task_LogEnquiry": {"enquiryCategory": "ADMINISTRATIVE",
                             "enquiryPriority": "ROUTINE",
                             "enquiryChannel": "Telephone",
                             "enquirySummary": "Asking about clinic access",
                             "answerableNow": "true",
                             "loggedBy": "C. Handler"},
    "CALL_Task_AnswerAdmin": {"responseGiven": "The clinic is on the ground floor.",
                              "answerableNow": "true", "answeredBy": "C. Handler"},
    "PCW_Task_ReviewOverdueList": {"letterOverdueDays": 10,
                                   "outstandingLettersReviewed": 1,
                                   "reminderAction": "SEND_REMINDER",
                                   "reviewedBy": "P. Coordinator"},
    "PCW_Task_ReviewDelay": {"delayAction": "KEEP_PATIENT_INFORMED",
                             "delayReason": "No clinic capacity",
                             "daysDelayed": 7,
                             "patientInformed": True,
                             "notes": "Write to the patient about the delay",
                             "reviewedBy": "P. Coordinator"},
    "ADM_Task_ContactConsultant": {"letterNowCompleted": "true",
                                   "contactMethod": "Email",
                                   "contactedBy": "A. Manager"},
    "ADM_Task_ReferHigher": {"reasonForEscalation": "Letter still outstanding after three months",
                             "higherManagementTeam": "Clinical directorate",
                             "monthsOutstanding": 3,
                             "referredBy": "A. Manager"},
}


# element id -> form id, and form id -> its fields, read from the shipped model
def form_index(model):
    xml = Path(model).read_text(encoding="utf-8")
    by_task = {}
    for m in re.finditer(r'<bpmn:userTask id="([^"]+)"[^>]*>(.*?)</bpmn:userTask>',
                         xml, re.S):
        f = re.search(r'<zeebe:formDefinition formId="([^"]+)"', m.group(2))
        if f:
            by_task[m.group(1)] = f.group(1)
    forms = {}
    for path in (Path(__file__).resolve().parent.parent / "model" / "forms").glob("*.form"):
        data = json.loads(path.read_text(encoding="utf-8"))
        fields = {}

        def walk(comps):
            for comp in comps:
                if comp.get("key"):
                    fields[comp["key"]] = comp
                if comp.get("components"):
                    walk(comp["components"])
        walk(data.get("components", []))
        forms[path.stem] = fields
    return by_task, forms


def field_value(comp):
    """A value of the type this component actually submits.

    A read-only field is not submitted by the renderer, so filling one here would
    make the driver behave unlike a person - and would overwrite the process
    variable the field is only meant to display.
    """
    if comp.get("readonly"):
        return None
    kind = comp.get("type")
    values = comp.get("values") or []
    if kind in ("radio", "select"):
        return values[0]["value"] if values else "value"
    if kind == "checklist":
        return [values[0]["value"]] if values else []
    if kind == "checkbox":
        return True
    if kind == "number":
        return (comp.get("validate") or {}).get("min", 1)
    if kind == "datetime":
        # A date is not a free choice: the worker-side DateRuleValidator checks it
        # against date-rules.json, and a referral date in the future is exactly the
        # sort of thing it exists to catch. `disallowPassedDates` marks the fields
        # that are commitments, so those get a future date and the rest get a past
        # one. The first version of this filler posted a fixed future date for all
        # of them, which the old jar accepted and the rebuilt jar does not.
        import datetime as _dt
        today = _dt.date.today()
        when = (today + _dt.timedelta(days=14) if comp.get("disallowPassedDates")
                else today - _dt.timedelta(days=3))
        return when.isoformat() if comp.get("subtype") == "date" else when.isoformat() + "T09:00:00"
    if kind == "taglist":
        return []
    # Never the label: a label is a sentence, and using it as the value is how
    # patientRef ended up as the literal string "Patient reference", which then
    # became the correlation key every message subscription waited on.
    return "recorded"


def form_defaults(fields):
    """Only the fields the form insists on.

    A person filling a form supplies the required fields and leaves the optional
    ones alone; Tasklist submits exactly that. Filling every field instead is how
    the first draft managed to overwrite cycleNumber - which the schedule worker
    owns - with the form's idea of a cycle number, and the pathway then looped for
    ever. Optional fields are left to whoever really sets them.
    """
    out = {}
    for key, comp in fields.items():
        if not (comp.get("validate") or {}).get("required"):
            continue
        value = field_value(comp)
        if value is not None:
            out[key] = value
    return out


def check_driver_variables(by_task, forms):
    """Every override must name a field the form really has."""
    problems = []
    for element, values in TASK_VARS.items():
        form = by_task.get(element)
        if form is None:
            problems.append("%s has no form in the model" % element)
            continue
        for key in values:
            if key not in forms.get(form, {}):
                problems.append("%s.%s is not a field of %s" % (element, key, form))
    return problems


FED_GRACE = 20          # seconds before an uncorrelated message is called out
FED_TIMEOUT = {}

SCENARIOS = {
    "normal": {},
    # the patient declines at the consultation
    "decline": {"CON_Task_RecordConsent": {"consentGiven": "false",
                                           "declineReason": "Patient does not wish to proceed"}},
    # the pack is readable but the oncology checklist is not satisfied, so the
    # validation worker raises REFERRAL_PACK_INCOMPLETE and the model has to go
    # round the missing-information loop
    "incomplete-pack": {"SEC_Task_CheckPack": {
        "supportingDocuments": ["referral-letter", "histology-report"]}},
    # no slot inside the window: needs the workers started with
    # DEMO_SCHEDULING_FORCE_NO_SLOTS=true
    "no-slots": {"OUT_Task_ReviewAvailability": {"availabilityAction": "ESCALATE"}},
    # the follow-up appointment is over, the account still has to be settled
    "refund": {"CON_Task_ReviewCycle": {"cycleReviewOutcome": "CHANGE_PLAN",
                                        "cycleReviewNotes": "Plan no longer suitable"},
               "CON_Task_AuthoriseModification": {"modificationAffectsFinance": "true"},
               "FIN_Task_ReviewImpact": {"impactAction": "REFUND_REQUIRED"},
               "FIN_Task_DecideRefund": {"refundDecision": "FULL_REFUND"}},
    "no-refund": {"CON_Task_ReviewCycle": {"cycleReviewOutcome": "CHANGE_PLAN",
                                           "cycleReviewNotes": "Plan no longer suitable"},
                  "CON_Task_AuthoriseModification": {"modificationAffectsFinance": "true"},
                  "FIN_Task_ReviewImpact": {"impactAction": "REFUND_REQUIRED"},
                  "FIN_Task_DecideRefund": {"refundDecision": "NO_REFUND"}},
    # the plan changes mid-course: the model has to give back the appointments it
    # already held, which is what the compensation handler on the confirmed series
    # is for
    "change-plan": {"CON_Task_ReviewCycle": {"cycleReviewOutcome": "CHANGE_PLAN",
                                             "cycleReviewNotes": "Plan no longer suitable"}},
    # The worker-side failure paths. Each one needs the workers started with a
    # matching DEMO_* flag; see docs/03-test-record.md section K for the command.
    #   declined-payment       DEMO_PAYMENT_STATUS=DECLINED
    #   lost-confirmation      DEMO_PAYMENT_STATUS=NO_CONFIRMATION
    #   no-capacity            DEMO_EXTERNAL_UNAVAILABLE_RESOURCES=Laboratory
    #   service-down           DEMO_SIMULATED_FAILURE_ENABLED=true,
    #                          DEMO_SIMULATED_FAILURE_MODE=once,
    #                          DEMO_SIMULATED_FAILURE_JOB_TYPES=scheduling.find-appointment-slots:SCHEDULING_SERVICE_UNAVAILABLE,
    #                            correspondence.dispatch-letter:CORRESPONDENCE_SERVICE_FAILED,
    #                            finance.calculate-charge:CHARGE_CALCULATION_FAILED
    #   refund-rejected        DEMO_PAYMENT_REFUND_STATUS=REJECTED
    "declined-payment": {},
    "lost-confirmation": {},
    "no-capacity": {},
    "service-down": {},
    "refund-rejected": {"CON_Task_ReviewCycle": {"cycleReviewOutcome": "CHANGE_PLAN"},
                        "CON_Task_AuthoriseModification": {"modificationAffectsFinance": "true"},
                        "FIN_Task_ReviewImpact": {"impactAction": "REFUND_REQUIRED"},
                        "FIN_Task_DecideRefund": {"refundDecision": "FULL_REFUND"}},
    # a treatment request with no authorising clinician: the worker raises
    # TREATMENT_REQUEST_UNAUTHORISED and the model has to send it back
    "unauthorised-request": {"CON_Task_RecordConsent": {"authorisingClinician": "",
                                                        "decidingClinician": ""}},
    # an urgent clinical enquiry from the patient rather than a referral
    "enquiry": {"_start": "enquiry.received"},

    # --- branch scenarios -----------------------------------------------------
    # One field turned round from the value the default run submits, so the taken
    # branch is the other one. Every value below is an option of the form bound to
    # that task, so a person in Tasklist could produce the same run by hand.
    "enquiry-clinical": {"_start": "enquiry.received",
                         "CALL_Task_LogEnquiry": {"enquiryCategory": "CLINICAL"}},
    "enquiry-financial": {"_start": "enquiry.received",
                          "CALL_Task_LogEnquiry": {"enquiryCategory": "FINANCIAL"}},
    "enquiry-unanswered": {"_start": "enquiry.received",
                           "CALL_Task_LogEnquiry": {"answerableNow": "false"}},
    "clinical-escalation": {"_start": "enquiry.received",
                            "CALL_Task_LogEnquiry": {"enquiryCategory": "CLINICAL"},
                            "CNS_Task_TriageEnquiry": {"needsConsultantReview": "true"}},
    "cycle-delay": {"CON_Task_ReviewCycle": {"cycleReviewOutcome": "DELAY",
                                             "cycleReviewNotes": "Bloods below threshold"}},
    "modification-refused": {"CON_Task_ReviewCycle": {"cycleReviewOutcome": "CHANGE_PLAN"},
                             "CON_Task_AuthoriseModification": {
                                 "modificationAuthorised": "false"}},
    "hospital-funded": {"FIN_Task_DetermineFunding": {"fundingRoute": "HOSPITAL_FUNDED"}},
    "insurer-approved": {"FIN_Task_DetermineFunding": {"fundingRoute": "INSURER_APPROVED"}},
    "referral-rejected": {"CON_Task_ReviewReferral": {"clinicalDecision": "REJECT"},
                          "SEC_Task_NotifyReferrer": {"referralOutcome": "REJECTED"}},
    "letter-correction": {"SEC_Task_ProcessLetter": {"clinicalErrorSuspected": "true"}},
    "cancellation-rebook": {"OUT_Task_DecideNextAction": {
        "appointmentOutcome": "ATTENDED", "cancellationAction": "REBOOK"}},
    "cancellation-clinical-review": {"OUT_Task_DecideNextAction": {
        "cancellationAction": "CLINICAL_REVIEW"}},
}

# A scenario that only makes sense on the first visit to a step. The missing
# information loop really does come back to the same task, and the second time
# round the referrer has supplied what was asked for, so the pack is complete and
# the pathway moves on. Without this the run only ever proves the loop works.
FIRST_VISIT_ONLY = {"incomplete-pack"}

# A scenario that changes its mind after a few attempts. With the scheduling
# service forced to return nothing, widening the search will never find a slot, so
# the point of the run is that the desk only escalates once widening has failed.
AFTER_VISITS = {"no-slots": (2, {"OUT_Task_ReviewAvailability":
                                 {"availabilityAction": "ESCALATE"}}),
                # Two loops in the model have no way out once the same answer is
                # given again: the cycle review keeps delaying, and the letter
                # keeps being found wrong. The scenarios below take the other
                # branch once, which is what proves the branch is reachable, and
                # then answer the second time the way a person would.
                "cycle-delay": (1, {"CON_Task_ReviewCycle":
                                    {"cycleReviewOutcome": "FIT_TO_CONTINUE"}}),
                "letter-correction": (1, {"SEC_Task_ProcessLetter":
                                          {"clinicalErrorSuspected": "false"}})}


def call(method, path, body=None, timeout=30):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as exc:
        raise SystemExit("%s %s failed: %s %s" % (method, path, exc.code,
                                                  exc.read().decode()[:400]))


def call_soft(method, path, body=None, timeout=30):
    """Like call(), but reports failure instead of ending the run.

    Used where a failure is expected and recoverable: the search index lags, a key
    is not queryable the instant it is returned, or a filter needs the other JSON
    encoding of an int64 key.
    """
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
            return True, (json.loads(raw) if raw.strip() else {})
    except urllib.error.HTTPError as exc:
        return False, exc.read().decode()[:300]
    except Exception as exc:                       # connection refused, timeout
        return False, str(exc)


def catch_messages(model):
    """element id -> message name, plus event-based gateway -> the messages it waits on."""
    xml = Path(model).read_text(encoding="utf-8")
    msgs, msg_keys = {}, {}
    for m in re.finditer(r'<bpmn:message id="([^"]+)" name="([^"]+)"[^>]*>'
                         r'(.*?)</bpmn:message>', xml, re.S):
        msgs[m.group(1)] = m.group(2)
        # the subscription lives in extensionElements inside the message body,
        # and the builder escapes the quotes inside the expression
        key = re.search(r'correlationKey="([^"]*)"', m.group(3))
        msg_keys[m.group(2)] = (key.group(1).replace("&#34;", '"')
                                .replace("&quot;", '"')
                                .replace("&amp;", "&") if key else "=patientRef")
    out, gates = {}, {}
    for m in re.finditer(r'<bpmn:(intermediateCatchEvent|boundaryEvent) id="([^"]+)"([^>]*)>'
                         r'(.*?)</bpmn:\1>', xml, re.S):
        kind, eid, attrs, body = m.groups()
        if kind == "boundaryEvent" and 'cancelActivity="false"' not in attrs:
            continue
        ref = re.search(r'messageRef="([^"]+)"', body)
        if ref:
            out[eid] = msgs.get(ref.group(1), ref.group(1))
    # An event-based gateway waits on the catch events that follow it, so those
    # are not active elements themselves: the gateway is. Resolve which messages
    # it is waiting for, so the driver can feed one.
    flows = re.findall(r'<bpmn:sequenceFlow[^>]*sourceRef="([^"]+)"[^>]*targetRef="([^"]+)"', xml)
    for gw in re.findall(r'<bpmn:eventBasedGateway id="([^"]+)"', xml):
        names = [out[eid] for src, eid in flows if src == gw and eid in out]
        if names:
            gates[gw] = names
    return out, gates, msg_keys


def key_for(msg_keys, message, patient):
    """Evaluate the subscription key the model declares for a message.

    Every catch event here subscribes on patientRef or patientRef plus a suffix;
    publishing under the bare patient reference would never correlate.
    """
    expr = msg_keys.get(message, "=patientRef").lstrip("= ").strip()
    if expr == "patientRef":
        return patient
    m = re.match(r'patientRef\s*\+\s*"([^"]*)"', expr)
    if m:
        return patient + m.group(1)
    if expr.startswith('"') and expr.endswith('"'):
        return expr[1:-1]
    return patient


def live_patient_ref(pi):
    """The patientRef the instance actually carries.

    A message that is published under the correlation key given on the command
    line only correlates when that key also happens to be the patient reference
    the instance holds. Reading it off the instance keeps the two in step.
    """
    try:
        d = call("POST", "/v2/variables/search",
                 {"filter": {"processInstanceKey": pi, "name": "patientRef"}})
        for item in d.get("items", []):
            value = item.get("value")
            if isinstance(value, str):
                value = value.strip('"')
            if value:
                return value
    except Exception:
        return None
    return None


def message_vars(args):
    """What a caught message carries when it is delivered.

    An automated run seeds the case as it goes, and re-sending that payload on every
    message is harmless because the driver owns every variable. When a person is
    filling the forms (or a run is attached to a case they have already touched),
    re-sending it would overwrite what they typed, so the message carries only the
    reference its subscription is keyed on.
    """
    if args.manual_forms or args.resume or args.form_fields_only:
        return {"patientRef": args.correlation_key}
    return dict(BASE_VARS)


# The referring organisation answering a request for the missing information. That
# reply is not just a signal: it carries the documents. Without them the model goes
# round the missing-information loop for ever, because the validation worker reads
# the same list, finds the same gap and asks again - which is exactly what a person
# filling the forms by hand sees as "the first form keeps coming back".
INFO_REPLY_MESSAGE = "referral.info-received"


def reply_variables(pi, args, msg):
    """The variables to send with a message the driver feeds.

    Normally just the correlation reference. The information reply is the exception:
    the documents the checklist reported missing are added, which is what closes the
    loop. The worker publishes `referralChecklist` and `missingDocuments`, so the
    reply is built from the engine's own answer rather than a guess.
    """
    v = message_vars(args)
    if msg != INFO_REPLY_MESSAGE or "supportingDocuments" in v:
        return v

    def as_list(x):
        return [str(i) for i in x] if isinstance(x, list) else []

    got = instance_variables(pi, {"referralDocumentsReceived", "missingDocuments",
                                  "referralChecklist", "supportingDocuments"})
    supplied = as_list(got.get("referralDocumentsReceived")) or \
        as_list(got.get("supportingDocuments"))
    missing = as_list(got.get("missingDocuments"))
    documents = list(dict.fromkeys(supplied + missing))
    if documents:
        v["supportingDocuments"] = documents
        print("        the referring organisation supplies: %s"
              % ", ".join(documents))
    return v


def active_elements(pi):
    d = call("POST", "/v2/element-instances/search",
             {"filter": {"processInstanceKey": pi, "state": "ACTIVE"}})
    return [e for e in d.get("items", [])]


def instance_state(pi):
    """The instance state, or None when it cannot be read (yet).

    CreateProcessInstance answers before the instance is queryable, so a GET on the
    key it has just returned can 404 for a moment. Returning None lets the caller
    wait for it rather than ending the run.
    """
    ok, d = call_soft("GET", "/v2/process-instances/%s" % pi)
    return d.get("state") if ok else None


def incidents(pi):
    d = call("POST", "/v2/incidents/search",
             {"filter": {"processInstanceKey": pi, "state": "ACTIVE"}})
    return d.get("items", [])


def decode_value(v):
    """A variable as the engine returns it: JSON-encoded, so `"PAT-1"` is a string."""
    if isinstance(v, str):
        try:
            return json.loads(v)
        except (ValueError, TypeError):
            return v
    return v


def instance_variables(pi, names):
    """Read named variables off a running instance.

    Same key-encoding caveat as instance_patient_ref: /v2/variables/search rejects a
    bare number for processInstanceKey on this engine.
    """
    out = {}
    for key in (str(pi), pi):
        ok, d = call_soft("POST", "/v2/variables/search",
                          {"filter": {"processInstanceKey": key},
                           "page": {"limit": 200}})
        if ok:
            for item in d.get("items", []):
                name = item.get("name")
                if name in names and name not in out:
                    out[name] = decode_value(item.get("value"))
            return out
    return out


def instance_patient_ref(pi):
    """The patientRef of a running instance.

    Every catch event in this model subscribes on a key derived from patientRef,
    so resuming a case means publishing under the reference it was opened with.
    Reading it back off the instance beats asking the operator to remember it.
    """
    got = instance_variables(pi, {"patientRef"})
    ref = got.get("patientRef")
    if isinstance(ref, str) and ref:
        return ref

    ok, d = call_soft("POST", "/v2/variables/search",
                      {"filter": {"name": "patientRef"}, "page": {"limit": 200}})
    if ok:
        for item in d.get("items", []):
            if str(item.get("processInstanceKey")) == str(pi):
                ref = decode_value(item.get("value"))
                if isinstance(ref, str) and ref:
                    return ref
    return None


class AlreadyDone(Exception):
    """The search index lags the completion, so a task can be offered twice."""


def finished_service_tasks(pi):
    """Element ids of service tasks this instance has completed."""
    d = call("POST", "/v2/element-instances/search",
             {"filter": {"processInstanceKey": pi, "type": "SERVICE_TASK",
                         "state": "COMPLETED"}, "page": {"limit": 200}})
    return {e["elementId"] for e in d.get("items", [])}


TRACE_LABEL = {
    "START_EVENT": "start",
    "END_EVENT": "end event",
    "EXCLUSIVE_GATEWAY": "gateway",
    "INCLUSIVE_GATEWAY": "gateway",
    "PARALLEL_GATEWAY": "gateway",
    "EVENT_BASED_GATEWAY": "evt gateway",
    "BOUNDARY_EVENT": "boundary",
    "INTERMEDIATE_CATCH_EVENT": "catch event",
    "INTERMEDIATE_THROW_EVENT": "throw event",
    "SUBPROCESS": "subprocess",
    "CALL_ACTIVITY": "call act",
}

# only these tags are flow nodes; ids on sequence flows, lanes and pools are not
NODE_TAGS = {"startEvent", "endEvent", "intermediateCatchEvent",
             "intermediateThrowEvent", "boundaryEvent", "exclusiveGateway",
             "inclusiveGateway", "parallelGateway", "eventBasedGateway",
             "complexGateway", "serviceTask", "userTask", "sendTask",
             "receiveTask", "manualTask", "businessRuleTask", "scriptTask",
             "callActivity", "subProcess", "task"}


def all_elements(pi):
    """Every element instance of this process instance, whatever its type."""
    items, start = [], 0
    while True:
        d = call("POST", "/v2/element-instances/search",
                 {"filter": {"processInstanceKey": pi},
                  "page": {"limit": 200, "from": start}})
        got = d.get("items", [])
        items.extend(got)
        if len(got) < 200:
            break
        start += 200
    return items


def trace_new(pi, visited):
    """Name every element the instance has reached that the log has not named yet.

    The log used to carry only user tasks and completed service tasks. Gateways,
    end events and boundary events were therefore invisible, which made reached
    branches look unvisited - the observation gap, not a model gap. User and
    service tasks stay with the main loop so nothing is printed twice.
    """
    fresh = []
    for e in all_elements(pi):
        eid = e.get("elementId")
        if not eid or eid in visited:
            continue
        visited[eid] = e.get("type")
        if visited[eid] in ("USER_TASK", "SERVICE_TASK"):
            continue
        fresh.append(eid)
    for eid in fresh:
        kind = visited[eid]
        print("     %-12s %s" % (TRACE_LABEL.get(kind, kind or "?"), eid))
    return fresh


def declared_nodes(model):
    """element id -> bpmn tag, for the flow nodes the model declares."""
    import re as _re
    with open(model, encoding="utf-8") as fh:
        xml = fh.read()
    out = {}
    for m in _re.finditer(r"<(?:[A-Za-z0-9_]+:)?([A-Za-z]+)\b[^>]*?\bid=\"([^\"]+)\"", xml):
        tag, eid = m.group(1), m.group(2)
        if tag in NODE_TAGS and eid not in out:
            out[eid] = tag
    return out


def trace_summary(visited, model):
    """What the trace saw, and what the model declares that it never saw."""
    declared = declared_nodes(model)
    covered = [e for e in declared if e in visited]
    missed = [e for e in declared if e not in visited]
    print("\n  --- element trace ---")
    print("  visited %d of %d flow nodes declared in the model"
          % (len(covered), len(declared)))
    for tag in ("startEvent", "endEvent", "boundaryEvent",
                "exclusiveGateway", "inclusiveGateway", "parallelGateway",
                "eventBasedGateway", "serviceTask", "userTask"):
        total = [e for e, t in declared.items() if t == tag]
        if not total:
            continue
        hit = [e for e in total if e in visited]
        print("    %-16s %2d / %2d" % (tag, len(hit), len(total)))
    if missed:
        print("  never reached (%d): %s" % (len(missed), ", ".join(sorted(missed))))
    else:
        print("  every flow node in the model was reached")
    print("  --- end trace ---")
    return missed


def complete(task, variables):
    key = task["userTaskKey"]
    data = json.dumps({"variables": variables}).encode()
    req = urllib.request.Request(BASE + "/v2/user-tasks/%s/completion" % key,
                                 data=data, method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise AlreadyDone(key)
        raise SystemExit("completing %s failed: %s %s"
                         % (key, exc.code, exc.read().decode()[:300]))
    return task.get("elementId"), task.get("name")


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default="normal", choices=sorted(SCENARIOS))
    ap.add_argument("--max-steps", type=int, default=60)
    ap.add_argument("--model", default=str(Path(__file__).resolve().parent.parent /
                                           "model" /
                                           "UFCEP6-0-3_Hospital_Patient_Pathway_v16.bpmn"))
    ap.add_argument("--correlation-key", default=PATIENT)
    ap.add_argument("--manual-forms", action="store_true",
                    help="do not complete user tasks: wait while you fill each form "
                         "yourself, and keep the service tasks and messages automatic")
    ap.add_argument("--form-fields-only", action="store_true",
                    help="start the instance with no variables and submit nothing that "
                         "is not a field of the form bound to the task, the way Tasklist "
                         "does. Every variable the run then needs has to come from a form "
                         "or from a worker, which is what a person demonstrates.")
    ap.add_argument("--form-timeout", type=int, default=1800,
                    help="seconds to wait for one form in --manual-forms mode")
    ap.add_argument("--total-timeout", type=int, default=0,
                    help="stop after this many seconds overall (0 = no limit). "
                         "--manual-forms ignores --max-steps and uses this instead")
    ap.add_argument("--resume", type=int, default=None,
                    help="attach to a process instance that is already running "
                         "instead of starting a new one")
    ap.add_argument("--tasklist", default="http://localhost:8080/tasklist",
                    help="where to fill the forms in when --manual-forms is on")
    ap.add_argument("--check-vars", action="store_true",
                    help="report driver overrides that are not fields of the bound form")
    args = ap.parse_args(argv[1:])

    catches, gates, msg_keys = catch_messages(args.model)
    by_task, forms = form_index(args.model)
    bad = check_driver_variables(by_task, forms)
    if args.check_vars:
        print("driver overrides checked against the bound forms")
        for b in bad:
            print("  PROBLEM:", b)
        print("  %d problem(s)" % len(bad))
        return 0 if not bad else 2
    if bad:
        for b in bad:
            print("DRIVER PROBLEM:", b)
        return 2
    overrides = SCENARIOS[args.scenario]
    # every catch event in this model subscribes on a key derived from patientRef,
    # so the patient reference the run uses has to be the one the messages are
    # published under
    BASE_VARS["patientRef"] = args.correlation_key

    print("scenario: %s" % args.scenario)
    # The instance search is eventually consistent, so asking for "the newest
    # instance" straight after publishing can return the previous run's - which is
    # exactly what made a sweep of six scenarios report six results for one run.
    before = {i["processInstanceKey"] for i in call(
        "POST", "/v2/process-instances/search",
        {"filter": {"processDefinitionId": PROCESS_ID}, "page": {"limit": 200}}).get("items", [])}

    # The pathway opens at a none start event, so its instance is created directly
    # with the case variables. The enquiry branch is still a message start event,
    # so a scenario that names a start message is started by publishing instead.
    # --resume takes over an instance that is already running, which is what you
    # want when a case is part-way through and you are filling the forms by hand.
    start_msg = overrides.get("_start")
    pi = args.resume
    if pi is not None:
        state = None
        for _ in range(30):
            state = instance_state(pi)
            if state is not None:
                break
            time.sleep(1)
        print("  attached to the running instance %s (state %s)" % (pi, state))
        if state is None:
            raise SystemExit("instance %s could not be read back from the engine"
                             % pi)
        if state != "ACTIVE":
            print("  nothing to drive: the instance is already %s" % state)
            return 0
        # the case is already open, so the reference it was opened with is the one
        # its message subscriptions are keyed on - take it from the instance
        ref = instance_patient_ref(pi)
        if ref:
            args.correlation_key = ref
            BASE_VARS["patientRef"] = ref
            print("  correlation key read from the instance: patientRef=%s" % ref)
        else:
            print("  no patientRef variable found; publishing under %s"
                  % args.correlation_key)
    elif start_msg:
        # the enquiry branch decides at a gateway the moment the message lands,
        # so a scenario that wants the clinical or financial arm has to carry the
        # category in the message itself - there is no form before the gateway
        start_vars = dict(BASE_VARS)
        start_vars.update(overrides.get("_start_vars") or {})
        call("POST", "/v2/messages/publication",
             {"name": start_msg, "correlationKey": args.correlation_key,
              "timeToLive": 600000, "variables": start_vars})
        print("  published %s  (correlationKey=%s)" % (start_msg, args.correlation_key))
    else:
        # --form-fields-only starts the case with nothing on it, which is what
        # Tasklist's "Start process" does for a process with no start form
        create_body = {"processDefinitionId": PROCESS_ID}
        if not args.form_fields_only:
            create_body["variables"] = dict(BASE_VARS)
        created = call("POST", "/v2/process-instances", create_body)
        print("  created from the none start event  (correlationKey=%s)"
              % args.correlation_key)
        print("  [debug] instances before: %d" % len(before))
        pi = created.get("processInstanceKey")

    if pi is None:
        # The instance search is eventually consistent, so asking for "the newest
        # instance" can return the previous run's - which is exactly what made a
        # sweep of six scenarios report six results for one run.
        fallback = None
        for _ in range(90):
            time.sleep(1)
            d = call("POST", "/v2/process-instances/search",
                     {"filter": {"processDefinitionId": PROCESS_ID},
                      "sort": [{"field": "startDate", "order": "DESC"}],
                      "page": {"limit": 200}})
            fresh = [i["processInstanceKey"] for i in d.get("items", [])
                     if i["processInstanceKey"] not in before]
            if fresh:
                fallback = fallback or fresh[0]
                # A row that is only just readable carries no variables yet, and
                # the previous run's instance can surface at the same moment, so
                # pick the new instance that carries this run's patient reference.
                for candidate in fresh:
                    if live_patient_ref(candidate) == args.correlation_key:
                        pi = candidate
                        break
            if pi is not None:
                break
        if pi is None:
            pi = fallback
    if pi is None:
        raise SystemExit("no instance was created within 90 s")
    # CreateProcessInstance answers before the instance is queryable, so the key it
    # has just returned can still 404. Wait for the instance to be readable before
    # the loop starts asking for its state.
    for _ in range(30):
        if instance_state(pi) is not None:
            break
        print("  ... instance %s is not readable yet, waiting" % pi)
        time.sleep(1)
    print("  instance %s" % pi)
    # Reply messages have to correlate on what the case really carries, not on
    # whatever key the command line asked for.
    corr_key = live_patient_ref(pi) or args.correlation_key
    print()

    seen, steps = {}, 0
    visited = {}
    done, fed, done_service = set(), {}, set()
    misses = 0
    # --form-fields-only: nothing is seeded, so the correlation reference only exists
    # once the first form has supplied it. Read it back when it appears, otherwise
    # every message would be published under the placeholder key and never correlate.
    ref_resolved = not args.form_fields_only
    # --manual-forms only: element id -> when the person was first sent to fill it,
    # and when the run last said it was still waiting
    pending, heartbeat = {}, {}
    started = time.time()
    while steps < args.max_steps or args.manual_forms:
        # A person takes minutes per form, so the step budget is meaningless here:
        # --manual-forms runs until the instance ends, a form times out, or the
        # operator sets a --total-timeout.
        if args.manual_forms and args.total_timeout and \
                time.time() - started > args.total_timeout:
            print("\nstopped after %d s (--total-timeout). instance still ACTIVE."
                  % args.total_timeout)
            return 1
        steps += 1
        if not ref_resolved:
            # the first form has supplied patientRef by now (or has not yet); take it
            # the moment it appears so the messages are published under the right key
            found = instance_patient_ref(pi)
            if found:
                args.correlation_key = found
                BASE_VARS["patientRef"] = found
                ref_resolved = True
                print("  correlation key read from the instance: patientRef=%s" % found)
        bad = incidents(pi)
        if bad:
            print("INCIDENT after %d steps:" % steps)
            for i in bad:
                print("   %s | %s | %s" % (i.get("elementId"), i.get("errorType"),
                                           i.get("errorMessage")))
            trace_summary(visited, args.model)
            return 3
        state = instance_state(pi)
        if state is None:
            # Transient: the instance is momentarily unreadable, or the engine is
            # busy. Wait it out rather than ending a run the operator is watching.
            misses += 1
            if misses > 60:
                print("\ninstance %s stayed unreadable for 60 polls" % pi)
                return 5
            time.sleep(1.5)
            continue
        misses = 0
        if state != "ACTIVE":
            for s_el in finished_service_tasks(pi) - done_service:
                done_service.add(s_el)
                print("  %2d  service     %s" % (steps, s_el))
            trace_new(pi, visited)
            print("\ninstance state: %s after %d steps" % (state, steps - 1))
            trace_summary(visited, args.model)
            return 0

        # service tasks are the half of the model a person never sees; without
        # them in the log there is no evidence that the workers ran at all
        for s_el in finished_service_tasks(pi) - done_service:
            done_service.add(s_el)
            print("  %2d  service     %s" % (steps, s_el))

        # everything else the instance has touched - gateways, boundary events,
        # end events - so a taken branch leaves a line in the log
        trace_new(pi, visited)

        acts = active_elements(pi)
        active_ids = {a.get("elementId") for a in acts}
        # --manual-forms: a form that was in the pending list and is no longer an
        # active element has been completed by the person
        for eid in [e for e in pending if e not in active_ids]:
            del pending[eid]
            print("  %2d  you filled  %s" % (steps, eid))
        if not acts:
            time.sleep(1.5)
            continue
        did = False
        for a in acts:
            eid, kind = a.get("elementId"), a.get("type")
            if kind == "USER_TASK":
                t = call("POST", "/v2/user-tasks/search",
                         {"filter": {"processInstanceKey": pi, "state": "CREATED",
                                     "elementId": eid}})
                waiting = [x for x in t.get("items", [])
                           if x["userTaskKey"] not in done]
                if not waiting:
                    continue
                if args.manual_forms:
                    # You fill this one. It is announced once; the loop then stays
                    # free to keep printing the service tasks the workers complete
                    # and to feed the messages the model is waiting for.
                    now = time.time()
                    if eid not in pending:
                        pending[eid] = now
                        heartbeat[eid] = now
                        print("  %2d  YOUR TURN  %s" % (steps, waiting[0].get("name")))
                        print("        element : %s" % eid)
                        print("        form    : %s" % (by_task.get(eid) or "-"))
                        print("        open    : %s" % args.tasklist)
                        print("        fill the form there and complete the task; "
                              "waiting up to %d s" % args.form_timeout)
                    elif now - pending[eid] > args.form_timeout:
                        print("  **  gave up waiting for %s after %d s"
                              % (eid, args.form_timeout))
                        return 4
                    elif now - heartbeat[eid] > 30:
                        heartbeat[eid] = now
                        print("        ... still waiting for %s (%d s)"
                              % (eid, int(now - pending[eid])))
                    continue
                for task in waiting:
                    # what the form would submit, then what the person in the
                    # scenario types on top of it
                    # the form's required fields first, then the case data the run
                    # was opened with, then what this scenario deliberately sets.
                    # --form-fields-only drops the middle step: nothing is submitted
                    # that the bound form does not itself carry, so a variable the
                    # worker needs but no form supplies shows up as a failure here
                    # instead of being papered over by the driver.
                    v = dict(form_defaults(forms.get(by_task.get(eid), {})))
                    if not args.form_fields_only:
                        v.update(BASE_VARS)
                    elif "patientRef" in forms.get(by_task.get(eid), {}):
                        # a person types the case reference; the filler's placeholder
                        # would do, but the reference is what every message
                        # subscription is keyed on, so it reads better as itself
                        v["patientRef"] = args.correlation_key
                    v.update(TASK_VARS.get(eid, {}))
                    if args.scenario not in FIRST_VISIT_ONLY or seen.get(eid, 0) == 0:
                        v.update(overrides.get(eid, {}))
                    after = AFTER_VISITS.get(args.scenario)
                    if after and seen.get(eid, 0) >= after[0]:
                        v.update(after[1].get(eid, {}))
                    try:
                        complete(task, v)
                    except AlreadyDone:
                        done.add(task["userTaskKey"])
                        continue
                    done.add(task["userTaskKey"])
                    seen[eid] = seen.get(eid, 0) + 1
                    print("  %2d  user task   %-34s %s" % (steps, eid, task.get("name")))
                    did = True
                if did:
                    break
            elif kind == "EVENT_BASED_GATEWAY":
                names = gates.get(eid)
                if names:
                    if eid in fed:
                        # The gateway stays active until one of its messages
                        # correlates. Publishing on every poll would flood the
                        # engine with hundreds of identical messages while the
                        # operator is reading the screen, so republish on a slow
                        # beat instead and keep the loop quiet in between.
                        tries = fed[eid]
                        if tries % 5 == 0:
                            for msg in names:
                                call("POST", "/v2/messages/publication",
                                     {"name": msg,
                                      "correlationKey": key_for(msg_keys, msg, corr_key),
                                      "timeToLive": 600000,
                                      "variables": reply_variables(pi, args, msg)})
                            print("  %2d  message in  %-34s %s  <-- republished, the "
                                  "gateway is still waiting"
                                  % (steps, eid, ", ".join(names)))
                        fed[eid] = tries + 1
                        time.sleep(1.0)
                        continue
                    for msg in names:
                        call("POST", "/v2/messages/publication",
                             {"name": msg,
                              "correlationKey": key_for(msg_keys, msg, corr_key),
                              "timeToLive": 600000, "variables": reply_variables(pi, args, msg)})
                        print("  %2d  message in  %-34s %s" % (steps, eid, msg))
                    fed[eid] = 1
                    did = True
                    break
            elif kind in ("INTERMEDIATE_CATCH_EVENT", "BOUNDARY_EVENT"):
                msg = catches.get(eid)
                if msg and eid in fed:
                    # Correlation is asynchronous, and a message published before
                    # the subscription exists is simply lost. Republish on a slow
                    # beat until it lands, but say so, because a subscription that
                    # never correlates is a defect and not a timing problem.
                    tries, left = fed[eid], FED_TIMEOUT.get(eid)
                    if left is not None and time.time() - left > FED_GRACE:
                        print("  %2d  message in  %-34s %s  <-- still not correlated "
                              "after %ds" % (steps, eid, msg, FED_GRACE))
                        FED_TIMEOUT[eid] = time.time()
                    if tries % 5 == 0:
                        call("POST", "/v2/messages/publication",
                             {"name": msg,
                              "correlationKey": key_for(msg_keys, msg, corr_key),
                              "timeToLive": 600000, "variables": reply_variables(pi, args, msg)})
                    fed[eid] = tries + 1
                    time.sleep(1.0)
                    continue
                if msg:
                    call("POST", "/v2/messages/publication",
                         {"name": msg,
                          "correlationKey": key_for(msg_keys, msg, corr_key),
                          "timeToLive": 600000, "variables": reply_variables(pi, args, msg)})
                    fed[eid] = 1
                    FED_TIMEOUT[eid] = time.time()
                    print("  %2d  message in  %-34s %s" % (steps, eid, msg))
                    did = True
                    break
        if not did:
            time.sleep(1.5)

    trace_new(pi, visited)
    print("\nstopped after %d steps (--max-steps). instance still ACTIVE." % steps)
    trace_summary(visited, args.model)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
