package uk.ac.uwe.ufcep603.hospital.db;

import org.h2.jdbcx.JdbcConnectionPool;
import org.h2.tools.RunScript;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.Reader;
import java.nio.charset.StandardCharsets;
import java.sql.Connection;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Connection and schema management for the H2 database; the whole worker process
 * shares one instance.
 *
 * <p>Why H2 (this answers the feedback recorded at Group Feedback line 7, item 3, "Implement
 * database integration to support data persistence"):
 * <ul>
 *   <li>It is <b>embedded</b>: there is no database service to install, so {@code java -jar}
 *       runs straight away and neither the demo nor marking fails because the machine has
 *       no database installed;</li>
 *   <li>The same jar can back onto a disk file (real persistence: the data survives a
 *       process restart) or open an in-memory database ({@code jdbc:h2:mem:...}, used by
 *       the unit tests), so tests and production share one code path;</li>
 *   <li>It is also the secondary storage shipped with the Camunda 8.10 distribution, so it
 *       belongs to the same database family as the engine.</li>
 * </ul>
 *
 * <p>The connection pool is H2's own {@link JdbcConnectionPool}; no extra pooling
 * dependency is pulled in, because this project builds offline and one fewer dependency
 * is one fewer problem.
 *
 * <p>This class is thread-safe: {@code JdbcConnectionPool} is itself thread-safe and
 * there is no mutable shared state. Job workers run on a shared thread pool, so this is
 * required.
 */
public final class HospitalDatabase implements AutoCloseable {

    private static final Logger LOG = LoggerFactory.getLogger(HospitalDatabase.class);

    /** Schema script (idempotent: everything is CREATE ... IF NOT EXISTS). */
    private static final String SCHEMA_RESOURCE = "/db/schema.sql";
    /** Reference data and the role permission matrix (idempotent: written with MERGE). */
    private static final String SEED_RESOURCE = "/db/seed.sql";

    /** Allows a lambda to throw SQLException, avoiding try/catch at every call site. */
    @FunctionalInterface
    public interface SqlCall<T> {
        T apply(Connection connection) throws SQLException;
    }

    private final String url;
    private final String user;
    private final JdbcConnectionPool pool;

    private HospitalDatabase(String url, String user, String password, int maxConnections) {
        this.url = url;
        this.user = user;
        this.pool = JdbcConnectionPool.create(url, user, password == null ? "" : password);
        // job workers use 4 execution threads by default; give the pool some headroom
        // so that concurrent writes do not have to wait for each other.
        this.pool.setMaxConnections(Math.max(4, maxConnections));
    }

    /**
     * Opens the database: create the connection pool, apply the schema, then seed the
     * reference data and the permission matrix.
     *
     * @param url            JDBC URL, for example {@code jdbc:h2:file:./data/hospital}
     * @param user           user name (the embedded H2 convention is {@code sa})
     * @param password       password, may be empty
     * @param seed           true to run seed.sql (reference patients, GP practices, role matrix)
     * @param maxConnections maximum number of connections in the pool
     */
    public static HospitalDatabase open(String url, String user, String password,
                                        boolean seed, int maxConnections) {
        HospitalDatabase database = new HospitalDatabase(url, user, password, maxConnections);
        database.bootstrap(seed);
        LOG.info("database ready: {}", database.describe());
        return database;
    }

    private void bootstrap(boolean seed) {
        try (Connection connection = connection()) {
            runScript(connection, SCHEMA_RESOURCE);
            LOG.info("schema applied");
            if (seed) {
                runScript(connection, SEED_RESOURCE);
                LOG.info("reference data and role matrix seeded");
            }
        } catch (SQLException | IOException e) {
            throw new DatabaseException("could not initialise the H2 database: " + url, e);
        }
    }

    /**
     * Runs one SQL script. H2's own {@link RunScript} is used rather than splitting on
     * semicolons by hand: it handles {@code --} comments, semicolons inside string literals
     * and a file that ends without a semicolon correctly.
     */
    private void runScript(Connection connection, String resource) throws IOException, SQLException {
        try (InputStream in = HospitalDatabase.class.getResourceAsStream(resource)) {
            if (in == null) {
                throw new DatabaseException("SQL script not on the classpath: " + resource);
            }
            try (Reader reader = new InputStreamReader(in, StandardCharsets.UTF_8)) {
                RunScript.execute(connection, reader);
            }
        }
    }

    /** Borrows a connection. The caller must close it (use try-with-resources). */
    public Connection connection() throws SQLException {
        return pool.getConnection();
    }

    /**
     * Runs a read-modify-write cycle inside a single transaction. It returns only after a
     * successful commit; any exception rolls back. The check-then-insert step for
     * idempotency keys (appointment references, payment references and so on) must go
     * through here, otherwise a concurrent retry can insert a duplicate.
     */
    public <T> T inTransaction(SqlCall<T> work) {
        try (Connection connection = connection()) {
            boolean previousAutoCommit = connection.getAutoCommit();
            connection.setAutoCommit(false);
            try {
                T result = work.apply(connection);
                connection.commit();
                return result;
            } catch (RuntimeException | SQLException e) {
                connection.rollback();
                throw e;
            } finally {
                connection.setAutoCommit(previousAutoCommit);
            }
        } catch (SQLException e) {
            throw new DatabaseException("database transaction failed", e);
        }
    }

    /** Read-only query, auto-commit. */
    public <T> T query(SqlCall<T> work) {
        try (Connection connection = connection()) {
            return work.apply(connection);
        } catch (SQLException e) {
            throw new DatabaseException("database query failed", e);
        }
    }

    /**
     * Statistics for the start-up banner: the row count of every business table.
     * These numbers are the most direct evidence that the data really is in the database,
     * and they are what the demo script prints.
     */
    public Map<String, Object> summary() {
        Map<String, Object> summary = new LinkedHashMap<>();
        summary.put("url", describe());
        String[] tables = {
                "gp_practice", "patient", "appointment", "treatment_series", "confirmed_series",
                "clinic_letter", "pathway_monitoring", "letter_reminder",
                "payment_reference", "provider_payment",
                "app_role", "role_permission", "audit_log"
        };
        Map<String, Object> counts = new LinkedHashMap<>();
        for (String table : tables) {
            counts.put(table, countRows(table));
        }
        summary.put("rows", counts);
        return summary;
    }

    private long countRows(String table) {
        return query(connection -> {
            try (Statement statement = connection.createStatement();
                 ResultSet rs = statement.executeQuery("SELECT COUNT(*) FROM " + table)) {
                return rs.next() ? rs.getLong(1) : 0L;
            }
        });
    }

    /** For the banner and the logs; the password never appears here. */
    public String describe() {
        return url + " (user=" + user + ")";
    }

    public String url() {
        return url;
    }

    @Override
    public void close() {
        // An explicit SHUTDOWN must come first; calling pool.dispose() alone is not enough.
        // Why (learned the hard way): dispose() only closes the connections and the database
        // object stays in the JVM; opening the same file path again then yields a read-only
        // handle that reports "The database is read only [90097-224]". The schema statements
        // pass because the tables already exist, so only the first statement that really
        // writes data (the MERGE in the seed) fails, which is easily misread as a permissions
        // problem. H2 closes the database and releases the file lock only once it receives
        // SHUTDOWN.
        try (Connection connection = pool.getConnection();
             Statement statement = connection.createStatement()) {
            statement.execute("SHUTDOWN");
        } catch (SQLException e) {
            LOG.debug("SHUTDOWN not executed (database may already be closed): {}", e.getMessage());
        }
        pool.dispose();
        LOG.info("database connection pool disposed");
    }
}
