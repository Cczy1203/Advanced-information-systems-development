package uk.ac.uwe.ufcep603.hospital.tasks;

import io.camunda.zeebe.client.ZeebeClient;
import uk.ac.uwe.ufcep603.hospital.AbstractHospitalWorker;
import uk.ac.uwe.ufcep603.hospital.JobContext;
import uk.ac.uwe.ufcep603.hospital.ValidationException;
import uk.ac.uwe.ufcep603.hospital.WorkerContext;
import uk.ac.uwe.ufcep603.hospital.support.Ids;

import java.util.Map;
import java.util.Optional;

/**
 * {@code finance.prepare-refund} - Finance Team, "Prepare the approved refund".
 *
 * <p>Checks the refund against the original transaction so the patient is never refunded more than
 * was taken.
 *
 * <p><b>Design decision:</b> a refund larger than the amount paid is reported as a failed job
 * (a {@link ValidationException} naming {@code refundAmount}) rather than as a BPMN error. The model
 * attaches no boundary error event to {@code FIN_Auto_PrepareRefund}, so a BPMN error would have
 * nowhere to go and would leave the instance without a defined route; failing the job raises an
 * incident that Finance must resolve, which is the safe outcome for money leaving the organisation.
 */
public final class FinancePrepareRefundWorker extends AbstractHospitalWorker {

    public static final String JOB_TYPE = "finance.prepare-refund";

    public FinancePrepareRefundWorker(WorkerContext context, ZeebeClient client) {
        super(JOB_TYPE, context, client);
    }

    @Override
    protected Map<String, Object> execute(JobContext job) {
        job.rejectCardData();

        String decision = job.optFirst("refundDecision", "refundDecision", "refundOutcome", "financeDecision");
        String originalPaymentRef = job.optFirst("originalPaymentRef", "originalPaymentRef", "paymentReference",
                "paymentRef", "matchedTransactionRef");
        String patientRef = job.patientKey();

        // How much was actually taken? Prefer the process variable, fall back to the provider record.
        Optional<Double> suppliedPaid = job.optNumberFirst("paidAmount", "paidAmount", "paymentAmount",
                "amountTaken", "chargeAmount");
        Double paidAmount = suppliedPaid.orElseGet(() -> {
            if (patientRef == null || originalPaymentRef == null) {
                return null;
            }
            return context().store().providerPayment(patientRef, originalPaymentRef)
                    .map(record -> ((Number) record.getOrDefault("amount", 0)).doubleValue())
                    .orElse(null);
        });
        if (paidAmount == null) {
            throw new ValidationException("paidAmount",
                    "Cannot check the refund against the original payment: neither 'paidAmount' nor a"
                            + " recorded transaction for payment reference '" + originalPaymentRef
                            + "' is available (job type " + JOB_TYPE + ")");
        }

        Optional<Double> requested = job.optNumberFirst("refundAmount", "refundAmount", "approvedRefundAmount",
                "refundValue");
        double refundAmount = requested.orElse(paidAmount);

        if (refundAmount < 0) {
            throw new ValidationException("refundAmount",
                    "Process variable 'refundAmount' must not be negative but was " + refundAmount
                            + " (job type " + JOB_TYPE + ")");
        }
        if (refundAmount > paidAmount + 0.001) {
            throw new ValidationException("refundAmount",
                    "Refund of " + refundAmount + " exceeds the " + paidAmount + " that was actually taken for"
                            + " payment reference '" + originalPaymentRef + "'. The patient can never be"
                            + " refunded more than was paid (job type " + JOB_TYPE + ")");
        }

        Map<String, Object> output = job.output();
        output.put("refundReference", Ids.reference("REF", originalPaymentRef, patientRef, refundAmount));
        output.put("approvedRefundAmount", refundAmount);
        output.put("refundDecisionRecorded", decision == null ? "NOT_RECORDED" : decision);
        output.put("refundCheckedAgainstPaid", paidAmount);
        output.put("refundPreparedAt", context().clock().timestamp());
        return output;
    }
}
