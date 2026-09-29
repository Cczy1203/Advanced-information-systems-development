package uk.ac.uwe.ufcep603.hospital.tasks;

import io.camunda.zeebe.client.ZeebeClient;
import uk.ac.uwe.ufcep603.hospital.AbstractHospitalWorker;
import uk.ac.uwe.ufcep603.hospital.JobContext;
import uk.ac.uwe.ufcep603.hospital.ValidationException;
import uk.ac.uwe.ufcep603.hospital.WorkerContext;

import java.util.Map;

/**
 * {@code treatment.authorise-request} - Consultants,
 * "Authorise the treatment booking request".
 *
 * <p>Only a Consultant can authorise treatment, and only with the patient's consent recorded.
 * Consent that is absent, {@code false} or not a boolean is a job failure with a message that names
 * {@code consentGiven}; the model has no boundary event for it, and an authorisation without consent
 * must never be completed quietly.
 */
public final class TreatmentAuthoriseRequestWorker extends AbstractHospitalWorker {

    public static final String JOB_TYPE = "treatment.authorise-request";

    public TreatmentAuthoriseRequestWorker(WorkerContext context, ZeebeClient client) {
        super(JOB_TYPE, context, client);
    }

    @Override
    protected Map<String, Object> execute(JobContext job) {
        String bookingReference = job.requireFirst("treatmentBookingRef",
                "treatmentBookingRef", "treatmentRef", "treatmentBookingReference");
        String clinician = job.requireFirst("decidingClinician",
                "decidingClinician", "authorisingClinician", "clinicianName", "authorisedBy", "consultantName");

        boolean consent = job.optBool("consentGiven").orElse(false);
        if (!consent) {
            throw new ValidationException("consentGiven",
                    "Treatment cannot be authorised without recorded patient consent: 'consentGiven' is "
                            + (job.opt("consentGiven") == null ? "missing" : "not true")
                            + " for treatment booking " + bookingReference + " (job type " + JOB_TYPE + ")");
        }

        Map<String, Object> output = job.output();
        output.put("treatmentAuthorised", true);
        output.put("treatmentAuthorisedBy", clinician);
        output.put("treatmentAuthorisedAt", context().clock().timestamp());
        output.put("treatmentAuthorisedRef", bookingReference);
        return output;
    }
}
