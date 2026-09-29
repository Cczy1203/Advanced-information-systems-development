package uk.ac.uwe.ufcep603.hospital.tasks;

import io.camunda.zeebe.client.ZeebeClient;
import uk.ac.uwe.ufcep603.hospital.AbstractHospitalWorker;
import uk.ac.uwe.ufcep603.hospital.JobContext;
import uk.ac.uwe.ufcep603.hospital.ValidationException;
import uk.ac.uwe.ufcep603.hospital.WorkerContext;

import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * {@code booking.record-appointment-outcome} - Outpatient Bookings Team,
 * "Record the appointment outcome".
 *
 * <p>Administrative staff record what happened; they do not decide whether treatment continues. The
 * worker therefore only classifies the outcome:
 * <ul>
 *   <li>{@code ATTENDED} - nothing further is needed, {@code ADMINISTRATIVE};</li>
 *   <li>{@code CANCELLED} - administrative unless a cancellation reason reads like a clinical
 *       problem, in which case the pathway needs a clinical decision;</li>
 *   <li>{@code DECLINED} and {@code DNA} (did not attend) - {@code CLINICAL_ACTION_REQUIRED}, because
 *       a patient who declines or does not attend may be deteriorating.</li>
 * </ul>
 *
 * <p>{@code appointmentOutcome} is required and must be one of the four values the model's gateway
 * understands; anything else fails the job naming the variable rather than being classified by
 * guesswork.
 */
public final class BookingRecordAppointmentOutcomeWorker extends AbstractHospitalWorker {

    public static final String JOB_TYPE = "booking.record-appointment-outcome";

    private static final List<String> ALLOWED_OUTCOMES =
            List.of("ATTENDED", "CANCELLED", "DECLINED", "DNA", "DID_NOT_ATTEND");

    private static final List<String> CLINICAL_REASON_MARKERS =
            List.of("clinical", "unwell", "medical", "deteriorat", "admitted", "emergency", "symptom", "pain");

    public BookingRecordAppointmentOutcomeWorker(WorkerContext context, ZeebeClient client) {
        super(JOB_TYPE, context, client);
    }

    @Override
    protected Map<String, Object> execute(JobContext job) {
        String outcome = job.requireFirst("appointmentOutcome",
                "appointmentOutcome", "appointmentStatus", "cancellationOutcome", "outcome");
        String upper = outcome.toUpperCase(Locale.ROOT).replace(' ', '_');
        if (!ALLOWED_OUTCOMES.contains(upper)) {
            throw ValidationException.notAllowed("appointmentOutcome", upper, ALLOWED_OUTCOMES, JOB_TYPE);
        }
        String normalised = "DID_NOT_ATTEND".equals(upper) ? "DNA" : upper;

        String cancellationReason = job.optFirst("cancellationReason", "cancellationReason", "outcomeReason",
                "declineReason");

        boolean clinicalAction;
        if ("ATTENDED".equals(normalised)) {
            clinicalAction = false;
        } else if ("CANCELLED".equals(normalised)) {
            clinicalAction = containsClinicalMarker(cancellationReason);
        } else {
            clinicalAction = true;
        }

        Map<String, Object> output = job.output();
        output.put("appointmentOutcomeRecordedAt", context().clock().timestamp());
        output.put("outcomeCategory", clinicalAction ? "CLINICAL_ACTION_REQUIRED" : "ADMINISTRATIVE");
        output.put("appointmentOutcomeRecorded", normalised);
        output.put("cancellationReasonRecorded", cancellationReason == null ? "NOT_RECORDED" : cancellationReason);
        return output;
    }

    private static boolean containsClinicalMarker(String reason) {
        if (reason == null) {
            return false;
        }
        String lower = reason.toLowerCase(Locale.ROOT);
        return CLINICAL_REASON_MARKERS.stream().anyMatch(lower::contains);
    }
}
