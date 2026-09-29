package uk.ac.uwe.ufcep603.hospital.tasks;

import io.camunda.zeebe.client.ZeebeClient;
import uk.ac.uwe.ufcep603.hospital.AbstractHospitalWorker;
import uk.ac.uwe.ufcep603.hospital.JobContext;
import uk.ac.uwe.ufcep603.hospital.WorkerContext;

import java.util.Map;

/**
 * {@code treatment.release-cycle-booking} - compensation handler for a cycle slot that was
 * pencilled in and then could not be filled.
 *
 * <p>Releasing a slot the patient never had confirmed is not an error, so this handler always
 * completes and records what it did.
 */
public final class TreatmentReleaseCycleBookingWorker extends AbstractHospitalWorker {

    public static final String JOB_TYPE = "treatment.release-cycle-booking";

    public TreatmentReleaseCycleBookingWorker(WorkerContext context, ZeebeClient client) {
        super(JOB_TYPE, context, client);
    }

    @Override
    protected Map<String, Object> execute(JobContext job) {
        String bookingReference = job.optFirst("treatmentBookingRef",
                "treatmentBookingRef", "treatmentRef", "treatmentBookingReference");
        int cycleNumber = job.intOr("cycleNumber", 0);

        Map<String, Object> output = job.output();
        output.put("cycleReleased", true);
        output.put("releasedCycleNumber", cycleNumber);
        output.put("releasedCycleRef", (bookingReference == null ? "NOT-RECORDED" : bookingReference)
                + "-CYCLE-" + cycleNumber);
        output.put("cycleReleasedAt", context().clock().timestamp());
        return output;
    }
}
