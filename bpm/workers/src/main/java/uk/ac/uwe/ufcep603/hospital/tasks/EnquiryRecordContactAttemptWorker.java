package uk.ac.uwe.ufcep603.hospital.tasks;

import io.camunda.zeebe.client.ZeebeClient;
import uk.ac.uwe.ufcep603.hospital.AbstractHospitalWorker;
import uk.ac.uwe.ufcep603.hospital.JobContext;
import uk.ac.uwe.ufcep603.hospital.WorkerContext;

import java.util.List;
import java.util.Map;

/**
 * {@code enquiry.record-contact-attempt} - Call Handling Team, "Log the contact attempt".
 *
 * <p>Every telephone attempt is counted, and the outcome must be one of the four the model
 * understands: {@code REACHED}, {@code NO_ANSWER}, {@code WRONG_NUMBER} or
 * {@code WANTS_ALTERNATIVE}. An outcome outside that set fails the job naming {@code contactOutcome}
 * rather than being logged as an unusable value - the gateway after this task retries while
 * {@code contactAttempts < 3}, so a wrong count would give up on the patient too early.
 */
public final class EnquiryRecordContactAttemptWorker extends AbstractHospitalWorker {

    public static final String JOB_TYPE = "enquiry.record-contact-attempt";

    private static final List<String> ALLOWED_OUTCOMES =
            List.of("REACHED", "NO_ANSWER", "WRONG_NUMBER", "WANTS_ALTERNATIVE");

    public EnquiryRecordContactAttemptWorker(WorkerContext context, ZeebeClient client) {
        super(JOB_TYPE, context, client);
    }

    @Override
    protected Map<String, Object> execute(JobContext job) {
        String outcome = job.requireOneOf("contactOutcome", ALLOWED_OUTCOMES);

        int previous = job.intOr("contactAttempts", 0);
        if (previous < 0) {
            throw new uk.ac.uwe.ufcep603.hospital.ValidationException("contactAttempts",
                    "Process variable 'contactAttempts' must not be negative but was " + previous
                            + " (job type " + JOB_TYPE + ")");
        }
        int attempts = previous + 1;

        Map<String, Object> output = job.output();
        output.put("contactAttempts", attempts);
        output.put("lastContactAttemptAt", context().clock().timestamp());
        output.put("contactOutcome", outcome);
        output.put("contactSucceeded", "REACHED".equals(outcome));
        output.put("contactAttemptsRemaining", Math.max(0, 3 - attempts));
        return output;
    }
}
