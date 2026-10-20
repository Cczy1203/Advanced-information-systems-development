package uk.ac.uwe.ufcep603.hospital.db;

import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

/**
 * Reference data access: the patient master index and GP practices.
 *
 * <p>This layer is where the external feedback's "check details against the database" lands: the
 * Group Feedback sheet, row 14 ("Add GP validation by checking details against the database" and
 * "Validate NHS numbers ... with database checks to verify patient details") and row 7 item 3
 * ("database integration"). It makes the database more than somewhere to "store results": it
 * takes part in the business decision, so an incoming referral first asks whether the patient
 * exists and whether the GP practice still accepts referrals.
 *
 * <p>This class performs no validation and throws no business exceptions; it only reads data. The
 * decision logic lives in {@link uk.ac.uwe.ufcep603.hospital.support.ReferralRegistry}, so that
 * "data" and "rules" stay separate and both can be tested on their own.
 */
public final class ReferenceData {

    private final HospitalDatabase database;

    /** One row of the patient master index. */
    public record PatientRecord(String patientRef,
                                String nhsNumber,
                                String fullName,
                                String dateOfBirth,
                                String practiceCode) {
        public Map<String, Object> toVariables() {
            Map<String, Object> variables = new LinkedHashMap<>();
            variables.put("patientRef", patientRef);
            variables.put("patientNhsNumber", nhsNumber);
            variables.put("patientName", fullName);
            variables.put("patientDateOfBirth", dateOfBirth);
            variables.put("gpPracticeCode", practiceCode);
            return variables;
        }
    }

    /** A GP practice. New referrals are not accepted when {@code acceptingReferrals} is false. */
    public record GpPractice(String practiceCode,
                             String name,
                             String city,
                             boolean acceptingReferrals) {
    }

    public ReferenceData(HospitalDatabase database) {
        this.database = database;
    }

    public Optional<PatientRecord> patient(String patientRef) {
        if (patientRef == null || patientRef.isBlank()) {
            return Optional.empty();
        }
        return database.query(connection -> {
            try (PreparedStatement statement = connection.prepareStatement(
                    "SELECT patient_ref, nhs_number, full_name, date_of_birth, practice_code "
                            + "FROM patient WHERE patient_ref = ?")) {
                statement.setString(1, patientRef.trim());
                try (ResultSet rs = statement.executeQuery()) {
                    return rs.next() ? Optional.of(readPatient(rs)) : Optional.<PatientRecord>empty();
                }
            }
        });
    }

    public Optional<PatientRecord> patientByNhsNumber(String nhsNumber) {
        String cleaned = NhsNumber.normalise(nhsNumber);
        if (cleaned == null || cleaned.isEmpty()) {
            return Optional.empty();
        }
        return database.query(connection -> {
            try (PreparedStatement statement = connection.prepareStatement(
                    "SELECT patient_ref, nhs_number, full_name, date_of_birth, practice_code "
                            + "FROM patient WHERE nhs_number = ?")) {
                statement.setString(1, cleaned);
                try (ResultSet rs = statement.executeQuery()) {
                    return rs.next() ? Optional.of(readPatient(rs)) : Optional.<PatientRecord>empty();
                }
            }
        });
    }

    public Optional<GpPractice> practice(String practiceCode) {
        if (practiceCode == null || practiceCode.isBlank()) {
            return Optional.empty();
        }
        return database.query(connection -> {
            try (PreparedStatement statement = connection.prepareStatement(
                    "SELECT practice_code, name, city, accepting_referrals "
                            + "FROM gp_practice WHERE practice_code = ?")) {
                statement.setString(1, practiceCode.trim());
                try (ResultSet rs = statement.executeQuery()) {
                    return rs.next() ? Optional.of(readPractice(rs)) : Optional.<GpPractice>empty();
                }
            }
        });
    }

    public List<GpPractice> practices() {
        return database.query(connection -> {
            List<GpPractice> practices = new ArrayList<>();
            try (PreparedStatement statement = connection.prepareStatement(
                    "SELECT practice_code, name, city, accepting_referrals FROM gp_practice "
                            + "ORDER BY practice_code");
                 ResultSet rs = statement.executeQuery()) {
                while (rs.next()) {
                    practices.add(readPractice(rs));
                }
            }
            return practices;
        });
    }

    public Map<String, Object> summary() {
        Map<String, Object> summary = new LinkedHashMap<>();
        summary.put("patients", database.query(connection -> count(connection, "patient")));
        summary.put("gpPractices", database.query(connection -> count(connection, "gp_practice")));
        summary.put("practicesNotAccepting", practices().stream()
                .filter(practice -> !practice.acceptingReferrals())
                .map(GpPractice::practiceCode)
                .toList());
        return summary;
    }

    private long count(java.sql.Connection connection, String table) throws SQLException {
        try (PreparedStatement statement = connection.prepareStatement("SELECT COUNT(*) FROM " + table);
             ResultSet rs = statement.executeQuery()) {
            return rs.next() ? rs.getLong(1) : 0L;
        }
    }

    private PatientRecord readPatient(ResultSet rs) throws SQLException {
        return new PatientRecord(
                rs.getString("patient_ref"),
                rs.getString("nhs_number"),
                rs.getString("full_name"),
                rs.getDate("date_of_birth") == null ? null : rs.getDate("date_of_birth").toString(),
                rs.getString("practice_code"));
    }

    private GpPractice readPractice(ResultSet rs) throws SQLException {
        return new GpPractice(
                rs.getString("practice_code"),
                rs.getString("name"),
                rs.getString("city"),
                rs.getBoolean("accepting_referrals"));
    }
}
