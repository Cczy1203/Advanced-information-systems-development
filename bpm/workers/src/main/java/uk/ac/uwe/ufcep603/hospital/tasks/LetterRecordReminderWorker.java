package uk.ac.uwe.ufcep603.hospital.tasks;

import io.camunda.zeebe.client.ZeebeClient;
import uk.ac.uwe.ufcep603.hospital.AbstractHospitalWorker;
import uk.ac.uwe.ufcep603.hospital.JobContext;
import uk.ac.uwe.ufcep603.hospital.WorkerContext;
import uk.ac.uwe.ufcep603.hospital.support.Ids;

import java.util.Map;

/**
 * {@code letter.record-reminder} - Consultants, "Record the reminder against the letter".
 *
 * <p>Runs when the pathway coordinators' weekly reminder lands on the drafting task. Increments the
 * reminder count for the letter: the incoming {@code reminderCount} is used as the base when the
 * message carried one, otherwise the count held in the in-memory store is used, so a repeated
 * reminder message can never reset the counter.
 */
public final class LetterRecordReminderWorker extends AbstractHospitalWorker {

    public static final String JOB_TYPE = "letter.record-reminder";

    public LetterRecordReminderWorker(WorkerContext context, ZeebeClient client) {
        super(JOB_TYPE, context, client);
    }

    @Override
    protected Map<String, Object> execute(JobContext job) {
        String letterRef = job.requireFirst("letterRef", "letterRef", "letterReference", "clinicLetterRef");
        Integer incoming = job.optInt("reminderCount").orElse(null);

        int reminderCount = context().store().nextReminderCount(letterRef, incoming);

        Map<String, Object> output = job.output();
        output.put("reminderRecordedRef", Ids.reference("REM", letterRef, reminderCount));
        output.put("reminderCount", reminderCount);
        output.put("reminderRecordedAt", context().clock().timestamp());
        output.put("remindedLetterRef", letterRef);
        return output;
    }
}
