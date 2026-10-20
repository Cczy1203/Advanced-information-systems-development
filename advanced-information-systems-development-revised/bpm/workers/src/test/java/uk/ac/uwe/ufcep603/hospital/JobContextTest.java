package uk.ac.uwe.ufcep603.hospital;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * The reading and validation half of the worker layer.
 *
 * <p>Every worker in the project reaches its input through these methods, so a
 * mistake here is a mistake in all 36 of them. They had no tests.
 */
class JobContextTest {

    private static JobContext context(Map<String, Object> variables) {
        return new JobContext(TestJob.job().type("test.job").variables(variables).build(),
                "test.job");
    }

    // ---------------------------------------------------------------- required input

    @Test
    @DisplayName("a missing required variable names itself and the job type")
    void missingRequiredVariable() {
        ValidationException thrown = assertThrows(ValidationException.class,
                () -> context(Map.of()).require("patientRef"));

        assertEquals("patientRef", thrown.variable());
        assertTrue(thrown.getMessage().contains("patientRef"), thrown.getMessage());
        assertTrue(thrown.getMessage().contains("test.job"), thrown.getMessage());
    }

    @Test
    @DisplayName("a blank required variable is as bad as a missing one")
    void blankRequiredVariable() {
        assertThrows(ValidationException.class, () -> context(Map.of("patientRef", "   "))
                .require("patientRef"));
    }

    @Test
    @DisplayName("requireFirst takes the first alias that is present")
    void requireFirstFollowsTheAliasOrder() {
        JobContext job = context(Map.of("bookingRef", "APT-1"));
        assertEquals("APT-1", job.requireFirst("booking", "treatmentBookingRef", "bookingRef"));
    }

    @Test
    @DisplayName("requireFirst reads the variable named by its label, not only the aliases")
    void requireFirstReadsTheLabelAsAVariableName() {
        // The label is a variable name as well as the wording of the error. A call site such as
        // requireFirst("paymentReference", "paymentRef") must read paymentReference when it is set;
        // if the label were only decoration, the canonical variable would never be read and the job
        // would fail with "missing or blank" while the variable sits right there in the instance.
        JobContext job = context(Map.of("paymentReference", "PAY-7D13391F"));
        assertEquals("PAY-7D13391F", job.requireFirst("paymentReference", "paymentRef"));
    }

    @Test
    @DisplayName("requireFirst still falls back to an alias when the label is absent")
    void requireFirstFallsBackToAliases() {
        JobContext job = context(Map.of("paymentRef", "PAY-ALIAS"));
        assertEquals("PAY-ALIAS", job.requireFirst("paymentReference", "paymentRef"));
    }

    @Test
    @DisplayName("requireFirst prefers the label over its aliases")
    void requireFirstPrefersTheLabel() {
        JobContext job = context(Map.of("paymentReference", "PAY-CANONICAL", "paymentRef", "PAY-ALIAS"));
        assertEquals("PAY-CANONICAL", job.requireFirst("paymentReference", "paymentRef"));
    }

    @Test
    @DisplayName("optFirst answers null rather than throwing when no alias is present")
    void optFirstIsSilentWhenAbsent() {
        assertEquals(null, context(Map.of()).optFirst("a", "b", "c"));
    }

    // ---------------------------------------------------------------- types

    @Test
    @DisplayName("a list read from a string says which variable and what it got")
    void wrongTypeNamesTheVariableAndTheValue() {
        ValidationException thrown = assertThrows(ValidationException.class,
                () -> context(Map.of("fundingLimitations", "maximum six cycles"))
                        .optStringList("fundingLimitations"));

        assertEquals("fundingLimitations", thrown.variable());
        assertTrue(thrown.getMessage().contains("a list"), thrown.getMessage());
        assertTrue(thrown.getMessage().contains("maximum six cycles"), thrown.getMessage());
    }

    // ------------------------------------------------- the textarea-as-list defect

    @Test
    @DisplayName("stringListOrText reads a list the way optStringList always did")
    void stringListOrTextAcceptsAList() {
        assertEquals(List.of("six cycles", "no private room"),
                context(Map.of("fundingLimitations", List.of("six cycles", "no private room")))
                        .stringListOrText("fundingLimitations"));
    }

    @Test
    @DisplayName("stringListOrText reads a free-text answer instead of failing on it")
    void stringListOrTextAcceptsFreeText() {
        // This is the defect: the form field is a textarea, so a person submits a
        // string, and the funding approval used to fail with "must be a list but was
        // String (111)" the first time anybody used the field.
        assertEquals(List.of("maximum six cycles"),
                context(Map.of("fundingLimitations", "maximum six cycles"))
                        .stringListOrText("fundingLimitations"));
    }

    @Test
    @DisplayName("stringListOrText splits a multi-line answer and drops the empty lines")
    void stringListOrTextSplitsOnNewlinesAndSemicolons() {
        assertEquals(List.of("six cycles", "no private room", "review in 3 months"),
                context(Map.of("fundingLimitations",
                                "six cycles\nno private room;\n\n  review in 3 months  "))
                        .stringListOrText("fundingLimitations"));
    }

    @Test
    @DisplayName("stringListOrText answers an empty list for a variable that is not there")
    void stringListOrTextOnAMissingVariable() {
        assertEquals(List.of(), context(Map.of()).stringListOrText("fundingLimitations"));
    }

    @Test
    @DisplayName("stringListOrText still refuses a value that is neither text nor a list")
    void stringListOrTextStillRejectsNonsense() {
        assertThrows(ValidationException.class,
                () -> context(Map.of("fundingLimitations", 42))
                        .stringListOrText("fundingLimitations"));
    }

    // ---------------------------------------------------------------- numbers and flags

    @Test
    @DisplayName("numberOr falls back and intOr keeps a whole number whole")
    void numbersFallBack() {
        JobContext job = context(Map.of("chargeAmount", 2450.5));
        assertEquals(2450.5, job.numberOr("chargeAmount", 0.0));
        assertEquals(7.0, job.numberOr("absent", 7.0));
        assertEquals(3, context(Map.of("cycleCount", 3)).intOr("cycleCount", 1));
        assertEquals(1, context(Map.of()).intOr("cycleCount", 1));
    }

    @Test
    @DisplayName("boolOr accepts the strings a form sends as well as real booleans")
    void boolOrAcceptsBothForms() {
        assertTrue(context(Map.of("flag", true)).boolOr("flag", false));
        assertTrue(context(Map.of("flag", "true")).boolOr("flag", false));
        assertFalse(context(Map.of("flag", "false")).boolOr("flag", true));
    }

    // ---------------------------------------------------------------- headers

    @Test
    @DisplayName("a message throw reads its messageName from the job headers")
    void headersAreReadable() {
        JobContext job = new JobContext(
                TestJob.job().customHeaders(Map.of("messageName", "referral.info-requested")).build(),
                "publish-message");
        assertEquals("referral.info-requested", job.header("messageName"));
    }
}
