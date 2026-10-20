package uk.ac.uwe.ufcep603.hospital;

/**
 * Bad input from the process: a required variable is missing, blank or of the wrong shape, or an
 * enumerated value is outside its allowed set.
 *
 * <p>It is an {@link IllegalArgumentException} on purpose - callers that just want "clear bad input
 * throws IllegalArgumentException" get exactly that - and the base worker turns it into a failed
 * job whose error message names the offending variable. It is never thrown as a BPMN error:
 * only the business conditions listed in the model's {@code bpmn:error} definitions do that.
 */
public class ValidationException extends IllegalArgumentException {

    private static final long serialVersionUID = 1L;

    private final String variable;

    public ValidationException(String variable, String message) {
        super(message);
        this.variable = variable;
    }

    public ValidationException(String message) {
        this(null, message);
    }

    /** Name of the offending process variable, or {@code null} when the message is self-contained. */
    public String variable() {
        return variable;
    }

    public static ValidationException missing(String variable, String jobType) {
        return new ValidationException(variable,
                "Required process variable '" + variable + "' is missing or blank (job type " + jobType + ")");
    }

    public static ValidationException wrongType(String variable, String expected, Object actual, String jobType) {
        return new ValidationException(variable,
                "Process variable '" + variable + "' must be " + expected + " but was "
                        + (actual == null ? "null" : actual.getClass().getSimpleName() + " (" + actual + ")")
                        + " (job type " + jobType + ")");
    }

    public static ValidationException notAllowed(String variable, Object actual, java.util.Collection<String> allowed,
                                                String jobType) {
        return new ValidationException(variable,
                "Process variable '" + variable + "' must be one of " + allowed + " but was '" + actual
                        + "' (job type " + jobType + ")");
    }

    /**
     * The date is outside the range the process allows.
     *
     * <p>Why this is placed here rather than thrown as a BPMN error: this class already states
     * that it is "never thrown as a BPMN error" - only business conditions declared in the model's
     * {@code bpmn:error} definitions take that path. A date out of range is bad input data, in the
     * same category as a missing required variable: it fails the job with a readable reason and
     * leaves the follow-up to the engine's retry policy, rather than inventing an error code that
     * the model has no catch path for (which would raise an incident directly).
     *
     * @param variable the name of the offending variable
     * @param actual   the actual value
     * @param rule     the rule in human-readable form, for example "a date that is not in the past"
     * @param jobType  the job type, to make it easier to locate in Operate
     */
    public static ValidationException invalidDate(String variable, Object actual, String rule, String jobType) {
        return new ValidationException(variable,
                "Process variable '" + variable + "' must be " + rule + " but was '" + actual
                        + "' (job type " + jobType + ")");
    }

    /**
     * The order between two dates does not hold (for example the end of a window is earlier than
     * its start).
     */
    public static ValidationException dateOrder(String first, Object firstValue, String second, Object secondValue,
                                                String jobType) {
        return new ValidationException(second,
                "Process variable '" + second + "' (" + secondValue + ") must not be before '"
                        + first + "' (" + firstValue + ") (job type " + jobType + ")");
    }

    /**
     * The role has not been granted permission to perform this business action (the code-side layer
     * of RBAC).
     *
     * <p>The same reasoning as {@link #invalidDate}: a permission refusal means this request is not
     * allowed, not a business condition declared in the model's {@code bpmn:error} definitions,
     * so it does not take the BPMN error path.
     */
    public static ValidationException notAuthorised(String roleId, String resourceType, String action,
                                                    String jobType) {
        return new ValidationException("actingRole",
                "Role '" + roleId + "' is not permitted to " + action + " " + resourceType
                        + " (job type " + jobType + ")");
    }

    /**
     * No such reference record can be found in the database (master patient index / GP practice /
     * referenced document number).
     *
     * @param variable the name of the variable carrying the reference
     * @param what     a human-readable kind of record, for example "patient record"
     * @param value    the value that was looked up
     */
    public static ValidationException unknownRecord(String variable, String what, Object value, String jobType) {
        return new ValidationException(variable,
                "No " + what + " matches '" + value + "' in the hospital database (job type " + jobType + ")");
    }

    /**
     * The value exists but is not currently usable (for example a GP practice has stopped accepting
     * new referrals, or a patient record has been archived).
     */
    public static ValidationException notUsable(String variable, String what, Object value, String reason,
                                                String jobType) {
        return new ValidationException(variable,
                what + " '" + value + "' cannot be used: " + reason + " (job type " + jobType + ")");
    }
}
