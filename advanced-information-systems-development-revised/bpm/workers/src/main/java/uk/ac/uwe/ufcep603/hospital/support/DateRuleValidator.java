package uk.ac.uwe.ufcep603.hospital.support;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import uk.ac.uwe.ufcep603.hospital.BpmnErrorException;
import uk.ac.uwe.ufcep603.hospital.JobContext;
import uk.ac.uwe.ufcep603.hospital.ValidationException;

import java.io.IOException;
import java.io.InputStream;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

/**
 * Server-side backstop for date rules.
 *
 * <h2>Why this layer is needed</h2>
 * The marker feedback asks for "invalid or unsuitable dates" to be prevented. The form
 * layer already does what it can, but **a form cannot stop an API call**: form-js
 * implements {@code disallowPassedDates} by setting flatpickr's {@code minDate: 'today'},
 * which is a **picker constraint** that the {@code hc()} validation function never checks at
 * render time. That means:
 * <ul>
 *   <li>a person clicking the calendar in Tasklist cannot select a past date ✔</li>
 *   <li>a direct call to the orchestration API submitting {@code referralDate = 2099-01-01}
 *       is not stopped by the form layer at all ✘</li>
 * </ul>
 * so the server needs a second layer. This class is that layer, and the rule table lives in
 * {@code src/main/resources/date-rules.json}, the **same file** that the form hardening
 * script on the Python side reads, so the two sets of rules cannot drift apart.
 *
 * <h2>Comparison granularity: by date, not by time of day</h2>
 * This matches form-js's {@code minDate: 'today'} (endpoints included) and also avoids
 * judging a value such as today's date with a {@code T09:00:00} time part as "already
 * past" after 9 a.m. The demo script auto_driver.py fills the form using
 * {@code TODAY + "T09:00:00"}, and comparing by time of day would break every one of
 * those submissions.
 *
 * <h2>Failure semantics</h2>
 * A violation throws {@link BpmnErrorException} with the code {@code INVALID_DATE}, which
 * {@code AbstractHospitalWorker} turns into a {@code throwError} command. The token then leaves the
 * service task through that task's {@code INVALID_DATE} boundary event, which routes it back to the
 * user task that captured the date so the form can be corrected and submitted again.
 *
 * <p>It used to throw {@link ValidationException}, which failed the job: the model's three retries
 * were spent on three identical attempts to fix a date that only a person can correct, and the
 * instance then parked on an incident. A date the user typed is bad input, not a transient fault,
 * so retrying it was the wrong semantic. The {@code INVALID_DATE} code is declared in the model
 * and every service task that can be the first one reached after a date-capturing user task carries
 * the matching boundary event; {@code tools/spec_v3.py} refuses to build the model otherwise.
 *
 * <h2>What happens when loading fails</h2>
 * A missing resource is a packaging error. Validation is then **skipped** (fail-open) but an
 * ERROR is logged and the state is exposed to the start-up banner ({@link #summary()}), and
 * a unit test checks that it must load. fail-open was chosen over fail-closed because
 * fail-closed would stop all 36 workers as soon as the resource is missing, a far greater
 * loss than the benefit.
 */
public final class DateRuleValidator {

    private static final Logger LOG = LoggerFactory.getLogger(DateRuleValidator.class);
    private static final String RESOURCE = "/date-rules.json";

    /** Variable name -> rule: the date part must be <= today (record-style dates). */
    /** The BPMN error code the model declares for a date that breaks the shared rule table. */
    public static final String INVALID_DATE = "INVALID_DATE";

    private static final Set<String> NOT_IN_FUTURE = new LinkedHashSet<>();
    /** Variable name -> rule: the date part must be >= today (appointment/scheduling dates). */
    private static final Set<String> NOT_IN_PAST = new LinkedHashSet<>();
    /** Cross-field ordering rule: {start variable, end variable}. */
    private static final List<String[]> ORDERED_PAIRS = new ArrayList<>();
    /** Reason loading failed; null means it loaded successfully. */
    private static final String LOAD_ERROR;
    private static final String VERSION;

    static {
        String error = null;
        String version = "unknown";
        try (InputStream in = DateRuleValidator.class.getResourceAsStream(RESOURCE)) {
            if (in == null) {
                error = "resource " + RESOURCE + " not found on the classpath";
            } else {
                JsonNode root = new ObjectMapper().readTree(in);
                version = root.path("version").asText("unknown");
                for (JsonNode node : root.path("futureDates")) {
                    String field = node.path("field").asText("");
                    if (!field.isBlank()) {
                        NOT_IN_PAST.add(field);
                    }
                }
                for (JsonNode node : root.path("pastOnlyDates")) {
                    String field = node.path("field").asText("");
                    if (!field.isBlank()) {
                        NOT_IN_FUTURE.add(field);
                    }
                }
                for (JsonNode node : root.path("crossFieldRules")) {
                    JsonNode fields = node.path("fields");
                    if (fields.isArray() && fields.size() == 2) {
                        ORDERED_PAIRS.add(new String[]{fields.get(0).asText(), fields.get(1).asText()});
                    }
                }
            }
        } catch (IOException | RuntimeException failure) {
            error = failure.getClass().getSimpleName() + ": " + failure.getMessage();
        }
        LOAD_ERROR = error;
        VERSION = version;
        if (error != null) {
            LOG.error("Date rule validation is DISABLED: {}", error);
        } else {
            LOG.info("Date rules loaded (version {}): {} must not be in the past, {} must not be in the future, "
                            + "{} ordered pair(s)",
                    version, NOT_IN_PAST.size(), NOT_IN_FUTURE.size(), ORDERED_PAIRS.size());
        }
    }

    private DateRuleValidator() {
    }

    /**
     * Validates every constrained date that appears in a job.
     *
     * <p>{@code clock} is passed in so that {@code demo.clock.today} and
     * {@code demo.clock.offset-days} are honoured: the demo can freeze "today" and
     * validation must use that same "today", otherwise the demo would be stopped by its own
     * validation.
     *
     * @throws BpmnErrorException with code {@code INVALID_DATE} when any date breaks a rule; the
     *         message carries the variable name, the actual value and the element
     */
    public static void validate(JobContext job, DemoClock clock) {
        if (LOAD_ERROR != null) {
            return; // fail-open; an ERROR was already logged during static initialisation
        }
        LocalDate today = clock.today();

        for (String name : NOT_IN_FUTURE) {
            LocalDate value = read(job, name);
            if (value != null && value.isAfter(today)) {
                throw reject(name, value, "not in the future (today is " + today + ")", job);
            }
        }

        for (String name : NOT_IN_PAST) {
            LocalDate value = read(job, name);
            if (value != null && value.isBefore(today)) {
                throw reject(name, value, "not in the past (today is " + today + ")", job);
            }
        }

        for (String[] pair : ORDERED_PAIRS) {
            LocalDate from = read(job, pair[0]);
            LocalDate to = read(job, pair[1]);
            if (from != null && to != null && to.isBefore(from)) {
                throw reject(pair[1], to,
                        "not earlier than '" + pair[0] + "' (which is " + from + ")", job);
            }
        }
    }

    /**
     * Reads a date variable; returns {@code null} if it is absent or is not a date.
     *
     * <p>This deliberately does **not** fail when "the value is not a valid date":
     * formatting problems are reported by each worker's own {@code requireDate} /
     * {@code optDate} where the variable is actually needed, and this class only performs
     * range checks. The swallowed exception is logged at debug level, so that a check never
     * looks as though it ran when it did not.
     */
    /**
     * A date that breaks the shared rule table is an <b>input</b> problem, not a fault of the
     * service that happened to notice it, so it is raised as a BPMN error rather than by failing
     * the job.
     *
     * <p>The distinction matters at run time. Failing the job spends the model's retries and ends
     * as an incident that parks the instance until somebody edits a variable by hand, and three
     * identical attempts cannot fix a date a person typed. A BPMN error instead leaves the service
     * task through the model's {@code INVALID_DATE} boundary event, which routes the token back to
     * the user task that captured the date, so the form can be corrected and submitted again.
     */
    private static BpmnErrorException reject(String name, Object value, String rule, JobContext job) {
        return new BpmnErrorException(INVALID_DATE,
                "Process variable '" + name + "' must be a date that is " + rule + " but was '"
                        + value + "' (element " + job.elementId() + "). Correct the date and complete"
                        + " the form again.");
    }

    private static LocalDate read(JobContext job, String name) {
        try {
            Optional<LocalDate> value = job.optDate(name);
            return value.orElse(null);
        } catch (ValidationException notADate) {
            LOG.debug("Skipping range check for '{}': {}", name, notADate.getMessage());
            return null;
        }
    }

    /** For the start-up banner and the tests: whether the rules loaded and how many of each. */
    public static Map<String, Object> summary() {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("loaded", LOAD_ERROR == null);
        out.put("version", VERSION);
        out.put("notInPast", new ArrayList<>(NOT_IN_PAST));
        out.put("notInFuture", new ArrayList<>(NOT_IN_FUTURE));
        out.put("orderedPairs", ORDERED_PAIRS.size());
        if (LOAD_ERROR != null) {
            out.put("loadError", LOAD_ERROR);
        }
        return out;
    }

    /** Whether the rule table loaded successfully. */
    public static boolean loaded() {
        return LOAD_ERROR == null;
    }
}
