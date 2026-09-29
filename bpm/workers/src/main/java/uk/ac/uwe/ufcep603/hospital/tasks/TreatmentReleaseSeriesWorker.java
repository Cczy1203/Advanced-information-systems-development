package uk.ac.uwe.ufcep603.hospital.tasks;

import io.camunda.zeebe.client.ZeebeClient;
import uk.ac.uwe.ufcep603.hospital.AbstractHospitalWorker;
import uk.ac.uwe.ufcep603.hospital.JobContext;
import uk.ac.uwe.ufcep603.hospital.WorkerContext;

import java.util.List;
import java.util.Map;

/**
 * {@code treatment.release-series} - compensation handler for the Treatment and
 * Chemotherapy Bookings Team.
 *
 * <p>Runs when a confirmed appointment series has to be undone, normally because external capacity
 * never came through. A compensation handler must never be the reason a case stalls, so a missing
 * booking reference is logged and the handler still completes: the appointment release is recorded
 * as "nothing to release" rather than failing the job and leaving the instance half compensated.
 */
public final class TreatmentReleaseSeriesWorker extends AbstractHospitalWorker {

    public static final String JOB_TYPE = "treatment.release-series";

    public TreatmentReleaseSeriesWorker(WorkerContext context, ZeebeClient client) {
        super(JOB_TYPE, context, client);
    }

    @Override
    protected Map<String, Object> execute(JobContext job) {
        String bookingReference = job.optFirst("treatmentBookingRef",
                "treatmentBookingRef", "treatmentRef", "treatmentBookingReference");

        List<String> held = job.optStringList("confirmedAppointmentRefs");
        if (held.isEmpty()) {
            held = job.optStringList("provisionalAppointmentRefs");
        }
        if (held.isEmpty()) {
            held = job.optStringList("releasedAppointmentRefs");
        }

        Map<String, Object> output = job.output();
        output.put("seriesReleased", true);
        output.put("releasedAppointmentRefs", held);
        output.put("releasedAppointmentCount", held.size());
        output.put("seriesReleasedAt", context().clock().timestamp());
        output.put("seriesReleaseReason", job.optFirst("capacityStopReason", "releaseReason") == null
                ? "EXTERNAL_CAPACITY_NOT_AVAILABLE" : job.optFirst("capacityStopReason", "releaseReason"));
        output.put("releasedBookingRef", bookingReference == null ? "NOT_RECORDED" : bookingReference);
        return output;
    }
}
