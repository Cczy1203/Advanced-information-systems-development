package uk.ac.uwe.ufcep603.hospital.tasks;

import io.camunda.zeebe.client.ZeebeClient;
import uk.ac.uwe.ufcep603.hospital.AbstractHospitalWorker;
import uk.ac.uwe.ufcep603.hospital.JobContext;
import uk.ac.uwe.ufcep603.hospital.WorkerContext;

import java.time.LocalDate;
import java.time.temporal.ChronoUnit;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

/**
 * {@code booking.check-priority-and-contact-rule} - Outpatient Bookings Team,
 * "Work out priority, timeframe and contact rule".
 *
 * <p>Applies the two week rule: an appointment inside the next fortnight, <em>or</em> any urgent
 * referral, also needs a telephone call; everything else is letter only. The result drives the
 * inclusive gateway that fans out to the correspondence service and/or the call handling team.
 *
 * <p>Outputs {@code appointmentPriority}, {@code requiresPhoneCall} and {@code contactRule}. When no
 * appointment date is known yet the rule falls back to the priority alone, which is the honest
 * answer rather than a guess.
 */
public final class BookingCheckPriorityAndContactRuleWorker extends AbstractHospitalWorker {

    public static final String JOB_TYPE = "booking.check-priority-and-contact-rule";

    private static final int TWO_WEEK_RULE_DAYS = 14;
    private static final Set<String> URGENT_PRIORITIES =
            Set.of("URGENT", "2WW", "TWO_WEEK_WAIT", "TWO-WEEK-WAIT", "CANCER_2WW", "EMERGENCY", "PRIORITY");

    public BookingCheckPriorityAndContactRuleWorker(WorkerContext context, ZeebeClient client) {
        super(JOB_TYPE, context, client);
    }

    @Override
    protected Map<String, Object> execute(JobContext job) {
        String priority = job.optFirst("referralPriority", "referralPriority", "appointmentPriority", "priority");
        String normalisedPriority = priority == null
                ? "ROUTINE"
                : priority.toUpperCase(Locale.ROOT).replace(' ', '_');
        boolean urgent = URGENT_PRIORITIES.contains(normalisedPriority);

        LocalDate today = context().clock().today();
        Optional<LocalDate> appointmentDate = job.optDateFirst(
                "appointmentDateTime", "appointmentDate", "chosenSlotStart", "slotStart", "selectedSlotStart");

        Long daysUntil = appointmentDate.map(date -> ChronoUnit.DAYS.between(today, date)).orElse(null);
        boolean withinTwoWeeks = daysUntil != null && daysUntil <= TWO_WEEK_RULE_DAYS && daysUntil >= 0;
        boolean requiresPhoneCall = urgent || withinTwoWeeks;

        String contactRule;
        if (urgent && withinTwoWeeks) {
            contactRule = "TELEPHONE_NOW_AND_LETTER";
        } else if (urgent) {
            contactRule = "TELEPHONE_BEFORE_APPOINTMENT_AND_LETTER";
        } else if (withinTwoWeeks) {
            contactRule = "TELEPHONE_WITHIN_24_HOURS_AND_LETTER";
        } else if (appointmentDate.isEmpty()) {
            contactRule = "LETTER_ONLY_UNTIL_DATE_CONFIRMED";
        } else {
            contactRule = "LETTER_ONLY";
        }

        Map<String, Object> output = job.output();
        output.put("appointmentPriority", normalisedPriority);
        output.put("requiresPhoneCall", requiresPhoneCall);
        output.put("contactRule", contactRule);
        output.put("twoWeekRuleApplied", withinTwoWeeks);
        output.put("appointmentUrgent", urgent);
        if (daysUntil != null) {
            output.put("daysUntilAppointment", daysUntil.intValue());
        }
        if (appointmentDate.isPresent()) {
            output.put("appointmentDateChecked", appointmentDate.get().toString());
        }
        output.put("contactRuleBasis", "urgent=" + urgent + ", withinTwoWeeks=" + withinTwoWeeks
                + ", today=" + today);
        return output;
    }
}
