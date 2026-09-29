"""
Model specification for the Hospital Patient Referral, Treatment and
Administration System (UFCEP6-0-3).

One collaboration, one diagram. Every team that owns work in the case study gets
its own pool, external services get their own pool, and every hand-off between
them is an explicit message flow backed by a message throw / catch pair so the
model actually runs on the Zeebe engine.

Correlation keys are worth a note. Camunda 8 allows only one active instance per
process definition per correlation key, so a plain patient reference would let
the Consultant pool exist only once at a time. Every hand-off therefore appends
a short purpose tag ("-referral-review", "-payment-2", ...). That keeps
concurrent work for one patient possible and gives us duplicate suppression for
free - a repeated hand-off for the same purpose is simply not correlated twice.
"""

from bpmn_builder import Builder

MODEL_NAME = "Hospital Patient Referral, Treatment and Administration System"


def K(tag):
    """Correlation key expression: patient reference plus a purpose tag."""
    return '=patientRef + "-%s"' % tag


def build():
    b = Builder("Collaboration_HospitalPatientPathway")

    # ------------------------------------------------------------------ pools
    p_ref = b.pool("P_ReferringOrg", "Referring Organisation (GP surgery or other hospital)")
    p_pat = b.pool("P_Patient", "Patient or authorised representative")
    p_sec = b.pool("P_MedicalSecretaries", "Medical Secretaries",
                   process_id="medical-secretaries", process_name="Medical Secretaries - referral and correspondence administration")
    p_con = b.pool("P_Consultants", "Consultants",
                   process_id="consultants", process_name="Consultants - clinical review, consent and treatment authorisation")
    p_out = b.pool("P_OutpatientBookings", "Outpatient Bookings Team",
                   process_id="outpatient-bookings", process_name="Outpatient Bookings Team - new patient and follow-up appointments")
    p_sch = b.pool("P_ExternalScheduling", "External Scheduling Service")
    p_trt = b.pool("P_TreatmentBookings", "Treatment and Chemotherapy Bookings Team",
                   process_id="treatment-bookings", process_name="Treatment and Chemotherapy Bookings Team")
    p_ext = b.pool("P_ExternalClinicalServices", "External Treatment, Laboratory and Imaging Services")
    p_fin = b.pool("P_Finance", "Finance Team",
                   process_id="finance-team", process_name="Finance Team - funding, payment and refunds")
    p_pay = b.pool("P_PaymentProvider", "External Payment Service Provider")
    p_cor = b.pool("P_Correspondence", "External Correspondence Service")
    p_cns = b.pool("P_ClinicalNurseSpecialist", "Clinical Nurse Specialist Team",
                   process_id="clinical-nurse-specialists", process_name="Clinical Nurse Specialist Team - clinical advice and support")
    p_call = b.pool("P_CallHandling", "Call Handling Team",
                    process_id="call-handling", process_name="Call Handling Team - enquiry logging, triage and routing")
    p_pcw = b.pool("P_PathwayCoordinators", "Patient Pathway Coordinators",
                   process_id="patient-pathway-coordinators", process_name="Patient Pathway Coordinators - pathway monitoring and overdue correspondence")
    p_adm = b.pool("P_AdministrativeManagement", "Administrative Management Team",
                   process_id="administrative-management", process_name="Administrative Management Team - escalation handling")

    # ------------------------------------------------------------------ errors
    for code, name in [
        ("REFERRAL_PACK_UNREADABLE", "Referral documents could not be read"),
        ("REFERRAL_PACK_INCOMPLETE", "Referral pack failed the document checklist"),
        ("SCHEDULING_SERVICE_UNAVAILABLE", "External scheduling service unavailable"),
        ("CORRESPONDENCE_SERVICE_FAILED", "External correspondence service rejected the job"),
        ("PAYMENT_PROVIDER_UNAVAILABLE", "External payment provider unavailable"),
        ("PAYMENT_CONFIRMATION_LOST", "Payment taken but no confirmation returned"),
        ("EXTERNAL_RESOURCE_UNAVAILABLE", "External treatment or diagnostic resource unavailable"),
        ("TREATMENT_REQUEST_UNAUTHORISED", "Treatment booking request is not authorised"),
        ("CHARGE_CALCULATION_FAILED", "Applicable charge could not be calculated"),
    ]:
        b.error(code, name)

    # =====================================================================
    # Medical Secretaries
    # =====================================================================
    mf1 = "FLOW_SEC_PACK_MISSING"
    p_sec.n("SEC_Start_Referral", "msgstart", "Referral received from GP or other hospital", 0, 0,
            msg=b.msg("referral.received"),
            documentation="Triggered by the referring organisation. Medical Secretaries own intake only; "
                          "they must not judge clinical suitability.")
    p_sec.n("SEC_Task_CheckPack", "utask", "Check referral pack against the document checklist", 1, 0,
            form="check-referral-pack", candidate_groups="medical-secretaries",
            documentation="Captures what was received and what is missing. The task never records a view on "
                          "whether the referral is clinically appropriate.")
    p_sec.n("SEC_Auto_ValidateDocuments", "stask", "Validate supporting documents and flag missing items", 2, 0,
            type="referral.check-supporting-documents", retries=3,
            documentation="Reads the document list, matches it against the speciality checklist and returns "
                          "referralPackComplete plus the missingDocuments collection.")
    p_sec.n("SEC_GW_PackComplete", "xg", "Is the referral pack complete?", 3, 0)
    p_sec.n("SEC_Throw_ReviewRequested", "throw", "Referral to Consultant", 4, 0,
            msg=b.msg("referral.review-requested", K("referral-review")), key=K("referral-review"),
            headers={"messageName": "referral.review-requested", "businessEvent": "REFERRAL_READY_FOR_REVIEW"},
            documentation="Only an authorised Consultant may accept or reject a referral, so the pack is "
                          "handed over without any administrative recommendation attached.")
    p_sec.n("SEC_End_ReviewRequested", "end", "Referral awaiting clinical decision", 5, 0)
    p_sec.n("SEC_Throw_InfoRequested", "throw", "Request the missing information", 3, 1,
            msg=b.msg("referral.info-requested", K("referral-info")), key=K("referral-info"),
            headers={"messageName": "referral.info-requested"},
            documentation="Reached from the completeness gateway and from the unreadable-document error "
                          "boundary, so a corrupted upload follows the same route as a missing document.")
    p_sec.n("SEC_EGW_InfoRequest", "eg", "Waiting for the missing information", 4, 1)
    p_sec.n("SEC_Catch_InfoReceived", "catch", "Information received", 5, 1,
            msg=b.msg("referral.info-received", K("referral-info")),
            documentation="The referral stays open for 14 days. If nothing arrives the referral is closed "
                          "rather than left in limbo.")
    p_sec.n("SEC_Catch_InfoTimeout", "ctimer", "No response after 14 days", 5, 2, timer="P14D")
    p_sec.n("SEC_End_InfoNotReceived", "end", "Referral closed - information not received", 6, 2)
    p_sec.n("SEC_Bnd_DocumentsUnreadable", "bnderror", "Unreadable", 0, 0,
            attach="SEC_Auto_ValidateDocuments", error="REFERRAL_PACK_UNREADABLE")
    p_sec.n("SEC_End_PackIncomplete", "end", "Referral held - checklist not satisfied", 3, 2,
            documentation="Raised when the worker cannot parse the pack at all, for example a corrupt PDF. "
                          "The case sits with the secretaries instead of reaching a clinician.")
    p_sec.n("SEC_Bnd_PackIncomplete", "bnderror", "Incomplete", 0, 0,
            attach="SEC_Auto_ValidateDocuments", error="REFERRAL_PACK_INCOMPLETE")

    p_sec.f("SEC_Start_Referral", "SEC_Task_CheckPack")
    p_sec.f("SEC_Task_CheckPack", "SEC_Auto_ValidateDocuments")
    p_sec.mf_in("P_ReferringOrg", "P_ReferringOrg", "SEC_Start_Referral", "Referral arrives from the GP or hospital")
    p_sec.mf_in("P_ReferringOrg", "P_ReferringOrg", "SEC_Catch_InfoReceived", "Missing information sent on")
    p_sec.mf("SEC_Throw_InfoRequested", "P_ReferringOrg", "P_ReferringOrg")
    p_sec.f("SEC_Auto_ValidateDocuments", "SEC_GW_PackComplete")
    p_sec.f("SEC_GW_PackComplete", "SEC_Throw_ReviewRequested",
            cond='=referralPackComplete = true', name="All expected documents present")
    p_sec.f("SEC_GW_PackComplete", "SEC_Throw_InfoRequested", default=True,
            name="Something is missing")
    p_sec.f("SEC_Throw_ReviewRequested", "SEC_End_ReviewRequested")
    p_sec.f("SEC_Throw_InfoRequested", "SEC_EGW_InfoRequest")
    p_sec.f("SEC_EGW_InfoRequest", "SEC_Catch_InfoReceived")
    p_sec.f("SEC_EGW_InfoRequest", "SEC_Catch_InfoTimeout")
    p_sec.f("SEC_Catch_InfoReceived", "SEC_Task_CheckPack", name="Re-check the pack")
    p_sec.f("SEC_Catch_InfoTimeout", "SEC_End_InfoNotReceived")
    p_sec.f("SEC_Bnd_DocumentsUnreadable", "SEC_End_PackIncomplete")
    p_sec.f("SEC_Bnd_PackIncomplete", "SEC_End_PackIncomplete")

    # referral outcome returned by the Consultant
    p_sec.n("SEC_Start_Outcome", "msgstart", "Referral outcome returned by the Consultant", 0, 3,
            msg=b.msg("referral.outcome-returned"))
    p_sec.n("SEC_Task_NotifyReferrer", "utask", "Record the decision and notify the referring organisation", 1, 3,
            form="notify-referrer-outcome", candidate_groups="medical-secretaries")
    p_sec.n("SEC_Throw_OutcomeToReferrer", "throw", "Outcome to the referrer", 2, 3,
            msg=b.msg("referral.outcome-sent", K("referral-outcome")), key=K("referral-outcome"),
            headers={"messageName": "referral.outcome-sent"})
    p_sec.n("SEC_End_OutcomeRecorded", "end", "Outcome recorded and referrer informed", 3, 3)
    p_sec.f("SEC_Start_Outcome", "SEC_Task_NotifyReferrer")
    p_sec.f("SEC_Task_NotifyReferrer", "SEC_Throw_OutcomeToReferrer")
    p_sec.f("SEC_Throw_OutcomeToReferrer", "SEC_End_OutcomeRecorded")
    p_sec.mf("SEC_Throw_OutcomeToReferrer", "P_ReferringOrg", "P_ReferringOrg")

    # clinic letter administration
    p_sec.n("SEC_Start_LetterApproved", "msgstart", "Clinic letter approved by the Consultant", 0, 4,
            msg=b.msg("clinic.letter-approved"))
    p_sec.n("SEC_Task_ProcessLetter", "utask", "Check and process the approved clinic letter", 1, 4,
            form="process-clinic-letter", candidate_groups="medical-secretaries",
            documentation="Administrative checks only. Formatting and administrative errors may be corrected; "
                          "the clinical meaning must not be altered.")
    p_sec.n("SEC_GW_LetterCheck", "xg", "Does the letter need a clinical correction?", 2, 4)
    p_sec.n("SEC_Throw_ClinicalError", "throw", "Return the letter to the Consultant", 3, 5,
            msg=b.msg("letter.clinical-error-returned", K("clinic-letter")), key=K("clinic-letter"),
            headers={"messageName": "letter.clinical-error-returned"})
    p_sec.n("SEC_End_LetterReturned", "end", "Returned for amendment", 4, 5)
    p_sec.n("SEC_Auto_PrepareDispatch", "stask", "Prepare the letter for distribution", 3, 4,
            type="correspondence.prepare-dispatch", retries=3,
            documentation="Resolves the recipient list and the channel each recipient prefers. No clinical "
                          "content is changed here.")
    p_sec.n("SEC_Auto_DispatchLetter", "stask", "Send the letter through the correspondence service", 4, 4,
            type="correspondence.dispatch-letter", retries=3,
            documentation="Outbound call to the external correspondence service. The supplier is modelled "
                          "as a black box pool - only the boundary and its failure modes matter here.")
    p_sec.n("SEC_Bnd_DispatchFailed", "bnderror", "Correspondence service rejected the job", 0, 0,
            attach="SEC_Auto_DispatchLetter", error="CORRESPONDENCE_SERVICE_FAILED")
    p_sec.n("SEC_Task_ResolveDispatch", "utask", "Resolve the distribution problem and pick another channel", 5, 5,
            form="resolve-dispatch-problem", candidate_groups="medical-secretaries")
    p_sec.n("SEC_End_LetterFiled", "end", "Letter filed with distribution evidence", 5, 4)

    p_sec.f("SEC_Start_LetterApproved", "SEC_Task_ProcessLetter")
    p_sec.f("SEC_Task_ProcessLetter", "SEC_GW_LetterCheck")
    p_sec.f("SEC_GW_LetterCheck", "SEC_Throw_ClinicalError",
            cond='=clinicalErrorSuspected = "true"', name="Suspected clinical error")
    p_sec.f("SEC_GW_LetterCheck", "SEC_Auto_PrepareDispatch", default=True, name="Administrative checks passed")
    p_sec.f("SEC_Throw_ClinicalError", "SEC_End_LetterReturned")
    p_sec.f("SEC_Auto_PrepareDispatch", "SEC_Auto_DispatchLetter")
    p_sec.f("SEC_Auto_DispatchLetter", "SEC_End_LetterFiled")
    p_sec.f("SEC_Bnd_DispatchFailed", "SEC_Task_ResolveDispatch")
    p_sec.f("SEC_Task_ResolveDispatch", "SEC_Auto_PrepareDispatch", name="Re-attempt on a working channel")
    p_sec.mf("SEC_Auto_DispatchLetter", "P_Correspondence", "P_Correspondence")

    # =====================================================================
    # Consultants
    # =====================================================================
    p_con.n("CON_Start_Review", "msgstart", "Referral waiting for clinical review", 0, 0,
            msg=b.msg("referral.review-requested"))
    p_con.n("CON_Task_ReviewReferral", "utask", "Review the referral and record the clinical decision", 1, 0,
            form="review-referral", candidate_groups="consultants",
            documentation="Accept, reject, redirect or ask for more information. The reason and the deciding "
                          "clinician are recorded for audit and cannot be edited afterwards.")
    p_con.n("CON_Auto_AuditDecision", "stask", "Write the clinical decision to the audit trail", 2, 0,
            type="audit.record-clinical-decision", retries=3,
            documentation="Immutable record of who decided what, when and why.")
    p_con.n("CON_GW_Decision", "xg", "What is the clinical decision?", 3, 0)
    p_con.n("CON_Throw_Accepted", "throw", "Referral accepted", 4, 0,
            msg=b.msg("referral.accepted", K("referral-accepted")), key=K("referral-accepted"),
            headers={"messageName": "referral.accepted"},
            documentation="A new patient appointment may only be arranged after an authorised Consultant has "
                          "accepted the referral.")
    p_con.n("CON_End_Accepted", "end", "Referral accepted", 5, 0)
    p_con.n("CON_Throw_Rejected", "throw", "Referral rejected", 4, 1,
            msg=b.msg("referral.outcome-returned", K("referral-outcome")), key=K("referral-outcome"),
            inputs=[('="REJECTED"', "referralOutcome")],
            headers={"messageName": "referral.outcome-returned"})
    p_con.n("CON_Throw_Redirected", "throw", "Referral redirected", 4, 2,
            msg=b.msg("referral.outcome-returned", K("referral-outcome")), key=K("referral-outcome"),
            inputs=[('="REDIRECTED"', "referralOutcome")],
            headers={"messageName": "referral.outcome-returned"})
    p_con.n("CON_Throw_MoreInfoNeeded", "throw", "Further clinical information requested", 4, 3,
            msg=b.msg("referral.outcome-returned", K("referral-outcome")), key=K("referral-outcome"),
            inputs=[('="CLINICAL_INFO_REQUESTED"', "referralOutcome")],
            headers={"messageName": "referral.outcome-returned"})
    p_con.n("CON_End_OutcomeReturned", "end", "Outcome returned to Medical Secretaries", 5, 2)
    p_con.f("CON_Start_Review", "CON_Task_ReviewReferral")
    p_con.f("CON_Task_ReviewReferral", "CON_Auto_AuditDecision")
    p_con.f("CON_Auto_AuditDecision", "CON_GW_Decision")
    p_con.f("CON_GW_Decision", "CON_Throw_Accepted", cond='=clinicalDecision = "ACCEPT"', name="Accept")
    p_con.f("CON_GW_Decision", "CON_Throw_Rejected", cond='=clinicalDecision = "REJECT"', name="Reject")
    p_con.f("CON_GW_Decision", "CON_Throw_Redirected", cond='=clinicalDecision = "REDIRECT"', name="Redirect")
    p_con.f("CON_GW_Decision", "CON_Throw_MoreInfoNeeded", default=True, name="Needs more clinical detail")
    p_con.f("CON_Throw_Accepted", "CON_End_Accepted")
    p_con.f("CON_Throw_Rejected", "CON_End_OutcomeReturned")
    p_con.f("CON_Throw_Redirected", "CON_End_OutcomeReturned")
    p_con.f("CON_Throw_MoreInfoNeeded", "CON_End_OutcomeReturned")
    p_con.mf("CON_Throw_Accepted", "P_OutpatientBookings", "OUT_Start_ReferralAccepted")
    p_con.mf("CON_Throw_Rejected", "P_MedicalSecretaries", "SEC_Start_Outcome")
    p_con.mf("CON_Throw_Redirected", "P_MedicalSecretaries", "SEC_Start_Outcome")
    p_con.mf("CON_Throw_MoreInfoNeeded", "P_MedicalSecretaries", "SEC_Start_Outcome")

    # new patient appointment: consent and treatment authorisation
    p_con.n("CON_Start_AppointmentAttended", "msgstart", "Patient attended the new patient appointment", 0, 5,
            msg=b.msg("appointment.attended"))
    p_con.n("CON_Task_RecordConsent", "utask", "Record consent and complete the treatment booking request", 1, 5,
            form="record-consent-and-treatment-request", candidate_groups="consultants",
            documentation="The Consultant explains the options, records whether the patient agrees to proceed "
                          "and, if so, completes the treatment booking request in full.")
    p_con.n("CON_GW_ConsentGiven", "xg", "Has the patient agreed to proceed?", 2, 5)
    p_con.n("CON_Auto_AuthoriseRequest", "stask", "Authorise the treatment booking request", 3, 5,
            type="treatment.authorise-request", retries=3,
            documentation="Stamps the request with the authorising clinician. Administrative teams cannot "
                          "process a request that has not been through this step.")
    p_con.n("CON_Throw_BookingRequested", "throw", "Authorised treatment booking request issued", 4, 5,
            msg=b.msg("treatment.booking-requested", K("treatment-booking")), key=K("treatment-booking"),
            headers={"messageName": "treatment.booking-requested"})
    p_con.n("CON_End_BookingRequested", "end", "Booking request issued", 5, 5)
    p_con.n("CON_Throw_TreatmentDeclined", "throw", "Patient declined treatment at this time", 3, 6,
            msg=b.msg("treatment.declined", K("treatment-declined")), key=K("treatment-declined"),
            headers={"messageName": "treatment.declined"})
    p_con.n("CON_End_TreatmentDeclined", "end", "Declined - pathway reviewed", 4, 6)
    p_con.f("CON_Start_AppointmentAttended", "CON_Task_RecordConsent")
    p_con.f("CON_Task_RecordConsent", "CON_GW_ConsentGiven")
    p_con.f("CON_GW_ConsentGiven", "CON_Auto_AuthoriseRequest", cond='=consentGiven = "true"', name="Consent recorded")
    p_con.f("CON_GW_ConsentGiven", "CON_Throw_TreatmentDeclined", default=True, name="Not proceeding")
    p_con.f("CON_Auto_AuthoriseRequest", "CON_Throw_BookingRequested")
    p_con.f("CON_Throw_BookingRequested", "CON_End_BookingRequested")
    p_con.f("CON_Throw_TreatmentDeclined", "CON_End_TreatmentDeclined")
    p_con.mf("CON_Throw_BookingRequested", "P_TreatmentBookings", "TRT_Start_BookingRequest")
    p_con.mf("CON_Throw_TreatmentDeclined", "P_OutpatientBookings", "OUT_Start_TreatmentDeclined")

    # chemotherapy cycle review
    p_con.n("CON_Start_CycleReview", "msgstart", "Chemotherapy cycle review requested", 0, 7,
            msg=b.msg("chemotherapy.review-requested"))
    p_con.n("CON_Task_ReviewCycle", "utask", "Review blood results and decide on the next cycle", 1, 7,
            form="review-chemotherapy-cycle", candidate_groups="consultants",
            documentation="Clinical decision only. The bookings, finance and administrative teams cannot make "
                          "or change this call.")
    p_con.n("CON_Auto_AuditCycle", "stask", "Record the cycle review decision", 2, 7,
            type="audit.record-clinical-decision", retries=3)
    p_con.n("CON_GW_CycleOutcome", "xg", "Is the patient fit to continue?", 3, 7)
    p_con.n("CON_Throw_CycleApproved", "throw", "Continue with the next cycle", 4, 7,
            msg=b.msg("chemotherapy.cycle-approved", K("chemotherapy-cycle")), key=K("chemotherapy-cycle"),
            headers={"messageName": "chemotherapy.cycle-approved"})
    p_con.n("CON_End_CycleApproved", "end", "Next cycle authorised", 5, 7)
    p_con.n("CON_Throw_CycleDelayed", "throw", "Delay the next cycle", 4, 8,
            msg=b.msg("chemotherapy.cycle-delayed", K("chemotherapy-cycle")), key=K("chemotherapy-cycle"),
            headers={"messageName": "chemotherapy.cycle-delayed"})
    p_con.n("CON_End_CycleDelayed", "end", "Cycle delayed for clinical reasons", 5, 8)
    p_con.n("CON_Throw_PlanChanged", "throw", "Change the treatment plan", 4, 9,
            msg=b.msg("treatment.modification-requested", K("treatment-modification")), key=K("treatment-modification"),
            headers={"messageName": "treatment.modification-requested"})
    p_con.n("CON_End_PlanChanged", "end", "Treatment change raised for authorisation", 5, 9)
    p_con.f("CON_Start_CycleReview", "CON_Task_ReviewCycle")
    p_con.f("CON_Task_ReviewCycle", "CON_Auto_AuditCycle")
    p_con.f("CON_Auto_AuditCycle", "CON_GW_CycleOutcome")
    p_con.f("CON_GW_CycleOutcome", "CON_Throw_CycleApproved", cond='=cycleReviewOutcome = "FIT_TO_CONTINUE"', name="Fit to continue")
    p_con.f("CON_GW_CycleOutcome", "CON_Throw_CycleDelayed", cond='=cycleReviewOutcome = "DELAY"', name="Delay")
    p_con.f("CON_GW_CycleOutcome", "CON_Throw_PlanChanged", default=True, name="Change the plan")
    p_con.f("CON_Throw_CycleApproved", "CON_End_CycleApproved")
    p_con.f("CON_Throw_CycleDelayed", "CON_End_CycleDelayed")
    p_con.f("CON_Throw_PlanChanged", "CON_End_PlanChanged")
    p_con.mf("CON_Throw_CycleApproved", "P_TreatmentBookings", "TRT_Start_CycleApproved")
    p_con.mf("CON_Throw_CycleDelayed", "P_TreatmentBookings", "TRT_Start_CycleDelayed")
    p_con.mf("CON_Throw_PlanChanged", "P_TreatmentBookings", "TRT_Start_Modification")

    # treatment modification authorisation
    p_con.n("CON_Start_Modification", "msgstart", "Treatment change raised", 0, 10,
            msg=b.msg("treatment.modification-requested"))
    p_con.n("CON_Task_AuthoriseModification", "utask", "Authorise the treatment modification", 1, 10,
            form="authorise-treatment-modification", candidate_groups="consultants",
            documentation="A change requested only by email or telephone is not processed. It has to be "
                          "formally authorised here so it stays traceable.")
    p_con.n("CON_GW_ModificationUrgent", "xg", "Is this an urgent patient-safety change?", 2, 10)
    p_con.n("CON_Throw_ModificationUrgent", "throw", "Urgent change authorised", 3, 10,
            msg=b.msg("treatment.modification-authorised", K("treatment-modification")), key=K("treatment-modification"),
            inputs=[("=true", "modificationUrgent")],
            headers={"messageName": "treatment.modification-authorised"})
    p_con.n("CON_Throw_ModificationRoutine", "throw", "Treatment change authorised", 3, 11,
            msg=b.msg("treatment.modification-authorised", K("treatment-modification")), key=K("treatment-modification"),
            inputs=[("=false", "modificationUrgent")],
            headers={"messageName": "treatment.modification-authorised"})
    p_con.n("CON_Throw_ModificationFinance", "throw", "Financial impact to Finance", 4, 10,
            msg=b.msg("finance.impact-review-requested", K("finance-impact")), key=K("finance-impact"),
            headers={"messageName": "finance.impact-review-requested"})
    p_con.n("CON_End_Modification", "end", "Change applied", 5, 10)
    p_con.f("CON_Start_Modification", "CON_Task_AuthoriseModification")
    p_con.f("CON_Task_AuthoriseModification", "CON_GW_ModificationUrgent")
    p_con.f("CON_GW_ModificationUrgent", "CON_Throw_ModificationUrgent", cond='=modificationUrgent = "true"',
            name="Patient safety - act now")
    p_con.f("CON_GW_ModificationUrgent", "CON_Throw_ModificationRoutine", default=True, name="Normal change")
    p_con.f("CON_Throw_ModificationRoutine", "CON_End_Modification")
    p_con.f("CON_Throw_ModificationUrgent", "CON_Throw_ModificationFinance")
    p_con.f("CON_Throw_ModificationFinance", "CON_End_Modification")
    p_con.mf("CON_Throw_ModificationUrgent", "P_TreatmentBookings", "TRT_Start_ModificationAuthorised")
    p_con.mf("CON_Throw_ModificationRoutine", "P_TreatmentBookings", "TRT_Start_ModificationAuthorised")
    p_con.mf("CON_Throw_ModificationFinance", "P_Finance", "FIN_Start_ImpactReview")

    # clinic letter drafting and approval
    p_con.n("CON_Start_LetterDraft", "msgstart", "Clinic letter to be written", 0, 12,
            msg=b.msg("clinic.letter-draft-required"))
    p_con.n("CON_Task_DraftLetter", "utask", "Draft and approve the clinic letter", 1, 12,
            form="draft-clinic-letter", candidate_groups="consultants",
            documentation="The Consultant owns the clinical content and signs it off. The seven day target "
                          "starts from the appointment date, not from when drafting begins.")
    p_con.n("CON_Bnd_LetterOverdue", "bndtimer", "Day 7", 0, 0,
            attach="CON_Task_DraftLetter", timer="P7D", non_interrupting=True)
    p_con.n("CON_Throw_LetterOverdue", "throw", "Flag the letter as delayed", 2, 13,
            msg=b.msg("letter.overdue-flagged", K("clinic-letter")), key=K("clinic-letter"),
            headers={"messageName": "letter.overdue-flagged"},
            documentation="Reaching the pathway monitoring queue, not a blocking reminder, so drafting continues.")
    p_con.n("CON_End_LetterOverdue", "end", "Letter flagged for pathway monitoring", 3, 13)
    p_con.n("CON_GW_LetterApproved", "xg", "Has the Consultant approved the letter?", 2, 12)
    p_con.n("CON_Throw_LetterApproved", "throw", "Clinic letter approved", 3, 12,
            msg=b.msg("clinic.letter-approved", K("clinic-letter")), key=K("clinic-letter"),
            headers={"messageName": "clinic.letter-approved"})
    p_con.n("CON_End_LetterApproved", "end", "Letter released to Medical Secretaries", 4, 12)
    p_con.n("CON_Bnd_LetterReminder", "bndmsg", "Reminder", 0, 0,
            attach="CON_Task_DraftLetter", msg=b.msg("letter.reminder", K("letter-reminder")),
            non_interrupting=True,
            documentation="The reminder lands on the drafting task without interrupting it, and repeated "
                          "reminders stop once the letter has been approved.")
    p_con.n("CON_Auto_RecordReminder", "stask", "Record the reminder against the letter", 1, 4,
            type="letter.record-reminder", retries=3)
    p_con.n("CON_End_ReminderRecorded", "end", "Reminder recorded", 2, 4)
    p_con.f("CON_Bnd_LetterReminder", "CON_Auto_RecordReminder")
    p_con.f("CON_Auto_RecordReminder", "CON_End_ReminderRecorded")
    p_con.f("CON_Start_LetterDraft", "CON_Task_DraftLetter")
    p_con.f("CON_Task_DraftLetter", "CON_GW_LetterApproved")
    p_con.f("CON_GW_LetterApproved", "CON_Throw_LetterApproved", cond='=letterApproved = "true"', name="Approved")
    p_con.f("CON_GW_LetterApproved", "CON_Task_DraftLetter", default=True, name="Still in progress")
    p_con.f("CON_Bnd_LetterOverdue", "CON_Throw_LetterOverdue")
    p_con.f("CON_Throw_LetterOverdue", "CON_End_LetterOverdue")
    p_con.f("CON_Throw_LetterApproved", "CON_End_LetterApproved")
    p_con.mf("CON_Throw_LetterApproved", "P_MedicalSecretaries", "SEC_Start_LetterApproved")
    p_con.mf("CON_Throw_LetterOverdue", "P_PathwayCoordinators", "PCW_Start_LetterOverdue")

    # letter returned for clinical correction
    p_con.n("CON_Start_LetterCorrection", "msgstart", "Letter returned for clinical correction", 0, 14,
            msg=b.msg("letter.clinical-error-returned"))
    p_con.n("CON_Task_CorrectLetter", "utask", "Correct and re-approve the clinic letter", 1, 14,
            form="correct-clinic-letter", candidate_groups="consultants")
    p_con.n("CON_Throw_LetterReapproved", "throw", "Corrected letter approved", 2, 14,
            msg=b.msg("clinic.letter-approved", K("clinic-letter")), key=K("clinic-letter"),
            headers={"messageName": "clinic.letter-approved"})
    p_con.n("CON_End_LetterReapproved", "end", "Corrected letter released", 3, 14)
    p_con.f("CON_Start_LetterCorrection", "CON_Task_CorrectLetter")
    p_con.f("CON_Task_CorrectLetter", "CON_Throw_LetterReapproved")
    p_con.f("CON_Throw_LetterReapproved", "CON_End_LetterReapproved")
    p_con.mf("CON_Throw_LetterReapproved", "P_MedicalSecretaries", "SEC_Start_LetterApproved")

    # urgent treatment without confirmed payment
    p_con.n("CON_Start_UrgencyAuthorisation", "msgstart", "Urgent treatment authorisation requested", 0, 15,
            msg=b.msg("treatment.urgency-authorisation-requested"))
    p_con.n("CON_Task_AuthoriseUrgentTreatment", "utask",
            "Authorise urgent treatment without confirmed payment", 1, 15,
            form="authorise-urgent-treatment", candidate_groups="consultants",
            documentation="Only a clinician may take this call. The clinical reason for proceeding is recorded "
                          "and the case is passed to Finance to resolve afterwards.")
    p_con.n("CON_Throw_UrgencyDecision", "throw", "Urgency decision returned", 2, 15,
            msg=b.msg("treatment.urgency-authorisation-result", K("urgency-authorisation")),
            key=K("urgency-authorisation"), headers={"messageName": "treatment.urgency-authorisation-result"})
    p_con.n("CON_End_UrgencyDecision", "end", "Urgent treatment decision recorded", 3, 15)
    p_con.f("CON_Start_UrgencyAuthorisation", "CON_Task_AuthoriseUrgentTreatment")
    p_con.f("CON_Task_AuthoriseUrgentTreatment", "CON_Throw_UrgencyDecision")
    p_con.f("CON_Throw_UrgencyDecision", "CON_End_UrgencyDecision")
    p_con.mf("CON_Throw_UrgencyDecision", "P_TreatmentBookings", "TRT_Catch_UrgencyDecision")

    # clinical review asked for by the nurse specialists
    p_con.n("CON_Start_ClinicalReview", "msgstart", "Clinical review requested", 5, 15,
            msg=b.msg("clinical.review-requested"))
    p_con.n("CON_Start_PathwayReview", "msgstart", "Pathway review requested by another team", 5, 16,
            msg=b.msg("pathway.review-requested"))
    p_con.n("CON_Start_ChangeRequest", "msgstart", "Treatment change forwarded", 5, 17,
            msg=b.msg("treatment.change-requested"))
    p_con.n("CON_Task_ClinicalReview", "utask", "Provide the clinical review outcome", 6, 15,
            form="clinical-review-advice", candidate_groups="consultants")
    p_con.n("CON_Throw_ClinicalReviewOutcome", "throw", "Clinical review outcome", 7, 15,
            msg=b.msg("clinical.review-outcome", K("clinical-review")), key=K("clinical-review"),
            headers={"messageName": "clinical.review-outcome"})
    p_con.n("CON_Throw_FollowUpRequested", "throw", "Ask for a follow-up appointment", 8, 15,
            msg=b.msg("follow-up.appointment-requested", K("follow-up")), key=K("follow-up"),
            headers={"messageName": "follow-up.appointment-requested"},
            documentation="Raised when the reviewing clinician wants to see the patient again, with the "
                          "period within which that should happen.")
    p_con.n("CON_End_ClinicalReview", "end", "Clinical review closed", 9, 15)
    p_con.f("CON_Start_ClinicalReview", "CON_Task_ClinicalReview")
    p_con.f("CON_Start_PathwayReview", "CON_Task_ClinicalReview")
    p_con.f("CON_Start_ChangeRequest", "CON_Task_AuthoriseModification")
    p_con.f("CON_Task_ClinicalReview", "CON_Throw_ClinicalReviewOutcome")
    p_con.f("CON_Throw_ClinicalReviewOutcome", "CON_Throw_FollowUpRequested")
    p_con.f("CON_Throw_FollowUpRequested", "CON_End_ClinicalReview")
    p_con.mf("CON_Throw_FollowUpRequested", "P_OutpatientBookings", "OUT_Start_FollowUp")
    p_con.mf("CON_Throw_ClinicalReviewOutcome", "P_ClinicalNurseSpecialist", "CNS_Catch_ClinicalReview")
    p_con.mf_in("P_Patient", "P_Patient", "CON_Start_AppointmentAttended", "Patient attends the appointment")

    # =====================================================================
    # Outpatient Bookings Team
    # =====================================================================
    p_out.n("OUT_Start_ReferralAccepted", "msgstart", "Referral accepted - to book", 0, 0,
            msg=b.msg("referral.accepted"))
    p_out.n("OUT_Auto_CheckPriority", "stask", "Work out priority, timeframe and contact rule", 1, 0,
            type="booking.check-priority-and-contact-rule", retries=3,
            documentation="Applies the two week rule: an appointment inside the next fortnight also needs a "
                          "telephone call, anything further out is letter only.")
    p_out.n("OUT_Auto_FindSlots", "stask", "Search the external scheduling service for appointments", 2, 0,
            type="scheduling.find-appointment-slots", retries=3,
            documentation="Outbound call to the scheduling supplier. The supplier itself is a black box - "
                          "the hospital models the boundary, not their internals.")
    p_out.n("OUT_Bnd_SchedulingUnavailable", "bnderror", "Service down", 0, 0,
            attach="OUT_Auto_FindSlots", error="SCHEDULING_SERVICE_UNAVAILABLE",
            documentation="Transient failures are retried first. Once the worker gives up, the booking gap "
                          "is handled deliberately instead of the request disappearing.")
    p_out.n("OUT_GW_SlotsFound", "xg", "Did the service return anything usable?", 3, 0)
    p_out.n("OUT_Task_ChooseSlot", "utask", "Choose and confirm the appointment", 4, 0,
            form="choose-appointment-slot", candidate_groups="outpatient-bookings",
            documentation="Records the slot chosen, the clinic location and any access requirement the "
                          "patient has told us about.")
    p_out.n("OUT_Auto_CreateAppointment", "stask", "Create the appointment record", 5, 0,
            type="booking.create-appointment", retries=3,
            documentation="Idempotent on the booking reference, so a resubmitted booking never produces a "
                          "second appointment.")
    p_out.n("OUT_GW_NotifyChannels", "ig", "Which contacts does this patient need?", 6, 0)
    p_out.n("OUT_Auto_DispatchAppointmentLetter", "stask", "Send the appointment letter", 7, 0,
            type="correspondence.dispatch-letter", retries=3,
            inputs=[('=["patient"]', "letterRecipients")],
            documentation="Goes to the patient on the channel they asked for. The recipients are set here "
                          "rather than left to the supplier.")
    p_out.n("OUT_Bnd_LetterFailed", "bnderror", "Rejected", 0, 0,
            attach="OUT_Auto_DispatchAppointmentLetter", error="CORRESPONDENCE_SERVICE_FAILED")
    p_out.n("OUT_Task_ChaseLetter", "utask", "Chase the appointment letter", 8, 2,
            form="resolve-dispatch-problem", candidate_groups="outpatient-bookings")
    p_out.n("OUT_Throw_PhoneContact", "throw", "Ask for a telephone call", 7, 3,
            msg=b.msg("appointment.phone-contact-requested", K("phone-contact")), key=K("phone-contact"),
            headers={"messageName": "appointment.phone-contact-requested"})
    p_out.n("OUT_Catch_PhoneContact", "catch", "Contact finished", 8, 3,
            msg=b.msg("appointment.phone-contact-finished", K("phone-contact")))
    p_out.n("OUT_GW_NotifyJoin", "ig", "Patient notification complete", 9, 0)
    p_out.n("OUT_End_AppointmentBooked", "end", "New patient appointment confirmed", 10, 0)
    p_out.n("OUT_Task_ReviewAvailability", "utask", "Decide what to do without a suitable slot", 4, 1,
            form="review-appointment-availability", candidate_groups="outpatient-bookings")
    p_out.n("OUT_GW_AvailabilityAction", "xg", "How should the booking gap be handled?", 5, 1)
    p_out.n("OUT_Throw_NoSlotEscalation", "throw", "Refer the delay to the pathway team", 6, 1,
            msg=b.msg("booking.no-slot-escalation", K("booking-escalation")), key=K("booking-escalation"),
            headers={"messageName": "booking.no-slot-escalation"},
            documentation="Escalated on purpose instead of quietly booking outside the period the "
                          "Consultant asked for.")
    p_out.n("OUT_End_NoSlotEscalated", "end", "Booking gap escalated", 7, 1)

    p_out.f("OUT_Start_ReferralAccepted", "OUT_Auto_CheckPriority")
    p_out.f("OUT_Auto_CheckPriority", "OUT_Auto_FindSlots")
    p_out.f("OUT_Auto_FindSlots", "OUT_GW_SlotsFound")
    p_out.f("OUT_GW_SlotsFound", "OUT_Task_ChooseSlot", cond="=slotCount > 0", name="Options available")
    p_out.f("OUT_GW_SlotsFound", "OUT_Task_ReviewAvailability", default=True, name="Nothing suitable")
    p_out.f("OUT_Bnd_SchedulingUnavailable", "OUT_Task_ReviewAvailability")
    p_out.f("OUT_Task_ChooseSlot", "OUT_Auto_CreateAppointment")
    p_out.f("OUT_Auto_CreateAppointment", "OUT_GW_NotifyChannels")
    p_out.f("OUT_GW_NotifyChannels", "OUT_Auto_DispatchAppointmentLetter", cond="=true", name="Letter always")
    p_out.f("OUT_GW_NotifyChannels", "OUT_Throw_PhoneContact", cond="=requiresPhoneCall = true",
            name="Within two weeks - call as well")
    p_out.f("OUT_Auto_DispatchAppointmentLetter", "OUT_GW_NotifyJoin")
    p_out.f("OUT_Bnd_LetterFailed", "OUT_Task_ChaseLetter")
    p_out.f("OUT_Task_ChaseLetter", "OUT_Auto_DispatchAppointmentLetter", name="Try another channel")
    p_out.f("OUT_Throw_PhoneContact", "OUT_Catch_PhoneContact")
    p_out.f("OUT_Catch_PhoneContact", "OUT_GW_NotifyJoin")
    p_out.f("OUT_GW_NotifyJoin", "OUT_End_AppointmentBooked")
    p_out.f("OUT_Task_ReviewAvailability", "OUT_GW_AvailabilityAction")
    p_out.f("OUT_GW_AvailabilityAction", "OUT_Auto_CheckPriority",
            cond='=availabilityAction = "WIDEN_SEARCH"', name="Search wider")
    p_out.f("OUT_GW_AvailabilityAction", "OUT_Throw_NoSlotEscalation", default=True, name="Escalate")
    p_out.f("OUT_Throw_NoSlotEscalation", "OUT_End_NoSlotEscalated")
    p_out.mf("OUT_Auto_FindSlots", "P_ExternalScheduling", "P_ExternalScheduling")
    p_out.mf("OUT_Auto_DispatchAppointmentLetter", "P_Correspondence", "P_Correspondence")
    p_out.mf("OUT_Throw_PhoneContact", "P_CallHandling", "CALL_Start_PhoneContact")
    p_out.mf("OUT_Throw_NoSlotEscalation", "P_PathwayCoordinators", "PCW_Start_BookingDelay")
    p_out.mf_in("P_Patient", "P_Patient", "OUT_Start_Cancelled", "Patient cancels or does not attend")

    # follow-up appointment
    p_out.n("OUT_Start_FollowUp", "msgstart", "Follow-up appointment requested", 0, 3,
            msg=b.msg("follow-up.appointment-requested"))
    p_out.n("OUT_Auto_FindFollowUpSlots", "stask", "Look for a follow-up slot", 1, 3,
            type="scheduling.find-appointment-slots", retries=3)
    p_out.n("OUT_Bnd_FollowUpNoSlots", "bnderror", "No slot", 0, 0,
            attach="OUT_Auto_FindFollowUpSlots", error="SCHEDULING_SERVICE_UNAVAILABLE")
    p_out.n("OUT_GW_FollowUpSlots", "xg", "Was a follow-up slot found?", 2, 3)
    p_out.n("OUT_Task_ConfirmFollowUp", "utask", "Confirm the follow-up appointment", 3, 3,
            form="confirm-follow-up-appointment", candidate_groups="outpatient-bookings")
    p_out.n("OUT_Auto_CreateFollowUp", "stask", "Create the follow-up appointment", 4, 3,
            type="booking.create-appointment", retries=3)
    p_out.n("OUT_Auto_SendFollowUpLetter", "stask", "Tell the patient about the follow-up", 5, 3,
            type="correspondence.dispatch-letter", retries=3,
            inputs=[('=["patient"]', "letterRecipients")])
    p_out.n("OUT_End_FollowUpBooked", "end", "Follow-up appointment confirmed", 6, 3)
    p_out.n("OUT_Throw_FollowUpEscalation", "throw", "Highlight the follow-up delay", 3, 4,
            msg=b.msg("follow-up.no-slot-escalation", K("followup-escalation")), key=K("followup-escalation"),
            headers={"messageName": "follow-up.no-slot-escalation"})
    p_out.n("OUT_End_FollowUpEscalated", "end", "Follow-up delay with the pathway team", 4, 4)
    p_out.f("OUT_Start_FollowUp", "OUT_Auto_FindFollowUpSlots")
    p_out.f("OUT_Auto_FindFollowUpSlots", "OUT_GW_FollowUpSlots")
    p_out.f("OUT_GW_FollowUpSlots", "OUT_Task_ConfirmFollowUp", cond="=slotCount > 0",
            name="Slot inside the window")
    p_out.f("OUT_GW_FollowUpSlots", "OUT_Throw_FollowUpEscalation", default=True,
            name="Outside the clinical window")
    p_out.f("OUT_Bnd_FollowUpNoSlots", "OUT_Throw_FollowUpEscalation")
    p_out.f("OUT_Task_ConfirmFollowUp", "OUT_Auto_CreateFollowUp")
    p_out.f("OUT_Auto_CreateFollowUp", "OUT_Auto_SendFollowUpLetter")
    p_out.f("OUT_Auto_SendFollowUpLetter", "OUT_End_FollowUpBooked")
    p_out.f("OUT_Throw_FollowUpEscalation", "OUT_End_FollowUpEscalated")
    p_out.mf("OUT_Auto_FindFollowUpSlots", "P_ExternalScheduling", "P_ExternalScheduling")
    p_out.mf("OUT_Auto_SendFollowUpLetter", "P_Correspondence", "P_Correspondence")
    p_out.mf("OUT_Throw_FollowUpEscalation", "P_PathwayCoordinators", "PCW_Start_FollowUpDelay")

    # cancellation, decline and did-not-attend
    p_out.n("OUT_Start_Cancelled", "msgstart", "Cancelled, declined or not attended", 0, 5,
            msg=b.msg("appointment.cancelled-or-dna"))
    p_out.n("OUT_Auto_RecordOutcome", "stask", "Record the appointment outcome", 2, 5,
            type="booking.record-appointment-outcome", retries=3,
            documentation="Captures the outcome, who reported it and when. Administrative staff record it; "
                          "they do not decide whether treatment continues.")
    p_out.n("OUT_Task_DecideNextAction", "utask", "Decide whether another appointment is offered", 1, 5,
            form="decide-cancellation-action", candidate_groups="outpatient-bookings")
    p_out.n("OUT_GW_CancellationAction", "xg", "What happens next?", 3, 5)
    p_out.n("OUT_Throw_ClinicalReviewOfPathway", "throw", "Ask the clinical team to review the pathway", 4, 5,
            msg=b.msg("pathway.review-requested", K("pathway-review")), key=K("pathway-review"),
            headers={"messageName": "pathway.review-requested"})
    p_out.n("OUT_End_PathwayReview", "end", "Pathway review requested", 5, 5)
    p_out.n("OUT_Auto_FindRebookSlots", "stask", "Look for a replacement appointment", 4, 6,
            type="scheduling.find-appointment-slots", retries=3)
    p_out.n("OUT_Bnd_RebookNoSlots", "bnderror", "No slot", 0, 0,
            attach="OUT_Auto_FindRebookSlots", error="SCHEDULING_SERVICE_UNAVAILABLE")
    p_out.n("OUT_End_Reoffered", "end", "Replacement appointment offered", 5, 6)
    p_out.n("OUT_Throw_ReferrerNotified", "throw", "Inform the referring organisation", 4, 7,
            msg=b.msg("referral.outcome-sent", K("referral-outcome")), key=K("referral-outcome"),
            headers={"messageName": "referral.outcome-sent"})
    p_out.n("OUT_Throw_FinanceReview", "throw", "Ask Finance about the payment taken", 5, 7,
            msg=b.msg("refund.required", K("refund")), key=K("refund"),
            headers={"messageName": "refund.required"},
            documentation="Only sent when money has already changed hands. Decisions about continuing "
                          "treatment stay with the clinical team.")
    p_out.n("OUT_End_CancellationHandled", "end", "Cancellation handled", 6, 7)
    p_out.f("OUT_Start_Cancelled", "OUT_Task_DecideNextAction")
    p_out.f("OUT_Task_DecideNextAction", "OUT_Auto_RecordOutcome")
    p_out.f("OUT_Auto_RecordOutcome", "OUT_GW_CancellationAction")
    p_out.f("OUT_GW_CancellationAction", "OUT_Auto_FindRebookSlots",
            cond='=cancellationAction = "REBOOK"', name="Offer another date")
    p_out.f("OUT_GW_CancellationAction", "OUT_Throw_ClinicalReviewOfPathway",
            cond='=cancellationAction = "CLINICAL_REVIEW"', name="Clinical review")
    p_out.f("OUT_GW_CancellationAction", "OUT_Throw_ReferrerNotified", default=True,
            name="Close and inform the referrer")
    p_out.f("OUT_Auto_FindRebookSlots", "OUT_End_Reoffered")
    p_out.f("OUT_Bnd_RebookNoSlots", "OUT_End_CancellationHandled")
    p_out.f("OUT_Throw_ClinicalReviewOfPathway", "OUT_End_PathwayReview")
    p_out.f("OUT_Throw_ReferrerNotified", "OUT_Throw_FinanceReview")
    p_out.f("OUT_Throw_FinanceReview", "OUT_End_CancellationHandled")
    p_out.mf("OUT_Auto_FindRebookSlots", "P_ExternalScheduling", "P_ExternalScheduling")
    p_out.mf("OUT_Throw_ClinicalReviewOfPathway", "P_Consultants", "CON_Start_PathwayReview")
    p_out.mf("OUT_Throw_ReferrerNotified", "P_ReferringOrg", "P_ReferringOrg")
    p_out.mf("OUT_Throw_FinanceReview", "P_Finance", "FIN_Start_Refund")

    # declined treatment reaches the bookings team as a pathway event
    p_out.n("OUT_Start_TreatmentDeclined", "msgstart", "Patient declined treatment", 0, 8,
            msg=b.msg("treatment.declined"))
    p_out.n("OUT_Task_RecordDecline", "utask", "Record the decline and arrange clinical follow-up", 1, 8,
            form="record-treatment-decline", candidate_groups="outpatient-bookings")
    p_out.n("OUT_Throw_DeclineToClinical", "throw", "Decline to clinical team", 2, 8,
            msg=b.msg("pathway.review-requested", K("pathway-review")), key=K("pathway-review"),
            headers={"messageName": "pathway.review-requested"})
    p_out.n("OUT_End_DeclineRecorded", "end", "Decline recorded", 3, 8)
    p_out.f("OUT_Start_TreatmentDeclined", "OUT_Task_RecordDecline")
    p_out.f("OUT_Task_RecordDecline", "OUT_Throw_DeclineToClinical")
    p_out.f("OUT_Throw_DeclineToClinical", "OUT_End_DeclineRecorded")
    p_out.mf("OUT_Throw_DeclineToClinical", "P_Consultants", "CON_Start_PathwayReview")

    # administrative enquiries handed over by the call handling team
    p_out.n("OUT_Start_AdminEnquiry", "msgstart", "Admin enquiry handed over", 0, 9,
            msg=b.msg("enquiry.assigned-admin"))
    p_out.n("OUT_Task_AnswerAdminEnquiry", "utask", "Answer the administrative enquiry", 1, 9,
            form="answer-administrative-enquiry", candidate_groups="outpatient-bookings",
            documentation="The same form the call handlers use, so an enquiry record looks the same "
                          "whichever team picks it up.")
    p_out.n("OUT_Throw_EnquiryAnswered", "throw", "Administrative enquiry answered", 2, 9,
            msg=b.msg("enquiry.resolved", K("enquiry")), key=K("enquiry"),
            headers={"messageName": "enquiry.resolved"})
    p_out.n("OUT_End_EnquiryAnswered", "end", "Enquiry answered", 3, 9)
    p_out.f("OUT_Start_AdminEnquiry", "OUT_Task_AnswerAdminEnquiry")
    p_out.f("OUT_Task_AnswerAdminEnquiry", "OUT_Throw_EnquiryAnswered")
    p_out.f("OUT_Throw_EnquiryAnswered", "OUT_End_EnquiryAnswered")
    p_out.mf("OUT_Throw_EnquiryAnswered", "P_CallHandling", "CALL_Catch_EnquiryResolved")

    # =====================================================================
    # Treatment and Chemotherapy Bookings Team
    # =====================================================================
    p_trt.n("TRT_Start_BookingRequest", "msgstart", "Booking request received", 0, 0,
            msg=b.msg("treatment.booking-requested"))
    p_trt.n("TRT_Auto_ValidateRequest", "stask", "Check the request is complete and authorised", 1, 0,
            type="treatment.validate-request", retries=3,
            documentation="Rejects anything without an authorising clinician. A request that only arrived "
                          "by email or telephone is not in the system at all, so it cannot reach this step.")
    p_trt.n("TRT_Bnd_NotAuthorised", "bnderror", "Not authorised", 0, 0,
            attach="TRT_Auto_ValidateRequest", error="TREATMENT_REQUEST_UNAUTHORISED")
    p_trt.n("TRT_Throw_RequestRejected", "throw", "Return the request to the clinical team", 2, 6,
            msg=b.msg("treatment.request-invalid", K("treatment-request-invalid")),
            key=K("treatment-request-invalid"), headers={"messageName": "treatment.request-invalid"})
    p_trt.n("TRT_End_RequestRejected", "end", "Request returned for authorisation", 3, 6)
    p_trt.n("TRT_Throw_FundingCheck", "throw", "Ask Finance how this treatment is funded", 2, 0,
            msg=b.msg("funding.check-requested", K("funding")), key=K("funding"),
            headers={"messageName": "funding.check-requested"})
    p_trt.n("TRT_EGW_Funding", "eg", "Waiting on the funding decision", 3, 0)
    p_trt.n("TRT_Catch_FundingDecision", "catch", "Funding decision received", 4, 0,
            msg=b.msg("funding.decision-received", K("funding")))
    p_trt.n("TRT_Catch_FundingTimeout", "ctimer", "Funding decision overdue", 4, 1, timer="P5D")
    p_trt.n("TRT_GW_FundingRoute", "xg", "Who is paying for this treatment?", 5, 0)
    p_trt.n("TRT_Auto_PreparePayment", "stask", "Prepare the secure payment request", 6, 1,
            type="payment.prepare-request", retries=3,
            inputs=[("=1", "paymentAttempt")],
            documentation="Creates the payment reference and the secure link. Card details are never held "
                          "in the hospital system.")
    p_trt.n("TRT_Auto_ProcessPayment", "stask", "Take the payment through the payment provider", 7, 1,
            type="payment.process-transaction", retries=3,
            documentation="Outbound call to the external payment provider. Only the status, reference, "
                          "date and amount come back - never card data.")
    p_trt.n("TRT_Bnd_ProviderUnavailable", "bnderror", "Provider down", 0, 0,
            attach="TRT_Auto_ProcessPayment", error="PAYMENT_PROVIDER_UNAVAILABLE")
    p_trt.n("TRT_Bnd_ConfirmationLost", "bnderror", "No confirmation", 0, 0,
            attach="TRT_Auto_ProcessPayment", error="PAYMENT_CONFIRMATION_LOST",
            documentation="The provider may have taken the money. The transaction is investigated rather "
                          "than charged again.")
    p_trt.n("TRT_GW_PaymentOutcome", "xg", "What did the provider report?", 8, 1)
    p_trt.n("TRT_IGW_ReadyToBook", "ig", "Booking prerequisites satisfied", 9, 0)
    p_trt.n("TRT_Auto_Deduplicate", "stask", "Check the charge has not already been taken", 8, 2,
            type="finance.check-duplicate-payment", retries=3)
    p_trt.n("TRT_Task_ReviewDeclinedPayment", "utask", "Decide how to handle the failed payment", 9, 2,
            form="review-declined-payment", candidate_groups="treatment-bookings")
    p_trt.n("TRT_GW_DeclinedAction", "xg", "Try again or hand it over?", 10, 2)
    p_trt.n("TRT_Auto_NextAttempt", "stask", "Record the next payment attempt", 11, 2,
            type="payment.prepare-request", retries=3,
            inputs=[("=paymentAttempt + 1", "paymentAttempt")],
            documentation="A new attempt gets a new payment reference, so the provider is never asked to "
                          "take the same charge twice.")
    p_trt.n("TRT_Throw_PaymentUnresolved", "throw", "Leave the payment with the Finance Team", 12, 2,
            msg=b.msg("payment.unresolved", K("payment-unresolved")), key=K("payment-unresolved"),
            headers={"messageName": "payment.unresolved"})
    p_trt.n("TRT_End_PaymentUnresolved", "end", "Payment unresolved - booking not confirmed", 13, 2)
    p_trt.n("TRT_Throw_Investigation", "throw", "Mark the transaction for investigation", 7, 3,
            msg=b.msg("payment.investigation-requested", K("payment-investigation")),
            key=K("payment-investigation"), headers={"messageName": "payment.investigation-requested"},
            documentation="Money may have left the patient's account without a confirmation reaching us.")
    p_trt.n("TRT_Throw_UrgencyAuthorisation", "throw", "Ask a clinician about proceeding anyway", 8, 3,
            msg=b.msg("treatment.urgency-authorisation-requested", K("urgency-authorisation")),
            key=K("urgency-authorisation"),
            headers={"messageName": "treatment.urgency-authorisation-requested"})
    p_trt.n("TRT_Catch_UrgencyDecision", "catch", "Urgency decision returned", 9, 3,
            msg=b.msg("treatment.urgency-authorisation-result", K("urgency-authorisation")))
    p_trt.n("TRT_GW_UrgencyDecision", "xg", "May treatment go ahead without confirmed payment?", 10, 3)
    p_trt.n("TRT_Task_ReviewFundingTimeout", "utask", "Chase the outstanding funding approval", 5, 4,
            form="chase-funding-approval", candidate_groups="treatment-bookings")
    p_trt.n("TRT_GW_FundingTimeoutAction", "xg", "Has the approval come through?", 6, 4)
    p_trt.n("TRT_Throw_FundingTimeoutEscalation", "throw", "Record the funding delay", 7, 4,
            msg=b.msg("funding.delay-recorded", K("funding-delay")), key=K("funding-delay"),
            headers={"messageName": "funding.delay-recorded"})
    p_trt.n("TRT_End_FundingPending", "end", "Booking held pending funding approval", 8, 4)

    p_trt.f("TRT_Start_BookingRequest", "TRT_Auto_ValidateRequest")
    p_trt.f("TRT_Auto_ValidateRequest", "TRT_Throw_FundingCheck")
    p_trt.f("TRT_Bnd_NotAuthorised", "TRT_Throw_RequestRejected")
    p_trt.f("TRT_Throw_RequestRejected", "TRT_End_RequestRejected")
    p_trt.f("TRT_Throw_FundingCheck", "TRT_EGW_Funding")
    p_trt.f("TRT_EGW_Funding", "TRT_Catch_FundingDecision")
    p_trt.f("TRT_EGW_Funding", "TRT_Catch_FundingTimeout")
    p_trt.f("TRT_Catch_FundingDecision", "TRT_GW_FundingRoute")
    p_trt.f("TRT_GW_FundingRoute", "TRT_Auto_PreparePayment", cond='=fundingRoute = "PATIENT_PAYS"',
            name="Patient pays")
    p_trt.f("TRT_GW_FundingRoute", "TRT_IGW_ReadyToBook", default=True,
            name="Hospital, insurer or exemption")
    p_trt.f("TRT_Auto_PreparePayment", "TRT_Auto_ProcessPayment")
    p_trt.f("TRT_Auto_ProcessPayment", "TRT_GW_PaymentOutcome")
    p_trt.f("TRT_Bnd_ProviderUnavailable", "TRT_Throw_PaymentUnresolved")
    p_trt.f("TRT_Bnd_ConfirmationLost", "TRT_Throw_Investigation")
    p_trt.f("TRT_GW_PaymentOutcome", "TRT_IGW_ReadyToBook", cond='=paymentStatus = "APPROVED"',
            name="Approved")
    p_trt.f("TRT_GW_PaymentOutcome", "TRT_Auto_Deduplicate", cond='=paymentStatus = "DUPLICATE"',
            name="Duplicate charge reported")
    p_trt.f("TRT_GW_PaymentOutcome", "TRT_Task_ReviewDeclinedPayment", default=True,
            name="Declined or cancelled")
    p_trt.f("TRT_Auto_Deduplicate", "TRT_IGW_ReadyToBook", name="Single charge confirmed")
    p_trt.f("TRT_Task_ReviewDeclinedPayment", "TRT_GW_DeclinedAction")
    p_trt.f("TRT_GW_DeclinedAction", "TRT_Auto_NextAttempt", cond='=declinedAction = "RETRY_PAYMENT"',
            name="Try another payment")
    p_trt.f("TRT_GW_DeclinedAction", "TRT_Throw_PaymentUnresolved", default=True, name="Leave with Finance")
    p_trt.f("TRT_Auto_NextAttempt", "TRT_Auto_PreparePayment")
    p_trt.f("TRT_Throw_PaymentUnresolved", "TRT_End_PaymentUnresolved")
    p_trt.f("TRT_Throw_Investigation", "TRT_Throw_UrgencyAuthorisation")
    p_trt.f("TRT_Throw_UrgencyAuthorisation", "TRT_Catch_UrgencyDecision")
    p_trt.f("TRT_Catch_UrgencyDecision", "TRT_GW_UrgencyDecision")
    p_trt.f("TRT_GW_UrgencyDecision", "TRT_IGW_ReadyToBook", cond='=urgentTreatmentAuthorised = "true"',
            name="Clinician authorised")
    p_trt.f("TRT_GW_UrgencyDecision", "TRT_End_PaymentUnresolved", default=True, name="Not authorised")
    p_trt.f("TRT_Catch_FundingTimeout", "TRT_Task_ReviewFundingTimeout")
    p_trt.f("TRT_Task_ReviewFundingTimeout", "TRT_GW_FundingTimeoutAction")
    p_trt.f("TRT_GW_FundingTimeoutAction", "TRT_Throw_FundingCheck",
            cond='=fundingChaseOutcome = "RECHECK"', name="Approval now in place")
    p_trt.f("TRT_GW_FundingTimeoutAction", "TRT_Throw_FundingTimeoutEscalation", default=True,
            name="Still waiting")
    p_trt.f("TRT_Throw_FundingTimeoutEscalation", "TRT_End_FundingPending")
    p_trt.mf("TRT_Throw_FundingCheck", "P_Finance", "FIN_Start_FundingCheck")
    p_trt.mf("TRT_Auto_ProcessPayment", "P_PaymentProvider", "P_PaymentProvider")
    p_trt.mf("TRT_Throw_UrgencyAuthorisation", "P_Consultants", "CON_Start_UrgencyAuthorisation")
    p_trt.mf("TRT_Throw_PaymentUnresolved", "P_Finance", "P_Finance")
    p_trt.mf("TRT_Throw_Investigation", "P_Finance", "FIN_Start_PaymentInvestigation")

    # external resource availability and confirmation
    p_trt.n("TRT_Auto_CreateSeries", "stask", "Create the provisional appointment series", 10, 0,
            type="treatment.create-appointment-series", retries=3,
            documentation="One appointment per cycle, all keyed on the treatment booking reference so a "
                          "retry cannot create a second series.")
    p_trt.n("TRT_Auto_CheckExternalResources", "stask", "Check external treatment and diagnostic capacity", 11, 0,
            type="external-resources.check-availability", retries=3,
            documentation="Outbound call to the external treatment, laboratory and imaging services. If "
                          "the booking cannot be held the case stays pending instead of being lost.")
    p_trt.n("TRT_Bnd_ExternalUnavailable", "bnderror", "Unavailable", 0, 0,
            attach="TRT_Auto_CheckExternalResources", error="EXTERNAL_RESOURCE_UNAVAILABLE")
    p_trt.n("TRT_GW_ExternalAvailable", "xg", "Is everything available?", 12, 0)
    p_trt.n("TRT_Auto_ConfirmAppointments", "stask", "Confirm the treatment appointments", 13, 0,
            type="treatment.confirm-appointments", retries=3,
            documentation="Runs once per booking reference. Re-running after a retry updates the same "
                          "appointments instead of adding new ones.")
    p_trt.n("TRT_Throw_TreatmentConfirmed", "throw", "Treatment schedule confirmed", 14, 0,
            msg=b.msg("treatment.confirmed", K("treatment-confirmed")), key=K("treatment-confirmed"),
            headers={"messageName": "treatment.confirmed"})
    p_trt.n("TRT_PGW_NotifySplit", "pg", "Tell the patient and start the clinic letter", 15, 0,
            documentation="Once treatment is confirmed both of these have to happen, so they run in "
                          "parallel rather than as a choice.")
    p_trt.n("TRT_Throw_LetterDraftRequested", "throw", "Clinic letter requested", 16, 0,
            msg=b.msg("clinic.letter-draft-required", K("clinic-letter")), key=K("clinic-letter"),
            headers={"messageName": "clinic.letter-draft-required"},
            documentation="Raised once treatment is confirmed so the seven day correspondence target "
                          "starts from a recorded point in the pathway.")
    p_trt.n("TRT_Auto_SendTreatmentLetter", "stask", "Send the treatment confirmation letter", 16, 1,
            type="correspondence.dispatch-letter", retries=3,
            inputs=[('=["patient"]', "letterRecipients")])
    p_trt.n("TRT_PGW_NotifyJoin", "pg", "Both notifications issued", 17, 0)
    p_trt.n("TRT_End_Scheduled", "end", "Schedule confirmed", 18, 0)
    p_trt.n("TRT_Throw_BookingPending", "throw", "Booking pending", 12, 5,
            msg=b.msg("treatment.booking-pending", K("treatment-pending")), key=K("treatment-pending"),
            headers={"messageName": "treatment.booking-pending"})
    p_trt.n("TRT_Catch_RetryTimer", "ctimer", "Retry external capacity", 13, 5, timer="P3D")
    p_trt.f("TRT_IGW_ReadyToBook", "TRT_Auto_CreateSeries")
    p_trt.f("TRT_Auto_CreateSeries", "TRT_Auto_CheckExternalResources")
    p_trt.f("TRT_Auto_CheckExternalResources", "TRT_GW_ExternalAvailable")
    p_trt.f("TRT_Bnd_ExternalUnavailable", "TRT_Throw_BookingPending")
    p_trt.f("TRT_GW_ExternalAvailable", "TRT_Auto_ConfirmAppointments",
            cond="=externalResourcesAvailable = true", name="All resources held")
    p_trt.f("TRT_GW_ExternalAvailable", "TRT_Throw_BookingPending", default=True,
            name="Something is unavailable")
    p_trt.f("TRT_Auto_ConfirmAppointments", "TRT_Throw_TreatmentConfirmed")
    p_trt.f("TRT_Throw_TreatmentConfirmed", "TRT_PGW_NotifySplit")
    p_trt.f("TRT_PGW_NotifySplit", "TRT_Throw_LetterDraftRequested")
    p_trt.f("TRT_PGW_NotifySplit", "TRT_Auto_SendTreatmentLetter")
    p_trt.f("TRT_Throw_LetterDraftRequested", "TRT_PGW_NotifyJoin")
    p_trt.f("TRT_Auto_SendTreatmentLetter", "TRT_PGW_NotifyJoin")
    p_trt.f("TRT_PGW_NotifyJoin", "TRT_End_Scheduled")
    p_trt.f("TRT_Throw_BookingPending", "TRT_Catch_RetryTimer")
    p_trt.f("TRT_Catch_RetryTimer", "TRT_Auto_CheckExternalResources",
            name="Try again, no duplicate booking")
    p_trt.mf("TRT_Auto_CheckExternalResources", "P_ExternalClinicalServices", "P_ExternalClinicalServices")
    p_trt.mf("TRT_Auto_SendTreatmentLetter", "P_Correspondence", "P_Correspondence")
    p_trt.mf("TRT_Throw_LetterDraftRequested", "P_Consultants", "CON_Start_LetterDraft")
    p_trt.mf("TRT_Throw_BookingPending", "P_PathwayCoordinators", "PCW_Start_BookingDelay")

    # chemotherapy cycles
    p_trt.n("TRT_Start_CycleApproved", "msgstart", "Next chemotherapy cycle authorised", 0, 7,
            msg=b.msg("chemotherapy.cycle-approved"))
    p_trt.n("TRT_Auto_ScheduleCycle", "stask", "Schedule the next cycle", 1, 7,
            type="treatment.schedule-next-cycle", retries=3)
    p_trt.n("TRT_Auto_FindCycleSlots", "stask", "Look for a slot for the next cycle", 2, 7,
            type="scheduling.find-appointment-slots", retries=3)
    p_trt.n("TRT_Bnd_CycleNoSlots", "bnderror", "No capacity", 0, 0,
            attach="TRT_Auto_FindCycleSlots", error="SCHEDULING_SERVICE_UNAVAILABLE")
    p_trt.n("TRT_GW_CycleSlots", "xg", "Was a cycle slot found?", 3, 7)
    p_trt.n("TRT_Throw_NextReviewDue", "throw", "Next cycle booked", 4, 7,
            msg=b.msg("chemotherapy.review-requested", K("chemotherapy-cycle")), key=K("chemotherapy-cycle"),
            headers={"messageName": "chemotherapy.review-requested"})
    p_trt.n("TRT_GW_MoreCycles", "xg", "Are there further cycles in this course?", 5, 7)
    p_trt.n("TRT_End_CycleScheduled", "end", "Next cycle booked and review requested", 6, 7)
    p_trt.n("TRT_End_CourseComplete", "end", "Course of treatment complete", 6, 8)
    p_trt.n("TRT_Throw_CycleCapacityIssue", "throw", "Flag the capacity problem", 4, 8,
            msg=b.msg("treatment.booking-pending", K("treatment-pending")), key=K("treatment-pending"),
            headers={"messageName": "treatment.booking-pending"})
    p_trt.n("TRT_End_CyclePending", "end", "Cycle booking held", 5, 8)
    p_trt.f("TRT_Start_CycleApproved", "TRT_Auto_ScheduleCycle")
    p_trt.f("TRT_Auto_ScheduleCycle", "TRT_Auto_FindCycleSlots")
    p_trt.f("TRT_Auto_FindCycleSlots", "TRT_GW_CycleSlots")
    p_trt.f("TRT_GW_CycleSlots", "TRT_Throw_NextReviewDue", cond="=slotCount > 0", name="Slot found")
    p_trt.f("TRT_GW_CycleSlots", "TRT_Throw_CycleCapacityIssue", default=True, name="Nothing available")
    p_trt.f("TRT_Bnd_CycleNoSlots", "TRT_Throw_CycleCapacityIssue")
    p_trt.f("TRT_Throw_NextReviewDue", "TRT_GW_MoreCycles")
    p_trt.f("TRT_GW_MoreCycles", "TRT_End_CycleScheduled", cond="=cycleNumber < cycleCount",
            name="Another cycle to come")
    p_trt.f("TRT_GW_MoreCycles", "TRT_End_CourseComplete", default=True, name="Last cycle of the course")
    p_trt.f("TRT_Throw_CycleCapacityIssue", "TRT_End_CyclePending")
    p_trt.mf("TRT_Auto_FindCycleSlots", "P_ExternalScheduling", "P_ExternalScheduling")
    p_trt.mf("TRT_Throw_NextReviewDue", "P_Consultants", "CON_Start_CycleReview")
    p_trt.mf("TRT_Throw_CycleCapacityIssue", "P_PathwayCoordinators", "PCW_Start_BookingDelay")

    # delayed cycle and treatment modification
    p_trt.n("TRT_Start_CycleDelayed", "msgstart", "Cycle delayed on clinical grounds", 0, 9,
            msg=b.msg("chemotherapy.cycle-delayed"))
    p_trt.n("TRT_Task_RecordDelay", "utask", "Record the delay and re-plan the cycle", 1, 9,
            form="record-cycle-delay", candidate_groups="treatment-bookings")
    p_trt.n("TRT_Throw_DelayNotified", "throw", "Tell the pathway team and the patient", 2, 9,
            msg=b.msg("treatment.booking-pending", K("treatment-pending")), key=K("treatment-pending"),
            headers={"messageName": "treatment.booking-pending"})
    p_trt.n("TRT_End_DelayRecorded", "end", "Delay recorded", 3, 9)
    p_trt.f("TRT_Start_CycleDelayed", "TRT_Task_RecordDelay")
    p_trt.f("TRT_Task_RecordDelay", "TRT_Throw_DelayNotified")
    p_trt.f("TRT_Throw_DelayNotified", "TRT_End_DelayRecorded")
    p_trt.mf("TRT_Throw_DelayNotified", "P_PathwayCoordinators", "PCW_Start_BookingDelay")

    p_trt.n("TRT_Start_Modification", "msgstart", "Treatment plan change requested", 0, 10,
            msg=b.msg("treatment.modification-requested"))
    p_trt.n("TRT_Start_ModificationAuthorised", "msgstart", "Treatment change authorised", 0, 11,
            msg=b.msg("treatment.modification-authorised"))
    p_trt.n("TRT_Auto_ApplyModification", "stask", "Apply the treatment change to the schedule", 1, 11,
            type="treatment.apply-modification", retries=3,
            documentation="Updates the existing appointments rather than creating a new series.")
    p_trt.n("TRT_GW_ModificationFinancial", "xg", "Does the change affect money already handled?", 2, 11)
    p_trt.n("TRT_Throw_ModificationFinance", "throw", "Refer the financial impact to Finance", 3, 11,
            msg=b.msg("finance.impact-review-requested", K("finance-impact")), key=K("finance-impact"),
            headers={"messageName": "finance.impact-review-requested"})
    p_trt.n("TRT_End_ModificationApplied", "end", "Treatment change applied", 4, 11)
    p_trt.n("TRT_Task_ReviewModification", "utask", "Review the treatment change request", 1, 10,
            form="review-treatment-change", candidate_groups="treatment-bookings")
    p_trt.n("TRT_Throw_ModificationToClinical", "throw", "Send the change for clinical authorisation", 2, 10,
            msg=b.msg("treatment.change-requested", K("treatment-change")),
            key=K("treatment-change"), headers={"messageName": "treatment.change-requested"})
    p_trt.n("TRT_End_ModificationForwarded", "end", "Change forwarded for authorisation", 3, 10)
    p_trt.f("TRT_Start_Modification", "TRT_Task_ReviewModification")
    p_trt.f("TRT_Task_ReviewModification", "TRT_Throw_ModificationToClinical")
    p_trt.f("TRT_Throw_ModificationToClinical", "TRT_End_ModificationForwarded")
    p_trt.f("TRT_Start_ModificationAuthorised", "TRT_Auto_ApplyModification")
    p_trt.f("TRT_Auto_ApplyModification", "TRT_GW_ModificationFinancial")
    p_trt.f("TRT_GW_ModificationFinancial", "TRT_Throw_ModificationFinance",
            cond='=modificationAffectsFinance = "true"', name="Charge or payment affected")
    p_trt.f("TRT_GW_ModificationFinancial", "TRT_End_ModificationApplied", default=True,
            name="No financial impact")
    p_trt.f("TRT_Throw_ModificationFinance", "TRT_End_ModificationApplied")
    p_trt.mf("TRT_Throw_ModificationToClinical", "P_Consultants", "CON_Start_ChangeRequest")
    p_trt.mf("TRT_Throw_ModificationFinance", "P_Finance", "FIN_Start_ImpactReview")

    # =====================================================================
    # Finance Team
    # =====================================================================
    p_fin.n("FIN_Start_FundingCheck", "msgstart", "Funding check requested", 0, 0,
            msg=b.msg("funding.check-requested"))
    p_fin.n("FIN_Task_DetermineFunding", "utask", "Determine the funding route and record the approval", 1, 0,
            form="determine-funding-route", candidate_groups="finance",
            documentation="Records the responsible organisation, the authorisation reference, the approved "
                          "amount and any limits attached to the approval.")
    p_fin.n("FIN_Auto_AuditFunding", "stask", "Record the funding decision for audit", 2, 0,
            type="audit.record-financial-decision", retries=3)
    p_fin.n("FIN_GW_FundingRoute", "xg", "Which funding route applies?", 3, 0)
    p_fin.n("FIN_Auto_RecordApproval", "stask", "Record the funding approval", 4, 0,
            type="finance.record-funding-approval", retries=3)
    p_fin.n("FIN_Throw_FundingDecision", "throw", "Return the funding decision", 5, 0,
            msg=b.msg("funding.decision-received", K("funding")), key=K("funding"),
            headers={"messageName": "funding.decision-received"})
    p_fin.n("FIN_End_FundingDecided", "end", "Funding decision returned", 6, 0)
    p_fin.n("FIN_Auto_CalculateCharge", "stask", "Work out the charge payable", 4, 1,
            type="finance.calculate-charge", retries=3,
            documentation="Applies the tariff for the treatment plus the patient's funding category. "
                          "Returns the amount only - never any card data.")
    p_fin.n("FIN_Bnd_ChargeFailed", "bnderror", "Pricing failed", 0, 0,
            attach="FIN_Auto_CalculateCharge", error="CHARGE_CALCULATION_FAILED")
    p_fin.n("FIN_Task_ManualCharge", "utask", "Price the treatment manually", 5, 1,
            form="manual-charge-entry", candidate_groups="finance")
    p_fin.n("FIN_Task_ChasePreAuthorisation", "utask", "Chase the insurer for pre-authorisation", 5, 2,
            form="chase-pre-authorisation", candidate_groups="finance")
    p_fin.f("FIN_Start_FundingCheck", "FIN_Task_DetermineFunding")
    p_fin.f("FIN_Task_DetermineFunding", "FIN_Auto_AuditFunding")
    p_fin.f("FIN_Auto_AuditFunding", "FIN_GW_FundingRoute")
    p_fin.f("FIN_GW_FundingRoute", "FIN_Auto_RecordApproval",
            cond='=fundingRoute = "HOSPITAL_FUNDED" or fundingRoute = "INSURER_APPROVED" or fundingRoute = "EXEMPTION"',
            name="Approved or exempt")
    p_fin.f("FIN_GW_FundingRoute", "FIN_Auto_CalculateCharge", cond='=fundingRoute = "PATIENT_PAYS"',
            name="Patient pays")
    p_fin.f("FIN_GW_FundingRoute", "FIN_Task_ChasePreAuthorisation", default=True,
            name="Pre-authorisation outstanding")
    p_fin.f("FIN_Auto_RecordApproval", "FIN_Throw_FundingDecision")
    p_fin.f("FIN_Auto_CalculateCharge", "FIN_Throw_FundingDecision")
    p_fin.f("FIN_Task_ChasePreAuthorisation", "FIN_Auto_RecordApproval")
    p_fin.f("FIN_Bnd_ChargeFailed", "FIN_Task_ManualCharge")
    p_fin.f("FIN_Task_ManualCharge", "FIN_Throw_FundingDecision")
    p_fin.f("FIN_Throw_FundingDecision", "FIN_End_FundingDecided")
    p_fin.mf("FIN_Throw_FundingDecision", "P_TreatmentBookings", "TRT_Catch_FundingDecision")

    # unconfirmed payments
    p_fin.n("FIN_Start_PaymentInvestigation", "msgstart", "Payment taken without confirmation", 0, 3,
            msg=b.msg("payment.investigation-requested"))
    p_fin.n("FIN_Task_InvestigatePayment", "utask", "Investigate the unconfirmed payment", 1, 3,
            form="investigate-unconfirmed-payment", candidate_groups="finance",
            documentation="Reconciles the provider's transaction list against the booking before anyone "
                          "asks the patient for money again.")
    p_fin.n("FIN_GW_InvestigationOutcome", "xg", "Was the money actually taken?", 2, 3)
    p_fin.n("FIN_Auto_RecordPayment", "stask", "Record the payment against the account", 3, 3,
            type="finance.record-payment-outcome", retries=3)
    p_fin.n("FIN_Throw_InvestigationResolved", "throw", "Investigation closed", 4, 3,
            msg=b.msg("payment.investigation-resolved", K("payment-investigation")),
            key=K("payment-investigation"), headers={"messageName": "payment.investigation-resolved"})
    p_fin.n("FIN_End_InvestigationClosed", "end", "Investigation closed", 5, 3)
    p_fin.f("FIN_Start_PaymentInvestigation", "FIN_Task_InvestigatePayment")
    p_fin.f("FIN_Task_InvestigatePayment", "FIN_GW_InvestigationOutcome")
    p_fin.f("FIN_GW_InvestigationOutcome", "FIN_Auto_RecordPayment", cond='=paymentFound = "true"',
            name="Payment located")
    p_fin.f("FIN_GW_InvestigationOutcome", "FIN_Throw_InvestigationResolved", default=True,
            name="Nothing was taken")
    p_fin.f("FIN_Auto_RecordPayment", "FIN_Throw_InvestigationResolved")
    p_fin.f("FIN_Throw_InvestigationResolved", "FIN_End_InvestigationClosed")
    p_fin.mf("FIN_Throw_InvestigationResolved", "P_TreatmentBookings", "P_TreatmentBookings")

    # refunds
    p_fin.n("FIN_Start_Refund", "msgstart", "Refund decision required", 0, 5,
            msg=b.msg("refund.required"))
    p_fin.n("FIN_Task_DecideRefund", "utask", "Decide whether a refund is due", 1, 5,
            form="decide-refund", candidate_groups="finance",
            documentation="Clinical staff may describe the treatment decision but only Finance, holding "
                          "the right financial authority, approves a refund.")
    p_fin.n("FIN_Auto_AuditRefund", "stask", "Record the refund decision for audit", 2, 5,
            type="audit.record-financial-decision", retries=3)
    p_fin.n("FIN_GW_RefundDecision", "xg", "What did Finance decide?", 3, 5)
    p_fin.n("FIN_Auto_PrepareRefund", "stask", "Prepare the approved refund", 4, 5,
            type="finance.prepare-refund", retries=3,
            documentation="Checks the refund against the original transaction so the patient is never "
                          "refunded more than was taken.")
    p_fin.n("FIN_Auto_ProcessRefund", "stask", "Send the refund to the payment provider", 5, 5,
            type="payment.process-refund", retries=3,
            documentation="Outbound call to the external payment provider. Only the refund status and "
                          "amount come back to the hospital.")
    p_fin.n("FIN_Bnd_RefundFailed", "bnderror", "Rejected", 0, 0,
            attach="FIN_Auto_ProcessRefund", error="PAYMENT_PROVIDER_UNAVAILABLE")
    p_fin.n("FIN_GW_RefundStatus", "xg", "Did the provider accept the refund?", 6, 5)
    p_fin.n("FIN_Auto_RecordRefund", "stask", "Record the refund against the patient account", 7, 5,
            type="finance.record-refund", retries=3)
    p_fin.n("FIN_End_RefundRecorded", "end", "Refund recorded", 8, 5)
    p_fin.n("FIN_Throw_RefundDelayed", "throw", "Tell the patient the refund is delayed", 7, 6,
            msg=b.msg("refund.delayed", K("refund")), key=K("refund"),
            headers={"messageName": "refund.delayed"})
    p_fin.n("FIN_End_RefundPending", "end", "Refund still with the provider", 8, 6)
    p_fin.n("FIN_Auto_RecordNoRefund", "stask", "Record that no refund is due", 4, 7,
            type="finance.record-refund", retries=3)
    p_fin.n("FIN_Throw_NoRefund", "throw", "Tell the patient no refund is due", 5, 7,
            msg=b.msg("refund.declined", K("refund")), key=K("refund"),
            headers={"messageName": "refund.declined"})
    p_fin.n("FIN_End_NoRefund", "end", "No refund - decision recorded", 6, 7)
    p_fin.f("FIN_Start_Refund", "FIN_Task_DecideRefund")
    p_fin.f("FIN_Task_DecideRefund", "FIN_Auto_AuditRefund")
    p_fin.f("FIN_Auto_AuditRefund", "FIN_GW_RefundDecision")
    p_fin.f("FIN_GW_RefundDecision", "FIN_Auto_PrepareRefund",
            cond='=refundDecision = "FULL_REFUND" or refundDecision = "PARTIAL_REFUND"', name="Refund approved")
    p_fin.f("FIN_GW_RefundDecision", "FIN_Auto_RecordNoRefund", default=True, name="No refund due")
    p_fin.f("FIN_Auto_PrepareRefund", "FIN_Auto_ProcessRefund")
    p_fin.f("FIN_Auto_ProcessRefund", "FIN_GW_RefundStatus")
    p_fin.f("FIN_Bnd_RefundFailed", "FIN_Throw_RefundDelayed")
    p_fin.f("FIN_GW_RefundStatus", "FIN_Auto_RecordRefund", cond='=refundStatus = "REFUNDED"',
            name="Refunded")
    p_fin.f("FIN_GW_RefundStatus", "FIN_Throw_RefundDelayed", default=True, name="Not accepted yet")
    p_fin.f("FIN_Auto_RecordRefund", "FIN_End_RefundRecorded")
    p_fin.f("FIN_Throw_RefundDelayed", "FIN_End_RefundPending")
    p_fin.f("FIN_Auto_RecordNoRefund", "FIN_Throw_NoRefund")
    p_fin.f("FIN_Throw_NoRefund", "FIN_End_NoRefund")
    p_fin.mf("FIN_Auto_ProcessRefund", "P_PaymentProvider", "P_PaymentProvider")
    p_fin.mf("FIN_Throw_RefundDelayed", "P_Patient", "P_Patient")
    p_fin.mf("FIN_Throw_NoRefund", "P_Patient", "P_Patient")

    # financial impact of a treatment change
    p_fin.n("FIN_Start_ImpactReview", "msgstart", "Financial impact review requested", 0, 8,
            msg=b.msg("finance.impact-review-requested"))
    p_fin.n("FIN_Task_ReviewImpact", "utask", "Review the financial impact of the treatment change", 1, 8,
            form="review-financial-impact", candidate_groups="finance")
    p_fin.n("FIN_GW_ImpactAction", "xg", "What does the change require?", 2, 8)
    p_fin.n("FIN_Throw_FinanceOutcome", "throw", "Record the financial outcome", 3, 8,
            msg=b.msg("finance.impact-resolved", K("finance-impact")), key=K("finance-impact"),
            headers={"messageName": "finance.impact-resolved"})
    p_fin.n("FIN_End_ImpactReviewed", "end", "Financial impact resolved", 4, 8)
    p_fin.f("FIN_Start_ImpactReview", "FIN_Task_ReviewImpact")
    p_fin.f("FIN_Task_ReviewImpact", "FIN_GW_ImpactAction")
    p_fin.f("FIN_GW_ImpactAction", "FIN_Throw_FinanceOutcome",
            cond='=impactAction = "ADJUST_CHARGE" or impactAction = "REFUND_REQUIRED"',
            name="Charge or refund to adjust")
    p_fin.f("FIN_GW_ImpactAction", "FIN_Throw_FinanceOutcome", default=True, name="No change to the account")
    p_fin.f("FIN_Throw_FinanceOutcome", "FIN_End_ImpactReviewed")
    p_fin.mf("FIN_Throw_FinanceOutcome", "P_TreatmentBookings", "P_TreatmentBookings")

    # finance enquiries routed from the call handling team
    p_fin.n("FIN_Start_Enquiry", "msgstart", "Payment enquiry", 0, 10,
            msg=b.msg("enquiry.assigned-finance"))
    p_fin.n("FIN_Task_AnswerEnquiry", "utask", "Answer the payment or funding enquiry", 1, 10,
            form="answer-financial-enquiry", candidate_groups="finance",
            documentation="Call handlers only answer from authorised information. Anything else comes here.")
    p_fin.n("FIN_Throw_EnquiryAnswered", "throw", "Enquiry answered", 2, 10,
            msg=b.msg("enquiry.resolved", K("enquiry")), key=K("enquiry"),
            headers={"messageName": "enquiry.resolved"})
    p_fin.n("FIN_End_EnquiryAnswered", "end", "Enquiry answered", 3, 10)
    p_fin.f("FIN_Start_Enquiry", "FIN_Task_AnswerEnquiry")
    p_fin.f("FIN_Task_AnswerEnquiry", "FIN_Throw_EnquiryAnswered")
    p_fin.f("FIN_Throw_EnquiryAnswered", "FIN_End_EnquiryAnswered")
    p_fin.mf("FIN_Throw_EnquiryAnswered", "P_CallHandling", "CALL_Catch_EnquiryResolved")

    # =====================================================================
    # Clinical Nurse Specialist Team
    # =====================================================================
    p_cns.n("CNS_Start_Enquiry", "msgstart", "Clinical enquiry assigned", 0, 0,
            msg=b.msg("enquiry.assigned-clinical"))
    p_cns.n("CNS_Start_UrgentEnquiry", "msgstart", "Urgent clinical concern assigned", 0, 1,
            msg=b.msg("enquiry.assigned-clinical-urgent"))
    p_cns.n("CNS_Task_TriageEnquiry", "utask", "Triage the enquiry and respond", 1, 0,
            form="triage-clinical-enquiry", candidate_groups="clinical-nurse-specialists",
            documentation="Only a qualified clinical professional answers here. Call handlers never "
                          "diagnose or interpret results.")
    p_cns.n("CNS_GW_NeedsConsultant", "xg", "Does this need a Consultant?", 2, 0)
    p_cns.n("CNS_Throw_ToConsultant", "throw", "Ask the Consultant for a clinical review", 3, 0,
            msg=b.msg("clinical.review-requested", K("clinical-review")), key=K("clinical-review"),
            headers={"messageName": "clinical.review-requested"})
    p_cns.n("CNS_Catch_ClinicalReview", "catch", "Clinical review outcome", 4, 0,
            msg=b.msg("clinical.review-outcome", K("clinical-review")))
    p_cns.n("CNS_Auto_RecordAdvice", "stask", "Record the advice given", 5, 0,
            type="cns.record-clinical-advice", retries=3)
    p_cns.n("CNS_Throw_Resolved", "throw", "Enquiry resolved", 6, 0,
            msg=b.msg("enquiry.resolved", K("enquiry")), key=K("enquiry"),
            headers={"messageName": "enquiry.resolved"})
    p_cns.n("CNS_End_Resolved", "end", "Enquiry answered and closed", 7, 0)
    p_cns.n("CNS_Bnd_UrgentOverdue", "bndtimer", "1 hour", 0, 0,
            attach="CNS_Task_TriageEnquiry", timer="PT1H", non_interrupting=True)
    p_cns.n("CNS_Throw_UrgentEscalation", "throw", "Escalate the unanswered urgent concern", 2, 1,
            msg=b.msg("enquiry.urgent-escalated", K("enquiry-escalation")), key=K("enquiry-escalation"),
            headers={"messageName": "enquiry.urgent-escalated"})
    p_cns.n("CNS_End_UrgentEscalated", "end", "Urgent concern escalated", 3, 1)
    p_cns.f("CNS_Start_Enquiry", "CNS_Task_TriageEnquiry")
    p_cns.f("CNS_Start_UrgentEnquiry", "CNS_Task_TriageEnquiry")
    p_cns.f("CNS_Task_TriageEnquiry", "CNS_GW_NeedsConsultant")
    p_cns.f("CNS_GW_NeedsConsultant", "CNS_Throw_ToConsultant", cond='=needsConsultantReview = "true"',
            name="Needs a Consultant")
    p_cns.f("CNS_GW_NeedsConsultant", "CNS_Auto_RecordAdvice", default=True, name="Answered directly")
    p_cns.f("CNS_Throw_ToConsultant", "CNS_Catch_ClinicalReview")
    p_cns.f("CNS_Catch_ClinicalReview", "CNS_Auto_RecordAdvice")
    p_cns.f("CNS_Auto_RecordAdvice", "CNS_Throw_Resolved")
    p_cns.f("CNS_Throw_Resolved", "CNS_End_Resolved")
    p_cns.f("CNS_Bnd_UrgentOverdue", "CNS_Throw_UrgentEscalation")
    p_cns.f("CNS_Throw_UrgentEscalation", "CNS_End_UrgentEscalated")
    p_cns.mf("CNS_Throw_ToConsultant", "P_Consultants", "CON_Start_ClinicalReview")
    p_cns.mf("CNS_Throw_Resolved", "P_CallHandling", "CALL_Catch_EnquiryResolved")
    p_cns.mf("CNS_Throw_UrgentEscalation", "P_PathwayCoordinators", "P_PathwayCoordinators")

    # =====================================================================
    # Call Handling Team
    # =====================================================================
    p_call.n("CALL_Start_Enquiry", "msgstart", "Enquiry received by the call handling team", 0, 0,
            msg=b.msg("enquiry.received"))
    p_call.n("CALL_Task_LogEnquiry", "utask", "Log the enquiry, classify it and set a priority", 1, 0,
            form="log-enquiry", candidate_groups="call-handling",
            documentation="Every enquiry gets a record, a category and a priority. Clinical questions are "
                          "flagged straight away even though the urgency rules are still being agreed.")
    p_call.n("CALL_GW_Category", "xg", "What kind of enquiry is this?", 2, 0)
    p_call.n("CALL_GW_Urgent", "xg", "Is this an urgent clinical concern?", 3, 1)
    p_call.n("CALL_Throw_UrgentClinical", "throw", "Urgent concern to CNS", 4, 1,
            msg=b.msg("enquiry.assigned-clinical-urgent", K("enquiry")), key=K("enquiry"),
            headers={"messageName": "enquiry.assigned-clinical-urgent"})
    p_call.n("CALL_Throw_Clinical", "throw", "Send the enquiry to the nurse specialists", 4, 2,
            msg=b.msg("enquiry.assigned-clinical", K("enquiry")), key=K("enquiry"),
            headers={"messageName": "enquiry.assigned-clinical"})
    p_call.n("CALL_Throw_Finance", "throw", "Send the enquiry to the Finance Team", 3, 3,
            msg=b.msg("enquiry.assigned-finance", K("enquiry")), key=K("enquiry"),
            headers={"messageName": "enquiry.assigned-finance"})
    p_call.n("CALL_GW_Answerable", "xg", "Can this be answered with the information available?", 3, 4)
    p_call.n("CALL_Task_AnswerAdmin", "utask", "Answer the administrative question", 4, 4,
            form="answer-administrative-enquiry", candidate_groups="call-handling")
    p_call.n("CALL_Throw_AdminTeam", "throw", "Enquiry to admin team", 4, 5,
            msg=b.msg("enquiry.assigned-admin", K("enquiry")), key=K("enquiry"),
            headers={"messageName": "enquiry.assigned-admin"})
    p_call.n("CALL_Catch_EnquiryResolved", "catch", "Enquiry resolved by the specialist team", 5, 0,
            msg=b.msg("enquiry.resolved", K("enquiry")))
    p_call.n("CALL_Auto_CloseEnquiry", "stask", "Close the enquiry record", 6, 0,
            type="enquiry.close-record", retries=3)
    p_call.n("CALL_End_EnquiryResolved", "end", "Enquiry resolved", 7, 0)
    p_call.f("CALL_Start_Enquiry", "CALL_Task_LogEnquiry")
    p_call.f("CALL_Task_LogEnquiry", "CALL_GW_Category")
    p_call.f("CALL_GW_Category", "CALL_GW_Urgent", cond='=enquiryCategory = "CLINICAL"', name="Clinical")
    p_call.f("CALL_GW_Category", "CALL_Throw_Finance", cond='=enquiryCategory = "FINANCIAL"', name="Financial")
    p_call.f("CALL_GW_Category", "CALL_GW_Answerable", default=True, name="Administrative")
    p_call.f("CALL_GW_Urgent", "CALL_Throw_UrgentClinical", cond="=enquiryPriority = \"URGENT\"",
            name="Urgent")
    p_call.f("CALL_GW_Urgent", "CALL_Throw_Clinical", default=True, name="Routine clinical")
    p_call.f("CALL_Throw_UrgentClinical", "CALL_Catch_EnquiryResolved",
             name="Wait for the nurse specialists")
    p_call.f("CALL_Throw_Clinical", "CALL_Catch_EnquiryResolved",
             name="Wait for the nurse specialists")
    p_call.f("CALL_GW_Answerable", "CALL_Task_AnswerAdmin", cond='=answerableNow = "true"',
            name="Answered on the call")
    p_call.f("CALL_GW_Answerable", "CALL_Throw_AdminTeam", default=True, name="Needs another team")
    p_call.f("CALL_Task_AnswerAdmin", "CALL_Catch_EnquiryResolved")
    p_call.f("CALL_Throw_AdminTeam", "CALL_Catch_EnquiryResolved")
    p_call.f("CALL_Throw_Finance", "CALL_Catch_EnquiryResolved")
    p_call.f("CALL_Catch_EnquiryResolved", "CALL_Auto_CloseEnquiry")
    p_call.f("CALL_Auto_CloseEnquiry", "CALL_End_EnquiryResolved")
    p_call.mf("CALL_Throw_UrgentClinical", "P_ClinicalNurseSpecialist", "CNS_Start_UrgentEnquiry")
    p_call.mf("CALL_Throw_Clinical", "P_ClinicalNurseSpecialist", "CNS_Start_Enquiry")
    p_call.mf("CALL_Throw_Finance", "P_Finance", "FIN_Start_Enquiry")
    p_call.mf("CALL_Throw_AdminTeam", "P_OutpatientBookings", "OUT_Start_AdminEnquiry")
    p_call.mf_in("P_Patient", "P_Patient", "CALL_Start_Enquiry", "Patient telephones the hospital")

    # outbound telephone contact for appointments inside two weeks
    p_call.n("CALL_Start_PhoneContact", "msgstart", "Short notice call requested", 0, 6,
            msg=b.msg("appointment.phone-contact-requested"))
    p_call.n("CALL_Task_AttemptContact", "utask", "Attempt to telephone the patient", 1, 6,
            form="record-telephone-contact-attempt", candidate_groups="call-handling",
            documentation="Every attempt is recorded, including the wrong number and the patient who "
                          "asks for a different date.")
    p_call.n("CALL_GW_ContactOutcome", "xg", "What was the outcome of the call?", 2, 6)
    p_call.n("CALL_Auto_LogAttempt", "stask", "Log the contact attempt", 3, 6,
            type="enquiry.record-contact-attempt", retries=3)
    p_call.n("CALL_GW_Retry", "xg", "Should we try again?", 4, 6)
    p_call.n("CALL_Throw_ContactFinished", "throw", "Contact finished", 5, 6,
            msg=b.msg("appointment.phone-contact-finished", K("phone-contact")), key=K("phone-contact"),
            headers={"messageName": "appointment.phone-contact-finished"})
    p_call.n("CALL_End_ContactFinished", "end", "Patient contacted", 6, 6)
    p_call.n("CALL_Throw_ContactFailed", "throw", "Report that the patient could not be reached", 5, 7,
            msg=b.msg("appointment.phone-contact-finished", K("phone-contact")), key=K("phone-contact"),
            inputs=[('="UNREACHABLE"', "contactOutcome")],
            headers={"messageName": "appointment.phone-contact-finished"})
    p_call.n("CALL_End_ContactFailed", "end", "Contact attempts exhausted", 6, 7)
    p_call.f("CALL_Start_PhoneContact", "CALL_Task_AttemptContact")
    p_call.f("CALL_Task_AttemptContact", "CALL_GW_ContactOutcome")
    p_call.f("CALL_GW_ContactOutcome", "CALL_Auto_LogAttempt", cond='=contactOutcome != "REACHED"',
            name="Not reached")
    p_call.f("CALL_GW_ContactOutcome", "CALL_Throw_ContactFinished", default=True, name="Spoke to the patient")
    p_call.f("CALL_Auto_LogAttempt", "CALL_GW_Retry")
    p_call.f("CALL_GW_Retry", "CALL_Task_AttemptContact", cond="=contactAttempts < 3",
            name="Try again")
    p_call.f("CALL_GW_Retry", "CALL_Throw_ContactFailed", default=True, name="Give up after three tries")
    p_call.f("CALL_Throw_ContactFinished", "CALL_End_ContactFinished")
    p_call.f("CALL_Throw_ContactFailed", "CALL_End_ContactFailed")
    p_call.mf("CALL_Throw_ContactFinished", "P_OutpatientBookings", "OUT_Catch_PhoneContact")
    p_call.mf("CALL_Throw_ContactFailed", "P_OutpatientBookings", "OUT_Catch_PhoneContact")

    # =====================================================================
    # Patient Pathway Coordinators
    # =====================================================================
    p_pcw.n("PCW_Start_WeeklyReview", "timerstart", "Weekly correspondence review", 0, 0,
            timer="R/PT168H",
            documentation="Runs every week and looks for clinic letters that have slipped past the seven "
                          "day target.")
    p_pcw.n("PCW_Auto_FindOverdue", "stask", "Find clinic letters that are overdue", 1, 0,
            type="pathway.find-overdue-letters", retries=3,
            documentation="Returns the letters still waiting, how long they have been outstanding and "
                          "whether a reminder has already gone out.")
    p_pcw.n("PCW_Task_ReviewOutstanding", "utask", "Review the outstanding correspondence list", 2, 0,
            form="review-outstanding-correspondence", candidate_groups="pathway-coordinators")
    p_pcw.n("PCW_GW_OverdueBand", "xg", "How far overdue is the letter?", 3, 0)
    p_pcw.n("PCW_Auto_SuppressDuplicates", "stask", "Drop letters that no longer need chasing", 4, 1,
            type="pathway.suppress-duplicate-reminders", retries=3,
            documentation="Stops repeat reminders once a letter has been completed or approved.")
    p_pcw.n("PCW_Throw_Reminder", "throw", "Send the weekly reminder to the Consultant", 5, 1,
            msg=b.msg("letter.reminder", K("letter-reminder")), key=K("letter-reminder"),
            headers={"messageName": "letter.reminder"})
    p_pcw.n("PCW_End_Reminded", "end", "Reminder issued", 6, 1)
    p_pcw.n("PCW_Throw_EscalateManager", "throw", "Escalate to the Administrative Manager", 4, 2,
            msg=b.msg("letter.escalation-admin-manager", K("letter-escalation")),
            key=K("letter-escalation"), headers={"messageName": "letter.escalation-admin-manager"})
    p_pcw.n("PCW_End_EscalatedManager", "end", "Escalated to the Administrative Manager", 5, 2)
    p_pcw.n("PCW_Throw_EscalateHigher", "throw", "Escalate beyond three months", 4, 3,
            msg=b.msg("letter.escalation-higher-management", K("letter-escalation")),
            key=K("letter-escalation"), headers={"messageName": "letter.escalation-higher-management"})
    p_pcw.n("PCW_End_EscalatedHigher", "end", "Escalated to higher management", 5, 3)
    p_pcw.f("PCW_Start_WeeklyReview", "PCW_Auto_FindOverdue")
    p_pcw.f("PCW_Auto_FindOverdue", "PCW_Task_ReviewOutstanding")
    p_pcw.f("PCW_Task_ReviewOutstanding", "PCW_GW_OverdueBand")
    p_pcw.f("PCW_GW_OverdueBand", "PCW_Auto_SuppressDuplicates", cond="=letterOverdueDays <= 30",
            name="One week to one month")
    p_pcw.f("PCW_GW_OverdueBand", "PCW_Throw_EscalateManager",
            cond="=letterOverdueDays > 30 and letterOverdueDays <= 90", name="Over one month")
    p_pcw.f("PCW_GW_OverdueBand", "PCW_Throw_EscalateHigher", default=True, name="Over three months")
    p_pcw.f("PCW_Auto_SuppressDuplicates", "PCW_Throw_Reminder")
    p_pcw.f("PCW_Throw_Reminder", "PCW_End_Reminded")
    p_pcw.f("PCW_Throw_EscalateManager", "PCW_End_EscalatedManager")
    p_pcw.f("PCW_Throw_EscalateHigher", "PCW_End_EscalatedHigher")
    p_pcw.mf("PCW_Throw_Reminder", "P_Consultants", "CON_Bnd_LetterReminder")
    p_pcw.mf("PCW_Throw_EscalateManager", "P_AdministrativeManagement", "ADM_Start_ManagerEscalation")
    p_pcw.mf("PCW_Throw_EscalateHigher", "P_AdministrativeManagement", "ADM_Start_HigherEscalation")

    # letters flagged as delayed by the Consultant
    p_pcw.n("PCW_Start_LetterOverdue", "msgstart", "Letter flagged as delayed", 0, 4,
            msg=b.msg("letter.overdue-flagged"))
    p_pcw.n("PCW_Auto_AddToMonitoring", "stask", "Add the letter to pathway monitoring", 1, 4,
            type="pathway.add-to-monitoring", retries=3)
    p_pcw.n("PCW_End_Monitoring", "end", "Letter added to the monitoring list", 2, 4)
    p_pcw.f("PCW_Start_LetterOverdue", "PCW_Auto_AddToMonitoring")
    p_pcw.f("PCW_Auto_AddToMonitoring", "PCW_End_Monitoring")

    # booking delays and pathway reviews
    p_pcw.n("PCW_Start_BookingDelay", "msgstart", "Booking delay flagged by a team", 0, 5,
            msg=b.msg("booking.no-slot-escalation"))
    p_pcw.n("PCW_Start_TreatmentPending", "msgstart", "Treatment booking still pending", 0, 6,
            msg=b.msg("treatment.booking-pending"))
    p_pcw.n("PCW_Start_FollowUpDelay", "msgstart", "Follow-up slot outside the clinical window", 0, 7,
            msg=b.msg("follow-up.no-slot-escalation"))
    p_pcw.n("PCW_Task_ReviewDelay", "utask", "Review the delay and agree the next step", 1, 5,
            form="review-booking-delay", candidate_groups="pathway-coordinators")
    p_pcw.n("PCW_GW_DelayAction", "xg", "What does the delay need?", 2, 5)
    p_pcw.n("PCW_Throw_DelayToClinical", "throw", "Ask the clinical team to reprioritise", 3, 5,
            msg=b.msg("pathway.review-requested", K("pathway-review")), key=K("pathway-review"),
            headers={"messageName": "pathway.review-requested"})
    p_pcw.n("PCW_End_DelayWithClinical", "end", "Delay with the clinical team", 4, 5)
    p_pcw.n("PCW_Auto_SendDelayLetter", "stask", "Write to the patient about the delay", 3, 6,
            type="correspondence.dispatch-letter", retries=3,
            inputs=[('=["patient"]', "letterRecipients")],
            documentation="Same external correspondence service, called straight from the pathway team.")
    p_pcw.n("PCW_End_PatientInformed", "end", "Patient informed", 4, 6)
    p_pcw.f("PCW_Start_BookingDelay", "PCW_Task_ReviewDelay")
    p_pcw.f("PCW_Start_TreatmentPending", "PCW_Task_ReviewDelay")
    p_pcw.f("PCW_Start_FollowUpDelay", "PCW_Task_ReviewDelay")
    p_pcw.f("PCW_Task_ReviewDelay", "PCW_GW_DelayAction")
    p_pcw.f("PCW_GW_DelayAction", "PCW_Throw_DelayToClinical", cond='=delayAction = "CLINICAL_REVIEW"',
            name="Clinical reprioritisation")
    p_pcw.f("PCW_GW_DelayAction", "PCW_Auto_SendDelayLetter", default=True, name="Keep the patient informed")
    p_pcw.f("PCW_Throw_DelayToClinical", "PCW_End_DelayWithClinical")
    p_pcw.f("PCW_Auto_SendDelayLetter", "PCW_End_PatientInformed")
    p_pcw.mf("PCW_Throw_DelayToClinical", "P_Consultants", "CON_Start_PathwayReview")
    p_pcw.mf("PCW_Auto_SendDelayLetter", "P_Correspondence", "P_Correspondence")

    # =====================================================================
    # Administrative Management Team
    # =====================================================================
    p_adm.n("ADM_Start_ManagerEscalation", "msgstart", "Overdue letter escalated to the manager", 0, 0,
            msg=b.msg("letter.escalation-admin-manager"))
    p_adm.n("ADM_Task_ContactConsultant", "utask", "Contact the responsible Consultant", 1, 0,
            form="contact-consultant-overdue-letter", candidate_groups="administrative-management")
    p_adm.n("ADM_GW_ManagerOutcome", "xg", "Has the letter been completed?", 2, 0)
    p_adm.n("ADM_Throw_EscalationRecorded", "throw", "Record the escalation outcome", 3, 0,
            msg=b.msg("letter.escalation-recorded", K("letter-escalation")), key=K("letter-escalation"),
            headers={"messageName": "letter.escalation-recorded"})
    p_adm.n("ADM_End_Recorded", "end", "Escalation recorded", 4, 0)
    p_adm.n("ADM_Start_HigherEscalation", "msgstart", "Letter outstanding beyond three months", 0, 1,
            msg=b.msg("letter.escalation-higher-management"))
    p_adm.n("ADM_Task_ReferHigher", "utask", "Refer the case to higher management", 1, 1,
            form="refer-to-higher-management", candidate_groups="administrative-management")
    p_adm.n("ADM_Throw_HigherRecorded", "throw", "Record the higher level escalation", 2, 1,
            msg=b.msg("letter.escalation-recorded", K("letter-escalation")), key=K("letter-escalation"),
            headers={"messageName": "letter.escalation-recorded"})
    p_adm.n("ADM_End_HigherRecorded", "end", "Higher management escalation recorded", 3, 1)
    p_adm.f("ADM_Start_ManagerEscalation", "ADM_Task_ContactConsultant")
    p_adm.f("ADM_Task_ContactConsultant", "ADM_GW_ManagerOutcome")
    p_adm.f("ADM_GW_ManagerOutcome", "ADM_Throw_EscalationRecorded", cond='=letterNowCompleted = "true"',
            name="Completed - close")
    p_adm.f("ADM_GW_ManagerOutcome", "ADM_Throw_EscalationRecorded", default=True, name="Still outstanding")
    p_adm.f("ADM_Throw_EscalationRecorded", "ADM_End_Recorded")
    p_adm.f("ADM_Start_HigherEscalation", "ADM_Task_ReferHigher")
    p_adm.f("ADM_Task_ReferHigher", "ADM_Throw_HigherRecorded")
    p_adm.f("ADM_Throw_HigherRecorded", "ADM_End_HigherRecorded")

    return b
