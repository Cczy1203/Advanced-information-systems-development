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
 * {@code finance.record-funding-approval} - Finance Team, "Record the funding approval".
 *
 * <p>Records the responsible organisation, the authorisation reference, the approved amount and any
 * limits attached to the approval. A payer-funded route without a payer name, or without an
 * authorisation reference, is rejected: invoicing a third party that has not authorised the
 * treatment is a finance error, not a business outcome, so the job fails with a message that names
 * the offending variable rather than throwing a BPMN error.
 */
public final class FinanceRecordFundingApprovalWorker extends AbstractHospitalWorker {

    public static final String JOB_TYPE = "finance.record-funding-approval";

    /** Routes where somebody other than the hospital pays and therefore must be identified. */
    private static final List<String> PAYER_FUNDED_ROUTES =
            List.of("INSURER_APPROVED", "INSURER", "PRIVATE_INSURER", "PRIVATE", "OVERSEAS_INSURER", "SPONSOR");

    public FinanceRecordFundingApprovalWorker(WorkerContext context, ZeebeClient client) {
        super(JOB_TYPE, context, client);
    }

    @Override
    protected Map<String, Object> execute(JobContext job) {
        job.rejectCardData();

        String fundingRoute = job.requireFirst("fundingRoute",
                "fundingRoute", "fundingSource", "fundingDecision", "payerType").toUpperCase(Locale.ROOT);
        String funderName = job.optFirst("funderName", "funderName", "payerName", "responsibleOrganisation",
                "insurerName", "sponsorName");
        String authorisationRef = job.optFirst("authorisationRef", "authorisationRef", "authorizationRef",
                "preAuthorisationRef", "approvalReference", "fundingAuthorisationRef");
        double approvedAmount = job.numberOr("approvedAmount", job.numberOr("chargeAmount", 0.0));
        List<String> limitations = job.optStringList("fundingLimitations");

        boolean payerFunded = PAYER_FUNDED_ROUTES.stream().anyMatch(fundingRoute::contains)
                || fundingRoute.contains("INSUR") || fundingRoute.contains("PRIVATE");
        if (payerFunded && funderName == null) {
            throw new ValidationException("funderName",
                    "Funding route '" + fundingRoute + "' is payer funded, so the responsible payer must be"
                            + " named in 'funderName' (job type " + JOB_TYPE + ")");
        }
        if (payerFunded && authorisationRef == null) {
            throw new ValidationException("authorisationRef",
                    "Funding route '" + fundingRoute + "' is payer funded, so the payer's authorisation"
                            + " reference must be recorded in 'authorisationRef' (job type " + JOB_TYPE + ")");
        }
        if (approvedAmount < 0) {
            throw new ValidationException("approvedAmount",
                    "Process variable 'approvedAmount' must not be negative but was " + approvedAmount
                            + " (job type " + JOB_TYPE + ")");
        }

        Map<String, Object> output = job.output();
        output.put("fundingApprovalRecordedRef",
                Ids.reference("FUND", job.opt("patientRef"), fundingRoute, funderName, authorisationRef, approvedAmount));
        output.put("fundingApprovalRecordedAt", context().clock().timestamp());
        output.put("fundingRouteRecorded", fundingRoute);
        output.put("funderNameRecorded", funderName == null ? "HOSPITAL" : funderName);
        output.put("approvedAmountRecorded", approvedAmount);
        output.put("fundingLimitationsRecorded", limitations);
        return output;
    }
}
