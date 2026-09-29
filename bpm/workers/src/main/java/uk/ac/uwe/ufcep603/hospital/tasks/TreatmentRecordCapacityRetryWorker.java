package uk.ac.uwe.ufcep603.hospital.tasks;

import io.camunda.zeebe.client.ZeebeClient;
import uk.ac.uwe.ufcep603.hospital.AbstractHospitalWorker;
import uk.ac.uwe.ufcep603.hospital.JobContext;
import uk.ac.uwe.ufcep603.hospital.ValidationException;
import uk.ac.uwe.ufcep603.hospital.WorkerContext;

import java.util.Map;

/**
 * {@code treatment.record-capacity-retry} - counts another attempt at reaching the external
 * treatment services.
 *
 * <p>The model increments {@code externalResourceAttempts} through an input mapping so the count is
 * visible in the diagram, and this worker records that the attempt happened. It exists so the retry
 * loop has a timestamped trail rather than silently going round again: the brief asks for further
 * attempts to be recorded without creating duplicate appointments.
 */
public final class TreatmentRecordCapacityRetryWorker extends AbstractHospitalWorker {

    public static final String JOB_TYPE = "treatment.record-capacity-retry";

    private static final int MAX_ATTEMPTS = 3;

    public TreatmentRecordCapacityRetryWorker(WorkerContext context, ZeebeClient client) {
        super(JOB_TYPE, context, client);
    }

    @Override
    protected Map<String, Object> execute(JobContext job) {
        int attempt = (int) job.numberOr("externalResourceAttempts",
                job.numberOr("externalResourceAttempt", 1));
        if (attempt < 1) {
            throw new ValidationException("externalResourceAttempts",
                    "Attempt counter must be at least 1 but was " + attempt
                            + " (job type " + JOB_TYPE + ")");
        }

        Map<String, Object> output = job.output();
        output.put("externalResourceAttempts", attempt);
        output.put("lastCapacityAttemptAt", context().clock().timestamp());
        output.put("capacityAttemptsRemaining", Math.max(0, MAX_ATTEMPTS - attempt));
        output.put("capacityExhausted", attempt >= MAX_ATTEMPTS);
        return output;
    }
}
