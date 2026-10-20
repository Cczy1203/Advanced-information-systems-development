package uk.ac.uwe.ufcep603.hospital.support;

import io.camunda.zeebe.client.api.response.ActivatedJob;
import org.junit.jupiter.api.Assumptions;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import uk.ac.uwe.ufcep603.hospital.BpmnErrorException;
import uk.ac.uwe.ufcep603.hospital.JobContext;
import uk.ac.uwe.ufcep603.hospital.ValidationException;
import uk.ac.uwe.ufcep603.hospital.config.AppConfig;

import java.lang.reflect.Proxy;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDate;
import java.util.LinkedHashMap;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Unit tests for {@link DateRuleValidator}.
 *
 * <p>This layer is worth testing because the tutor feedback asks for invalid or unsuitable
 * dates to be prevented, and the form layer cannot block out-of-range dates submitted by a
 * direct API call (the form-js disallowPassedDates option only constrains the calendar
 * picker). These tests cover the boundaries with a fixed "today": today is accepted,
 * yesterday and tomorrow are rejected, and the granularity is the date, not the instant.
 *
 * <p>No mocking framework is used: {@link ActivatedJob} is faked with a JDK dynamic proxy
 * because {@link JobContext} only touches a few of its getters.
 */
class DateRuleValidatorTest {

    private static final String JOB_TYPE = "test.date-rules";
    /** Fixed "today", so the boundary assertions do not depend on the real clock. */
    private static final String FIXED_TODAY = "2026-03-15";

    // ------------------------------------------------------------------ helpers

    private static DemoClock clockAt(String isoDate) {
        AppConfig config = AppConfig.load(new String[0], Map.of("DEMO_CLOCK_TODAY", isoDate));
        return new DemoClock(config);
    }

    /** Fake an ActivatedJob with a dynamic proxy, filling only the fields JobContext reads. */
    private static JobContext jobWith(Map<String, Object> variables) {
        ActivatedJob stub = (ActivatedJob) Proxy.newProxyInstance(
                ActivatedJob.class.getClassLoader(),
                new Class<?>[]{ActivatedJob.class},
                (proxy, method, args) -> {
                    switch (method.getName()) {
                        case "getVariablesAsMap":
                            return new LinkedHashMap<>(variables);
                        case "getCustomHeaders":
                            return new LinkedHashMap<String, String>();
                        case "getType":
                            return JOB_TYPE;
                        case "getKey":
                            return 1L;
                        case "getElementId":
                            return "Test_Element";
                        case "getProcessInstanceKey":
                            return 100L;
                        case "getBpmnProcessId":
                            return "test-process";
                        case "getRetries":
                            return 3;
                        case "toString":
                            return "ActivatedJobStub";
                        case "hashCode":
                            return System.identityHashCode(proxy);
                        case "equals":
                            return proxy == args[0];
                        default:
                            // Unstubbed proxy methods must return a value compatible with the
                            // return type, or primitive unboxing will fail with a null pointer.
                            Class<?> rt = method.getReturnType();
                            if (rt == boolean.class) {
                                return false;
                            }
                            if (rt == int.class) {
                                return 0;
                            }
                            if (rt == long.class) {
                                return 0L;
                            }
                            if (rt == double.class) {
                                return 0d;
                            }
                            if (rt == float.class) {
                                return 0f;
                            }
                            if (rt == short.class) {
                                return (short) 0;
                            }
                            if (rt == byte.class) {
                                return (byte) 0;
                            }
                            if (rt == char.class) {
                                return (char) 0;
                            }
                            return null;
                    }
                });
        return new JobContext(stub, JOB_TYPE);
    }

    private static void validate(Map<String, Object> variables) {
        DateRuleValidator.validate(jobWith(variables), clockAt(FIXED_TODAY));
    }

    // ------------------------------------------------------------------ the rule table itself

    @Test
    @DisplayName("Shared rule table loads from the classpath with entry counts matching date-rules.json")
    void ruleTableLoads() {
        assertTrue(DateRuleValidator.loaded(),
                "date-rules.json must be packaged with the jar; a load failure disables server-side date validation");

        Map<String, Object> summary = DateRuleValidator.summary();
        assertEquals("15.0", summary.get("version"));
        // Note that these are de-duplicated variable name counts, not the entry count of
        // date-rules.json: rules take effect per process variable name, and several forms
        // bind the same variable name, for example
        //   futureDates  has 8 entries -> 7 variable names (choose-appointment-slot and
        //                confirm-follow-up-appointment share appointmentDateTime)
        //   pastOnlyDates has 9 entries -> 6 variable names (referralDate / reviewDate /
        //                decisionDate are each shared by two forms; consultationDate moved
        //                to freeDates because the demonstration timebox puts the
        //                consultation in the future, which made the rule fail falsely)
        assertEquals(7, ((java.util.List<?>) summary.get("notInPast")).size(),
                "The future-date variable count changed; update date-rules.json and this document");
        assertEquals(6, ((java.util.List<?>) summary.get("notInFuture")).size(),
                "The past-only date variable count changed; update date-rules.json and this document");
        assertEquals(1, summary.get("orderedPairs"));
    }

    @Test
    @DisplayName("Every form field in the rule table really exists (rules cannot point at renamed fields)")
    void ruleFieldsExistInTheForms() throws Exception {
        Path formsDir = findFormsDirectory();
        Assumptions.assumeTrue(formsDir != null,
                "bpm/model/forms was not found, skipping the form consistency check");
        assertTrue(DateRuleValidator.loaded());

        String json = Files.readString(
                Path.of("src", "main", "resources", "date-rules.json"), StandardCharsets.UTF_8);
        // String-level existence check only, to avoid another JSON parsing branch in the test
        for (Object field : (java.util.List<?>) DateRuleValidator.summary().get("notInPast")) {
            assertTrue(json.contains("\"" + field + "\""), "rule field " + field + " is not in date-rules.json");
        }
        for (String required : new String[]{"appointmentDateTime", "preferredFromDate", "preferredToDate"}) {
            assertTrue(json.contains(required), "missing rule for key date field: " + required);
        }
    }

    /** Walk up from the current working directory looking for bpm/model/forms or model/forms. */
    private static Path findFormsDirectory() {
        Path dir = Path.of("").toAbsolutePath();
        for (int i = 0; i < 5 && dir != null; i++) {
            Path candidate = dir.resolve("model").resolve("forms");
            if (Files.isDirectory(candidate)) {
                return candidate;
            }
            Path nested = dir.resolve("bpm").resolve("model").resolve("forms");
            if (Files.isDirectory(nested)) {
                return nested;
            }
            dir = dir.getParent();
        }
        return null;
    }

    // ------------------------------------------------------------------ record dates

    @Test
    @DisplayName("Record date set to tomorrow -> rejected (referralDate must not be later than today)")
    void pastOnlyDateInTheFutureIsRejected() {
        // A date the user typed is bad input, not a transient fault: it must leave through the
        // INVALID_DATE boundary event and go back to the form, not spend the task's retries.
        BpmnErrorException failure = assertThrows(BpmnErrorException.class,
                () -> validate(Map.of("referralDate", LocalDate.parse("2026-03-16"))));
        assertEquals(DateRuleValidator.INVALID_DATE, failure.errorCode());
        assertTrue(failure.getMessage().contains("referralDate"), failure.getMessage());
        assertTrue(failure.getMessage().contains("not in the future"), failure.getMessage());
        assertTrue(failure.getMessage().toLowerCase().contains("correct the date"),
                "the message has to tell the reader what to do: " + failure.getMessage());
    }

    @Test
    @DisplayName("Record date set to today -> accepted")
    void pastOnlyDateTodayIsAccepted() {
        assertDoesNotThrow(() -> validate(Map.of("referralDate", FIXED_TODAY)));
    }

    @Test
    @DisplayName("Record date set to yesterday -> accepted")
    void pastOnlyDateYesterdayIsAccepted() {
        assertDoesNotThrow(() -> validate(Map.of("referralDate", "2026-03-14")));
    }

    // ------------------------------------------------------------------ appointment dates

    @Test
    @DisplayName("Appointment date set to yesterday -> rejected (appointmentDateTime must not be in the past)")
    void futureDateInThePastIsRejected() {
        BpmnErrorException failure = assertThrows(BpmnErrorException.class,
                () -> validate(Map.of("appointmentDateTime", "2026-03-14T09:00:00")));
        assertEquals(DateRuleValidator.INVALID_DATE, failure.errorCode());
        assertTrue(failure.getMessage().contains("not in the past"), failure.getMessage());
    }

    @Test
    @DisplayName("Appointment date set to today -> accepted (consistent with form-js minDate: today, inclusive)")
    void futureDateTodayIsAccepted() {
        assertDoesNotThrow(() -> validate(Map.of("appointmentDateTime", FIXED_TODAY)));
    }

    @Test
    @DisplayName("Full timestamp at 09:00 today -> accepted (the granularity is the date, not the instant)")
    void futureDateTimeWithTimeTodayIsAccepted() {
        // auto_driver.py fills the forms with TODAY + "T09:00:00".
        // If the comparison were by instant, the driver would be blocked wholesale after
        // 09:00, and this test is the regression guard for that.
        assertDoesNotThrow(() -> validate(Map.of("appointmentDateTime", FIXED_TODAY + "T09:00:00")));
    }

    // ------------------------------------------------------------------ cross-field ordering

    @Test
    @DisplayName("Appointment window ends before it starts -> rejected")
    void unorderedWindowIsRejected() {
        BpmnErrorException failure = assertThrows(BpmnErrorException.class, () -> validate(Map.of(
                "preferredFromDate", "2026-03-20",
                "preferredToDate", "2026-03-18")));
        assertEquals(DateRuleValidator.INVALID_DATE, failure.errorCode());
        assertTrue(failure.getMessage().contains("preferredToDate"), failure.getMessage());
    }

    @Test
    @DisplayName("Appointment window start equals end -> accepted (a same-day window is valid)")
    void windowOfOneDayIsAccepted() {
        assertDoesNotThrow(() -> validate(Map.of(
                "preferredFromDate", "2026-03-20",
                "preferredToDate", "2026-03-20")));
    }

    @Test
    @DisplayName("Window only half filled -> no ordering check, left to the business logic")
    void halfFilledWindowIsIgnored() {
        assertDoesNotThrow(() -> validate(Map.of("preferredFromDate", "2026-03-20")));
    }

    // ------------------------------------------------------------------ unrelated variables

    @Test
    @DisplayName("Variables unrelated to date rules -> never interfered with")
    void unrelatedVariablesAreIgnored() {
        assertDoesNotThrow(() -> validate(Map.of(
                "patientRef", "PAT-2026-0001",
                "clinicalDecision", "ACCEPT",
                "cycleCount", 6)));
    }

    @Test
    @DisplayName("Constrained variable value is not a date -> range check skipped (each worker reports format problems)")
    void nonDateValueIsSkippedNotRejected() {
        assertDoesNotThrow(() -> validate(Map.of("referralDate", "not-a-date")));
    }

    @Test
    @DisplayName("Empty job (no variables at all) -> no error")
    void emptyJobIsAccepted() {
        assertDoesNotThrow(() -> validate(Map.of()));
    }
}
