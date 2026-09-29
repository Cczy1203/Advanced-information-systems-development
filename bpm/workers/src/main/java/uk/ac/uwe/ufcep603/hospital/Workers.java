package uk.ac.uwe.ufcep603.hospital;

import io.camunda.zeebe.client.ZeebeClient;
import uk.ac.uwe.ufcep603.hospital.tasks.AuditRecordClinicalDecisionWorker;
import uk.ac.uwe.ufcep603.hospital.tasks.AuditRecordFinancialDecisionWorker;
import uk.ac.uwe.ufcep603.hospital.tasks.BookingCheckPriorityAndContactRuleWorker;
import uk.ac.uwe.ufcep603.hospital.tasks.BookingCreateAppointmentWorker;
import uk.ac.uwe.ufcep603.hospital.tasks.BookingRecordAppointmentOutcomeWorker;
import uk.ac.uwe.ufcep603.hospital.tasks.CnsRecordClinicalAdviceWorker;
import uk.ac.uwe.ufcep603.hospital.tasks.CorrespondenceDispatchLetterWorker;
import uk.ac.uwe.ufcep603.hospital.tasks.CorrespondencePrepareDispatchWorker;
import uk.ac.uwe.ufcep603.hospital.tasks.EnquiryCloseRecordWorker;
import uk.ac.uwe.ufcep603.hospital.tasks.EnquiryRecordContactAttemptWorker;
import uk.ac.uwe.ufcep603.hospital.tasks.ExternalResourcesCheckAvailabilityWorker;
import uk.ac.uwe.ufcep603.hospital.tasks.FinanceCalculateChargeWorker;
import uk.ac.uwe.ufcep603.hospital.tasks.FinanceCheckDuplicatePaymentWorker;
import uk.ac.uwe.ufcep603.hospital.tasks.FinancePrepareRefundWorker;
import uk.ac.uwe.ufcep603.hospital.tasks.FinanceRecordFundingApprovalWorker;
import uk.ac.uwe.ufcep603.hospital.tasks.FinanceRecordPaymentOutcomeWorker;
import uk.ac.uwe.ufcep603.hospital.tasks.FinanceRecordRefundWorker;
import uk.ac.uwe.ufcep603.hospital.tasks.LetterRecordReminderWorker;
import uk.ac.uwe.ufcep603.hospital.tasks.PathwayAddToMonitoringWorker;
import uk.ac.uwe.ufcep603.hospital.tasks.PathwayFindOverdueClinicLettersWorker;
import uk.ac.uwe.ufcep603.hospital.tasks.PathwaySuppressDuplicateRemindersWorker;
import uk.ac.uwe.ufcep603.hospital.tasks.PaymentPrepareRequestWorker;
import uk.ac.uwe.ufcep603.hospital.tasks.PaymentProcessRefundWorker;
import uk.ac.uwe.ufcep603.hospital.tasks.PaymentProcessTransactionWorker;
import uk.ac.uwe.ufcep603.hospital.tasks.PublishMessageWorker;
import uk.ac.uwe.ufcep603.hospital.tasks.ReferralCheckSupportingDocumentsWorker;
import uk.ac.uwe.ufcep603.hospital.tasks.SchedulingFindAppointmentSlotsWorker;
import uk.ac.uwe.ufcep603.hospital.tasks.TreatmentApplyModificationWorker;
import uk.ac.uwe.ufcep603.hospital.tasks.TreatmentAuthoriseRequestWorker;
import uk.ac.uwe.ufcep603.hospital.tasks.TreatmentConfirmAppointmentsWorker;
import uk.ac.uwe.ufcep603.hospital.tasks.TreatmentCreateAppointmentSeriesWorker;
import uk.ac.uwe.ufcep603.hospital.tasks.TreatmentRecordCapacityRetryWorker;
import uk.ac.uwe.ufcep603.hospital.tasks.TreatmentReleaseCycleBookingWorker;
import uk.ac.uwe.ufcep603.hospital.tasks.TreatmentReleaseSeriesWorker;
import uk.ac.uwe.ufcep603.hospital.tasks.TreatmentScheduleNextCycleWorker;
import uk.ac.uwe.ufcep603.hospital.tasks.TreatmentValidateRequestWorker;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * The explicit worker catalogue: one worker for the {@code publish-message} dispatcher and one for
 * each of the 32 domain service task types in the model.
 *
 * <p>There is no classpath scanning and no reflection. The order below is the order the workers are
 * subscribed at start up and the order they are reported in the log.
 */
public final class Workers {

    private Workers() {
    }

    /**
     * Builds every worker. The returned list has 36 entries: the dispatcher plus the 35 service
     * task types in the v2.0 model.
     */
    public static List<AbstractHospitalWorker> all(WorkerContext context, ZeebeClient client) {
        List<AbstractHospitalWorker> workers = new ArrayList<>(36);

        // 0 - the single message dispatcher for every BPMN message throw event.
        workers.add(new PublishMessageWorker(context, client));

        // 1..32 - one worker per service task job type.
        workers.add(new ReferralCheckSupportingDocumentsWorker(context, client));
        workers.add(new AuditRecordClinicalDecisionWorker(context, client));
        workers.add(new AuditRecordFinancialDecisionWorker(context, client));
        workers.add(new BookingCheckPriorityAndContactRuleWorker(context, client));
        workers.add(new BookingCreateAppointmentWorker(context, client));
        workers.add(new BookingRecordAppointmentOutcomeWorker(context, client));
        workers.add(new TreatmentValidateRequestWorker(context, client));
        workers.add(new TreatmentAuthoriseRequestWorker(context, client));
        workers.add(new TreatmentCreateAppointmentSeriesWorker(context, client));
        workers.add(new TreatmentConfirmAppointmentsWorker(context, client));
        workers.add(new TreatmentScheduleNextCycleWorker(context, client));
        workers.add(new TreatmentApplyModificationWorker(context, client));
        workers.add(new TreatmentReleaseSeriesWorker(context, client));
        workers.add(new TreatmentReleaseCycleBookingWorker(context, client));
        workers.add(new TreatmentRecordCapacityRetryWorker(context, client));
        workers.add(new PaymentPrepareRequestWorker(context, client));
        workers.add(new FinanceCalculateChargeWorker(context, client));
        workers.add(new FinanceRecordFundingApprovalWorker(context, client));
        workers.add(new FinanceCheckDuplicatePaymentWorker(context, client));
        workers.add(new FinanceRecordPaymentOutcomeWorker(context, client));
        workers.add(new FinancePrepareRefundWorker(context, client));
        workers.add(new FinanceRecordRefundWorker(context, client));
        workers.add(new CorrespondencePrepareDispatchWorker(context, client));
        workers.add(new CorrespondenceDispatchLetterWorker(context, client));
        workers.add(new SchedulingFindAppointmentSlotsWorker(context, client));
        workers.add(new ExternalResourcesCheckAvailabilityWorker(context, client));
        workers.add(new PaymentProcessTransactionWorker(context, client));
        workers.add(new PaymentProcessRefundWorker(context, client));
        workers.add(new PathwayFindOverdueClinicLettersWorker(context, client));
        workers.add(new PathwaySuppressDuplicateRemindersWorker(context, client));
        workers.add(new PathwayAddToMonitoringWorker(context, client));
        workers.add(new LetterRecordReminderWorker(context, client));
        workers.add(new EnquiryCloseRecordWorker(context, client));
        workers.add(new EnquiryRecordContactAttemptWorker(context, client));
        workers.add(new CnsRecordClinicalAdviceWorker(context, client));

        return List.copyOf(workers);
    }

    /**
     * Job type to "pool / BPMN step" for the start-up banner and the README. The element ids come
     * from the generated BPMN, so a step can be found in Camunda Modeler by searching for its id.
     */
    public static Map<String, String> bpmnOwners() {
        Map<String, String> owners = new LinkedHashMap<>();
        owners.put(PublishMessageWorker.JOB_TYPE,
                "every pool / every message throw event (intermediate throw + message end events)");
        owners.put(ReferralCheckSupportingDocumentsWorker.JOB_TYPE,
                "Medical Secretaries / SEC_Auto_ValidateDocuments - validate the referral pack");
        owners.put(AuditRecordClinicalDecisionWorker.JOB_TYPE,
                "Consultants / CON_Auto_AuditDecision, CON_Auto_AuditCycle - clinical decision audit trail");
        owners.put(AuditRecordFinancialDecisionWorker.JOB_TYPE,
                "Finance / FIN_Auto_AuditFunding, FIN_Auto_AuditRefund - financial decision audit trail");
        owners.put(BookingCheckPriorityAndContactRuleWorker.JOB_TYPE,
                "Outpatient Bookings / OUT_Auto_CheckPriority - priority, two week rule, contact rule");
        owners.put(BookingCreateAppointmentWorker.JOB_TYPE,
                "Outpatient Bookings / OUT_Auto_CreateAppointment, OUT_Auto_CreateFollowUp - idempotent booking");
        owners.put(BookingRecordAppointmentOutcomeWorker.JOB_TYPE,
                "Outpatient Bookings / OUT_Auto_RecordOutcome - outcome category");
        owners.put(TreatmentValidateRequestWorker.JOB_TYPE,
                "Treatment Bookings / TRT_Auto_ValidateRequest - authorisation check");
        owners.put(TreatmentAuthoriseRequestWorker.JOB_TYPE,
                "Consultants / CON_Auto_AuthoriseRequest - consent and authorisation");
        owners.put(TreatmentCreateAppointmentSeriesWorker.JOB_TYPE,
                "Treatment Bookings / TRT_Auto_CreateSeries - provisional cycle series");
        owners.put(TreatmentConfirmAppointmentsWorker.JOB_TYPE,
                "Treatment Bookings / TRT_Auto_ConfirmAppointments - idempotent confirmation");
        owners.put(TreatmentScheduleNextCycleWorker.JOB_TYPE,
                "Treatment Bookings / TRT_Auto_ScheduleCycle - next cycle date");
        owners.put(TreatmentApplyModificationWorker.JOB_TYPE,
                "Treatment Bookings / TRT_Auto_ApplyModification - apply an authorised change");
        owners.put(TreatmentReleaseSeriesWorker.JOB_TYPE,
                "Treatment Bookings / TRT_Comp_ReleaseSeries - compensation, free the series");
        owners.put(TreatmentReleaseCycleBookingWorker.JOB_TYPE,
                "Treatment Bookings / TRT_Comp_ReleaseCycle - compensation, free the cycle slot");
        owners.put(TreatmentRecordCapacityRetryWorker.JOB_TYPE,
                "Treatment Bookings / TRT_Auto_RecordRetry - count another capacity attempt");
        owners.put(PaymentPrepareRequestWorker.JOB_TYPE,
                "Treatment Bookings / TRT_Auto_PreparePayment, TRT_Auto_NextAttempt - payment reference");
        owners.put(FinanceCalculateChargeWorker.JOB_TYPE,
                "Finance / FIN_Auto_CalculateCharge - tariff and funding category");
        owners.put(FinanceRecordFundingApprovalWorker.JOB_TYPE,
                "Finance / FIN_Auto_RecordApproval - payer, authorisation, amount, limits");
        owners.put(FinanceCheckDuplicatePaymentWorker.JOB_TYPE,
                "Treatment Bookings / TRT_Auto_Deduplicate - repeat charge detection");
        owners.put(FinanceRecordPaymentOutcomeWorker.JOB_TYPE,
                "Finance / FIN_Auto_RecordPayment - record the payment or investigation result");
        owners.put(FinancePrepareRefundWorker.JOB_TYPE,
                "Finance / FIN_Auto_PrepareRefund - refund never exceeds the amount paid");
        owners.put(FinanceRecordRefundWorker.JOB_TYPE,
                "Finance / FIN_Auto_RecordRefund, FIN_Auto_RecordNoRefund - refund record");
        owners.put(CorrespondencePrepareDispatchWorker.JOB_TYPE,
                "Medical Secretaries / SEC_Auto_PrepareDispatch - assemble the letter");
        owners.put(CorrespondenceDispatchLetterWorker.JOB_TYPE,
                "Secretaries, Outpatient Bookings, Treatment Bookings, Pathway Coordinators / "
                        + "SEC_Auto_DispatchLetter, OUT_Auto_DispatchAppointmentLetter, OUT_Auto_SendFollowUpLetter, "
                        + "TRT_Auto_SendTreatmentLetter, PCW_Auto_SendDelayLetter - simulated dispatch");
        owners.put(SchedulingFindAppointmentSlotsWorker.JOB_TYPE,
                "Outpatient Bookings, Treatment Bookings / OUT_Auto_FindSlots, OUT_Auto_FindFollowUpSlots, "
                        + "OUT_Auto_FindRebookSlots, TRT_Auto_FindCycleSlots - simulated scheduling");
        owners.put(ExternalResourcesCheckAvailabilityWorker.JOB_TYPE,
                "Treatment Bookings / TRT_Auto_CheckExternalResources - simulated capacity check");
        owners.put(PaymentProcessTransactionWorker.JOB_TYPE,
                "Treatment Bookings / TRT_Auto_ProcessPayment - simulated provider transaction");
        owners.put(PaymentProcessRefundWorker.JOB_TYPE,
                "Finance / FIN_Auto_ProcessRefund - simulated provider refund");
        owners.put(PathwayFindOverdueClinicLettersWorker.JOB_TYPE,
                "Pathway Coordinators / PCW_Auto_FindOverdue - overdue letters and escalation bands");
        owners.put(PathwayFindOverdueClinicLettersWorker.ALIAS_JOB_TYPE,
                "Pathway Coordinators / PCW_Auto_FindOverdue - accepted alias of "
                        + PathwayFindOverdueClinicLettersWorker.JOB_TYPE);
        owners.put(PathwaySuppressDuplicateRemindersWorker.JOB_TYPE,
                "Pathway Coordinators / PCW_Auto_SuppressDuplicates - one reminder per letter");
        owners.put(PathwayAddToMonitoringWorker.JOB_TYPE,
                "Pathway Coordinators / PCW_Auto_AddToMonitoring - monitoring reference");
        owners.put(LetterRecordReminderWorker.JOB_TYPE,
                "Consultants / CON_Auto_RecordReminder - reminder count against the letter");
        owners.put(EnquiryCloseRecordWorker.JOB_TYPE,
                "Call Handling / CALL_Auto_CloseEnquiry - enquiry status");
        owners.put(EnquiryRecordContactAttemptWorker.JOB_TYPE,
                "Call Handling / CALL_Auto_LogAttempt - contact attempt count");
        owners.put(CnsRecordClinicalAdviceWorker.JOB_TYPE,
                "Clinical Nurse Specialists / CNS_Auto_RecordAdvice - clinical advice record");
        // unmodifiableMap keeps the declaration order, unlike Map.copyOf.
        return java.util.Collections.unmodifiableMap(owners);
    }
}
