package uk.ac.uwe.ufcep603.hospital.db;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Unit tests for the NHS number check digit rule.
 *
 * <p>The tutor feedback asks several times for NHS numbers to be validated ("Validate NHS
 * numbers to ensure that they contain exactly 10 digits"). The form layer can only express
 * length and pattern constraints such as "10 digits"; the modulus 11 check digit cannot be
 * expressed there, so this layer has to pin the rule down with tests, otherwise a wrong rule
 * would go unnoticed.
 */
class NhsNumberTest {

    @Test
    @DisplayName("Valid NHS numbers pass validation")
    void acceptsValidNumbers() {
        // 9434765919: the first 9 digits have weighted sum 299, 299 mod 11 = 2, so the check
        // digit is 11 - 2 = 9
        assertTrue(NhsNumber.isValid("9434765919"));
        // 4010232137: weighted sum 92, 92 mod 11 = 4, check digit 11 - 4 = 7
        assertTrue(NhsNumber.isValid("4010232137"));
        // 4000000004: weighted sum 40, 40 mod 11 = 7, check digit 11 - 7 = 4
        assertTrue(NhsNumber.isValid("4000000004"));
    }

    @Test
    @DisplayName("Forms with spaces or hyphens are normalised before validation")
    void normalisesSeparators() {
        assertTrue(NhsNumber.isValid("943 476 5919"));
        assertTrue(NhsNumber.isValid("943-476-5919"));
        assertEquals("9434765919", NhsNumber.normalise("943 476 5919"));
    }

    @Test
    @DisplayName("A wrong check digit must be reported with a specific reason")
    void rejectsWrongCheckDigit() {
        // Change the last digit of a valid number
        Optional<String> problem = NhsNumber.problemWith("9434765918");
        assertTrue(problem.isPresent(), "A wrong check digit must be judged invalid");
        assertTrue(problem.get().contains("modulus 11"),
                "The reason should state that the modulus 11 check digit is at fault");
    }

    @Test
    @DisplayName("Wrong length, non-digits and empty input are each reported separately")
    void rejectsMalformedInput() {
        assertTrue(NhsNumber.problemWith("943476591").get().contains("exactly 10 digits"));
        assertTrue(NhsNumber.problemWith("94347659190").get().contains("exactly 10 digits"));
        assertTrue(NhsNumber.problemWith("94347659X9").get().contains("digits only"));
        assertTrue(NhsNumber.problemWith("").isPresent());
        assertTrue(NhsNumber.problemWith(null).isPresent());
    }

    @Test
    @DisplayName("Numbers whose check digit would be 10 do not exist under the rule")
    void rejectsNumbersWhoseCheckDigitWouldBeTen() {
        // For prefix 100000001 the weighted sum is 1 x 10 + 1 x 2 = 12, and 12 mod 11 = 1,
        // so the check digit would be 11 - 1 = 10. Ten is not a legal check digit value, so
        // this number does not exist under the rule and must be identified separately
        // (rather than reported as a check digit mismatch).
        Optional<String> problem = NhsNumber.problemWith("1000000010");
        assertTrue(problem.isPresent());
        assertTrue(problem.get().contains("cannot be 10"),
                "The reason should state clearly that the check digit cannot be 10; actual message: "
                        + problem.get());
    }
}
