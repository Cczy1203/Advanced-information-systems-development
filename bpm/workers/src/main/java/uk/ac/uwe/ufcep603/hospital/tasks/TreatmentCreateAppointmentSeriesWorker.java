package uk.ac.uwe.ufcep603.hospital.tasks;

import io.camunda.zeebe.client.ZeebeClient;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import uk.ac.uwe.ufcep603.hospital.AbstractHospitalWorker;
import uk.ac.uwe.ufcep603.hospital.JobContext;
import uk.ac.uwe.ufcep603.hospital.ValidationException;
import uk.ac.uwe.ufcep603.hospital.WorkerContext;
import uk.ac.uwe.ufcep603.hospital.support.Ids;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * {@code treatment.create-appointment-series} - Treatment and Chemotherapy Bookings Team,
 * "Create the provisional appointment series".
 *
 * <p>One provisional appointment per chemotherapy cycle, all derived from the treatment booking
 * reference. The series is stored against that reference, so a retried job - the engine retries three
 * times - returns the series that already exists instead of appending cycles.
 */
public final class TreatmentCreateAppointmentSeriesWorker extends AbstractHospitalWorker {

    public static final String JOB_TYPE = "treatment.create-appointment-series";

    private static final Logger LOG = LoggerFactory.getLogger(TreatmentCreateAppointmentSeriesWorker.class);
    private static final int MAX_CYCLES = 24;

    public TreatmentCreateAppointmentSeriesWorker(WorkerContext context, ZeebeClient client) {
        super(JOB_TYPE, context, client);
    }

    @Override
    protected Map<String, Object> execute(JobContext job) {
        String bookingReference = job.requireFirst("treatmentBookingRef",
                "treatmentBookingRef", "treatmentRef", "treatmentBookingReference");
        String plan = job.optFirst("treatmentPlan", "treatmentPlan", "treatmentRegimen", "plan");

        int cycleCount = job.intOr("cycleCount", job.intOr("validatedCycleCount", 1));
        if (cycleCount < 1 || cycleCount > MAX_CYCLES) {
            throw new ValidationException("cycleCount",
                    "Process variable 'cycleCount' must be between 1 and " + MAX_CYCLES + " but was "
                            + cycleCount + " (job type " + JOB_TYPE + ")");
        }

        int intervalDays = job.intOr("cycleIntervalDays", 21);
        if (intervalDays < 1 || intervalDays > 365) {
            throw new ValidationException("cycleIntervalDays",
                    "Process variable 'cycleIntervalDays' must be between 1 and 365 but was " + intervalDays
                            + " (job type " + JOB_TYPE + ")");
        }

        LocalDate start = job.optDateFirst("treatmentStartDate", "treatmentStartDate", "treatmentStart", "startDate")
                .orElseGet(() -> context().clock().today().plusDays(7));

        List<String> references = new ArrayList<>();
        List<String> dates = new ArrayList<>();
        for (int cycle = 1; cycle <= cycleCount; cycle++) {
            LocalDate date = start.plusDays((long) (cycle - 1) * intervalDays);
            references.add(Ids.reference("CYC", bookingReference, cycle, date));
            dates.add(date.toString());
        }

        List<String> stored = context().store().createOrGetSeries(bookingReference, () -> List.copyOf(references));
        if (!stored.equals(references)) {
            LOG.info("treatment series for {} already existed with {} cycle(s); reusing it",
                    bookingReference, stored.size());
        }

        String seriesReference = Ids.reference("SER", bookingReference, plan);

        Map<String, Object> output = job.output();
        output.put("provisionalAppointmentRefs", stored);
        output.put("seriesReference", seriesReference);
        output.put("provisionalAppointmentDates", dates);
        output.put("seriesCycleCount", stored.size());
        return output;
    }
}
