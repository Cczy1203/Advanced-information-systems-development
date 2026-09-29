package uk.ac.uwe.ufcep603.hospital.config;

import uk.ac.uwe.ufcep603.hospital.TransientJobException;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * Drives the simulated external failures used by the demonstration.
 *
 * <p>Two independent switches:
 * <ul>
 *   <li><b>BPMN error injection</b> - {@code demo.simulated-failure.enabled} plus a list of job
 *       types. Each activation of a listed job type throws that service's documented BPMN error,
 *       so the error boundary event on the model is genuinely exercised. In {@code once} mode only
 *       the first activation fails, which demonstrates the engine retry policy
 *       ({@code retries="3"} on every service task) recovering on the next attempt.</li>
 *   <li><b>Forced payment outcome</b> - {@code demo.payment.status} forces
 *       {@code payment.process-transaction} to return APPROVED / DECLINED / DUPLICATE, or, for
 *       {@code NO_CONFIRMATION}, to leave the job retrying so the caller's {@code PT2H} timer is
 *       the thing that fires.</li>
 * </ul>
 *
 * <p>The registry is thread safe: job workers run on a shared executor.
 */
public final class SimulatedFailureRegistry {

    /** Canonical BPMN error code thrown by each simulated external service. */
    private static final Map<String, String> DEFAULT_ERROR_CODES = Map.of(
            "correspondence.dispatch-letter", "CORRESPONDENCE_SERVICE_FAILED",
            "scheduling.find-appointment-slots", "SCHEDULING_SERVICE_UNAVAILABLE",
            "external-resources.check-availability", "EXTERNAL_RESOURCE_UNAVAILABLE",
            "payment.process-transaction", "PAYMENT_PROVIDER_UNAVAILABLE",
            "payment.process-refund", "PAYMENT_PROVIDER_UNAVAILABLE");

    private final boolean enabled;
    private final String mode;
    private final Map<String, String> jobTypesWithErrorCode;
    private final Set<String> alreadyFired = ConcurrentHashMap.newKeySet();

    private final String forcedPaymentStatus;
    private final boolean paymentStatusOnce;
    private final AtomicInteger paymentInvocations = new AtomicInteger();
    public SimulatedFailureRegistry(AppConfig config) {
        this.enabled = config.failureInjectionEnabled();
        this.mode = "ONCE".equals(config.failureInjectionMode()) ? "ONCE" : "ALWAYS";
        this.jobTypesWithErrorCode = parseJobTypes(config.failureInjectionJobTypes());
        this.forcedPaymentStatus = config.paymentStatus();
        this.paymentStatusOnce = config.paymentStatusOnce();
    }

    private static Map<String, String> parseJobTypes(List<String> configured) {
        Map<String, String> parsed = new LinkedHashMap<>();
        for (String entry : configured) {
            String jobType = entry;
            String errorCode = null;
            int separator = entry.indexOf(':');
            if (separator < 0) {
                separator = entry.indexOf('=');
            }
            if (separator > 0) {
                jobType = entry.substring(0, separator);
                errorCode = entry.substring(separator + 1).trim();
            }
            jobType = jobType.trim();
            if (!jobType.isEmpty()) {
                // The value is null when a job type was configured without a pinned error code;
                // Map.copyOf rejects null values, so an unmodifiable LinkedHashMap is used instead.
                parsed.put(jobType, errorCode == null || errorCode.isEmpty() ? null : errorCode);
            }
        }
        return java.util.Collections.unmodifiableMap(parsed);
    }

    // ------------------------------------------------------------------ BPMN error injection

    /**
     * @return {@code true} when the next activation of this job type must fail with its BPMN error.
     */
    public boolean shouldInjectFailure(String jobType) {
        if (!enabled || !jobTypesWithErrorCode.containsKey(jobType)) {
            return false;
        }
        if ("ONCE".equals(mode)) {
            return alreadyFired.add(jobType);
        }
        return true;
    }

    /**
     * The error code the demo wants this job type to fail with, consulted by
     * {@link uk.ac.uwe.ufcep603.hospital.AbstractHospitalWorker} before any worker runs.
     *
     * @return {@code null} when no failure is configured for this job type; an empty string when the
     *         failure must be a plain job failure (retryable, no BPMN error boundary needed);
     *         otherwise the BPMN error code to throw
     */
    public String forcedErrorCode(String jobType) {
        if (!shouldInjectFailure(jobType)) {
            return null;
        }
        String configured = jobTypesWithErrorCode.get(jobType);
        if (configured != null && !configured.isBlank()) {
            return configured;
        }
        String canonical = DEFAULT_ERROR_CODES.get(jobType);
        return canonical == null ? "" : canonical;
    }

    /** Human readable explanation for a forced failure, mentioning the service where there is one. */
    public String forcedMessage(String jobType) {
        return switch (jobType) {
            case "correspondence.dispatch-letter" ->
                    "the external correspondence service rejected the request";
            case "scheduling.find-appointment-slots" ->
                    "the external scheduling service is unavailable";
            case "external-resources.check-availability" ->
                    "the external treatment, laboratory or imaging service is unavailable";
            case "payment.process-transaction", "payment.process-refund" ->
                    "the external payment service provider is unavailable";
            default -> "a failure was forced for this job type by the demo configuration";
        };
    }

    // ------------------------------------------------------------------ forced payment outcome

    /**
     * @return the payment status this transaction should report:
     *         the configured override, or {@code APPROVED} by default. When
     *         {@code demo.payment.status-once} is {@code true} the override applies to the first
     *         transaction only.
     */
    public String paymentStatus() {
        int invocation = paymentInvocations.incrementAndGet();
        if (forcedPaymentStatus == null || forcedPaymentStatus.isBlank()) {
            return "APPROVED";
        }
        if (paymentStatusOnce && invocation > 1) {
            return "APPROVED";
        }
        return forcedPaymentStatus;
    }

    /**
     * The "confirmation lost" branch: the provider takes the money but nothing comes back. The job
     * is failed (not a BPMN error) so it is retried by the engine and eventually becomes an
     * incident; the caller's timer is what moves its own process on.
     */
    public void failForLostConfirmation(String jobType) {
        throw new TransientJobException("[simulated] " + jobType
                + ": confirmation never returned by the payment provider. The job is failed on purpose"
                + " so the engine retry policy applies; the caller's PT2H timer is what fires.");
    }

    public Map<String, Object> summary() {
        Map<String, Object> summary = new LinkedHashMap<>();
        summary.put("enabled", enabled);
        summary.put("mode", mode);
        summary.put("jobTypes", jobTypesWithErrorCode.keySet());
        summary.put("paymentStatus", forcedPaymentStatus);
        summary.put("paymentStatusOnce", paymentStatusOnce);
        return summary;
    }

    /** Canonical BPMN error code for a simulated service, for diagnostics. */
    public static String canonicalErrorCode(String jobType) {
        return DEFAULT_ERROR_CODES.get(jobType);
    }
}
