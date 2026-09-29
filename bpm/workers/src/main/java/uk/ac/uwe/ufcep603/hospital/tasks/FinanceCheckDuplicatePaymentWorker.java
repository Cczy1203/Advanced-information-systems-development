package uk.ac.uwe.ufcep603.hospital.tasks;

import io.camunda.zeebe.client.ZeebeClient;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import uk.ac.uwe.ufcep603.hospital.AbstractHospitalWorker;
import uk.ac.uwe.ufcep603.hospital.JobContext;
import uk.ac.uwe.ufcep603.hospital.WorkerContext;
import uk.ac.uwe.ufcep603.hospital.support.Ids;

import java.util.Map;
import java.util.Optional;

/**
 * {@code finance.check-duplicate-payment} - Treatment and Chemotherapy Bookings Team,
 * "Check the charge has not already been taken".
 *
 * <p>Runs when the provider reports a duplicate, and before any further attempt is made. A repeat is
 * any {@code paymentReference} already recorded against the same {@code patientRef}, either because
 * this worker has seen it before or because the (simulated) provider recorded a transaction for it.
 * A duplicate is never charged again: the resolved reference is a new investigation reference and
 * {@code duplicateChargeFound} is {@code true}, which is what stops the pathway asking the patient
 * for money twice.
 */
public final class FinanceCheckDuplicatePaymentWorker extends AbstractHospitalWorker {

    public static final String JOB_TYPE = "finance.check-duplicate-payment";

    private static final Logger LOG = LoggerFactory.getLogger(FinanceCheckDuplicatePaymentWorker.class);

    public FinanceCheckDuplicatePaymentWorker(WorkerContext context, ZeebeClient client) {
        super(JOB_TYPE, context, client);
    }

    @Override
    protected Map<String, Object> execute(JobContext job) {
        job.rejectCardData();

        String paymentReference = job.requireFirst("paymentReference",
                "paymentReference", "paymentRef", "resolvedPaymentReference", "transactionReference",
                "matchedTransactionRef");
        String patientRef = job.requirePatientKey();
        double paidAmount = job.numberFirstOr(0.0, "paidAmount", "amountTaken", "chargeAmount");

        boolean seenBefore = context().store().markPaymentReference(patientRef, paymentReference);
        Optional<Map<String, Object>> providerRecord =
                context().store().providerPayment(patientRef, paymentReference);
        boolean duplicate = seenBefore || providerRecord.isPresent();

        String resolved = duplicate
                ? Ids.reference("PAY-INV", patientRef, paymentReference)
                : paymentReference;

        if (duplicate) {
            LOG.warn("duplicate charge detected for patient {}: reference {} has already been recorded"
                            + " (seenBefore={}, providerRecord={})",
                    patientRef, paymentReference, seenBefore, providerRecord.isPresent());
        }

        Map<String, Object> output = job.output();
        output.put("duplicateChargeFound", duplicate);
        output.put("resolvedPaymentReference", resolved);
        output.put("duplicateChargeCheckedAt", context().clock().timestamp());
        output.put("duplicateChargeAmount", paidAmount);
        output.put("duplicateChargeEvidence",
                duplicate ? (seenBefore ? "ALREADY_CHECKED" : "PROVIDER_RECORD") : "NO_DUPLICATE");
        return output;
    }
}
