package uk.ac.uwe.ufcep603.hospital.config;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.dataformat.yaml.YAMLFactory;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.time.LocalDate;
import java.time.format.DateTimeParseException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

/**
 * Configuration for the hospital external workers.
 *
 * <p>Resolution order, highest priority first:
 * <ol>
 *   <li>environment variables (the key path in upper case, dots and dashes replaced by
 *       underscores, e.g. {@code camunda.client.zeebe.gateway-address} becomes
 *       {@code CAMUNDA_CLIENT_ZEEBE_GATEWAY_ADDRESS});</li>
 *   <li>a YAML file supplied with {@code --config=...} / {@code WORKERS_CONFIG=...}
 *       (merged over the template);</li>
 *   <li>{@code application.yaml} from the classpath (the template shipped in the jar);</li>
 *   <li>the built-in defaults below.</li>
 * </ol>
 *
 * <p>Nothing here depends on Spring: the project is deliberately a plain
 * {@code main()} program so it can be run with {@code java -jar} or {@code mvn exec:java}.
 */
public final class AppConfig {

    private static final String TEMPLATE = "/application.yaml";

    private final Map<String, Object> fileValues;
    private final Map<String, String> environment;

    private AppConfig(Map<String, Object> fileValues, Map<String, String> environment) {
        this.fileValues = fileValues;
        this.environment = environment;
    }

    // ------------------------------------------------------------------ loading

    public static AppConfig load(String[] args) {
        return load(args, System.getenv());
    }

    public static AppConfig load(String[] args, Map<String, String> environment) {
        Map<String, Object> values = new LinkedHashMap<>();
        merge(values, readClasspathTemplate());
        Path override = overridePath(args, environment);
        if (override != null) {
            merge(values, readFile(override));
        }
        return new AppConfig(values, environment == null ? Map.of() : environment);
    }

    private static Path overridePath(String[] args, Map<String, String> environment) {
        for (String arg : args == null ? new String[0] : args) {
            if (arg.startsWith("--config=")) {
                return Path.of(arg.substring("--config=".length()));
            }
        }
        String fromEnvironment = environment.get("WORKERS_CONFIG");
        return fromEnvironment == null || fromEnvironment.isBlank() ? null : Path.of(fromEnvironment);
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> readClasspathTemplate() {
        try (InputStream in = AppConfig.class.getResourceAsStream(TEMPLATE)) {
            if (in == null) {
                return Map.of();
            }
            ObjectMapper mapper = new ObjectMapper(new YAMLFactory());
            Map<String, Object> parsed = mapper.readValue(in, Map.class);
            return parsed == null ? Map.of() : parsed;
        } catch (IOException e) {
            throw new IllegalStateException("could not read " + TEMPLATE + " from the classpath", e);
        }
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> readFile(Path path) {
        if (!Files.isReadable(path)) {
            throw new IllegalStateException("configuration file is not readable: " + path.toAbsolutePath());
        }
        try (InputStream in = Files.newInputStream(path)) {
            ObjectMapper mapper = new ObjectMapper(new YAMLFactory());
            Map<String, Object> parsed = mapper.readValue(in, Map.class);
            return parsed == null ? Map.of() : parsed;
        } catch (IOException e) {
            throw new IllegalStateException("could not read configuration file " + path.toAbsolutePath(), e);
        }
    }

    @SuppressWarnings("unchecked")
    private static void merge(Map<String, Object> target, Map<String, Object> overlay) {
        for (Map.Entry<String, Object> entry : overlay.entrySet()) {
            Object existing = target.get(entry.getKey());
            if (existing instanceof Map && entry.getValue() instanceof Map) {
                merge((Map<String, Object>) existing, (Map<String, Object>) entry.getValue());
            } else {
                target.put(entry.getKey(), entry.getValue());
            }
        }
    }

    // ------------------------------------------------------------------ accessors

    /** Raw value for a dotted key path, environment first, then the YAML file. */
    private Object raw(String key, String... alternativeEnvironmentKeys) {
        String fromEnvironment = firstEnvironment(alternativeEnvironmentKeys);
        if (fromEnvironment != null) {
            return fromEnvironment;
        }
        Object cursor = fileValues;
        for (String segment : key.split("\\.")) {
            if (!(cursor instanceof Map)) {
                return null;
            }
            cursor = ((Map<?, ?>) cursor).get(segment);
        }
        return cursor;
    }

    private String firstEnvironment(String... keys) {
        for (String key : keys) {
            String value = environment.get(key);
            if (value != null && !value.isBlank()) {
                return value;
            }
        }
        return null;
    }

    private static String environmentKey(String dottedKey) {
        return dottedKey.toUpperCase(Locale.ROOT).replace('.', '_').replace('-', '_');
    }

    private String string(String key, String fallback, String... extraEnvironmentKeys) {
        List<String> keys = new ArrayList<>();
        keys.add(environmentKey(key));
        keys.addAll(Arrays.asList(extraEnvironmentKeys));
        Object value = raw(key, keys.toArray(new String[0]));
        if (value == null) {
            return fallback;
        }
        String text = String.valueOf(value).trim();
        return text.isEmpty() ? fallback : text;
    }

    private boolean bool(String key, boolean fallback, String... extraEnvironmentKeys) {
        List<String> keys = new ArrayList<>();
        keys.add(environmentKey(key));
        keys.addAll(Arrays.asList(extraEnvironmentKeys));
        Object value = raw(key, keys.toArray(new String[0]));
        if (value == null) {
            return fallback;
        }
        if (value instanceof Boolean b) {
            return b;
        }
        return switch (String.valueOf(value).trim().toLowerCase(Locale.ROOT)) {
            case "true", "yes", "1", "on" -> true;
            case "false", "no", "0", "off" -> false;
            default -> fallback;
        };
    }

    private int integer(String key, int fallback, String... extraEnvironmentKeys) {
        List<String> keys = new ArrayList<>();
        keys.add(environmentKey(key));
        keys.addAll(Arrays.asList(extraEnvironmentKeys));
        Object value = raw(key, keys.toArray(new String[0]));
        if (value instanceof Number number) {
            return number.intValue();
        }
        if (value == null) {
            return fallback;
        }
        try {
            return Integer.parseInt(String.valueOf(value).trim());
        } catch (NumberFormatException e) {
            throw new IllegalStateException("configuration key " + key + " must be an integer but was '"
                    + value + "'", e);
        }
    }

    private List<String> stringList(String key, List<String> fallback, String... extraEnvironmentKeys) {
        List<String> keys = new ArrayList<>();
        keys.add(environmentKey(key));
        keys.addAll(Arrays.asList(extraEnvironmentKeys));
        Object value = raw(key, keys.toArray(new String[0]));
        if (value == null) {
            return fallback;
        }
        Set<String> result = new LinkedHashSet<>();
        if (value instanceof Iterable<?> iterable) {
            for (Object element : iterable) {
                if (element != null && !String.valueOf(element).isBlank()) {
                    result.add(String.valueOf(element).trim());
                }
            }
        } else {
            for (String piece : String.valueOf(value).split(",")) {
                if (!piece.isBlank()) {
                    result.add(piece.trim());
                }
            }
        }
        return List.copyOf(result);
    }

    // ------------------------------------------------------------------ camunda client

    public String gatewayAddress() {
        return string("camunda.client.zeebe.gateway-address", "localhost:26500",
                "ZEEBE_GATEWAY_ADDRESS", "CAMUNDA_CLIENT_ZEEBE_GATEWAYADDRESS");
    }

    public boolean plaintext() {
        return bool("camunda.client.zeebe.plaintext", true, "ZEEBE_PLAINTEXT");
    }

    public Duration requestTimeout() {
        return Duration.ofMillis(integer("camunda.client.zeebe.request-timeout-ms", 20_000));
    }

    // ------------------------------------------------------------------ workers

    public String workerNamePrefix() {
        return string("workers.name-prefix", "hospital-external-workers");
    }

    public int maxJobsActive() {
        return integer("workers.max-jobs-active", 32);
    }

    public Duration jobTimeout() {
        return Duration.ofMillis(integer("workers.job-timeout-ms", 30_000));
    }

    public Duration pollInterval() {
        return Duration.ofMillis(integer("workers.poll-interval-ms", 100));
    }

    public int executionThreads() {
        return integer("workers.execution-threads", 4);
    }

    // ------------------------------------------------------------------ demo switches

    public boolean failureInjectionEnabled() {
        return bool("demo.simulated-failure.enabled", false);
    }

    /** Entries are either {@code job.type} or {@code job.type:ERROR_CODE}. */
    public List<String> failureInjectionJobTypes() {
        return stringList("demo.simulated-failure.job-types", List.of());
    }

    /** {@code always} or {@code once}. */
    public String failureInjectionMode() {
        return string("demo.simulated-failure.mode", "always").toUpperCase(Locale.ROOT);
    }

    public String paymentStatus() {
        return string("demo.payment.status", "APPROVED").toUpperCase(Locale.ROOT);
    }

    public boolean paymentStatusOnce() {
        return bool("demo.payment.status-once", true);
    }

    /**
     * How {@code payment.process-transaction} reports the "confirmation lost" scenario:
     * <ul>
     *   <li>{@code bpmn-error} (default) - throw {@code PAYMENT_CONFIRMATION_LOST}, which the model
     *       catches with the boundary event {@code TRT_Bnd_ConfirmationLost} and routes to Finance
     *       for investigation;</li>
     *   <li>{@code retry} - fail the job so the engine retry policy applies and the job is left
     *       retrying, which is the behaviour to use with a model whose caller waits on a timer.</li>
     * </ul>
     */
    public String confirmationLostMode() {
        return string("demo.payment.confirmation-lost-mode", "bpmn-error",
                "DEMO_PAYMENT_CONFIRMATION_LOST_MODE").toUpperCase(Locale.ROOT);
    }

    public String refundStatus() {
        return string("demo.payment.refund-status", "REFUNDED", "DEMO_REFUND_STATUS").toUpperCase(Locale.ROOT);
    }

    public boolean schedulingForceNoSlots() {
        return bool("demo.scheduling.force-no-slots", false, "DEMO_SCHEDULING_NO_SLOTS");
    }

    public List<String> unavailableResources() {
        return stringList("demo.external.unavailable-resources", List.of(), "DEMO_EXTERNAL_UNAVAILABLE");
    }

    public String pathwayScenario() {
        return string("demo.pathway.scenario", "THREE_MONTHS").toUpperCase(Locale.ROOT);
    }

    public int reminderCooldownDays() {
        return integer("demo.pathway.reminder-cooldown-days", 0);
    }

    /** Fixed demo date, or {@code null} when the real system date should be used. */
    public LocalDate demoToday() {
        String value = string("demo.clock.today", null);
        if (value == null) {
            return null;
        }
        try {
            return LocalDate.parse(value);
        } catch (DateTimeParseException e) {
            throw new IllegalStateException("demo.clock.today must be an ISO date (yyyy-MM-dd) but was '"
                    + value + "'", e);
        }
    }

    public int demoClockOffsetDays() {
        return integer("demo.clock.offset-days", 0);
    }

    // ------------------------------------------------------------------ diagnostics

    /** Redacted, printable view of the effective configuration. */
    public Map<String, Object> summary() {
        Map<String, Object> summary = new LinkedHashMap<>();
        summary.put("gateway", gatewayAddress());
        summary.put("plaintext", plaintext());
        summary.put("requestTimeout", requestTimeout().toMillis() + "ms");
        summary.put("maxJobsActive", maxJobsActive());
        summary.put("jobTimeout", jobTimeout().toMillis() + "ms");
        summary.put("pollInterval", pollInterval().toMillis() + "ms");
        summary.put("executionThreads", executionThreads());
        summary.put("failureInjection", failureInjectionEnabled()
                ? failureInjectionMode() + " " + failureInjectionJobTypes()
                : "off");
        summary.put("paymentStatus", paymentStatus() + (paymentStatusOnce() ? " (first only)" : " (always)"));
        summary.put("confirmationLostMode", confirmationLostMode());
        summary.put("refundStatus", refundStatus());
        summary.put("pathwayScenario", pathwayScenario());
        return summary;
    }
}
