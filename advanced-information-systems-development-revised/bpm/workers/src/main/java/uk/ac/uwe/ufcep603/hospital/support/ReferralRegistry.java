package uk.ac.uwe.ufcep603.hospital.support;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import uk.ac.uwe.ufcep603.hospital.JobContext;
import uk.ac.uwe.ufcep603.hospital.ValidationException;
import uk.ac.uwe.ufcep603.hospital.config.AppConfig;
import uk.ac.uwe.ufcep603.hospital.db.NhsNumber;
import uk.ac.uwe.ufcep603.hospital.db.ReferenceData;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Optional;

/**
 * Checks a job's input against the **reference data held in the database**.
 *
 * <p>This class addresses the tutor feedback that "the database should not only store results but
 * also take part in business decisions":
 * <ul>
 *   <li>"Add GP validation by checking details against the database" — check whether the GP
 *       practice still accepts referrals;</li>
 *   <li>"Validate NHS numbers to ensure that they contain exactly 10 digits, with database
 *       checks to verify patient details" — validate the number itself with the modulus 11
 *       check, then look it up in the patient master index;</li>
 *   <li>"Retrieve and use existing database records within the process" — on a hit, copy the
 *       patient name, NHS number and GP practice back into process variables for later steps.</li>
 * </ul>
 *
 * <p>The strictness trade-off is described on
 * {@link AppConfig#databaseValidationStrictPatient()}: the default is lenient — a database
 * lookup is required only when the process **actually carries an NHS number**; when it carries
 * an ordinary {@code patientRef} that the database does not know, the record is simply not
 * enriched and the check does not fail. This demonstrates the database taking part in the
 * business logic without breaking the whole main path just because a demonstration script
 * happens to use an identifier that is missing from the reference data.
 *
 * <p>Violations always throw {@link ValidationException} (rather than a BPMN error), for the
 * reason given in that class: only business conditions declared as {@code bpmn:error} in the
 * model are reported as BPMN errors.
 */
public final class ReferralRegistry {

    private static final Logger LOG = LoggerFactory.getLogger(ReferralRegistry.class);

    /** Enrichment variables use the {@code registered} prefix to avoid form field clashes. */
    public static final String VAR_PATIENT_NAME = "registeredPatientName";
    public static final String VAR_PATIENT_NHS = "registeredPatientNhsNumber";
    public static final String VAR_GP_CODE = "registeredGpPracticeCode";
    public static final String VAR_GP_NAME = "registeredGpPracticeName";
    public static final String VAR_GP_ACCEPTING = "registeredGpAcceptingReferrals";

    private final AppConfig config;
    private final ReferenceData referenceData;

    public ReferralRegistry(AppConfig config, ReferenceData referenceData) {
        this.config = config;
        this.referenceData = referenceData;
    }

    /**
     * Verifies the job input and writes back anything it finds.
     *
     * @return additional variables to merge into the job output; an empty map when there is
     *         nothing to enrich
     * @throws ValidationException the NHS number is invalid, it matches no patient, or the GP
     *         practice has stopped accepting referrals
     */
    public Map<String, Object> verify(JobContext job) {
        Map<String, Object> enrichment = new LinkedHashMap<>();
        if (!config.databaseValidationEnabled()) {
            return enrichment;
        }

        // ---- 1) If the process carries an NHS number, validate it and then look it up ----
        String nhs = job.optFirst("patientNhsNumber", "nhsNumber");
        if (nhs != null && !nhs.isBlank()) {
            Optional<String> problem = NhsNumber.problemWith(nhs);
            if (problem.isPresent()) {
                throw new ValidationException("patientNhsNumber",
                        "NHS number check failed: " + problem.get() + " (job type " + job.jobType() + ")");
            }
            String cleaned = NhsNumber.normalise(nhs);
            Optional<ReferenceData.PatientRecord> byNhs = referenceData.patientByNhsNumber(cleaned);
            if (byNhs.isEmpty()) {
                throw ValidationException.unknownRecord("patientNhsNumber", "patient record", cleaned,
                        job.jobType());
            }
            enrich(enrichment, byNhs.get());
        }

        // ---- 2) Patient reference: enrich on a hit; a miss fails only in strict mode ----
        String patientRef = job.optFirst("patientRef", "patientReference", "patientId");
        if (patientRef != null && !patientRef.isBlank()) {
            Optional<ReferenceData.PatientRecord> record = referenceData.patient(patientRef);
            if (record.isPresent()) {
                enrich(enrichment, record.get());
            } else if (config.databaseValidationStrictPatient()) {
                throw ValidationException.unknownRecord("patientRef", "patient record", patientRef, job.jobType());
            } else {
                LOG.debug("Patient {} not in the reference data; lenient mode allows it (job {})",
                        patientRef, job.jobType());
            }
        }

        // ---- 3) On a patient hit, check whether their GP practice still accepts referrals ----
        Object practiceCode = enrichment.get(VAR_GP_CODE);
        if (practiceCode != null && config.databaseValidationGpAccepting()) {
            referenceData.practice(String.valueOf(practiceCode)).ifPresent(practice -> {
                enrichment.put(VAR_GP_NAME, practice.name());
                enrichment.put(VAR_GP_ACCEPTING, practice.acceptingReferrals());
                if (!practice.acceptingReferrals()) {
                    throw ValidationException.notUsable("patientRef", "GP practice", practice.practiceCode(),
                            "the practice has stopped accepting new referrals", job.jobType());
                }
            });
        }

        if (!enrichment.isEmpty()) {
            LOG.debug("Database check complete; enriched {} variables (job {})",
                    enrichment.size(), job.jobType());
        }
        return enrichment;
    }

    private void enrich(Map<String, Object> enrichment, ReferenceData.PatientRecord record) {
        enrichment.put(VAR_PATIENT_NAME, record.fullName());
        if (record.nhsNumber() != null) {
            enrichment.put(VAR_PATIENT_NHS, record.nhsNumber());
        }
        if (record.practiceCode() != null) {
            enrichment.put(VAR_GP_CODE, record.practiceCode());
        }
    }

    /** Exposes the size of the reference data for the start-up banner. */
    public Map<String, Object> summary() {
        return referenceData.summary();
    }
}
