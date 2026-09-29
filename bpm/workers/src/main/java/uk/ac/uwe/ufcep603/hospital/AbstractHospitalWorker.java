package uk.ac.uwe.ufcep603.hospital;

import io.camunda.zeebe.client.ZeebeClient;
import io.camunda.zeebe.client.api.response.ActivatedJob;
import io.camunda.zeebe.client.api.worker.JobClient;
import io.camunda.zeebe.client.api.worker.JobHandler;
import io.camunda.zeebe.client.api.worker.JobWorker;
import io.camunda.zeebe.client.api.worker.JobWorkerBuilderStep1.JobWorkerBuilderStep3;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Shared base class for all 33 hospital job workers (the 32 domain service tasks plus the single
 * {@code publish-message} dispatcher).
 *
 * <p>It centralises exactly the things that must behave identically everywhere:
 * <ul>
 *   <li><b>subscription</b> - one job type per worker, with the concurrency, lock timeout and poll
 *       interval from {@code application.yaml} ({@link #subscribe()});</li>
 *   <li><b>logging</b> - every line carries the job key, element id and process instance key, so a
 *       demo can be followed next to Operate;</li>
 *   <li><b>variable extraction and validation</b> - via {@link JobContext}, which throws a clear
 *       {@link IllegalArgumentException} ({@link ValidationException}) naming the offending
 *       variable;</li>
 *   <li><b>completion</b> - the map returned by {@link #execute(JobContext)} becomes the job's
 *       output variables;</li>
 *   <li><b>failure semantics</b> - a {@link BpmnErrorException} is thrown as a BPMN error so the
 *       model's error boundary event catches it; anything else fails the job and decrements the
 *       remaining retries, leaving the engine retry policy ({@code retries="3"} in the BPMN) to
 *       decide what happens next.</li>
 * </ul>
 *
 * <p>Subclasses only implement {@link #execute(JobContext)}. No reflection, no annotation scanning:
 * the worker list is explicit in {@link Workers}.
 */
public abstract class AbstractHospitalWorker implements JobHandler {

    private static final Logger LOG = LoggerFactory.getLogger(AbstractHospitalWorker.class);
    private static final int MAX_ERROR_MESSAGE_LENGTH = 900;

    private final String jobType;
    private final WorkerContext context;
    private final ZeebeClient client;

    protected AbstractHospitalWorker(String jobType, WorkerContext context, ZeebeClient client) {
        this.jobType = jobType;
        this.context = context;
        this.client = client;
    }

    // ------------------------------------------------------------------ identity

    public final String jobType() {
        return jobType;
    }

    /**
     * Extra job type names this worker also subscribes to, so that a job type renamed on one side of
     * the model cannot silently leave a service task without a worker. Empty for all but a couple of
     * workers; see {@link #jobTypes()}.
     */
    protected List<String> additionalJobTypes() {
        return List.of();
    }

    /** The primary job type followed by any accepted aliases. */
    public final List<String> jobTypes() {
        List<String> types = new ArrayList<>();
        types.add(jobType);
        for (String alias : additionalJobTypes()) {
            if (!alias.isBlank() && !types.contains(alias)) {
                types.add(alias);
            }
        }
        return List.copyOf(types);
    }

    protected final WorkerContext context() {
        return context;
    }

    protected final ZeebeClient client() {
        return client;
    }

    // ------------------------------------------------------------------ subscription

    /**
     * Opens one job worker per accepted job type ({@link #jobTypes()}). Concurrency, lock timeout and
     * poll interval come from {@code workers.*} in {@code application.yaml}.
     */
    public final List<JobWorker> subscribeAll() {
        List<JobWorker> workers = new ArrayList<>();
        for (String type : jobTypes()) {
            JobWorkerBuilderStep3 builder = client.newWorker()
                    .jobType(type)
                    .handler(this)
                    .name(context.config().workerNamePrefix() + ":" + type)
                    .maxJobsActive(context.config().maxJobsActive())
                    .timeout(context.config().jobTimeout())
                    .pollInterval(context.config().pollInterval());
            workers.add(builder.open());
        }
        return List.copyOf(workers);
    }

    /** Convenience for the common single job type case. */
    public final JobWorker subscribe() {
        return subscribeAll().get(0);
    }

    // ------------------------------------------------------------------ handling

    /**
     * Handles one activated job. The method is {@code final} on purpose: every worker gets the same
     * completion / BPMN error / retryable failure behaviour.
     */
    @Override
    public final void handle(JobClient jobClient, ActivatedJob job) {
        // The activated job's own type is authoritative: it also covers accepted aliases.
        String effectiveType = job.getType() == null || job.getType().isBlank() ? jobType : job.getType();
        JobContext jobContext = new JobContext(job, effectiveType);
        try {
            injectForcedFailure(jobContext, effectiveType);
            Map<String, Object> output = execute(jobContext);
            Map<String, Object> variables = new LinkedHashMap<>();
            if (output != null) {
                for (Map.Entry<String, Object> entry : output.entrySet()) {
                    if (entry.getValue() == null) {
                        // A null output variable carries no meaning in Zeebe; drop it loudly instead
                        // of sending the engine something it would reject.
                        LOG.warn("ignoring null output variable '{}' from {}", entry.getKey(), jobContext.where());
                        continue;
                    }
                    variables.put(entry.getKey(), entry.getValue());
                }
            }
            jobClient.newCompleteCommand(job.getKey()).variables(variables).send().join();
            LOG.info("COMPLETED {} retriesLeft={} outputs={}",
                    jobContext.where(), job.getRetries(), variables.keySet());
        } catch (BpmnErrorException businessError) {
            LOG.warn("BPMN ERROR {} code={} message={}",
                    jobContext.where(), businessError.errorCode(), businessError.getMessage());
            try {
                jobClient.newThrowErrorCommand(job.getKey())
                        .errorCode(businessError.errorCode())
                        .errorMessage(trim(businessError.getMessage()))
                        .send()
                        .join();
            } catch (Exception throwFailure) {
                LOG.error("could not throw BPMN error {} for {}: {}",
                        businessError.errorCode(), jobContext.where(), throwFailure.toString());
            }
        } catch (Exception failure) {
            failJob(jobClient, jobContext, failure);
        }
    }

    /**
     * Applies the demo's simulated failure injection before the worker does any work, so that any
     * job type - not just the simulated external services - can be forced to fail. The BPMN error
     * code is either the one pinned in the configuration, or the service's canonical code, or none
     * at all, in which case the job simply fails and the engine retries it.
     */
    private void injectForcedFailure(JobContext jobContext, String effectiveType) {
        String errorCode = context().failures().forcedErrorCode(effectiveType);
        if (errorCode == null) {
            return;
        }
        String message = "[simulated] " + context().failures().forcedMessage(effectiveType)
                + " - forced by demo.simulated-failure for job type " + effectiveType
                + " on element " + jobContext.elementId();
        if (errorCode.isEmpty()) {
            throw new TransientJobException(message
                    + ". No BPMN error code is configured for this job type, so the job is failed and"
                    + " the engine retry policy applies.");
        }
        throw new BpmnErrorException(errorCode, message + " (error code " + errorCode + ")");
    }

    /** Fails the job and decrements the remaining retries, which is what the BPMN retries="3" means. */
    private void failJob(JobClient jobClient, JobContext jobContext, Exception failure) {
        String message = describe(failure);
        int remaining = Math.max(0, jobContext.retries() - 1);
        LOG.warn("FAILED {} remainingRetries={} reason={}", jobContext.where(), remaining, message);
        if (LOG.isDebugEnabled()) {
            LOG.debug("failure detail for {}", jobContext.where(), failure);
        }
        try {
            jobClient.newFailCommand(jobContext.jobKey())
                    .retries(remaining)
                    .errorMessage(trim(message))
                    .send()
                    .join();
        } catch (Exception sendFailure) {
            LOG.error("could not fail job {} (it will be retried after the lock timeout): {}",
                    jobContext.jobKey(), sendFailure.toString());
        }
    }

    private static String describe(Exception failure) {
        String message = failure.getMessage();
        if (failure instanceof ValidationException) {
            return message;
        }
        StringBuilder description = new StringBuilder();
        description.append(failure.getClass().getSimpleName());
        if (message != null && !message.isBlank()) {
            description.append(": ").append(message);
        }
        Throwable cause = failure.getCause();
        if (cause != null && cause != failure) {
            description.append(" (caused by ").append(cause.getClass().getSimpleName());
            if (cause.getMessage() != null) {
                description.append(": ").append(cause.getMessage());
            }
            description.append(')');
        }
        return description.toString();
    }

    private static String trim(String message) {
        if (message == null) {
            return "job failed without a message";
        }
        return message.length() <= MAX_ERROR_MESSAGE_LENGTH
                ? message
                : message.substring(0, MAX_ERROR_MESSAGE_LENGTH) + "...";
    }

    // ------------------------------------------------------------------ the one thing to implement

    /**
     * Does the work for one job.
     *
     * @param job the job's variables plus every shared helper
     * @return the output variables to write back; an empty map is fine, {@code null} is treated as
     *         an empty map
     * @throws BpmnErrorException for a business condition the model handles with a boundary event
     * @throws IllegalArgumentException for bad input (a {@link ValidationException} names the variable)
     */
    protected abstract Map<String, Object> execute(JobContext job) throws Exception;
}
