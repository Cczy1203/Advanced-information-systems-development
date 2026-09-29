package uk.ac.uwe.ufcep603.hospital.tasks;

import io.camunda.zeebe.client.ZeebeClient;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import uk.ac.uwe.ufcep603.hospital.AbstractHospitalWorker;
import uk.ac.uwe.ufcep603.hospital.JobContext;
import uk.ac.uwe.ufcep603.hospital.WorkerContext;
import uk.ac.uwe.ufcep603.hospital.support.Ids;

import java.time.LocalDate;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * {@code scheduling.find-appointment-slots} - <b>simulated</b> External Scheduling Service,
 * "Query available appointment slots".
 *
 * <p>Deterministic stand-in for a clinic scheduling system: given a priority, a speciality or
 * purpose and a date window it returns a fixed number of options, or {@code NO_SLOTS} when the
 * window is empty / the demo forces it. The outcome drives the {@code slotCount > 0} gateway that
 * decides between returning options and reporting nothing suitable.
 *
 * <p>Throws the BPMN error {@code SCHEDULING_SERVICE_UNAVAILABLE} when the simulated failure
 * injection is switched on, which the model catches and treats as "no answer returned - caller times
 * out".
 *
 * <p>Limitations: the slots are synthetic and evenly spaced, there is no clinic diary, no clinician
 * roster and no cap on how often the same slot can be offered.
 */
public final class SchedulingFindAppointmentSlotsWorker extends AbstractHospitalWorker {

    public static final String JOB_TYPE = "scheduling.find-appointment-slots";

    private static final int DEFAULT_WINDOW_DAYS = 14;
    private static final int DEFAULT_SLOT_COUNT = 3;

    private static final Logger LOG = LoggerFactory.getLogger(SchedulingFindAppointmentSlotsWorker.class);

    public SchedulingFindAppointmentSlotsWorker(WorkerContext context, ZeebeClient client) {
        super(JOB_TYPE, context, client);
    }

    @Override
    protected Map<String, Object> execute(JobContext job) {
        String purpose = job.optFirst("schedulingPurpose", "schedulingPurpose", "appointmentPurpose",
                "searchPurpose");
        String speciality = job.optFirst("referralSpeciality", "referralSpeciality", "speciality", "specialty");
        String priority = job.optFirst("appointmentPriority", "appointmentPriority", "referralPriority",
                "priority");
        String target = speciality == null ? (purpose == null ? "general" : purpose) : speciality;

        LocalDate today = context().clock().today();
        LocalDate from = job.optDateFirst("preferredFromDate", "preferredFromDate", "searchFromDate",
                "requestedFromDate").orElse(today.plusDays(1));
        LocalDate to = job.optDateFirst("preferredToDate", "preferredToDate", "searchToDate",
                "requestedToDate").orElse(from.plusDays(DEFAULT_WINDOW_DAYS));

        long windowDays = ChronoUnit.DAYS.between(from, to);
        boolean forceNoSlots = context().config().schedulingForceNoSlots()
                || job.boolOr("simulateNoSlots", false)
                || job.boolOr("noSlotsAvailable", false)
                || "NONE".equalsIgnoreCase(job.optFirst("slotAvailability", "slotAvailability"));

        List<Map<String, Object>> options = new ArrayList<>();
        if (!forceNoSlots && windowDays >= 1) {
            int count = Math.min(DEFAULT_SLOT_COUNT, (int) windowDays);
            for (int index = 1; index <= count; index++) {
                LocalDate date = from.plusDays(index);
                if (date.isAfter(to)) {
                    break;
                }
                Map<String, Object> slot = new java.util.LinkedHashMap<>();
                slot.put("slotRef", Ids.reference("SLOT", target, purpose, date, index));
                slot.put("start", date + "T" + String.format("%02d", 8 + index) + ":00:00Z");
                slot.put("location", locationFor(target, index));
                slot.put("clinicType", purpose == null ? "new-patient" : purpose);
                options.add(slot);
            }
        }

        String outcome = options.isEmpty() ? "NO_SLOTS" : "SLOTS_FOUND";
        if (options.isEmpty()) {
            LOG.info("no slots offered for {} between {} and {} (forced={})", target, from, to, forceNoSlots);
        }

        Map<String, Object> output = job.output();
        output.put("slotCount", options.size());
        output.put("slotOptions", options);
        output.put("schedulingOutcome", outcome);
        output.put("schedulingSearchFrom", from.toString());
        output.put("schedulingSearchTo", to.toString());
        output.put("schedulingTarget", target);
        output.put("schedulingPriority", priority == null ? "ROUTINE" : priority.toUpperCase(Locale.ROOT));
        output.put("schedulingProvider", "SIMULATED-EXTERNAL-SCHEDULING-SERVICE");
        return output;
    }

    private static String locationFor(String target, int index) {
        String lower = target.toLowerCase(Locale.ROOT);
        String base;
        if (lower.contains("chemo") || lower.contains("oncology") || lower.contains("treatment")) {
            base = "ONCOLOGY-DAY-UNIT";
        } else if (lower.contains("imaging") || lower.contains("radiology") || lower.contains("scan")) {
            base = "IMAGING-SUITE";
        } else if (lower.contains("cardio")) {
            base = "CARDIOLOGY-CLINIC";
        } else if (lower.contains("respiratory") || lower.contains("chest")) {
            base = "RESPIRATORY-CLINIC";
        } else {
            base = "OUTPATIENT-CLINIC";
        }
        return base + "-" + index;
    }
}
