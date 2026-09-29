"""
Camunda Form definitions for the hospital pathway model.

Field keys are deliberately identical to the process variables the gateways and
workers use (clinicalDecision, fundingRoute, refundDecision, and so on), so a
form submission lands straight in the variable the model is already reading.

Layout note: most fields sit on their own row. That is a deliberate
accessibility choice - a single column form is easier to follow with a screen
reader or a magnifier than a dense two column grid. Only a couple of genuinely
related short fields (an amount and its currency, a start date and an interval)
share a row.
"""

FORM_VERSION = "8.10.0"

_field_seq = [0]


def _next():
    _field_seq[0] += 1
    return _field_seq[0]


def _base(key, label, ctype, desc=None, validate=None, extra=None, columns=None, row=None):
    n = _next()
    comp = {
        "label": label,
        "type": ctype,
        "layout": {"row": row or ("Row_%03d" % n), "columns": columns},
        "id": "Field_%03d" % n,
        "key": key,
    }
    if desc:
        comp["description"] = desc
    if validate:
        comp["validate"] = validate
    if extra:
        comp.update(extra)
    return comp


def text(key, label, desc=None, required=True, minlen=None, maxlen=None, pattern=None,
         placeholder=None, row=None, columns=None):
    v = {}
    if required:
        v["required"] = True
    if minlen:
        v["minLength"] = minlen
    if maxlen:
        v["maxLength"] = maxlen
    if pattern:
        v["pattern"] = pattern
    extra = {"properties": {"placeholder": placeholder}} if placeholder else None
    return _base(key, label, "textfield", desc, v or None, extra, columns, row)


def area(key, label, desc=None, required=True, rows=4, row=None, columns=None):
    return _base(key, label, "textarea", desc, {"required": True} if required else None,
                 {"properties": {"rows": rows}}, columns, row)


def num(key, label, desc=None, required=True, mn=None, mx=None, row=None, columns=None):
    v = {}
    if required:
        v["required"] = True
    if mn is not None:
        v["min"] = mn
    if mx is not None:
        v["max"] = mx
    return _base(key, label, "number", desc, v or None, None, columns, row)


def date(key, label, desc=None, required=True, row=None, columns=None):
    """A date-only field.

    Camunda Forms has no 'date' field type - only a datetime field with a
    subtype. Emitting type "date" produces a form the renderer refuses to draw,
    which is what stopped every form with a date on it from opening in Tasklist.
    """
    return _base(key, label, "datetime", desc, {"required": True} if required else None,
                 {"subtype": "date"}, columns, row)


def dt(key, label, desc=None, required=True, row=None, columns=None):
    return _base(key, label, "datetime", desc, {"required": True} if required else None,
                 {"subtype": "datetime"}, columns, row)


def check(key, label, desc=None, default=False, row=None, columns=None):
    return _base(key, label, "checkbox", desc, None, {"defaultValue": default}, columns, row)


def radio(key, label, options, desc=None, required=True, row=None, columns=None, conditional=None):
    extra = {"values": _values(options)}
    if conditional:
        extra["conditional"] = conditional
    return _base(key, label, "radio", desc, {"required": True} if required else None, extra, columns, row)


def sel(key, label, options, desc=None, required=True, row=None, columns=None, conditional=None):
    extra = {"values": _values(options)}
    if conditional:
        extra["conditional"] = conditional
    return _base(key, label, "select", desc, {"required": True} if required else None, extra, columns, row)


def ticks(key, label, options, desc=None, row=None, columns=None, conditional=None):
    extra = {"values": _values(options)}
    if conditional:
        extra["conditional"] = conditional
    return _base(key, label, "checklist", desc, None, extra, columns, row)


def _values(options):
    """Options may be plain strings or (label, value) pairs.

    Checklist and select fields whose answer is read by a worker send the
    canonical value while showing the member of staff a readable label.
    """
    out = []
    for o in options:
        if isinstance(o, (tuple, list)):
            out.append({"label": o[0], "value": o[1]})
        else:
            out.append({"label": o, "value": o})
    return out


def _form(description, components):
    return {"description": description, "components": components}


FORMS = {}

# ---------------------------------------------------------------- referral ---
FORMS["check-referral-pack"] = _form(
    "Medical Secretaries record what arrived with the referral. This form never asks for a "
    "view on whether the referral is clinically appropriate - that is the Consultant's call.",
    [
        text("patientRef", "Patient reference",
             "Copy it from the referral exactly. Every hand-off in the pathway is keyed on this, so a "
             "wrong reference follows the patient through the whole service.",
             minlen=4, maxlen=24),
        text("referralRef", "Referral reference", "The reference the referring organisation quoted.",
             minlen=3, maxlen=30),
        sel("referralSource", "Where did the referral come from?",
            ["GP surgery", "Another hospital", "Internal transfer", "Other"]),
        date("referralDate", "Date on the referral"),
        sel("referralSpeciality", "Speciality the referral is for",
            ["Medical oncology", "Clinical oncology", "Haematology", "Chemotherapy day unit", "Other"]),
        radio("referralPriority", "Priority stated by the referrer",
              ["Routine", "Urgent", "Two week wait"],
              "Copy what the referrer wrote. Do not upgrade or downgrade it here."),
        ticks("supportingDocuments", "Documents received with the referral",
              [("Referral letter", "referral-letter"),
               ("Blood test results", "blood-tests"),
               ("Imaging report", "imaging-report"),
               ("Histology or biopsy report", "histology-report"),
               ("Signed consent form", "consent-form"),
               ("Other clinical documentation", "other-clinical-documentation")],
              "Tick everything that is actually attached. Missing items are worked out from this, so an "
              "unticked box means the document is chased."),
        area("documentChecklistNotes", "Anything else about the pack",
             "For example a document that will not open, or a page that is illegible.",
             required=False, rows=3),
        check("packChecked", "I have checked the pack against the speciality checklist",
              "Required before the referral can move on."),
        text("receivedBy", "Checked by", "Your name, so the check is traceable.", maxlen=80),
    ])

FORMS["notify-referrer-outcome"] = _form(
    "Records the Consultant's decision and how the referring organisation was told about it.",
    [
        sel("referralOutcome", "Outcome recorded",
            ["REJECTED", "REDIRECTED", "CLINICAL_INFO_REQUESTED", "ACCEPTED"]),
        area("referralOutcomeReason", "Reason to pass to the referrer",
             "Use the Consultant's own wording. Do not add clinical opinion of your own."),
        sel("notificationMethod", "How was the referrer told?", ["Letter", "Secure email", "Telephone call"]),
        text("referrerContactName", "Who at the referring organisation?", required=False, maxlen=80),
        text("referrerContactEmail", "Contact email", required=False, maxlen=120),
        text("outcomeRecordedBy", "Recorded by", maxlen=80),
    ])

FORMS["process-clinic-letter"] = _form(
    "Administrative processing of an approved clinic letter. Formatting and administrative errors may be "
    "corrected here; anything that looks like a clinical error goes back to the Consultant.",
    [
        text("letterRef", "Letter reference", required=False, maxlen=40),
        date("consultationDate", "Date of the appointment the letter refers to"),
        ticks("letterRecipients", "Recipients confirmed",
              [("Patient", "patient"), ("Patient's GP", "gp"),
               ("Referring hospital", "referring-hospital"),
               ("Another healthcare provider", "other-provider"),
               ("Other professional", "other-professional")],
              "Check each recipient against the letter the Consultant approved."),
        ticks("adminChecksCarriedOut", "Checks completed",
              ["Patient identifiers correct", "Recipient list confirmed", "Formatting corrected",
               "Accessible format applied", "Translation arranged"]),
        radio("clinicalErrorSuspected", "Does anything look like a clinical error?", ["true", "false"],
              "If yes the letter goes back to the Consultant. Administrative staff must not change "
              "clinical meaning."),
        area("clinicalErrorDetails", "What looks wrong?",
             "Describe the query factually so the Consultant can act on it.",
             required=False, rows=3),
        text("processedBy", "Processed by", maxlen=80),
    ])

FORMS["resolve-dispatch-problem"] = _form(
    "Used when the correspondence service rejects a clinic letter, or never answers.",
    [
        sel("dispatchFailureReason", "What went wrong?",
            ["Recipient address rejected", "Channel unavailable", "Letter not accepted",
             "No response from the service"]),
        radio("alternativeChannel", "Channel to try next",
              ["Secure email", "Post", "Collection in person"],
              "Pick a channel the recipient has agreed to."),
        check("patientInformedOfDelay", "The patient has been told about the delay"),
        area("resolutionNotes", "What was done", required=False, rows=3),
        text("resolvedBy", "Dealt with by", maxlen=80),
    ])

# -------------------------------------------------------------- consultant ---
FORMS["review-referral"] = _form(
    "The clinical decision on a referral. The reason and the deciding clinician are kept for audit "
    "and cannot be edited once the decision is recorded.",
    [
        radio("clinicalDecision", "Clinical decision",
              ["ACCEPT", "REJECT", "REDIRECT", "REQUEST_CLINICAL_INFORMATION"],
              "Only a Consultant may answer this."),
        area("clinicalDecisionReason", "Reason for the decision",
             "This is what appears in the audit record and in any letter back to the referrer."),
        text("redirectSpeciality", "Speciality to redirect to", required=False, maxlen=80),
        sel("clinicalPriorityConfirmed", "Priority confirmed at review",
            ["Routine", "Urgent", "Two week wait"]),
        text("decidingClinician", "Deciding clinician", maxlen=80),
        date("decisionDate", "Date of decision"),
    ])

FORMS["record-consent-and-treatment-request"] = _form(
    "Completed at the new patient appointment. If the patient agrees to proceed, the whole treatment "
    "booking request has to be filled in here - an incomplete request cannot be authorised.",
    [
        radio("consentGiven", "Has the patient agreed to proceed with treatment?", ["true", "false"],
              "Record what the patient actually said, not what was recommended."),
        text("consentDiscussedWith", "Consent discussed with",
             "Leave blank if the patient consented on their own behalf.", required=False, maxlen=80),
        sel("treatmentPlan", "Proposed treatment",
            ["Chemotherapy", "Radiotherapy", "Immunotherapy", "Combination", "Other"],
            conditional={"hide": "=consentGiven = false"}),
        date("treatmentStartDate", "Required start date", required=False),
        num("cycleCount", "Number of cycles", mn=1, mx=30),
        num("cycleIntervalDays", "Days between cycles", mn=1, mx=90),
        check("reviewsBetweenCycles", "A clinical review is needed between cycles"),
        ticks("specialResources", "Special resources likely to be needed",
              ["Laboratory", "Imaging", "Pharmacy", "Day unit chair", "Isolation room", "Interpreter"]),
        text("treatmentBookingRef", "Treatment booking reference", maxlen=40),
        text("authorisingClinician", "Authorising clinician", maxlen=80),
        area("declineReason", "If the patient is not proceeding, what was discussed?",
             required=False, rows=3),
    ])

FORMS["review-chemotherapy-cycle"] = _form(
    "Clinical review before a further cycle. Administrative teams cannot make this decision and the "
    "form says so on the face of it.",
    [
        num("cycleNumber", "Cycle number being reviewed", mn=1, mx=30),
        check("bloodResultsReviewed", "Blood results have been reviewed"),
        radio("cycleReviewOutcome", "Outcome of the review",
              ["FIT_TO_CONTINUE", "DELAY", "CHANGE_PLAN"],
              "Fit to continue books the next cycle. Delay or change the plan goes back to the bookings team."),
        area("cycleReviewNotes", "Notes to support the decision"),
        text("reviewClinician", "Reviewed by", maxlen=80),
        date("reviewDate", "Review date"),
    ])

FORMS["authorise-treatment-modification"] = _form(
    "A treatment change only counts once it has been authorised here. A change asked for by email or "
    "over the phone is not processed until this record exists.",
    [
        area("modificationReason", "Reason for the change",
             "Say what changed clinically, not just what the new schedule should be."),
        radio("modificationUrgent", "Is this urgent for patient safety?", ["true", "false"],
              "Urgent changes are applied straight away and the financial impact is reviewed afterwards."),
        radio("modificationAffectsFinance", "Does this affect a charge or a payment already taken?",
              ["true", "false"]),
        area("alternativePlan", "New plan", required=False, rows=3),
        text("modificationAuthorisedBy", "Authorised by", maxlen=80),
        date("modificationDate", "Date authorised"),
    ])

FORMS["draft-clinic-letter"] = _form(
    "The clinic letter. The Consultant owns the clinical content and approves it; Medical Secretaries "
    "may only correct formatting and administrative errors afterwards.",
    [
        date("consultationDate", "Date of the appointment"),
        sel("letterType", "Letter type", ["New patient clinic letter", "Follow-up clinic letter"]),
        ticks("letterRecipients", "Who should receive this letter?",
              [("Patient", "patient"), ("Patient's GP", "gp"),
               ("Referring hospital", "referring-hospital"),
               ("Another healthcare provider", "other-provider"),
               ("Other professional", "other-professional")]),
        area("diagnosisSummary", "Diagnosis", rows=3),
        area("clinicalFindings", "Clinical findings", required=False, rows=3),
        area("treatmentDecisions", "Treatment decisions", required=False, rows=3),
        area("followUpArrangements", "Follow-up arrangements", required=False, rows=3),
        area("instructionsToCommunicate", "Anything that must be passed on", required=False, rows=3),
        radio("letterApproved", "Do you approve this letter for distribution?", ["true", "false"]),
        text("approvingClinician", "Approved by", maxlen=80),
    ])

FORMS["correct-clinic-letter"] = _form(
    "Used when a letter comes back because of a possible clinical error. Administrative staff cannot "
    "change clinical meaning, so it returns to the Consultant.",
    [
        area("correctionReason", "What was queried?",
             "Quote the query from the Medical Secretary so the trail is clear."),
        ticks("correctedSections", "Sections changed",
              ["Diagnosis", "Clinical findings", "Treatment decisions", "Follow-up arrangements",
               "Instructions to communicate"]),
        radio("letterApproved", "Do you approve the corrected letter?", ["true", "false"]),
        text("approvingClinician", "Approved by", maxlen=80),
    ])

FORMS["authorise-urgent-treatment"] = _form(
    "Only used when treatment must go ahead before payment is confirmed. A clinician has to justify it "
    "and Finance picks the money side up afterwards.",
    [
        radio("urgentTreatmentAuthorised", "May treatment go ahead without confirmed payment?",
              ["true", "false"]),
        area("clinicalUrgencyReason", "Clinical reason for proceeding now",
             "Be specific. This record is what Finance and the audit team will read."),
        area("clinicalRiskIfDelayed", "What is the risk if treatment is delayed?", required=False, rows=3),
        check("financeReferralAccepted", "I understand this is being referred to the Finance Team"),
        text("authorisedBy", "Authorised by", maxlen=80),
    ])

FORMS["clinical-review-advice"] = _form(
    "Consultant response to a clinical question raised by the nurse specialists or another team.",
    [
        text("enquiryRef", "Enquiry reference", required=False, maxlen=40),
        area("clinicalReviewOutcome", "Clinical review outcome"),
        area("clinicalAdviceSummary", "Advice to pass back", required=False, rows=4),
        radio("needsConsultantReview", "Does this need a face to face review?", ["true", "false"],
              required=False),
        text("reviewedBy", "Reviewed by", maxlen=80),
        date("reviewDate", "Review date"),
    ])

# ------------------------------------------------------- outpatient booking ---
FORMS["choose-appointment-slot"] = _form(
    "Booking a new patient appointment. The slot is confirmed in the hospital system and any access "
    "requirement is captured at the same time so the clinic can prepare.",
    [
        text("chosenSlotRef", "Slot reference from the scheduling service", maxlen=40),
        dt("appointmentDateTime", "Appointment date and time"),
        text("appointmentLocation", "Clinic location", maxlen=120),
        sel("appointmentPriority", "Priority", ["Routine", "Urgent", "Two week wait"]),
        check("interpreterRequired", "An interpreter is needed"),
        area("patientAccessibilityNeeds", "Access or communication needs",
             "For example a large print letter, a step free route, or a carer attending.",
             required=False, rows=3),
        text("chosenBy", "Booked by", maxlen=80),
    ])

FORMS["review-appointment-availability"] = _form(
    "What to do when the scheduling service has nothing inside the period the Consultant asked for. "
    "The appointment is never quietly moved outside that window.",
    [
        radio("availabilityAction", "How should this be handled?",
              ["WIDEN_SEARCH", "OFFER_NEXT_AVAILABLE", "ESCALATE"],
              "Widening the search keeps the clinical window. Escalating hands it to the pathway team."),
        sel("noSlotReason", "Why was nothing available?",
            ["No clinic capacity", "Consultant unavailable", "Required resource unavailable",
             "Patient asked for a different period"]),
        date("preferredFromDate", "Search again from", required=False),
        date("preferredToDate", "Search again to", required=False),
        area("notes", "Notes", required=False, rows=3),
        text("reviewedBy", "Reviewed by", maxlen=80),
    ])

FORMS["confirm-follow-up-appointment"] = _form(
    "Follow-up bookings must land inside the period the clinical team asked for.",
    [
        sel("requestedReviewPeriod", "Period requested by the clinical team",
            ["2 weeks", "4 weeks", "3 months", "6 months", "Other"]),
        dt("appointmentDateTime", "Appointment date and time"),
        text("appointmentLocation", "Clinic location", required=False, maxlen=120),
        radio("withinRequestedPeriod", "Is this inside the requested period?", ["true", "false"],
              "Answering no sends the case to the pathway team instead of booking it anyway."),
        area("outsidePeriodReason", "If not, why not?", required=False, rows=3),
        text("confirmedBy", "Confirmed by", maxlen=80),
    ])

FORMS["decide-cancellation-action"] = _form(
    "Cancellations, declines and missed appointments all land here. Administrative staff coordinate the "
    "next step; they do not decide whether treatment continues.",
    [
        sel("appointmentOutcome", "What happened?",
            ["CANCELLED_BY_PATIENT", "DECLINED", "DID_NOT_ATTEND", "CANCELLED_BY_HOSPITAL"]),
        area("cancellationReason", "Reason given", required=False, rows=3),
        radio("cancellationAction", "What happens next?",
              ["REBOOK", "CLINICAL_REVIEW", "CLOSE_AND_INFORM_REFERRER"],
              "Clinical review and discharge decisions belong to the clinical team."),
        num("rebookWithinDays", "Offer another appointment within (days)", required=False, mn=1, mx=180,
            row="Row_booking_action", columns=6),
        sel("communicationChannel", "How should the patient be told?",
            ["Letter", "Telephone", "Secure email"], required=False,
            row="Row_booking_action", columns=6),
        check("patientInformedOfOptions", "The patient has been told what the options are"),
        text("recordedBy", "Recorded by", maxlen=80),
    ])

FORMS["record-treatment-decline"] = _form(
    "The patient has decided not to go ahead. The decision on whether the pathway continues is the "
    "clinical team's, so this form only records and routes.",
    [
        sel("declineReason", "Why is the patient not proceeding?",
            ["Patient choice", "Patient unwell", "Treatment no longer appropriate", "Other"]),
        area("declineNotes", "What was discussed with the patient?", required=False, rows=4),
        radio("clinicalFollowUpRequired", "Does a clinician need to review the pathway?",
              ["true", "false"]),
        text("discussedWithClinician", "Clinician already spoken to", required=False, maxlen=80),
        text("recordedBy", "Recorded by", maxlen=80),
    ])

# --------------------------------------------------------- treatment book ---
FORMS["review-declined-payment"] = _form(
    "Payment did not go through. The booking stays unconfirmed until this is resolved, and a second "
    "attempt must not create a duplicate charge.",
    [
        sel("paymentStatus", "What did the provider report?", ["DECLINED", "CANCELLED", "INCOMPLETE"]),
        area("providerMessage", "Message from the provider", required=False, rows=3),
        radio("declinedAction", "What should happen?",
              ["RETRY_PAYMENT", "LEAVE_WITH_FINANCE", "CANCEL_BOOKING"],
              "A retry gets a new payment reference, so the patient is never charged twice."),
        check("patientInformed", "The patient has been told the payment did not go through"),
        area("notes", "Notes", required=False, rows=3),
        text("reviewedBy", "Reviewed by", maxlen=80),
    ])

FORMS["chase-funding-approval"] = _form(
    "Used when a funding decision has not come back inside the expected window.",
    [
        radio("fundingChaseOutcome", "What is the position now?",
              ["RECHECK", "STILL_WAITING", "DECLINED"],
              "Choose recheck once the approval is actually in the system."),
        text("payerContactName", "Who was spoken to", required=False, maxlen=80),
        text("payerReference", "Payer reference", required=False, maxlen=40),
        area("chaseNotes", "Notes from the chase", required=False, rows=3),
        text("chasedBy", "Chased by", maxlen=80),
    ])

FORMS["record-cycle-delay"] = _form(
    "Recording a clinically agreed delay and replanning the cycle.",
    [
        num("cycleNumber", "Cycle number", mn=1, mx=30),
        area("delayReason", "Reason for the delay"),
        date("newProposedStartDate", "Proposed new start date", required=False),
        check("patientInformed", "The patient has been told"),
        text("recordedBy", "Recorded by", maxlen=80),
    ])

FORMS["review-treatment-change"] = _form(
    "First pass at a treatment change request. A change that only arrived informally is sent back for "
    "proper authorisation.",
    [
        area("modificationReason", "What is being asked for?"),
        text("requestedBy", "Requested by", maxlen=80),
        radio("requestFormallySubmitted", "Was the request submitted through the system?",
              ["true", "false"],
              "Email and telephone requests are not processed until they are formally authorised."),
        sel("changeCategory", "Type of change",
            ["Date change", "Dose change", "Regimen change", "Stop treatment", "Other"]),
        area("notes", "Notes", required=False, rows=3),
    ])

# ----------------------------------------------------------------- finance ---
FORMS["determine-funding-route"] = _form(
    "The funding decision. The responsible organisation, the authorisation reference, the approved "
    "amount and any limits all have to be recorded.",
    [
        radio("fundingRoute", "Funding route",
              ["HOSPITAL_FUNDED", "INSURER_APPROVED", "PATIENT_PAYS", "EXEMPTION"]),
        text("funderName", "Responsible funding organisation",
             "Required for insurer or funding organisation routes.", required=False, maxlen=120,
             row="Row_funder", columns=6),
        text("authorisationRef", "Authorisation reference", required=False, maxlen=40,
             row="Row_funder", columns=6),
        num("approvedAmount", "Approved amount", required=False, mn=0, row="Row_amount", columns=6),
        sel("currency", "Currency", ["GBP", "EUR", "USD"], required=False,
            row="Row_amount", columns=6),
        area("fundingLimitations", "Limits attached to the approval",
             "For example a capped number of cycles or a named treatment only.", required=False, rows=3),
        sel("exemptionReason", "Exemption reason",
            ["Not applicable", "Overseas visitor exemption", "Clinical trial",
             "Prescribed special service", "Other"], required=False),
        date("approvalDate", "Decision date"),
        text("decidedBy", "Decided by", maxlen=80),
    ])

FORMS["manual-charge-entry"] = _form(
    "Fallback pricing when the automated tariff lookup cannot work out the charge.",
    [
        text("treatmentPlan", "Treatment being priced", maxlen=120),
        text("tariffCode", "Tariff code", required=False, maxlen=30),
        num("chargeAmount", "Charge amount", mn=0, row="Row_manual_amount", columns=6),
        sel("currency", "Currency", ["GBP", "EUR", "USD"], row="Row_manual_amount", columns=6),
        area("overrideReason", "Why is this being priced manually?"),
        text("pricedBy", "Priced by", maxlen=80),
    ])

FORMS["chase-pre-authorisation"] = _form(
    "Following up an insurer or funding organisation that has not yet authorised treatment.",
    [
        text("payerContactName", "Who was spoken to", required=False, maxlen=80),
        text("payerReference", "Payer reference", required=False, maxlen=40),
        radio("outcome", "Outcome of the contact", ["Approved", "Declined", "Awaiting response"]),
        text("authorisationRef", "Authorisation reference", required=False, maxlen=40,
             row="Row_preauth", columns=6),
        num("approvedAmount", "Approved amount", required=False, mn=0,
            row="Row_preauth", columns=6),
        area("notes", "Notes", required=False, rows=3),
        text("chasedBy", "Chased by", maxlen=80),
    ])

FORMS["investigate-unconfirmed-payment"] = _form(
    "The provider took a payment but no confirmation reached the hospital. Nobody asks the patient for "
    "money again until this has been checked.",
    [
        text("paymentReference", "Payment reference under investigation", maxlen=40),
        check("providerStatementChecked", "The provider's transaction list has been checked"),
        radio("paymentFound", "Was the money actually taken?", ["true", "false"]),
        text("matchedTransactionRef", "Matched transaction reference", required=False, maxlen=40,
             row="Row_invest", columns=6),
        num("amountTaken", "Amount taken", required=False, mn=0, row="Row_invest", columns=6),
        area("investigationNotes", "What was found"),
        text("investigatedBy", "Investigated by", maxlen=80),
    ])

FORMS["decide-refund"] = _form(
    "Refunds are a Finance decision. Clinical staff may explain the treatment decision, but only "
    "someone with financial authority approves the money.",
    [
        radio("refundDecision", "Refund decision",
              ["FULL_REFUND", "PARTIAL_REFUND", "NO_REFUND"]),
        num("refundAmount", "Refund amount", required=False, mn=0),
        num("paidAmount", "Amount originally taken", required=False, mn=0),
        area("refundReason", "Reason for the decision"),
        sel("refundMethod", "Refund method",
            ["Original card", "Bank transfer", "Credit on account"], required=False),
        date("decisionDate", "Decision date"),
        text("decidedBy", "Decided by", maxlen=80),
    ])

FORMS["review-financial-impact"] = _form(
    "Used when a treatment change touches a charge, a funding approval or a payment already taken.",
    [
        radio("impactAction", "What does the change need?",
              ["ADJUST_CHARGE", "REFUND_REQUIRED", "NO_CHANGE"]),
        num("impactAmount", "Amount affected", required=False, mn=0),
        area("impactNotes", "What was reviewed"),
        text("reviewedBy", "Reviewed by", maxlen=80),
    ])

FORMS["answer-financial-enquiry"] = _form(
    "Payment and funding enquiries passed over by the call handling team.",
    [
        text("enquiryRef", "Enquiry reference", maxlen=40),
        area("enquirySummary", "What is the patient asking about?", required=False, rows=3),
        area("responseGiven", "Answer given"),
        radio("resolvedNow", "Is the enquiry resolved?", ["true", "false"]),
        text("answeredBy", "Answered by", maxlen=80),
    ])

# ------------------------------------------------------------ nurse spec ---
FORMS["triage-clinical-enquiry"] = _form(
    "Clinical enquiries are answered by a qualified clinical professional. Call handlers never diagnose "
    "or interpret results, so nothing reaches this form until it has been routed here.",
    [
        text("enquiryRef", "Enquiry reference", maxlen=40),
        radio("needsConsultantReview", "Does a Consultant need to look at this?", ["true", "false"]),
        area("clinicalAssessment", "Clinical assessment"),
        area("clinicalAdviceSummary", "Advice given to the patient", required=False, rows=4),
        sel("priority", "Priority", ["Urgent", "Same day", "Routine"]),
        text("advisedBy", "Advised by", maxlen=80),
    ])

# ---------------------------------------------------------- call handling ---
FORMS["log-enquiry"] = _form(
    "Every enquiry gets a record, a category and a priority before it goes anywhere.",
    [
        text("enquiryRef", "Enquiry reference", minlen=3, maxlen=40),
        radio("enquiryChannel", "How did the enquiry come in?",
              ["Telephone", "Email", "Post", "In person"]),
        radio("enquiryCategory", "What kind of enquiry is it?",
              ["ADMINISTRATIVE", "FINANCIAL", "CLINICAL"],
              "Clinical enquiries go to a qualified clinical professional. Call handlers do not advise."),
        radio("enquiryPriority", "Priority", ["URGENT", "ROUTINE"],
              "Urgent clinical concerns are flagged immediately. The full urgency rules are still being agreed."),
        area("enquirySummary", "What is the enquiry about?"),
        text("callerName", "Caller name", required=False, maxlen=80),
        text("callerContact", "Contact number or email", required=False, maxlen=120),
        text("loggedBy", "Logged by", maxlen=80),
    ])

FORMS["record-telephone-contact-attempt"] = _form(
    "Short notice appointments also need a telephone call. Every attempt is recorded, including the "
    "wrong number and the patient who wants a different date.",
    [
        radio("contactOutcome", "What happened on the call?",
              ["REACHED", "NO_ANSWER", "WRONG_NUMBER", "WANTS_ALTERNATIVE"],
              "Record the attempt even when nobody answered - the pattern matters."),
        num("contactAttempts", "Attempt number", mn=1, mx=3,
            desc="Three attempts then the bookings team is told the patient could not be reached."),
        check("patientRequestsAlternative", "The patient asked for a different appointment"),
        date("preferredAlternativeDate", "Date the patient asked for", required=False),
        area("contactNotes", "Notes", required=False, rows=3),
        text("attemptedBy", "Attempted by", maxlen=80),
    ])

# ------------------------------------------------------ pathway coordinators ---
FORMS["review-outstanding-correspondence"] = _form(
    "Weekly review of clinic letters that have slipped past the seven day target.",
    [
        num("letterOverdueDays", "Worst case days outstanding", mn=0, mx=365,
            desc="Seven days or less is on target. Over thirty days goes to the Administrative Manager, "
                 "over ninety goes higher."),
        num("outstandingLettersReviewed", "Letters reviewed", required=False, mn=0),
        radio("reminderAction", "Action for this batch",
              ["SEND_REMINDER", "ESCALATE_MANAGER", "ESCALATE_HIGHER"]),
        area("reasonForDelay", "Any valid reason recorded for the delay", required=False, rows=3),
        text("reviewedBy", "Reviewed by", maxlen=80),
    ])

FORMS["review-booking-delay"] = _form(
    "Used when a booking could not be made inside the clinically requested window, or is still pending "
    "on an external service.",
    [
        radio("delayAction", "What does this delay need?",
              ["CLINICAL_REVIEW", "KEEP_PATIENT_INFORMED", "WIDEN_SEARCH"]),
        sel("delayReason", "Main reason for the delay",
            ["No clinic capacity", "External service unavailable", "Funding not approved",
             "Patient unavailable", "Other"]),
        num("daysDelayed", "Days delayed so far", required=False, mn=0),
        check("patientInformed", "The patient has been kept informed"),
        area("notes", "Notes", required=False, rows=3),
        text("reviewedBy", "Reviewed by", maxlen=80),
    ])

# ------------------------------------------------- administrative management ---
FORMS["contact-consultant-overdue-letter"] = _form(
    "A letter outstanding for more than a month is taken up with the responsible Consultant directly.",
    [
        text("letterRef", "Letter reference", required=False, maxlen=40),
        text("consultantName", "Responsible Consultant", maxlen=80),
        radio("contactMethod", "How were they contacted?", ["Email", "Telephone", "In person"]),
        radio("letterNowCompleted", "Has the letter been completed?", ["true", "false"]),
        date("expectedCompletionDate", "Expected completion date", required=False),
        area("escalationNotes", "What was agreed?"),
        date("contactedOn", "Date of contact", required=False),
        text("contactedBy", "Contacted by", maxlen=80),
    ])

FORMS["refer-to-higher-management"] = _form(
    "Anything still outstanding after three months leaves the pathway team and goes up.",
    [
        text("letterRef", "Letter reference", required=False, maxlen=40),
        num("monthsOutstanding", "Months outstanding", mn=1, mx=60),
        sel("higherManagementTeam", "Which team?",
            ["Clinical directorate", "Medical director", "Executive team"]),
        area("reasonForEscalation", "Why is this being escalated?"),
        date("referralDate", "Date of referral"),
        text("referredBy", "Referred by", maxlen=80),
    ])

FORMS["answer-administrative-enquiry"] = _form(
    "Shared by the call handling team and the outpatient bookings team so an enquiry record looks the "
    "same whichever team answers it.",
    [
        text("enquiryRef", "Enquiry reference", maxlen=40),
        sel("enquiryCategory", "Type of administrative enquiry",
            ["Appointment date, time or location", "Referral progress", "Clinic letter query",
             "Transport or access", "Other"]),
        area("responseGiven", "Answer given"),
        radio("answerableNow", "Answered with the information you have?", ["true", "false"]),
        sel("handedToTeam", "If not, which team has it now?",
            ["Outpatient bookings", "Medical secretaries", "Pathway coordinators", "Finance"],
            required=False),
        text("answeredBy", "Answered by", maxlen=80),
    ])
