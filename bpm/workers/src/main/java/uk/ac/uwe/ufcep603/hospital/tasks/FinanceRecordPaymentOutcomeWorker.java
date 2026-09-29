package uk.ac.uwe.ufcep603.hospital.tasks;

import io.camunda.zeebe.client.ZeebeClient;
import uk.ac.uwe.ufcep603.hospital.AbstractHospitalWorker;
import uk.ac.uwe.ufcep603.hospital.JobContext;
import uk.ac.uwe.ufcep603.hospital.ValidationException;
import uk.ac.uwe.ufcep603.hospital.WorkerContext;
import uk.ac.uwe.ufcep603.hospital.support.Ids;

import java.util.List;
import java.util.Map;

/**
 * {@code finance.record-payment-outcome} - Finance Team, "Record the payment against the account".
 *
 * <p>Runs after a provider result and after a Finance investigation. The investigation path has no
 * {@code paymentStatus} variable, only {@code paymentFound}, so the outcome falls back to that:
 * money that was located is recorded as APPROVED, and {@code paymentConfirmed} is true only for an
 * APPROVED status.
 */
public final class FinanceRecordPaymentOutcomeWorker extends AbstractHospitalWorker {

    public static final String JOB_TYPE = "finance.record-payment-outcome";

    private static final List<String> ALLOWED_STATUSES =
            List.of("APPROVED", "DECLINED", "DUPLICATE", "CONFIRMED", "PENDING", "CANCELLED", "UNKNOWN");

    public FinanceRecordPaymentOutcomeWorker(WorkerContext context, ZeebeClient client) {
        super(JOB_TYPE, context, client);
    }

    @Override
    protected Map<String, Object> execute(JobContext job) {
        job.rejectCardData();

        String status = job.optOneOf("paymentStatus", ALLOWED_STATUSES);
        if (status == null) {
            status = job.optOneOf("paymentOutcome", ALLOWED_STATUSES);
        }
        if (status == null) {
            // Investigation path: no provider status, only the outcome of the reconciliation.
            boolean paymentFound = job.boolOr("paymentFound", false);
            status = paymentFound ? "CONFIRMED" : "UNKNOWN";
        }

        String paymentReference = job.optFirst("paymentRef", "paymentRef", "paymentReference",
                "resolvedPaymentReference", "transactionReference", "matchedTransactionRef");
        String patientRef = job.patientKey();
        if (paymentReference == null && patientRef == null) {
            throw ValidationException.missing("paymentRef", JOB_TYPE);
        }
        if (paymentReference == null) {
            paymentReference = Ids.reference("PAY-UNKNOWN", patientRef);
        }

        double paidAmount = job.numberFirstOr(0.0, "paidAmount", "amountTaken", "chargeAmount");
        boolean confirmed = "APPROVED".equals(status) || "CONFIRMED".equals(status);

        Map<String, Object> output = job.output();
        output.put("paymentRecordedRef", Ids.reference("PRC", patientRef, paymentReference, status));
        output.put("paymentConfirmed", confirmed);
        output.put("paymentRecordedStatus", status);
        output.put("paymentRecordedAmount", paidAmount);
        output.put("paymentRecordedAt", context().clock().timestamp());
        return output;
    }
}
