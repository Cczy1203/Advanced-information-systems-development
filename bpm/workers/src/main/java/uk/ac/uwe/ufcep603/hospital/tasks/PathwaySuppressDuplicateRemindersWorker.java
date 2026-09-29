package uk.ac.uwe.ufcep603.hospital.tasks;

import io.camunda.zeebe.client.ZeebeClient;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import uk.ac.uwe.ufcep603.hospital.AbstractHospitalWorker;
import uk.ac.uwe.ufcep603.hospital.JobContext;
import uk.ac.uwe.ufcep603.hospital.WorkerContext;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * {@code pathway.suppress-duplicate-reminders} - Patient Pathway Coordinators,
 * "Drop letters that no longer need chasing".
 *
 * <p>A reminder must not be sent twice for the same letter. Reminders already recorded - either by
 * this worker on a previous weekly run, or supplied in the {@code reminderHistory} variable - are
 * dropped, and {@code suppressedReminderCount} reports how many were dropped.
 *
 * <p>The threshold is strict by design ({@code demo.pathway.reminder-cooldown-days = 0}): once a
 * letter has been reminded it is never reminded again. Setting the cooldown to 7 days makes the
 * chasing behave like a real weekly cycle instead.
 */
public final class PathwaySuppressDuplicateRemindersWorker extends AbstractHospitalWorker {

    public static final String JOB_TYPE = "pathway.suppress-duplicate-reminders";

    private static final Logger LOG = LoggerFactory.getLogger(PathwaySuppressDuplicateRemindersWorker.class);

    public PathwaySuppressDuplicateRemindersWorker(WorkerContext context, ZeebeClient client) {
        super(JOB_TYPE, context, client);
    }

    @Override
    protected Map<String, Object> execute(JobContext job) {
        LocalDate today = context().clock().today();
        int cooldownDays = context().config().reminderCooldownDays();

        List<Map<String, Object>> candidates = new ArrayList<>();
        if (job.optList("outstandingLetters").isPresent()) {
            candidates.addAll(job.optMapList("outstandingLetters"));
        } else if (job.optList("lettersRequiringReminder").isPresent()) {
            candidates.addAll(job.optMapList("lettersRequiringReminder"));
        } else {
            for (Map<String, Object> letter : context().store().letters()) {
                if (Boolean.TRUE.equals(letter.get("approved"))) {
                    continue;
                }
                Object consultationDate = letter.get("consultationDate");
                if (consultationDate != null) {
                    long days = java.time.temporal.ChronoUnit.DAYS.between(
                            LocalDate.parse(String.valueOf(consultationDate)), today);
                    if (days < 7) {
                        continue;
                    }
                }
                candidates.add(letter);
            }
        }

        Set<String> history = new LinkedHashSet<>();
        for (Object entry : job.optList("reminderHistory").orElse(List.of())) {
            if (entry == null) {
                continue;
            }
            if (entry instanceof Map<?, ?> map) {
                Object reference = map.get("letterRef") != null ? map.get("letterRef") : map.get("letterReference");
                if (reference != null) {
                    history.add(String.valueOf(reference));
                }
            } else {
                history.add(String.valueOf(entry).trim());
            }
        }

        List<Map<String, Object>> toRemind = new ArrayList<>();
        int suppressed = 0;
        for (Map<String, Object> candidate : candidates) {
            Object reference = candidate.get("letterRef");
            if (reference == null) {
                continue;
            }
            String letterRef = String.valueOf(reference);
            boolean alreadyReminded = history.contains(letterRef)
                    || context().store().alreadyReminded(letterRef, today, cooldownDays);
            if (alreadyReminded) {
                suppressed++;
                continue;
            }
            Map<String, Object> reminder = new LinkedHashMap<>(candidate);
            reminder.put("reminderDueOn", today.toString());
            reminder.put("reminderCount", context().store().reminderCountFor(letterRef) + 1);
            toRemind.add(reminder);
            // Record it now: re-running the weekly review for the same letter must not chase twice.
            context().store().recordReminder(letterRef, today);
        }

        if (suppressed > 0) {
            LOG.info("suppressed {} duplicate reminder(s); {} letter(s) still to chase",
                    suppressed, toRemind.size());
        }

        Map<String, Object> output = job.output();
        output.put("lettersToRemind", toRemind);
        output.put("suppressedReminderCount", suppressed);
        output.put("remindersDueCount", toRemind.size());
        output.put("reminderCooldownDays", cooldownDays);
        return output;
    }
}
