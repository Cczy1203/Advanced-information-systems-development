package uk.ac.uwe.ufcep603.hospital;

/**
 * A transient problem: the job is failed so that the engine retry policy applies (every service
 * task in the model carries {@code retries="3"}), and the same job is activated again later.
 *
 * <p>Used for the "confirmation lost" payment scenario and for a simulated service that is
 * temporarily unavailable but has no BPMN error boundary event in the model.
 */
public final class TransientJobException extends RuntimeException {

    private static final long serialVersionUID = 1L;

    public TransientJobException(String message) {
        super(message);
    }

    public TransientJobException(String message, Throwable cause) {
        super(message, cause);
    }
}
