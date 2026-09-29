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
}
