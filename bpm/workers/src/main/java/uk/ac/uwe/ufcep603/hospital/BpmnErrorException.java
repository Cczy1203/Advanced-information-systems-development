package uk.ac.uwe.ufcep603.hospital;

/**
 * A business condition that the BPMN model handles with an error boundary event or an error event
 * sub-process.
 *
 * <p>Thrown from a worker with an error code that matches a {@code bpmn:error} declared in the
 * model. The base worker converts it into
 * {@code client.newThrowErrorCommand().jobKey(...).errorCode(...).errorMessage(...)}, so the token
 * leaves the service task through the boundary event instead of being retried.
 */
public final class BpmnErrorException extends RuntimeException {

    private static final long serialVersionUID = 1L;

    private final String errorCode;

    public BpmnErrorException(String errorCode, String message) {
        super(message);
        this.errorCode = errorCode;
    }

    public String errorCode() {
        return errorCode;
    }
}
