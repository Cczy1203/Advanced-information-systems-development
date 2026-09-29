package uk.ac.uwe.ufcep603.hospital.tasks;

import io.camunda.zeebe.client.ZeebeClient;
import uk.ac.uwe.ufcep603.hospital.AbstractHospitalWorker;
import uk.ac.uwe.ufcep603.hospital.JobContext;
import uk.ac.uwe.ufcep603.hospital.ValidationException;
import uk.ac.uwe.ufcep603.hospital.WorkerContext;
import uk.ac.uwe.ufcep603.hospital.support.Ids;

import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * {@code finance.record-refund} - Finance Team, "Record the refund against the patient account" and
 * "Record that no refund is due".
 *
 * <p>Both model paths use this job type, so the status may legitimately be absent on the
 * "no refund is due" route: the decision variable is then recorded instead and
 * {@code refundCompleted} is false. {@code refundCompleted} is true only for a REFUNDED status.
 */
public final class FinanceRecordRefundWorker extends AbstractHospitalWorker {

    public static final String JOB_TYPE = "finance.record-refund";

    private static final List<String> ALLOWED_STATUSES = List.of(
            "REFUNDED", "REJECTED", "PENDING", "DECLINED", "NOT_DUE", "NO_REFUND", "NO_REFUND_DUE", "CANCELLED");

    public FinanceRecordRefundWorker(WorkerContext context, ZeebeClient client) {
        super(JOB_TYPE, context, client);
    }

    @Override
    protected Map<String, Object> execute(JobContext job) {
        job.rejectCardData();

        String status = job.optOneOf("refundStatus", ALLOWED_STATUSES);
        if (status == null) {
            status = job.optOneOf("refundOutcome", ALLOWED_STATUSES);
        }
        if (status == null) {
            String decision = job.optFirst("refundDecision", "refundDecision", "financeDecision");
            if (decision != null) {
                String upper = decision.toUpperCase(Locale.ROOT);
                status = ALLOWED_STATUSES.contains(upper) ? upper : "NOT_DUE";
            } else {
                status = "NOT_DUE";
            }
        }

        String reference = job.optFirst("refundReference", "refundReference", "originalPaymentRef",
                "paymentReference", "paymentRef");
        String patientRef = job.optFirst("patientRef", "patientRef", "patientReference", "patientId");
        if (reference == null && patientRef == null) {
            throw ValidationException.missing("refundReference", JOB_TYPE);
        }
        if (reference == null) {
            reference = Ids.reference("REF-NONE", patientRef);
        }

        double refundAmount = job.numberFirstOr(0.0, "refundAmount", "approvedRefundAmount", "refundedAmount");
        boolean completed = "REFUNDED".equals(status);

        Map<String, Object> output = job.output();
        output.put("refundRecordedRef", Ids.reference("REF-REC", reference, status, refundAmount));
        output.put("refundCompleted", completed);
        output.put("refundStatusRecorded", status);
        output.put("refundedAmount", completed ? refundAmount : 0.0);
        output.put("refundRecordedAt", context().clock().timestamp());
        return output;
    }
}
