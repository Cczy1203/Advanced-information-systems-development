package uk.ac.uwe.ufcep603.hospital.support;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import uk.ac.uwe.ufcep603.hospital.JobContext;
import uk.ac.uwe.ufcep603.hospital.WorkerContext;

import java.util.Optional;

/**
 * Translates a "job type" into "which role, on which kind of business resource, performing
 * which action", then hands it to
 * {@link uk.ac.uwe.ufcep603.hospital.db.AccessControl} for the decision and the audit record.
 *
 * <p>Why this layer exists: an external worker does its work behind a user task, and the job
 * itself does not carry "who pressed the button". The {@code candidateGroups} on the user
 * task already restrict, at the Camunda level, **who may claim** the task; this class fills
 * in the second half: "once it has been claimed and submitted, which role may perform this
 * kind of business action".
 *
 * <p>The mapping is keyed on the **prefix** of the job type, that is, the business domain in
 * the model, so the rules are collected in this one class and there is a single place to
 * change them. A job type with no matching prefix takes no part in the decision and is not
 * audited either: rather than putting role=null noise into the audit table, it is
 * deliberately not recorded, and the reason is set out here.
 *
 * <p>About {@code enforce}: it is on by default. Every (role, resource, action) combination
 * in the mapping below is present in the permission matrix in {@code db/seed.sql}, so
 * enabling it does not interrupt any normal job, while an unauthorised combination (for
 * example an audit role attempting to raise a refund) is blocked and recorded as DENY.
 */
public final class JobSecurity {

    private static final Logger LOG = LoggerFactory.getLogger(JobSecurity.class);

    /** One decision rule: (role, business resource, action). */
    public record Policy(String roleId, String resourceType, String action) {
    }

    private JobSecurity() {
    }

    /**
     * Resolves the permission required by a job type prefix.
     *
     * <p>Each prefix corresponds one-to-one with a business domain in the BPMN (referral,
     * finance, treatment and so on), so a new job in the same domain in the model
     * automatically falls under the same rule and there is no long list to keep in step.
     */
    public static Optional<Policy> policyFor(String jobType) {
        if (jobType == null) {
            return Optional.empty();
        }
        String type = jobType.trim().toLowerCase(java.util.Locale.ROOT);
        if (type.startsWith("referral.")) {
            return Optional.of(new Policy("medical-secretaries", "REFERRAL", "READ"));
        }
        if (type.startsWith("correspondence.")) {
            return Optional.of(new Policy("medical-secretaries", "CLINIC_LETTER", "DISPATCH"));
        }
        if (type.startsWith("audit.")) {
            return Optional.of(new Policy("auditor", "AUDIT_LOG", "READ"));
        }
        if (type.startsWith("booking.") || type.startsWith("scheduling.")) {
            return Optional.of(new Policy("outpatient-bookings", "APPOINTMENT", "WRITE"));
        }
        if (type.startsWith("treatment.")) {
            return Optional.of(new Policy("treatment-bookings", "TREATMENT_SERIES", "WRITE"));
        }
        if (type.startsWith("payment.") || type.startsWith("finance.")) {
            return Optional.of(new Policy("finance", "PAYMENT", "WRITE"));
        }
        if (type.startsWith("pathway.") || type.startsWith("letter.")) {
            return Optional.of(new Policy("pathway-coordinators", "PATHWAY_MONITORING", "WRITE"));
        }
        if (type.startsWith("enquiry.")) {
            return Optional.of(new Policy("call-handling", "ENQUIRY", "WRITE"));
        }
        if (type.startsWith("cns.")) {
            return Optional.of(new Policy("clinical-nurse-specialists", "ENQUIRY", "WRITE"));
        }
        // publish-message is the shared dispatcher for every message throw event in the model
        // and belongs to no single business domain, so it takes no part in the RBAC decision
        // (its authorisation comes from the MESSAGE resource at the Camunda level).
        return Optional.empty();
    }

    /**
     * Makes the permission decision for one job and writes the audit record.
     *
     * <ul>
     *   <li>{@code security.enabled=false}: skipped entirely, behaviour identical to v14;</li>
     *   <li>{@code security.enforce=false}: audit only, nothing is blocked (for observation);</li>
     *   <li>default (both enabled): an unauthorised job throws {@code ValidationException},
     *       the job fails and a DENY record is left behind.</li>
     * </ul>
     */
    public static void audit(WorkerContext context, JobContext job) {
        if (context.accessControl() == null || !context.config().securityEnabled()) {
            return;
        }
        Optional<Policy> resolved = policyFor(job.jobType());
        if (resolved.isEmpty()) {
            LOG.debug("No RBAC rule matches job type {}, skipping the decision", job.jobType());
            return;
        }
        Policy policy = resolved.get();
        String actor = actorFor(job);
        String resourceId = job.optFirst("patientRef", "patientReference", "letterRef", "referralRef",
                "treatmentBookingRef", "paymentReference", "enquiryRef");

        if (context.config().securityEnforce()) {
            context.accessControl().require(actor, policy.roleId(), job.jobType(),
                    job.processInstanceKey(), policy.resourceType(), policy.action(), resourceId);
        } else {
            context.accessControl().record(actor, policy.roleId(), job.jobType(), job.processInstanceKey(),
                    policy.resourceType(), policy.action(), resourceId,
                    "audit only (security.enforce=false)");
        }
    }

    /**
     * The "actor" recorded in the audit entry.
     *
     * <p>A service task has no logged-in user behind it, so the {@code actingUser} process
     * variable is used (the "handled by" value entered on the user task is normally carried
     * into the process). If it is absent, the job's worker name is used instead, which at
     * least identifies which worker did the work.
     */
    private static String actorFor(JobContext job) {
        String actor = job.optFirst("actingUser", "completedBy", "receivedBy", "recordedBy", "reviewedBy");
        return actor != null && !actor.isBlank() ? actor : "worker:" + job.jobType();
    }
}
