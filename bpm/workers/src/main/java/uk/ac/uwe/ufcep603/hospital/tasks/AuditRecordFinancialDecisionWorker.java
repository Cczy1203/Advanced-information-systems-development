package uk.ac.uwe.ufcep603.hospital.tasks;

import io.camunda.zeebe.client.ZeebeClient;
import uk.ac.uwe.ufcep603.hospital.AbstractHospitalWorker;
import uk.ac.uwe.ufcep603.hospital.JobContext;
import uk.ac.uwe.ufcep603.hospital.WorkerContext;
import uk.ac.uwe.ufcep603.hospital.support.Ids;

import java.util.Map;

/**
 * {@code audit.record-financial-decision} - Finance Team,
 * "Record the funding decision for audit" and "Record the refund decision for audit".
 *
 * <p>The same worker serves both finance audit steps, so it accepts the funding vocabulary and the
 * refund vocabulary. {@code patientRef} is required and fails the job when blank; the decision
 * itself is also required, because an audit row that does not say what was decided is worthless.
 * Financial variables are never written back - only the audit reference is added.
 */
public final class AuditRecordFinancialDecisionWorker extends AbstractHospitalWorker {

    public static final String JOB_TYPE = "audit.record-financial-decision";

    public AuditRecordFinancialDecisionWorker(WorkerContext context, ZeebeClient client) {
        super(JOB_TYPE, context, client);
    }

    @Override
    protected Map<String, Object> execute(JobContext job) {
        String patientRef = job.require("patientRef");
        String decision = job.requireFirst("financialDecision",
                "financialDecision", "fundingDecision", "refundDecision", "financeDecision", "fundingRoute",
                "impactAction", "outcome", "decision");
        String reason = job.optFirst("financialDecisionReason",
                "financialDecisionReason", "fundingReason", "refundReason", "decisionReason", "impactNotes",
                "chaseNotes", "reason");
        String officer = job.requireFirst("decidingFinanceOfficer",
                "decidingFinanceOfficer", "decidedBy", "financeOfficerName", "financeOfficer",
                "authorisedBy", "chasedBy", "pricedBy", "reviewedBy", "answeredBy",
                "decidingClinician", "decidingAdminOfficer");
        String decisionSubject = job.optFirst("fundingRoute", "fundingRoute", "refundReference",
                "originalPaymentRef", "paymentReference");

        String auditRef = Ids.reference("AUD-FIN", patientRef, decision, reason, officer, decisionSubject);

        Map<String, Object> output = job.output();
        output.put("financialDecisionAuditRef", auditRef);
        output.put("financialDecisionAuditAt", context().clock().timestamp());
        return output;
    }
}
