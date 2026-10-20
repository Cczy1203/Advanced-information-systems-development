package uk.ac.uwe.ufcep603.hospital.db;

/**
 * Runtime exception for the database layer.
 *
 * <p>Extending {@link RuntimeException} is deliberate: JDBC's {@link java.sql.SQLException} is a
 * checked exception, and letting it propagate would pollute the {@code execute} signature of every
 * worker. A database fault means "the infrastructure is broken", not "business validation failed",
 * so this is an unchecked exception, and {@code AbstractHospitalWorker} handles it uniformly as a
 * failed job (logging FAILED and letting the engine retry).
 */
public class DatabaseException extends RuntimeException {

    private static final long serialVersionUID = 1L;

    public DatabaseException(String message) {
        super(message);
    }

    public DatabaseException(String message, Throwable cause) {
        super(message, cause);
    }
}
