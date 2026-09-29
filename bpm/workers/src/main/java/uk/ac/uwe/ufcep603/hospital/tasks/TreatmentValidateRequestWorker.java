package uk.ac.uwe.ufcep603.hospital.tasks;

import io.camunda.zeebe.client.ZeebeClient;
import uk.ac.uwe.ufcep603.hospital.AbstractHospitalWorker;
import uk.ac.uwe.ufcep603.hospital.BpmnErrorException;
import uk.ac.uwe.ufcep603.hospital.JobContext;
import uk.ac.uwe.ufcep603.hospital.ValidationException;
import uk.ac.uwe.ufcep603.hospital.WorkerContext;

import java.util.Map;

/**
 * {@code treatment.validate-request} - Treatment and Chemotherapy Bookings Team,
 * "Check the request is complete and authorised".
 *
 * <p>A treatment request that has no authorising clinician, or no treatment booking reference, is a
 * business condition the model handles with the {@code TREATMENT_REQUEST_UNAUTHORISED} boundary
 * event, which returns the request to the clinical team. Missing {@code cycleCount} is different:
 * that is bad data rather than a business outcome, so it fails the job after naming the variable.
 *
 * <p>Outputs {@code requestValidated = true} and the normalised {@code validatedCycleCount}.
 */
public final class TreatmentValidateRequestWorker extends AbstractHospitalWorker {

    public static final String JOB_TYPE = "treatment.validate-request";

    private static final String TREATMENT_REQUEST_UNAUTHORISED = "TREATMENT_REQUEST_UNAUTHORISED";
    private static final int MAX_CYCLES = 24;

    public TreatmentValidateRequestWorker(WorkerContext context, ZeebeClient client) {
        super(JOB_TYPE, context, client);
    }

    @Override
    protected Map<String, Object> execute(JobContext job) {
        String bookingReference = job.optFirst("treatmentBookingRef", "treatmentBookingRef", "treatmentRef",
                "treatmentBookingReference");
        String authorisingClinician = job.optFirst("authorisingClinician", "authorisingClinician",
                "authorizingClinician", "decidingClinician", "authorisedBy");

        if (bookingReference == null || authorisingClinician == null) {
            throw new BpmnErrorException(TREATMENT_REQUEST_UNAUTHORISED,
                    "Treatment request is not authorised: treatmentBookingRef="
                            + (bookingReference == null ? "MISSING" : bookingReference)
                            + ", authorisingClinician="
                            + (authorisingClinician == null ? "MISSING" : authorisingClinician)
                            + " (element " + job.elementId() + ")");
        }

        String plan = job.optFirst("treatmentPlan", "treatmentPlan", "treatmentRegimen", "plan");
        if (plan == null) {
            throw ValidationException.missing("treatmentPlan", JOB_TYPE);
        }

        int cycleCount = job.intOr("cycleCount", 1);
        if (cycleCount < 1 || cycleCount > MAX_CYCLES) {
            throw new ValidationException("cycleCount",
                    "Process variable 'cycleCount' must be between 1 and " + MAX_CYCLES + " but was "
                            + cycleCount + " (job type " + JOB_TYPE + ")");
        }

        Map<String, Object> output = job.output();
        output.put("requestValidated", true);
        output.put("validatedCycleCount", cycleCount);
        output.put("validatedTreatmentBookingRef", bookingReference);
        output.put("validatedAuthorisingClinician", authorisingClinician);
        output.put("validatedTreatmentPlan", plan);
        return output;
    }
}
