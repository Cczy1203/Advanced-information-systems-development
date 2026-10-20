package uk.ac.uwe.ufcep603.hospital.db;

import java.util.Optional;

/**
 * The format and check-digit rules for an NHS number.
 *
 * <p>An NHS number is 10 digits, the tenth of which is a **modulus 11 check digit**, computed as:
 * <ol>
 *   <li>take the first 9 digits, multiply them by 10, 9, 8, 7, 6, 5, 4, 3, 2 respectively and
 *       add the products;</li>
 *   <li>take the remainder when that sum is divided by 11;</li>
 *   <li>check digit = 11 − remainder;</li>
 *   <li>if the result is 11 it is recorded as 0; if the result is 10 the number is **invalid in
 *       itself** (no such NHS number exists).</li>
 * </ol>
 *
 * <p>Why this layer is needed: the tutor feedback asked several times for the NHS number to be
 * validated ("Validate NHS numbers to ensure that they contain exactly 10 digits", and also
 * "check patient details against the database"). The form layer can only enforce length and
 * regular-expression constraints such as "10 digits" — form-js's {@code pattern} is an ordinary
 * regular expression and cannot express a modulus 11 check. The check-digit layer therefore has
 * to sit on the server side, which is here.
 *
 * <p>This class is stateless; every method is static.
 */
public final class NhsNumber {

    private NhsNumber() {
    }

    /**
     * Removes the separators commonly seen inside NHS numbers (spaces and hyphens) and trims
     * leading and trailing whitespace. Users copying a number from a record often write it as
     * {@code 943 476 5919}, and such forms should be accepted.
     */
    public static String normalise(String value) {
        if (value == null) {
            return null;
        }
        return value.replace(" ", "").replace("-", "").trim();
    }

    /**
     * Checks whether an NHS number is valid.
     *
     * @return {@link Optional#empty()} when the number is valid; otherwise a **human-readable**
     *         explanation of what is wrong. A reason is returned rather than a boolean so that
     *         {@code ValidationException} can use it directly as its message, and so that the
     *         audit log records exactly what was wrong.
     */
    public static Optional<String> problemWith(String value) {
        String cleaned = normalise(value);
        if (cleaned == null || cleaned.isEmpty()) {
            return Optional.of("NHS number is required");
        }
        if (cleaned.length() != 10) {
            return Optional.of("NHS number must be exactly 10 digits but was " + cleaned.length());
        }
        for (int i = 0; i < cleaned.length(); i++) {
            if (!Character.isDigit(cleaned.charAt(i))) {
                return Optional.of("NHS number must contain digits only");
            }
        }
        int total = 0;
        for (int i = 0; i < 9; i++) {
            total += Character.digit(cleaned.charAt(i), 10) * (10 - i);
        }
        int remainder = total % 11;
        int expected = 11 - remainder;
        if (expected == 11) {
            expected = 0;
        }
        if (expected == 10) {
            // A check digit of 10 is an impossible value, so the first 9 digits cannot be valid.
            return Optional.of("NHS number " + cleaned + " is not a valid number (check digit cannot be 10)");
        }
        int actual = Character.digit(cleaned.charAt(9), 10);
        if (actual != expected) {
            return Optional.of("NHS number " + cleaned + " fails the modulus 11 check digit (expected "
                    + expected + " but the number ends in " + actual + ")");
        }
        return Optional.empty();
    }

    /** Convenience check. */
    public static boolean isValid(String value) {
        return problemWith(value).isEmpty();
    }
}
