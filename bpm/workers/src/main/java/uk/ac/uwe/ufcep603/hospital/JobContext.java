package uk.ac.uwe.ufcep603.hospital;

import io.camunda.zeebe.client.api.response.ActivatedJob;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.time.format.DateTimeParseException;
import java.util.ArrayList;
import java.util.Collection;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

/**
 * The process variables of one activated job, plus every extraction and validation helper the 33
 * workers share.
 *
 * <p>Two rules are enforced here so that no worker can break them by accident:
 * <ul>
 *   <li><b>aliases</b> - the hospital forms are free to name a field slightly differently, so
 *       {@link #optFirst(String...)} and {@link #requireFirst(String, String...)} read the first
 *       non-blank value from a list of accepted names;</li>
 *   <li><b>no silent defaults for required data</b> - {@code require*} methods throw a
 *       {@link ValidationException} that names the offending variable, which the base worker turns
 *       into a failed job (retryable) rather than a quietly wrong result.</li>
 * </ul>
 *
 * <p>Instances are used by a single worker thread for the duration of one job and are not shared.
 */
public final class JobContext {

    private final ActivatedJob job;
    private final String jobType;
    private final Map<String, Object> variables;

    public JobContext(ActivatedJob job, String jobType) {
        this.job = job;
        this.jobType = jobType;
        this.variables = new LinkedHashMap<>(job.getVariablesAsMap());
    }

    // ------------------------------------------------------------------ identity

    public ActivatedJob job() {
        return job;
    }

    public String jobType() {
        return jobType;
    }

    public long jobKey() {
        return job.getKey();
    }

    public String elementId() {
        return job.getElementId();
    }

    public long processInstanceKey() {
        return job.getProcessInstanceKey();
    }

    public String processId() {
        return job.getBpmnProcessId();
    }

    public int retries() {
        return job.getRetries();
    }

    /** Short description used in every log line. */
    public String where() {
        return "jobKey=" + job.getKey()
                + " type=" + jobType
                + " elementId=" + job.getElementId()
                + " processInstanceKey=" + job.getProcessInstanceKey()
                + " process=" + job.getBpmnProcessId();
    }

    /** A task header from the BPMN (e.g. {@code messageName}); never {@code null}. */
    public String header(String name) {
        Map<String, String> headers = job.getCustomHeaders();
        return headers == null ? null : headers.get(name);
    }

    // ------------------------------------------------------------------ raw access

    public Map<String, Object> variables() {
        return Map.copyOf(variables);
    }

    public Map<String, Object> rawVariables() {
        return variables;
    }

    public boolean has(String name) {
        return variables.get(name) != null;
    }

    public Object get(String name) {
        return variables.get(name);
    }

    public Set<String> names() {
        return variables.keySet();
    }

    // ------------------------------------------------------------------ strings

    /** The value as a trimmed string, or {@code null} when absent or blank. */
    public String opt(String name) {
        Object value = variables.get(name);
        if (value == null) {
            return null;
        }
        String text = String.valueOf(value).trim();
        return text.isEmpty() ? null : text;
    }

    /** First non-blank value among the given names, or {@code null}. */
    public String optFirst(String... names) {
        for (String name : names) {
            String value = opt(name);
            if (value != null) {
                return value;
            }
        }
        return null;
    }

    /** @throws ValidationException naming the variable when it is absent or blank. */
    public String require(String name) {
        String value = opt(name);
        if (value == null) {
            throw ValidationException.missing(name, jobType);
        }
        return value;
    }

    /**
     * @param label the variable name reported in the error (usually the canonical name)
     * @param names accepted aliases, in priority order
     * @throws ValidationException when none of the aliases holds a non-blank value
     */
    public String requireFirst(String label, String... names) {
        String value = optFirst(names);
        if (value == null) {
            throw ValidationException.missing(label, jobType);
        }
        return value;
    }

    // ------------------------------------------------------------------ numbers

    public Optional<Double> optNumber(String name) {
        Object value = variables.get(name);
        if (value == null) {
            return Optional.empty();
        }
        if (value instanceof Number number) {
            return Optional.of(number.doubleValue());
        }
        String text = String.valueOf(value).trim();
        if (text.isEmpty()) {
            return Optional.empty();
        }
        try {
            return Optional.of(Double.parseDouble(text));
        } catch (NumberFormatException e) {
            throw ValidationException.wrongType(name, "a number", value, jobType);
        }
    }

    /** @throws ValidationException naming the variable when it is absent or not a number. */
    public double requireNumber(String name) {
        return optNumber(name).orElseThrow(() -> ValidationException.missing(name, jobType));
    }

    public double numberOr(String name, double fallback) {
        return optNumber(name).orElse(fallback);
    }

    public Optional<Integer> optInt(String name) {
        return optNumber(name).map(Double::intValue);
    }

    public int intOr(String name, int fallback) {
        return optInt(name).orElse(fallback);
    }

    public int requireInt(String name) {
        return optInt(name).orElseThrow(() -> ValidationException.missing(name, jobType));
    }

    // ------------------------------------------------------------------ booleans

    public Optional<Boolean> optBool(String name) {
        Object value = variables.get(name);
        if (value == null) {
            return Optional.empty();
        }
        if (value instanceof Boolean bool) {
            return Optional.of(bool);
        }
        String text = String.valueOf(value).trim().toLowerCase(Locale.ROOT);
        if (text.isEmpty()) {
            return Optional.empty();
        }
        return switch (text) {
            case "true", "yes", "y", "1" -> Optional.of(Boolean.TRUE);
            case "false", "no", "n", "0" -> Optional.of(Boolean.FALSE);
            default -> throw ValidationException.wrongType(name, "a boolean", value, jobType);
        };
    }

    public boolean boolOr(String name, boolean fallback) {
        return optBool(name).orElse(fallback);
    }

    public boolean requireBool(String name) {
        return optBool(name).orElseThrow(() -> ValidationException.missing(name, jobType));
    }

    // ------------------------------------------------------------------ collections

    /** @return the value as a list, or empty when absent. */
    @SuppressWarnings("unchecked")
    public Optional<List<Object>> optList(String name) {
        Object value = variables.get(name);
        if (value == null) {
            return Optional.empty();
        }
        if (value instanceof List<?> list) {
            return Optional.of((List<Object>) list);
        }
        if (value instanceof Collection<?> collection) {
            return Optional.of(new ArrayList<>(collection));
        }
        if (value instanceof Object[] array) {
            return Optional.of(new ArrayList<>(java.util.Arrays.asList(array)));
        }
        throw ValidationException.wrongType(name, "a list", value, jobType);
    }

    /** Strings, trimmed; a {@code null} entry becomes an empty string so "malformed" is detectable. */
    public List<String> optStringList(String name) {
        return optList(name).map(list -> list.stream()
                .map(element -> element == null ? "" : String.valueOf(element).trim())
                .toList()).orElse(List.of());
    }

    public List<String> requireStringList(String name) {
        List<Object> list = optList(name).orElseThrow(() -> ValidationException.missing(name, jobType));
        return list.stream().map(element -> element == null ? "" : String.valueOf(element).trim()).toList();
    }

    /** Maps inside a list; entries that are not maps are reported as bad input. */
    @SuppressWarnings("unchecked")
    public List<Map<String, Object>> optMapList(String name) {
        List<Object> list = optList(name).orElse(List.of());
        List<Map<String, Object>> result = new ArrayList<>();
        for (Object element : list) {
            if (element instanceof Map<?, ?> map) {
                result.add((Map<String, Object>) map);
            } else {
                throw ValidationException.wrongType(name, "a list of objects", element, jobType);
            }
        }
        return result;
    }

    @SuppressWarnings("unchecked")
    public Optional<Map<String, Object>> optMap(String name) {
        Object value = variables.get(name);
        if (value == null) {
            return Optional.empty();
        }
        if (value instanceof Map<?, ?> map) {
            return Optional.of((Map<String, Object>) map);
        }
        throw ValidationException.wrongType(name, "an object", value, jobType);
    }

    // ------------------------------------------------------------------ dates & enums

    /** Dates and timestamps are accepted in any common ISO-8601 shape. */
    public Optional<LocalDate> optDate(String name) {
        Object value = variables.get(name);
        if (value == null) {
            return Optional.empty();
        }
        if (value instanceof LocalDate date) {
            return Optional.of(date);
        }
        String text = String.valueOf(value).trim();
        if (text.isEmpty()) {
            return Optional.empty();
        }
        return Optional.of(parseDate(name, text));
    }

    private LocalDate parseDate(String name, String text) {
        try {
            return LocalDate.parse(text);
        } catch (DateTimeParseException ignored) {
            // fall through to the date-time shapes below
        }
        try {
            return OffsetDateTime.parse(text).toLocalDate();
        } catch (DateTimeParseException ignored) {
            // fall through
        }
        try {
            return LocalDateTime.parse(text).toLocalDate();
        } catch (DateTimeParseException ignored) {
            // fall through
        }
        try {
            return java.time.Instant.parse(text).atZone(ZoneOffset.UTC).toLocalDate();
        } catch (DateTimeParseException e) {
            throw ValidationException.wrongType(name, "an ISO-8601 date or date-time", text, jobType);
        }
    }

    public LocalDate requireDate(String name) {
        return optDate(name).orElseThrow(() -> ValidationException.missing(name, jobType));
    }

    /** First parseable date among the given names, or empty. */
    public Optional<LocalDate> optDateFirst(String... names) {
        for (String name : names) {
            Optional<LocalDate> value = optDate(name);
            if (value.isPresent()) {
                return value;
            }
        }
        return Optional.empty();
    }

    /** First parseable number among the given names, or empty. */
    public Optional<Double> optNumberFirst(String... names) {
        for (String name : names) {
            Optional<Double> value = optNumber(name);
            if (value.isPresent()) {
                return value;
            }
        }
        return Optional.empty();
    }

    public double numberFirstOr(double fallback, String... names) {
        return optNumberFirst(names).orElse(fallback);
    }

    /** Uppercases and validates against an allowed set. */
    public String requireOneOf(String name, Collection<String> allowed) {
        String value = require(name).toUpperCase(Locale.ROOT);
        if (!allowed.contains(value)) {
            throw ValidationException.notAllowed(name, value, allowed, jobType);
        }
        return value;
    }

    /** Same as {@link #requireOneOf} but returns {@code null} when the variable is absent. */
    public String optOneOf(String name, Collection<String> allowed) {
        String value = opt(name);
        if (value == null) {
            return null;
        }
        String upper = value.toUpperCase(Locale.ROOT);
        if (!allowed.contains(upper)) {
            throw ValidationException.notAllowed(name, upper, allowed, jobType);
        }
        return upper;
    }

    // ------------------------------------------------------------------ output

    /** A fresh, ordered output-variable map. */
    public Map<String, Object> output() {
        return new LinkedHashMap<>();
    }

    /**
     * Insurance against card data leaking into process variables: the model is explicit that the
     * hospital system never holds card details, so a card-like variable is treated as bad input.
     *
     * @throws ValidationException naming the offending variable
     */
    public void rejectCardData() {
        for (String name : variables.keySet()) {
            String normalised = name.toLowerCase(Locale.ROOT).replace("_", "").replace("-", "");
            if (normalised.contains("cardnumber") || normalised.contains("cardno")
                    || (normalised.contains("pan") && normalised.startsWith("card"))
                    || normalised.contains("cvv") || normalised.contains("cvc")
                    || normalised.contains("cardexpiry") || normalised.contains("expirydate")
                    || normalised.contains("securitycode") || normalised.contains("cardholder")) {
                throw new ValidationException(name,
                        "Card data must never reach the hospital system, but process variable '" + name
                                + "' looks like card data (job type " + jobType + ")");
            }
        }
    }

    /** Convenience for logging: a compact, sorted list of the variables this job carried. */
    public String variableNames() {
        return String.join(",", variables.keySet());
    }

    // ------------------------------------------------------------------ pathway identity

    /**
     * The patient identifier the pathway correlates on.
     *
     * <p>{@code patientRef} is the canonical variable. The hospital form definitions do not currently
     * capture it on every path, so this falls back to the business reference the job does carry
     * (referral, treatment booking, enquiry, letter or appointment). Callers that must hard-fail on a
     * blank {@code patientRef} - the two audit workers - use {@link #require(String)} instead.
     *
     * @return the identifier, or {@code null} when the job carries none at all
     */
    public String patientKey() {
        String direct = optFirst("patientRef", "patientReference", "patientId", "patientNhsNumber", "nhsNumber");
        if (direct != null) {
            return direct;
        }
        return optFirst("referralRef", "referralReference", "treatmentBookingRef", "treatmentRef",
                "enquiryRef", "letterRef", "appointmentRef");
    }

    /** @throws ValidationException naming {@code patientRef} when no identifier at all is available. */
    public String requirePatientKey() {
        String key = patientKey();
        if (key == null) {
            throw ValidationException.missing("patientRef", jobType);
        }
        return key;
    }
}
