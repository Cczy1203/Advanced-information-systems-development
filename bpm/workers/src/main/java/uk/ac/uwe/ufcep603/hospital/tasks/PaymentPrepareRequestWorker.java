package uk.ac.uwe.ufcep603.hospital.tasks;

import io.camunda.zeebe.client.ZeebeClient;
import uk.ac.uwe.ufcep603.hospital.AbstractHospitalWorker;
import uk.ac.uwe.ufcep603.hospital.JobContext;
import uk.ac.uwe.ufcep603.hospital.ValidationException;
import uk.ac.uwe.ufcep603.hospital.WorkerContext;
import uk.ac.uwe.ufcep603.hospital.support.Ids;

import java.util.Locale;
import java.util.Map;

/**
 * {@code payment.prepare-request} - Treatment and Chemotherapy Bookings Team,
 * "Prepare the secure payment request" and "Record the next payment attempt".
 *
 * <p>Creates the payment reference for one attempt. The reference is a deterministic function of
 * the patient, the attempt number and the amount, which is what makes the provider-side duplicate
 * detection meaningful: the same attempt always produces the same reference, a new attempt produces
 * a new one (which is also a new message correlation key, so the provider is never asked twice for
 * the same charge).
 *
 * <p>{@code paymentAttempt} is preserved when the model already set it (the second entry point maps
 * {@code =paymentAttempt + 1} into it) and defaults to 1 otherwise. Card data is refused outright:
 * the hospital system must never hold it.
 */
public final class PaymentPrepareRequestWorker extends AbstractHospitalWorker {

    public static final String JOB_TYPE = "payment.prepare-request";

    public PaymentPrepareRequestWorker(WorkerContext context, ZeebeClient client) {
        super(JOB_TYPE, context, client);
    }

    @Override
    protected Map<String, Object> execute(JobContext job) {
        job.rejectCardData();

        String patientRef = job.requirePatientKey();
        double chargeAmount = job.requireNumber("chargeAmount");
        if (chargeAmount < 0) {
            throw new ValidationException("chargeAmount",
                    "Process variable 'chargeAmount' must not be negative but was " + chargeAmount
                            + " (job type " + JOB_TYPE + ")");
        }
        String currency = job.optFirst("currency", "currency", "currencyCode");
        currency = currency == null ? "GBP" : currency.toUpperCase(Locale.ROOT);

        int paymentAttempt = job.intOr("paymentAttempt", 1);
        if (paymentAttempt < 1) {
            throw new ValidationException("paymentAttempt",
                    "Process variable 'paymentAttempt' must be 1 or more but was " + paymentAttempt
                            + " (job type " + JOB_TYPE + ")");
        }

        Map<String, Object> output = job.output();
        output.put("paymentReference", Ids.reference("PAY", patientRef, paymentAttempt, chargeAmount, currency));
        output.put("paymentRequestedAt", context().clock().timestamp());
        output.put("paymentAttempt", paymentAttempt);
        output.put("paymentAmount", chargeAmount);
        output.put("paymentCurrency", currency);
        return output;
    }
}
