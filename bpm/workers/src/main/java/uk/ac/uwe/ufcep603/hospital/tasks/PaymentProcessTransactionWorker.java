package uk.ac.uwe.ufcep603.hospital.tasks;

import io.camunda.zeebe.client.ZeebeClient;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import uk.ac.uwe.ufcep603.hospital.AbstractHospitalWorker;
import uk.ac.uwe.ufcep603.hospital.BpmnErrorException;
import uk.ac.uwe.ufcep603.hospital.JobContext;
import uk.ac.uwe.ufcep603.hospital.ValidationException;
import uk.ac.uwe.ufcep603.hospital.WorkerContext;
import uk.ac.uwe.ufcep603.hospital.support.Ids;

import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * {@code payment.process-transaction} - <b>simulated</b> External Payment Service Provider,
 * "Process the card transaction".
 *
 * <p>Returns a status, a transaction reference, the payment date and the amount taken. <b>No card
 * data is ever accepted or returned</b>: a card-like process variable fails the job outright.
 *
 * <p>Branches:
 * <ul>
 *   <li>{@code APPROVED} (the default) - the provider records the transaction so that a later
 *       duplicate check can find it;</li>
 *   <li>{@code DECLINED} - reported back, nothing recorded;</li>
 *   <li>{@code DUPLICATE} - reported back, which routes the caller into
 *       {@code finance.check-duplicate-payment};</li>
 *   <li>{@code NO_CONFIRMATION} - the "confirmation lost" scenario: the provider took the money but
 *       the answer never arrived. The worker <em>fails the job</em> so the engine retry policy
 *       applies and the process eventually holds an incident, leaving the caller's {@code PT2H}
 *       timer to fire and send the case to Finance for investigation. Nothing is published.</li>
 * </ul>
 *
 * <p>Throws the BPMN error {@code PAYMENT_PROVIDER_UNAVAILABLE} when the simulated failure injection
 * is switched on.
 *
 * <p>The status can be forced with {@code demo.payment.status} /
 * {@code DEMO_PAYMENT_STATUS}, or per instance with the {@code simulatedPaymentStatus} variable.
 */
public final class PaymentProcessTransactionWorker extends AbstractHospitalWorker {

    public static final String JOB_TYPE = "payment.process-transaction";

    private static final String PAYMENT_CONFIRMATION_LOST = "PAYMENT_CONFIRMATION_LOST";
    private static final String NO_CONFIRMATION = "NO_CONFIRMATION";
    private static final List<String> ALLOWED_STATUSES =
            List.of("APPROVED", "DECLINED", "DUPLICATE", "CANCELLED", "NO_CONFIRMATION");

    private static final Logger LOG = LoggerFactory.getLogger(PaymentProcessTransactionWorker.class);

    public PaymentProcessTransactionWorker(WorkerContext context, ZeebeClient client) {
        super(JOB_TYPE, context, client);
    }

    @Override
    protected Map<String, Object> execute(JobContext job) {
        job.rejectCardData();

        String status = job.optOneOf("simulatedPaymentStatus", ALLOWED_STATUSES);
        if (status == null) {
            status = job.optOneOf("forcedPaymentStatus", ALLOWED_STATUSES);
        }
        if (status == null) {
            status = context().failures().paymentStatus();
        }

        if (NO_CONFIRMATION.equals(status)) {
            if ("RETRY".equals(context().config().confirmationLostMode())) {
                LOG.warn("simulated lost confirmation for payment reference {} (element {}) - failing the job"
                                + " on purpose so the engine retries and the caller's timer fires",
                        job.opt("paymentReference"), job.elementId());
                context().failures().failForLostConfirmation(JOB_TYPE);
            }
            // Default: the model carries a PAYMENT_CONFIRMATION_LOST boundary event on the payment
            // service task, so the provider reports the lost confirmation as a business error and the
            // token is routed to Finance for investigation instead of being charged twice.
            throw new BpmnErrorException(PAYMENT_CONFIRMATION_LOST,
                    "Payment provider took the payment but returned no confirmation for reference '"
                            + job.opt("paymentReference") + "'. The transaction must be investigated before"
                            + " the patient is charged again (element " + job.elementId() + ")");
        }

        String paymentReference = job.requireFirst("paymentReference",
                "paymentReference", "paymentRef", "transactionReference", "resolvedPaymentReference");
        String patientRef = job.optFirst("patientRef", "patientRef", "patientReference", "patientId");
        double chargeAmount = job.numberFirstOr(-1.0, "chargeAmount", "paymentAmount", "approvedAmount");
        if (chargeAmount < 0) {
            throw ValidationException.missing("chargeAmount", JOB_TYPE);
        }

        String effectiveStatus = "CANCELLED".equals(status) ? "DECLINED" : status;
        double paidAmount = "APPROVED".equals(effectiveStatus) ? chargeAmount : 0.0;

        if (patientRef != null) {
            context().store().recordProviderPayment(patientRef, paymentReference, effectiveStatus, paidAmount);
        }

        Map<String, Object> output = job.output();
        output.put("paymentStatus", effectiveStatus);
        output.put("paymentRef", Ids.reference("TXN", patientRef, paymentReference, effectiveStatus));
        output.put("paymentDate", context().clock().today().toString());
        output.put("paidAmount", paidAmount);
        output.put("paymentReferenceProcessed", paymentReference);
        output.put("paymentCurrency", currencyOrDefault(job));
        output.put("paymentProvider", "SIMULATED-PAYMENT-SERVICE-PROVIDER");
        // No card data, no card token, no authorisation code: only what the hospital is allowed to hold.
        return output;
    }

    private static String currencyOrDefault(JobContext job) {
        String currency = job.optFirst("currency", "currency", "paymentCurrency");
        return currency == null ? "GBP" : currency.toUpperCase(Locale.ROOT);
    }
}
