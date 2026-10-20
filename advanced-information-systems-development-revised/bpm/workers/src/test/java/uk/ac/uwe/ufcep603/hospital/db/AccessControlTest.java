package uk.ac.uwe.ufcep603.hospital.db;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import uk.ac.uwe.ufcep603.hospital.ValidationException;

import java.util.List;
import java.util.Map;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Unit tests for database-driven permission decisions and auditing: the evidence for the
 * RBAC layer on the code side.
 *
 * <p>They run against an in-memory database ({@code jdbc:h2:mem:...;DB_CLOSE_DELAY=-1}) but
 * exercise exactly the same SQL and code paths as production. {@code DB_CLOSE_DELAY=-1} is
 * required, otherwise the database is gone as soon as the connection is closed.
 */
class AccessControlTest {

    private HospitalDatabase database;
    private AccessControl accessControl;
    private ReferenceData referenceData;

    @BeforeEach
    void setUp() {
        database = HospitalDatabase.open("jdbc:h2:mem:acl-test;DB_CLOSE_DELAY=-1", "sa", "", true, 2);
        accessControl = new AccessControl(database);
        referenceData = new ReferenceData(database);
    }

    @AfterEach
    void tearDown() {
        database.close();
    }

    @Test
    @DisplayName("The permission matrix is seeded into the database following least privilege")
    void matrixIsSeeded() {
        List<Map<String, Object>> matrix = accessControl.matrix();
        assertFalse(matrix.isEmpty(), "The permission matrix must not be empty");
        Map<String, Object> counts = accessControl.summary();
        assertEquals(11L, ((Number) counts.get("roles")).longValue(), "There must be 11 business roles");
        assertTrue(((Number) counts.get("permissions")).longValue() > 40,
                "There must be more than 40 permission entries");
    }

    @Test
    @DisplayName("Actions granted to a role are allowed, actions not granted are denied")
    void allowsGrantedAndDeniesMissing() {
        // Finance may raise a refund
        assertTrue(accessControl.check("finance", "PAYMENT", "REFUND").allowed());
        // but finance may not modify a treatment series
        AccessControl.Decision denied = accessControl.check("finance", "TREATMENT_SERIES", "WRITE");
        assertFalse(denied.allowed());
        assertTrue(denied.reason().contains("no WRITE permission"),
                "The denial reason should name the missing permission: " + denied.reason());
    }

    @Test
    @DisplayName("The auditor role may only read the audit log, any business write is denied")
    void auditorIsReadOnly() {
        assertTrue(accessControl.check("auditor", "AUDIT_LOG", "READ").allowed());
        assertFalse(accessControl.check("auditor", "PAYMENT", "WRITE").allowed());
        assertFalse(accessControl.check("auditor", "CLINIC_LETTER", "APPROVE").allowed());
    }

    @Test
    @DisplayName("Unknown roles and missing arguments both give a readable denial reason")
    void rejectsUnknownRolesAndMissingArguments() {
        assertTrue(accessControl.check("no-such-role", "PAYMENT", "READ").reason()
                .contains("not a known role"));
        assertTrue(accessControl.check(null, "PAYMENT", "READ").reason()
                .contains("no role was supplied"));
        assertTrue(accessControl.check("finance", null, null).reason()
                .contains("no resource or action"));
    }

    @Test
    @DisplayName("require() throws ValidationException when permission is missing, and audits both outcomes")
    void requireThrowsAndAuditsBothOutcomes() {
        long allowedBefore = accessControl.countByDecision("ALLOW");
        long deniedBefore = accessControl.countByDecision("DENY");

        // Allowed: no exception is thrown and one ALLOW row is written
        accessControl.require("fin.demo", "finance", "finance.record-refund", 42L,
                "PAYMENT", "REFUND", "PAT-1");
        assertEquals(allowedBefore + 1, accessControl.countByDecision("ALLOW"));

        // Denied: ValidationException is thrown and one DENY row is written
        ValidationException failure = assertThrows(ValidationException.class, () ->
                accessControl.require("audit.demo", "auditor", "finance.record-refund", 43L,
                        "PAYMENT", "WRITE", "PAT-1"));
        assertTrue(failure.getMessage().contains("auditor"), failure.getMessage());
        assertTrue(failure.getMessage().contains("PAYMENT"), failure.getMessage());
        assertEquals(deniedBefore + 1, accessControl.countByDecision("DENY"));

        // The audit entries themselves must be readable, with the newest first
        List<Map<String, Object>> recent = accessControl.recent(5);
        assertFalse(recent.isEmpty());
        assertEquals("DENY", recent.get(0).get("decision"),
                "The newest entry must be the denial that has just happened");
        assertEquals("auditor", recent.get(0).get("role"));
        assertEquals("PAT-1", recent.get(0).get("resourceId"));
    }

    @Test
    @DisplayName("The reference data carries valid NHS numbers and GP practices")
    void referenceDataIsSeeded() {
        Optional<ReferenceData.PatientRecord> jordan = referenceData.patient("PAT-2026-0001");
        assertTrue(jordan.isPresent(), "Reference patient PAT-2026-0001 must exist");
        assertEquals("9434765919", jordan.get().nhsNumber());
        assertTrue(NhsNumber.isValid(jordan.get().nhsNumber()),
                "The NHS number in the seed data must really pass the modulus 11 check, otherwise the validation tests would be fooled by fake data");

        // Look the same patient up by NHS number
        assertTrue(referenceData.patientByNhsNumber("943 476 5919").isPresent(),
                "An NHS number written with spaces must also be found");

        // GP-5580 has stopped accepting new referrals; this demonstrates database-driven validation
        Optional<ReferenceData.GpPractice> closed = referenceData.practice("GP-5580");
        assertTrue(closed.isPresent());
        assertFalse(closed.get().acceptingReferrals());
        assertTrue(referenceData.practice("GP-4471").orElseThrow().acceptingReferrals());

        assertTrue(referenceData.patient("PAT-NOT-THERE").isEmpty());
        assertTrue(referenceData.patientByNhsNumber(null).isEmpty());
    }
}
