package uk.ac.uwe.ufcep603.hospital.db;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import uk.ac.uwe.ufcep603.hospital.ValidationException;

import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Timestamp;
import java.sql.Types;
import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Database-driven role permission checks and audit logging — the **code-side layer** of RBAC.
 *
 * <p>Camunda's own authorisation is declared in {@code bpm/camunda/application.yaml} and held in
 * the engine's {@code AUTHORIZATIONS} table; it governs "can this role see, claim or complete a
 * user task in the engine". Once a user task has been completed, the real work is done by these
 * external workers, which also need to know "can this role perform this kind of business action".
 * A finance role may raise a refund, for example, while an audit role may not. That is what this
 * layer decides, using the {@code role_permission} matrix held in the database.
 *
 * <p>Keeping the permission matrix in the database rather than in code has two advantages:
 * <ul>
 *   <li>permissions can be changed without recompiling and redeploying;</li>
 *   <li>the permissions themselves become queryable data, so an audit can answer "what could this
 *       role actually do at the time".</li>
 * </ul>
 *
 * <p>Every decision — allow and deny alike — writes one {@code audit_log} row. Healthcare systems
 * require traceability, and "denied" records matter most: they are the evidence of an attempted
 * privilege escalation.
 *
 * <p>This class is thread-safe (it relies on the {@link HospitalDatabase} connection pool and on
 * the database constraints).
 */
public final class AccessControl {

    private static final Logger LOG = LoggerFactory.getLogger(AccessControl.class);

    /** The outcome of a decision. {@code reason} explains a denial, and is null when allowed. */
    public record Decision(boolean allowed, String reason) {
        public static Decision allow() {
            return new Decision(true, null);
        }

        public static Decision deny(String reason) {
            return new Decision(false, reason);
        }
    }

    private final HospitalDatabase database;

    public AccessControl(HospitalDatabase database) {
        this.database = database;
    }

    /**
     * Looks a decision up in the permission matrix.
     *
     * <p>Note that this method **does not cache**. The permission table is tiny (about 60 rows in
     * this demonstration) and every lookup is a primary-key hit, whereas the invalidation problems
     * that caching would bring are more trouble than they are worth. Add a cache if this ever
     * faces genuinely high concurrency.
     */
    public Decision check(String roleId, String resourceType, String action) {
        if (roleId == null || roleId.isBlank()) {
            return Decision.deny("no role was supplied for this job");
        }
        if (resourceType == null || action == null) {
            return Decision.deny("no resource or action was supplied for this job");
        }
        Boolean found = database.query(connection -> {
            try (PreparedStatement statement = connection.prepareStatement(
                    "SELECT 1 FROM role_permission WHERE role_id = ? AND resource_type = ? AND action = ?")) {
                statement.setString(1, roleId);
                statement.setString(2, resourceType);
                statement.setString(3, action);
                try (ResultSet rs = statement.executeQuery()) {
                    return rs.next();
                }
            }
        });
        if (Boolean.TRUE.equals(found)) {
            return Decision.allow();
        }
        // Distinguish "no such role" from "role lacks this permission", for a clearer denial.
        boolean roleExists = database.query(connection -> {
            try (PreparedStatement statement = connection.prepareStatement(
                    "SELECT 1 FROM app_role WHERE role_id = ?")) {
                statement.setString(1, roleId);
                try (ResultSet rs = statement.executeQuery()) {
                    return rs.next();
                }
            }
        });
        return Decision.deny(roleExists
                ? "role '" + roleId + "' has no " + action + " permission on " + resourceType
                : "role '" + roleId + "' is not a known role");
    }

    /**
     * Checks for a permission and requires it; throws {@link ValidationException} when denied.
     *
     * <p>The audit entry is written first, whether the decision is to allow or to deny.
     */
    public void require(String actor, String roleId, String jobType, Long processInstanceKey,
                        String resourceType, String action, String resourceId) {
        Decision decision = check(roleId, resourceType, action);
        audit(actor, roleId, jobType, processInstanceKey, action, resourceType, resourceId,
                decision.allowed(), decision.allowed() ? null : decision.reason());
        if (!decision.allowed()) {
            throw ValidationException.notAuthorised(roleId, resourceType, action, jobType);
        }
    }

    /** Records an audit entry without a permission check, for "note that this happened" cases. */
    public void record(String actor, String roleId, String jobType, Long processInstanceKey,
                       String resourceType, String action, String resourceId, String detail) {
        audit(actor, roleId, jobType, processInstanceKey, action, resourceType, resourceId, true, detail);
    }

    private void audit(String actor, String roleId, String jobType, Long processInstanceKey,
                       String action, String resourceType, String resourceId,
                       boolean allowed, String detail) {
        String trimmed = detail == null ? null
                : detail.substring(0, Math.min(detail.length(), 900));
        try {
            database.inTransaction(connection -> {
                try (PreparedStatement statement = connection.prepareStatement(
                        "INSERT INTO audit_log (occurred_at, actor, role_id, job_type, process_instance_key, "
                                + "action, resource_type, resource_id, decision, detail) "
                                + "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)")) {
                    statement.setTimestamp(1, Timestamp.from(Instant.now()));
                    statement.setString(2, actor);
                    statement.setString(3, roleId);
                    statement.setString(4, jobType);
                    if (processInstanceKey == null) {
                        statement.setNull(5, Types.BIGINT);
                    } else {
                        statement.setLong(5, processInstanceKey);
                    }
                    statement.setString(6, action);
                    statement.setString(7, resourceType);
                    statement.setString(8, resourceId);
                    statement.setString(9, allowed ? "ALLOW" : "DENY");
                    statement.setString(10, trimmed);
                    statement.executeUpdate();
                }
                return null;
            });
        } catch (RuntimeException e) {
            // A failed audit write must not bring the business job down: log at ERROR and continue.
            // Deliberate trade-off, noted here so it is not mistaken for missing error handling.
            LOG.error("Could not write the audit entry: {} {} {} {}", roleId, action,
                    resourceType, e.getMessage());
            return;
        }
        if (allowed) {
            LOG.debug("AUDIT ALLOW role={} action={} {} id={}", roleId, action, resourceType, resourceId);
        } else {
            LOG.warn("AUDIT DENY  role={} action={} {} id={} reason={}", roleId, action, resourceType, resourceId,
                    trimmed);
        }
    }

    public long countByDecision(String decision) {
        return database.query(connection -> {
            try (PreparedStatement statement = connection.prepareStatement(
                    "SELECT COUNT(*) FROM audit_log WHERE decision = ?")) {
                statement.setString(1, decision);
                try (ResultSet rs = statement.executeQuery()) {
                    return rs.next() ? rs.getLong(1) : 0L;
                }
            }
        });
    }

    /** The most recent audit entries, newest first. Printed as evidence in demos and marking. */
    public List<Map<String, Object>> recent(int limit) {
        return database.query(connection -> {
            List<Map<String, Object>> entries = new ArrayList<>();
            try (PreparedStatement statement = connection.prepareStatement(
                    "SELECT occurred_at, actor, role_id, job_type, action, resource_type, resource_id, "
                            + "decision, detail FROM audit_log ORDER BY audit_id DESC LIMIT ?")) {
                statement.setInt(1, Math.max(1, limit));
                try (ResultSet rs = statement.executeQuery()) {
                    while (rs.next()) {
                        Map<String, Object> entry = new LinkedHashMap<>();
                        entry.put("occurredAt", String.valueOf(rs.getTimestamp("occurred_at")));
                        entry.put("actor", rs.getString("actor"));
                        entry.put("role", rs.getString("role_id"));
                        entry.put("jobType", rs.getString("job_type"));
                        entry.put("action", rs.getString("action"));
                        entry.put("resourceType", rs.getString("resource_type"));
                        entry.put("resourceId", rs.getString("resource_id"));
                        entry.put("decision", rs.getString("decision"));
                        entry.put("detail", rs.getString("detail"));
                        entries.add(entry);
                    }
                }
            }
            return entries;
        });
    }

    /** The permission matrix itself, used for documentation and marking. */
    public List<Map<String, Object>> matrix() {
        return database.query(connection -> {
            List<Map<String, Object>> rows = new ArrayList<>();
            try (PreparedStatement statement = connection.prepareStatement(
                    "SELECT p.role_id, r.name, p.resource_type, p.action FROM role_permission p "
                            + "LEFT JOIN app_role r ON r.role_id = p.role_id "
                            + "ORDER BY p.role_id, p.resource_type, p.action");
                 ResultSet rs = statement.executeQuery()) {
                while (rs.next()) {
                    Map<String, Object> row = new LinkedHashMap<>();
                    row.put("roleId", rs.getString("role_id"));
                    row.put("roleName", rs.getString("name"));
                    row.put("resourceType", rs.getString("resource_type"));
                    row.put("action", rs.getString("action"));
                    rows.add(row);
                }
            }
            return rows;
        });
    }

    public Map<String, Object> summary() {
        Map<String, Object> summary = new LinkedHashMap<>();
        summary.put("roles", database.query(connection -> count(connection, "app_role")));
        summary.put("permissions", database.query(connection -> count(connection, "role_permission")));
        summary.put("auditAllowed", countByDecision("ALLOW"));
        summary.put("auditDenied", countByDecision("DENY"));
        return summary;
    }

    private long count(java.sql.Connection connection, String table) throws SQLException {
        try (PreparedStatement statement = connection.prepareStatement("SELECT COUNT(*) FROM " + table);
             ResultSet rs = statement.executeQuery()) {
            return rs.next() ? rs.getLong(1) : 0L;
        }
    }
}
