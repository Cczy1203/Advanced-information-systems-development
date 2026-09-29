package uk.ac.uwe.ufcep603.hospital.tasks;

import io.camunda.zeebe.client.ZeebeClient;
import uk.ac.uwe.ufcep603.hospital.AbstractHospitalWorker;
import uk.ac.uwe.ufcep603.hospital.JobContext;
import uk.ac.uwe.ufcep603.hospital.WorkerContext;
import uk.ac.uwe.ufcep603.hospital.support.Ids;

import java.util.Map;

/**
 * {@code audit.record-clinical-decision} - Consultants,
 * "Write the clinical decision to the audit trail" (also used for the chemotherapy cycle review).
 *
 * <p>The audit record is immutable: the clinical variables are <em>read</em>, never written back, so
 * a later clinical update cannot be overwritten by a retried audit job. Only the audit reference and
 * its timestamp are added to the process.
 *
 * <p>{@code patientRef} is required and is a plain job failure when blank (no BPMN error boundary
 * exists for it, and a missing patient reference is a data problem rather than a business outcome).
 * The audit reference is deterministic, so the three engine retries cannot produce three audit rows.
 */
public final class AuditRecordClinicalDecisionWorker extends AbstractHospitalWorker {

    public static final String JOB_TYPE = "audit.record-clinical-decision";

    public AuditRecordClinicalDecisionWorker(WorkerContext context, ZeebeClient client) {
        super(JOB_TYPE, context, client);
    }

    @Override
    protected Map<String, Object> execute(JobContext job) {
        // Hard requirement: no audit record without a patient.
        String patientRef = job.require("patientRef");
        String decision = job.requireFirst("clinicalDecision",
                "clinicalDecision", "cycleReviewOutcome", "clinicalOutcome", "decision", "cycleDecision");
        String reason = job.optFirst("clinicalDecisionReason", "clinicalDecisionReason", "decisionReason",
                "cycleReviewNotes", "reason");
        String clinician = job.requireFirst("decidingClinician",
                "decidingClinician", "reviewClinician", "clinicianName", "clinician", "decidedBy",
                "consultantName");

        String auditRef = Ids.reference("AUD-CLIN", patientRef, decision, reason, clinician);

        Map<String, Object> output = job.output();
        output.put("clinicalDecisionAuditRef", auditRef);
        output.put("clinicalDecisionAuditAt", context().clock().timestamp());
        // Deliberately not echoed back: clinicalDecision, clinicalDecisionReason, decidingClinician.
        return output;
    }
}
