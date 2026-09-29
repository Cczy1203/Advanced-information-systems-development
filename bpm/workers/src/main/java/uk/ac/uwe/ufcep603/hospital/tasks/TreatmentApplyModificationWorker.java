package uk.ac.uwe.ufcep603.hospital.tasks;

import io.camunda.zeebe.client.ZeebeClient;
import uk.ac.uwe.ufcep603.hospital.AbstractHospitalWorker;
import uk.ac.uwe.ufcep603.hospital.JobContext;
import uk.ac.uwe.ufcep603.hospital.WorkerContext;
import uk.ac.uwe.ufcep603.hospital.support.Ids;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Optional;

/**
 * {@code treatment.apply-modification} - Treatment and Chemotherapy Bookings Team,
 * "Apply the treatment change to the schedule".
 *
 * <p>A modification has to be explained: an urgent change with no recorded reason is exactly the
 * case that must be visible, so a blank {@code modificationReason} fails the job naming that
 * variable. The modified references come from the series that was actually created
 * ({@code treatment.create-appointment-series}); when the series is unknown, references are derived
 * deterministically from the booking reference so the result is still stable across retries.
 */
public final class TreatmentApplyModificationWorker extends AbstractHospitalWorker {

    public static final String JOB_TYPE = "treatment.apply-modification";

    public TreatmentApplyModificationWorker(WorkerContext context, ZeebeClient client) {
        super(JOB_TYPE, context, client);
    }

    @Override
    protected Map<String, Object> execute(JobContext job) {
        String bookingReference = job.requireFirst("treatmentBookingRef",
                "treatmentBookingRef", "treatmentRef", "treatmentBookingReference");
        String reason = job.requireFirst("modificationReason",
                "modificationReason", "changeReason", "modificationNotes", "modificationDetail");
        boolean urgent = job.boolOr("modificationUrgent", false);

        Optional<List<String>> series = context().store().series(bookingReference);
        List<String> modified;
        if (series.isPresent() && !series.get().isEmpty()) {
            modified = series.get();
        } else {
            int cycles = job.intOr("cycleCount", job.intOr("validatedCycleCount", 1));
            modified = new ArrayList<>();
            for (int cycle = 1; cycle <= cycles; cycle++) {
                modified.add(Ids.reference("CYC", bookingReference, cycle, "modified"));
            }
        }

        Map<String, Object> output = job.output();
        output.put("modificationAppliedRef", Ids.reference("MOD", bookingReference, reason, urgent));
        output.put("modifiedAppointmentRefs", modified);
        output.put("modificationAppliedAt", context().clock().timestamp());
        output.put("modificationUrgentApplied", urgent);
        output.put("modificationReasonRecorded", reason);
        return output;
    }
}
