package uk.ac.uwe.ufcep603.hospital.tasks;

import io.camunda.zeebe.client.ZeebeClient;
import uk.ac.uwe.ufcep603.hospital.AbstractHospitalWorker;
import uk.ac.uwe.ufcep603.hospital.JobContext;
import uk.ac.uwe.ufcep603.hospital.ValidationException;
import uk.ac.uwe.ufcep603.hospital.WorkerContext;

import java.time.LocalDate;
import java.util.Map;

/**
 * {@code treatment.schedule-next-cycle} - Treatment and Chemotherapy Bookings Team,
 * "Schedule the next cycle".
 *
 * <p>Works out the next cycle number and the date it is provisionally booked for. The date is
 * {@code treatmentStartDate + nextCycle * cycleIntervalDays} when both are known, otherwise a
 * three week default from the demo clock - never a hard-coded date.
 */
public final class TreatmentScheduleNextCycleWorker extends AbstractHospitalWorker {

    public static final String JOB_TYPE = "treatment.schedule-next-cycle";

    private static final int DEFAULT_INTERVAL_DAYS = 21;

    public TreatmentScheduleNextCycleWorker(WorkerContext context, ZeebeClient client) {
        super(JOB_TYPE, context, client);
    }

    @Override
    protected Map<String, Object> execute(JobContext job) {
        String bookingReference = job.requireFirst("treatmentBookingRef",
                "treatmentBookingRef", "treatmentRef", "treatmentBookingReference");
        int cycleNumber = job.intOr("cycleNumber", job.intOr("validatedCycleCount", 0));
        if (cycleNumber < 0) {
            throw new ValidationException("cycleNumber",
                    "Process variable 'cycleNumber' must not be negative but was " + cycleNumber
                            + " (job type " + JOB_TYPE + ")");
        }

        int nextCycleNumber = cycleNumber + 1;
        int intervalDays = job.intOr("cycleIntervalDays", DEFAULT_INTERVAL_DAYS);
        LocalDate start = job.optDateFirst("treatmentStartDate", "treatmentStartDate", "treatmentStart", "startDate")
                .orElse(context().clock().today());
        LocalDate scheduledFor = start.plusDays((long) nextCycleNumber * intervalDays);

        Map<String, Object> output = job.output();
        output.put("nextCycleNumber", nextCycleNumber);
        output.put("cycleScheduledFor", scheduledFor.toString());
        output.put("nextCycleBookingRef", bookingReference);
        output.put("nextCycleIntervalDays", intervalDays);
        return output;
    }
}
