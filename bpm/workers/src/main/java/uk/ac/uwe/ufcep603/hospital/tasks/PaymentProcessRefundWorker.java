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
 * {@code payment.process-refund} - <b>simulated</b> External Payment Service Provider,
 * "Process the refund".
 *
 * <p>Refunds the approved amount and reports {@code REFUNDED} / {@code REJECTED} plus the amount
 * actually refunded. The status can be forced with {@code demo.payment.refund-status} /
 * {@code DEMO_REFUND_STATUS} or per instance with {@code simulatedRefundStatus}, so the rejected
 * branch - which the model routes to {@code refund.result-received} with a failed status - is
 * genuinely exercised.
 *
 * <p>The simulated outage throws the BPMN error {@code PAYMENT_PROVIDER_UNAVAILABLE}, which the model
 * catches with the {@code FIN_Bnd_RefundFailed} boundary event and turns into
 * {@code refund.delayed} - the provider is unreachable, the refund is not rejected, and the patient
 * is told it is still pending.
 */
public final class PaymentProcessRefundWorker extends AbstractHospitalWorker {

    public static final String JOB_TYPE = "payment.process-refund";

    private static final List<String> ALLOWED_STATUSES = List.of("REFUNDED", "REJECTED", "PENDING");

    public PaymentProcessRefundWorker(WorkerContext context, ZeebeClient client) {
        super(JOB_TYPE, context, client);
    }

    @Override
    protected Map<String, Object> execute(JobContext job) {
        job.rejectCardData();

        String refundReference = job.requireFirst("refundReference",
                "refundReference", "originalPaymentRef", "paymentReference");
        double approvedAmount = job.numberFirstOr(-1.0, "approvedRefundAmount", "refundAmount", "refundedAmount");
        if (approvedAmount < 0) {
            throw ValidationException.missing("approvedRefundAmount", JOB_TYPE);
        }

        String status = job.optOneOf("simulatedRefundStatus", ALLOWED_STATUSES);
        if (status == null) {
            status = context().config().refundStatus();
            if (!ALLOWED_STATUSES.contains(status)) {
                status = "REFUNDED";
            }
        }

        boolean refunded = "REFUNDED".equals(status) && approvedAmount > 0;
        String effectiveStatus = refunded ? "REFUNDED" : ("PENDING".equals(status) ? "PENDING" : "REJECTED");

        Map<String, Object> output = job.output();
        output.put("refundStatus", effectiveStatus);
        output.put("refundProcessedAt", context().clock().timestamp());
        output.put("refundedAmount", refunded ? approvedAmount : 0.0);
        output.put("refundProviderReference",
                Ids.reference("RFD", refundReference, effectiveStatus, approvedAmount));
        output.put("refundProvider", "SIMULATED-PAYMENT-SERVICE-PROVIDER");
        return output;
    }
}
