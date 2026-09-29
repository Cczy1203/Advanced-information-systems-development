package uk.ac.uwe.ufcep603.hospital.tasks;

import io.camunda.zeebe.client.ZeebeClient;
import uk.ac.uwe.ufcep603.hospital.AbstractHospitalWorker;
import uk.ac.uwe.ufcep603.hospital.JobContext;
import uk.ac.uwe.ufcep603.hospital.WorkerContext;

import java.time.LocalDate;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

/**
 * {@code pathway.find-overdue-clinic-letters} - Patient Pathway Coordinators,
 * "Find clinic letters that are overdue".
 *
 * <p>Returns the letters still waiting, how long they have been outstanding, and which of them have
 * passed the seven day target. {@code letterOverdueDays} is the <em>worst</em> case, because the
 * model's gateway escalates on that single number:
 * <ul>
 *   <li>{@code <= 30} - one week to one month: suppress duplicates and remind the Consultant;</li>
 *   <li>{@code > 30 and <= 90} - over one month: escalate to the Administrative Manager;</li>
 *   <li>otherwise - over three months: escalate to higher management.</li>
 * </ul>
 *
 * <p>Letters come from the in-memory store, which is seeded with dates relative to the demo clock so
 * every band can be shown ({@code demo.pathway.scenario} =
 * {@code SEVEN_DAYS} / {@code ONE_MONTH} / {@code THREE_MONTHS}). An explicit {@code clinicLetters}
 * list, or a single {@code letterRef} + {@code consultationDate}, overrides the store, and
 * {@code demo.clock.today} / {@code demo.clock.offset-days} move "today" so a demo does not have to
 * wait three months.
 */
public final class PathwayFindOverdueClinicLettersWorker extends AbstractHospitalWorker {

    public static final String JOB_TYPE = "pathway.find-overdue-clinic-letters";

    /**
     * The BPMN element id {@code PCW_Auto_FindOverdue} has been modelled with the shorter job type
     * {@code pathway.find-overdue-letters}; both names are accepted so the service task is never left
     * without a worker.
     */
    public static final String ALIAS_JOB_TYPE = "pathway.find-overdue-letters";

    private static final int REMINDER_THRESHOLD_DAYS = 7;
    private static final int MONTH_BAND_DAYS = 30;
    private static final int THREE_MONTH_BAND_DAYS = 90;

    public PathwayFindOverdueClinicLettersWorker(WorkerContext context, ZeebeClient client) {
        super(JOB_TYPE, context, client);
    }

    @Override
    protected List<String> additionalJobTypes() {
        return List.of(ALIAS_JOB_TYPE);
    }

    @Override
    protected Map<String, Object> execute(JobContext job) {
        LocalDate today = context().clock().today();
        context().store().seedClinicLetters(today, context().config().pathwayScenario());

        List<Map<String, Object>> sources = new ArrayList<>();
        Optional<Map<String, Object>> singleLetter = singleLetter(job, today);
        if (singleLetter.isPresent()) {
            sources.add(singleLetter.get());
        } else if (job.optList("clinicLetters").isPresent()) {
            sources.addAll(job.optMapList("clinicLetters"));
        } else {
            sources.addAll(context().store().letters());
        }

        List<Map<String, Object>> outstanding = new ArrayList<>();
        for (Map<String, Object> source : sources) {
            Map<String, Object> letter = evaluate(source, today);
            if (letter == null) {
                continue;
            }
            context().store().putLetter(letter);
            outstanding.add(letter);
        }
        outstanding.sort(Comparator.comparingInt(letter -> -((Integer) letter.get("daysOutstanding"))));

        List<Map<String, Object>> requiringReminder = outstanding.stream()
                .filter(letter -> ((Integer) letter.get("daysOutstanding")) >= REMINDER_THRESHOLD_DAYS)
                .toList();
        int worstCase = outstanding.stream()
                .mapToInt(letter -> (Integer) letter.get("daysOutstanding"))
                .max()
                .orElse(0);

        Map<String, Object> output = job.output();
        output.put("outstandingLetters", outstanding);
        output.put("letterOverdueDays", worstCase);
        output.put("lettersRequiringReminder", requiringReminder);
        output.put("overdueLettersAsOf", today.toString());
        output.put("reminderThresholdDays", REMINDER_THRESHOLD_DAYS);
        output.put("outstandingLetterCount", outstanding.size());
        return output;
    }

    private Optional<Map<String, Object>> singleLetter(JobContext job, LocalDate today) {
        String reference = job.optFirst("letterRef", "letterRef", "letterReference", "clinicLetterRef");
        Optional<LocalDate> consultationDate = job.optDateFirst("consultationDate", "consultationDate",
                "appointmentDate", "clinicDate");
        if (reference == null && consultationDate.isEmpty()) {
            return Optional.empty();
        }
        Map<String, Object> letter = new LinkedHashMap<>();
        letter.put("letterRef", reference == null ? "CL-" + today : reference);
        letter.put("consultationDate", consultationDate.orElse(today.minusDays(REMINDER_THRESHOLD_DAYS + 2))
                .toString());
        String subject = job.optFirst("letterSubject", "letterSubject", "clinicType");
        if (subject != null) {
            letter.put("subject", subject);
        }
        letter.put("approved", job.boolOr("letterApproved", false));
        return Optional.of(letter);
    }

    /** Adds {@code daysOutstanding} and the escalation band, and drops letters already approved. */
    private Map<String, Object> evaluate(Map<String, Object> source, LocalDate today) {
        Object reference = source.get("letterRef");
        if (reference == null || String.valueOf(reference).isBlank()) {
            return null;
        }
        if (Boolean.TRUE.equals(source.get("approved"))) {
            return null;
        }
        LocalDate consultationDate = parse(source.get("consultationDate"), today);
        int daysOutstanding = (int) Math.max(0, ChronoUnit.DAYS.between(consultationDate, today));

        Map<String, Object> letter = new LinkedHashMap<>(source);
        letter.put("daysOutstanding", daysOutstanding);
        letter.put("overdueBand", band(daysOutstanding));
        letter.put("requiresReminder", daysOutstanding >= REMINDER_THRESHOLD_DAYS);
        return letter;
    }

    private static LocalDate parse(Object value, LocalDate fallback) {
        if (value == null) {
            return fallback;
        }
        try {
            return LocalDate.parse(String.valueOf(value).trim());
        } catch (RuntimeException e) {
            return fallback;
        }
    }

    static String band(int daysOutstanding) {
        if (daysOutstanding >= THREE_MONTH_BAND_DAYS) {
            return "OVER_THREE_MONTHS";
        }
        if (daysOutstanding > MONTH_BAND_DAYS) {
            return "OVER_ONE_MONTH";
        }
        if (daysOutstanding >= REMINDER_THRESHOLD_DAYS) {
            return "ONE_WEEK_TO_ONE_MONTH";
        }
        return "WITHIN_SEVEN_DAYS";
    }
}
