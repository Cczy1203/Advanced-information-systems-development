#!/usr/bin/env python3
"""
Drive the v2.0 case study scenario through a running cluster.

The point is to show the pathway moving between pools, not to replace Tasklist.
Each step below is exactly what someone would do in the Tasklist UI: open the
task, fill in the form, submit. The script just does it over the REST API so the
run is repeatable and can be shown in a demo without clicking.

Prerequisites
    - the engine is up on the base URL
    - the model and forms have been deployed (tools/deploy.sh)
    - the Java workers are running (workers/run-workers.sh)

Usage
    python3 demo_scenario.py                 # happy path
    python3 demo_scenario.py --exception     # unreadable referral pack instead

v2.0 differences from v1.0: the outbound telephone routine is now a collapsed
subprocess, so its task id is SUB_CallHandling_Contact_Attempt.
"""

import argparse
import os
import json
import sys
import time
import urllib.error
import urllib.request

BASE = "http://localhost:8080"
OUR_PROCESSES = {
    "medical-secretaries", "consultants", "outpatient-bookings", "treatment-bookings",
    "finance-team", "clinical-nurse-specialists", "call-handling",
    "patient-pathway-coordinators", "administrative-management",
}


def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode()
        raise SystemExit("%s %s failed: %s %s" % (method, path, exc.code, detail[:400]))


def publish(name, correlation_key, variables):
    call("POST", "/v2/messages/publication",
         {"name": name, "correlationKey": correlation_key, "variables": variables})


def wait_for_task(process_id, element_id, timeout=45):
    """Wait until a user task exists for that process and element.

    The filter is the newest deployed version of the pool process, and tasks
    belonging to instances that were already on the broker are ignored. Without
    both, this picks whichever matching task the search happens to return first -
    and on a shared engine that is regularly a leftover from an earlier session.
    Completing somebody else's task leaves this run's instance waiting for ever,
    which is exactly what an early version of this script did: it drove an
    abandonned instance from a previous run while the current one sat at the same
    task, and the two-week telephone branch looked broken when it was not.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        # Newest first, and a page big enough to clear the backlog. A shared
        # engine accumulates pending tasks from every earlier run, and the
        # default page returns the oldest first, so the task this run just
        # created can sit beyond the first page and never be seen.
        body = {"filter": {"processDefinitionId": process_id, "state": "CREATED"},
                "sort": [{"field": "creationDate", "order": "DESC"}]}
        try:
            res = call("POST", "/v2/user-tasks/search", dict(body, page={"limit": 200}))
        except SystemExit:
            res = call("POST", "/v2/user-tasks/search", body)
        for task in res.get("items", []):
            if task.get("elementId") != element_id:
                continue
            if task.get("processInstanceKey") in PRE_EXISTING:
                continue
            RUN_INSTANCES.add(task.get("processInstanceKey"))
            return task
        time.sleep(1)
    raise SystemExit("timed out waiting for %s / %s" % (process_id, element_id))


def complete(task, variables, label):
    call("POST", "/v2/user-tasks/%s/completion" % task["userTaskKey"], {"variables": variables})
    print("   form submitted: %s" % label)


def deployment_scope():
    """The process definition keys of the newest deployed version of each pool.

    The engine this runs against is shared and keeps the history of every earlier
    session, including models that are not in this folder. Reporting "no
    incidents" while five incidents from somebody else's test processes sit on
    the same broker would be true but useless, so every query below is scoped to
    the deployment this run is actually exercising.
    """
    keys = {}
    for proc in sorted(OUR_PROCESSES):
        res = call("POST", "/v2/process-definitions/search",
                   {"filter": {"processDefinitionId": proc}})
        items = res.get("items", [])
        if not items:
            continue
        newest = max(items, key=lambda d: d.get("version", 0))
        keys[proc] = newest.get("processDefinitionKey")
    return keys


SCOPE = {}
PRE_EXISTING = set()
RUN_INSTANCES = set()


def _search(path, body):
    """Search with a page limit, falling back if the engine rejects the page."""
    try:
        return call("POST", path, dict(body, page={"limit": 200}))
    except SystemExit:
        return call("POST", path, body)


def snapshot_instances():
    """Instance keys already on the deployment before this run starts.

    Several runs share one deployment version, so keying the evidence on the
    deployment alone would still show the previous run's leftovers. Anything
    already there is excluded from the listings below, which leaves the log
    describing exactly what this run did.
    """
    keys = set()
    for proc in OUR_PROCESSES:
        res = _search("/v2/process-instances/search",
                      {"filter": {"processDefinitionId": proc}})
        for i in res.get("items", []):
            keys.add(i.get("processInstanceKey"))
    return keys


def active_elements():
    rows = []
    for proc, key in sorted(SCOPE.items()):
        res = _search("/v2/element-instances/search",
                      {"filter": {"processDefinitionKey": key, "state": "ACTIVE"}})
        for inst in res.get("items", []):
            if inst.get("processInstanceKey") in PRE_EXISTING:
                continue
            rows.append((proc, inst.get("elementId"), inst.get("type")))
    return rows


def incidents():
    """Active incidents raised by the pool processes of this deployment.

    The search response does not always carry the process definition key, so the
    match falls back to the process id and to the element id. An incident check
    that silently matches nothing is worse than no check at all - an earlier
    version of this function reported "incidents: none" while two incidents from
    the same run sat on the broker.
    """
    res = _search("/v2/incidents/search", {"filter": {"state": "ACTIVE"}})
    out = []
    for i in res.get("items", []):
        if i.get("processDefinitionId") not in OUR_PROCESSES:
            continue
        # An incident on an instance that was already on the broker before this
        # run belongs to an earlier session, not to this one.
        if i.get("processInstanceKey") in PRE_EXISTING:
            continue
        out.append(i)
    return out


def show(stage):
    print("\n--- %s ---" % stage)
    for proc, element, etype in active_elements():
        print("   %-26s %-36s %s" % (proc, element, etype))
    bad = incidents()
    if bad:
        print("   INCIDENTS:")
        for i in bad:
            print("     %s %s: %s" % (i.get("processDefinitionId"), i.get("elementId"),
                                      (i.get("errorMessage") or "")[:160]))
    else:
        print("   incidents: none")


# Tasks the main path reaches only under some worker settings. Each is driven if
# it appears; a task that never appears is reported as "not reached", which is
# itself the evidence that the branch was not taken.
EXTRAS = [
    ("always", "treatment-bookings", "TRT_Task_ReviewDeclinedPayment",
     {"declinedAction": "RETRY_PAYMENT", "paymentStatus": "DECLINED",
      "patientInformed": True, "reviewedBy": "T. Booker"},
     "decide how to handle the failed payment"),
    ("always", "treatment-bookings", "TRT_Task_ReviewFundingTimeout",
     {"fundingChaseOutcome": "RECHECK", "chasedBy": "T. Booker"},
     "chase the outstanding funding approval"),
    ("investigate", "finance-team", "FIN_Task_InvestigatePayment",
     {"paymentReference": "PAY-DEMO-0001", "providerStatementChecked": True,
      "paymentFound": "false",
      "investigationNotes": "Provider has not returned a confirmation. No duplicate "
                            "charge found, so no further payment is requested.",
      "investigatedBy": "F. Officer"},
     "investigate the payment the provider never confirmed"),
    ("investigate", "consultants", "CON_Task_AuthoriseUrgentTreatment",
     {"urgentTreatmentAuthorised": "true",
      "clinicalUrgencyReason": "Delay would take the patient outside the treatment window.",
      "clinicalRiskIfDelayed": "Progression during the delay.",
      "financeReferralAccepted": True,
      "authorisedBy": "Dr R. Mensah"},
     "authorise urgent treatment without confirmed payment"),
    ("overdue", "patient-pathway-coordinators", "SUB_Pathway_Report_Review",
     # The band the review declares drives the escalation gateway: over 90 days
     # goes to higher management, 31-90 to the Administrative Manager. The value
     # is settable so both rungs can be shown without touching the model.
     {"letterOverdueDays": int(os.environ.get("DEMO_LETTER_OVERDUE_DAYS", "120")),
      "outstandingLettersReviewed": 1,
      "reminderAction": os.environ.get("DEMO_LETTER_ACTION", "ESCALATE_HIGHER"),
      "reasonForDelay": "Consultant unavailable; letter still unsigned.",
      "reviewedBy": "P. Coordinator"},
     "review the overdue correspondence list"),
    ("overdue", "administrative-management", "ADM_Task_ContactConsultant",
     {"consultantName": "Dr R. Mensah", "contactMethod": "Email",
      "letterNowCompleted": "false",
      "escalationNotes": "Reminded by the Administrative Manager; letter still outstanding.",
      "contactedBy": "A. Manager"},
     "contact the Consultant about the overdue letter"),
    ("overdue", "administrative-management", "ADM_Task_ReferHigher",
     {"monthsOutstanding": 4, "higherManagementTeam": "Medical director",
      "reasonForEscalation": "Clinic letter outstanding beyond three months.",
      "referralDate": "2026-06-01T09:00:00", "referredBy": "A. Manager"},
     "refer the case to higher management"),
]


def drive_extras(enabled):
    """Work whatever branch tasks are waiting, then say which were not reached."""
    driven, reached = [], set()
    for tag, proc, element, payload, label in EXTRAS:
        if tag not in enabled:
            continue
        try:
            # The escalation rungs are reached through the weekly review timer,
            # so they appear a little after the review task is completed rather
            # than immediately. Give them longer than the synchronous steps.
            # The branch wait has to cover the engine round trip for the step
            # that precedes the branch: on a cold worker JVM the payment
            # transaction alone took 60 s, so a fixed 20 s window reported
            # "not reached" for a branch that had in fact been reached by the
            # model (the element history showed TRT_Task_ReviewDeclinedPayment).
            timeout = 150 if tag == "overdue" else int(
                os.environ.get("DEMO_BRANCH_TIMEOUT", "60"))
            task = wait_for_task(proc, element, timeout=timeout)
        except SystemExit:
            print("   not reached: %s (%s)" % (element, label))
            continue
        complete(task, payload, label)
        driven.append(element)
        reached.add(element)
        time.sleep(5)
    return driven


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exception", action="store_true",
                        help="send a damaged document so the pack fails validation")
    parser.add_argument("--investigate", action="store_true",
                        help="also work the unconfirmed-payment branch "
                             "(run the workers with DEMO_PAYMENT_STATUS=NO_CONFIRMATION)")
    parser.add_argument("--overdue", action="store_true",
                        help="also flag an overdue clinic letter and work the "
                             "administrator and higher-management escalations")
    args = parser.parse_args()

    global SCOPE
    SCOPE = deployment_scope()
    if not SCOPE:
        raise SystemExit("no process definition found for this collaboration - run tools/deploy.sh")
    print("evidence scoped to deployment: %s"
          % ", ".join("%s=v%s" % (p, k) for p, k in sorted(SCOPE.items())[:3]) + " ...")
    print("   (%d pool processes, newest deployed version of each)" % len(SCOPE))
    PRE_EXISTING.update(snapshot_instances())
    print("   %d instances already on this deployment are excluded from the evidence"
          % len(PRE_EXISTING))

    ref = "PAT-DEMO-%d" % (int(time.time()) % 100000)
    print("patient reference: %s" % ref)

    documents = ["referral-letter", "blood-tests", "imaging-report", "histology-report", "consent-form"]
    if args.exception:
        documents = ["referral-letter", "corrupt-scan"]

    print("\n1. referral arrives from the GP (message start event)")
    publish("referral.received", ref, {
        "patientRef": ref,
        "patientName": "Jordan Ellis",
        "patientContactNumber": "07700 900123",
        "patientPreferredChannel": "POST",
        "patientAccessibilityNeeds": "Large print letters.",
        "referralRef": "REF-2026-0042",
        "referralSource": "GP surgery",
        "referralDate": "2026-09-18",
        "referralSpeciality": "Medical oncology",
        "referralPriority": "Urgent",
        "supportingDocuments": documents,
        "receivedBy": "A. Secretary",
    })

    if args.overdue:
        print("1b. a clinic letter is more than three months overdue (message from the "
              "reminder routine)")
        publish("letter.overdue-flagged", ref + "-clinic-letter",
                {"patientRef": ref, "letterRef": "CL-2026-0042",
                 "letterOverdueDays": 120, "overdueBand": "OVER_THREE_MONTHS",
                 "consultantName": "Dr R. Mensah", "consultationDate": "2026-05-20"})

    print("2. Medical Secretaries check the pack")
    task = wait_for_task("medical-secretaries", "SEC_Task_CheckPack")
    complete(task, {"packChecked": True,
                    "documentChecklistNotes": "Checked against the oncology checklist."},
             "Check referral pack against the document checklist")

    if args.exception:
        time.sleep(6)
        show("exception path: the pack failed validation")
        print("\nExpected: referral.check-supporting-documents threw REFERRAL_PACK_UNREADABLE, the "
              "boundary event caught it, and the case joined the missing-information loop rather "
              "than reaching a clinician.")
        return

    print("3. Consultant records the clinical decision")
    task = wait_for_task("consultants", "CON_Task_ReviewReferral")
    complete(task, {
        "clinicalDecision": "ACCEPT",
        "clinicalDecisionReason": "Histology confirms the suspected diagnosis; suitable for systemic treatment.",
        "clinicalPriorityConfirmed": "Urgent",
        "decidingClinician": "Dr R. Mensah",
        "decisionDate": "2026-09-22",
    }, "Review the referral and record the clinical decision")
    time.sleep(6)

    print("4. Outpatient Bookings choose an appointment")
    task = wait_for_task("outpatient-bookings", "OUT_Task_ChooseSlot")
    complete(task, {
        "chosenSlotRef": "SLOT-4471",
        "appointmentDateTime": "2026-09-29T09:30:00",
        "appointmentLocation": "Oncology Day Unit, Level 2",
        "appointmentPriority": "Urgent",
        "interpreterRequired": False,
        "chosenBy": "B. Booker",
    }, "Choose and confirm the appointment")
    time.sleep(6)

    print("5. Call Handling telephone the patient about the short notice appointment")
    task = wait_for_task("call-handling", "SUB_CallHandling_Contact_Attempt")
    complete(task, {
        "contactOutcome": "REACHED",
        "contactAttempts": 1,
        "patientRequestsAlternative": False,
        "contactNotes": "Patient confirmed the date and the large print requirement.",
        "attemptedBy": "C. Handler",
    }, "Attempt to telephone the patient")
    time.sleep(6)

    show("after the booking is confirmed")

    print("\n6. patient attends the new patient appointment (message from outside)")
    publish("appointment.attended", ref, {"patientRef": ref, "attendedOn": "2026-09-29"})

    print("7. Consultant records consent and completes the treatment booking request")
    task = wait_for_task("consultants", "CON_Task_RecordConsent")
    complete(task, {
        "consentGiven": "true",
        "consentDiscussedWith": "Patient attended alone",
        "treatmentPlan": "Chemotherapy",
        "treatmentStartDate": "2026-10-06",
        "cycleCount": 6,
        "cycleIntervalDays": 21,
        "reviewsBetweenCycles": True,
        "specialResources": ["Laboratory", "Imaging", "Pharmacy"],
        "treatmentBookingRef": "TBR-2026-0007",
        "authorisingClinician": "Dr R. Mensah",
    }, "Record consent and complete the treatment booking request")

    print("8. Finance Team determine the funding route")
    task = wait_for_task("finance-team", "FIN_Task_DetermineFunding", timeout=60)
    complete(task, {
        "fundingRoute": "PATIENT_PAYS",
        "approvalDate": "2026-09-30",
        "decidedBy": "F. Officer",
    }, "Determine the funding route and record the approval")
    time.sleep(8)

    print("9. branch work: whatever the current worker configuration produced")
    enabled = {"always"}
    if args.investigate:
        enabled.add("investigate")
    if args.overdue:
        enabled.add("overdue")
    driven = drive_extras(enabled)
    if driven:
        print("   driven: %s" % ", ".join(driven))
    else:
        print("   no branch task appeared")

    time.sleep(6)
    show("after treatment is booked")

    print("\n10. Consultant drafts and approves the clinic letter")
    try:
        task = wait_for_task("consultants", "CON_Task_DraftLetter", timeout=45)
        complete(task, {
            "consultationDate": "2026-09-29",
            "letterType": "New patient clinic letter",
            "letterRecipients": ["patient", "gp"],
            "diagnosisSummary": "Histologically confirmed malignancy. Planned systemic treatment.",
            "treatmentDecisions": "Adjuvant chemotherapy, six cycles, three weekly.",
            "followUpArrangements": "Clinical review before each cycle.",
            "letterApproved": "true",
            "approvingClinician": "Dr R. Mensah",
        }, "Draft and approve the clinic letter")
    except SystemExit:
        print("   (no clinic letter task appeared - check the previous step)")

    time.sleep(6)
    print("11. Medical Secretaries process and send the letter")
    try:
        task = wait_for_task("medical-secretaries", "SEC_Task_ProcessLetter", timeout=45)
        complete(task, {
            "consultationDate": "2026-09-29",
            "letterRecipients": ["patient", "gp"],
            "adminChecksCarriedOut": ["Patient identifiers correct", "Recipient list confirmed",
                                      "Accessible format applied"],
            "clinicalErrorSuspected": "false",
            "processedBy": "A. Secretary",
        }, "Check and process the approved clinic letter")
    except SystemExit:
        print("   (no letter processing task appeared - check the previous step)")

    time.sleep(8)
    show("end of the demonstration")

    print("""
What the run has shown
    1. a referral message starts the Medical Secretaries process
    2. the document check worker passes the pack and the case is handed to the Consultant pool
    3. the Consultant accepts, and the Outpatient Bookings pool picks the booking up
    4. the inclusive gateway sends a letter and, because the appointment is inside two weeks,
       asks the Call Handling pool to telephone the patient as well
    5. attendance, consent and an authorised treatment request reach the Treatment Bookings pool
    6. the funding decision comes back from the Finance Team
    7. the payment is taken through the simulated provider and the series is confirmed
    8. the confirmed schedule triggers the clinic letter, which goes Consultant -> Medical
       Secretaries -> correspondence service

Branches this run could reach
    python3 demo_scenario.py --exception                     unreadable referral pack
    DEMO_PAYMENT_STATUS=DECLINED  ... --investigate           the provider declines, then the retry is approved
    DEMO_PAYMENT_STATUS=NO_CONFIRMATION ... --investigate     the provider never confirms, so the case goes to
                                                              investigation and a clinician authorises urgent care
    ... --overdue                                            a clinic letter over three months old escalates to
                                                              the Administrative Manager and to higher management
""")


if __name__ == "__main__":
    sys.exit(main())
