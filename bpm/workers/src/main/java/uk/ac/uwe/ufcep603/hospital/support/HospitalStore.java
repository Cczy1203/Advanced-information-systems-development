package uk.ac.uwe.ufcep603.hospital.support;

import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;

/**
 * The in-memory state that makes several workers idempotent.
 *
 * <p>Camunda retries a failed job up to three times, and the model intentionally sends the same
 * booking, payment and reminder requests more than once. A real implementation would hold all of
 * this in the hospital PAS database; for the deliverable a single process-wide store shared by all
 * workers is enough, and it is honest about its limitation: the state disappears when the JVM
 * stops, so it only deduplicates within one run of the worker set.
 *
 * <p>Every method is thread safe; job workers run on a shared executor.
 */
public final class HospitalStore {

    /** An appointment that has actually been issued. */
    public record Appointment(String reference, String dateTime, String location) {
        public Map<String, Object> toVariables() {
            Map<String, Object> variables = new LinkedHashMap<>();
            variables.put("appointmentRef", reference);
            variables.put("appointmentDateTime", dateTime);
            variables.put("appointmentLocation", location);
            return variables;
        }
    }

    /** The stored appointment plus whether this call is the one that created it. */
    public record AppointmentResult(Appointment appointment, boolean created) {
    }

    private final Map<String, Appointment> appointments = new ConcurrentHashMap<>();
    private final Map<String, List<String>> treatmentSeries = new ConcurrentHashMap<>();
    private final Map<String, List<String>> confirmedSeries = new ConcurrentHashMap<>();
    private final Map<String, Map<String, Object>> clinicLetters = new ConcurrentHashMap<>();
    private final Map<String, String> monitoring = new ConcurrentHashMap<>();
    private final Map<String, Integer> reminderCounts = new ConcurrentHashMap<>();
    private final Map<String, LocalDate> remindedOn = new ConcurrentHashMap<>();
    private final Map<String, Set<String>> paymentReferences = new ConcurrentHashMap<>();
    private final Map<String, Map<String, Object>> providerPayments = new ConcurrentHashMap<>();

    // ------------------------------------------------------------------ appointments

    /**
     * Idempotent appointment creation. The first caller wins; every later caller with the same key
     * receives the appointment that already exists, with {@code created == false}.
     */
    public AppointmentResult createAppointment(String key, java.util.function.Supplier<Appointment> factory) {
        Appointment candidate = factory.get();
        Appointment existing = appointments.putIfAbsent(key, candidate);
        return existing == null ? new AppointmentResult(candidate, true) : new AppointmentResult(existing, false);
    }

    public Optional<Appointment> appointment(String key) {
        return Optional.ofNullable(appointments.get(key));
    }

    // ------------------------------------------------------------------ treatment series

    /** Idempotent on the treatment booking reference: a retry never creates a second series. */
    public List<String> createOrGetSeries(String treatmentBookingRef, java.util.function.Supplier<List<String>> factory) {
        List<String> existing = treatmentSeries.computeIfAbsent(treatmentBookingRef, key -> List.copyOf(factory.get()));
        return existing;
    }

    public Optional<List<String>> series(String treatmentBookingRef) {
        return Optional.ofNullable(treatmentSeries.get(treatmentBookingRef));
    }

    /**
     * Idempotent confirmation, keyed on the set of provisional references. Confirming the same set
     * twice returns the same list and never changes the count.
     */
    public List<String> confirmAppointments(String signature, java.util.function.Supplier<List<String>> factory) {
        return confirmedSeries.computeIfAbsent(signature, key -> List.copyOf(factory.get()));
    }

    // ------------------------------------------------------------------ clinic letters

    /** The current letters waiting on a Consultant, keyed by letter reference. */
    public List<Map<String, Object>> letters() {
        return clinicLetters.values().stream().map(Map::copyOf).toList();
    }

    public void putLetter(Map<String, Object> letter) {
        Object reference = letter.get("letterRef");
        if (reference != null) {
            clinicLetters.put(String.valueOf(reference), new LinkedHashMap<>(letter));
        }
    }

    public Optional<Map<String, Object>> letter(String letterRef) {
        return Optional.ofNullable(clinicLetters.get(letterRef)).map(Map::copyOf);
    }

    /**
     * Seeds the letter store so the 7 day / 1 month / 3 month escalation bands can be shown. The
     * dates are relative to the demo clock, never to a hard-coded calendar date.
     */
    public void seedClinicLetters(LocalDate today, String scenario) {
        if (!clinicLetters.isEmpty()) {
            return;
        }
        String normalised = scenario == null ? "THREE_MONTHS" : scenario.toUpperCase(Locale.ROOT);
        boolean oneMonth = !"SEVEN_DAYS".equals(normalised);
        boolean threeMonths = "THREE_MONTHS".equals(normalised) || "MIXED".equals(normalised);
        // These are letters that are still waiting on a Consultant, so approved is always false.
        addSeedLetter("CL-1001", today.minusDays(9), "Cardiology clinic letter", false);
        if (oneMonth) {
            addSeedLetter("CL-1002", today.minusDays(45), "Oncology clinic letter", false);
        }
        if (threeMonths) {
            addSeedLetter("CL-1003", today.minusDays(120), "Respiratory clinic letter", false);
        }
        addSeedLetter("CL-1004", today.minusDays(2), "Dermatology clinic letter", false);
    }

    private void addSeedLetter(String reference, LocalDate consultationDate, String subject, boolean approved) {
        Map<String, Object> letter = new LinkedHashMap<>();
        letter.put("letterRef", reference);
        letter.put("consultationDate", consultationDate.toString());
        letter.put("subject", subject);
        letter.put("approved", approved);
        clinicLetters.put(reference, letter);
    }

    // ------------------------------------------------------------------ pathway monitoring

    public String addToMonitoring(String letterRef, String consultationDate) {
        return monitoring.computeIfAbsent(letterRef,
                key -> Ids.reference("MON", key, consultationDate));
    }

    public Map<String, String> monitoringEntries() {
        return Map.copyOf(monitoring);
    }

    // ------------------------------------------------------------------ reminders

    public boolean alreadyReminded(String letterRef, LocalDate today, int cooldownDays) {
        LocalDate last = remindedOn.get(letterRef);
        if (last == null) {
            return false;
        }
        return cooldownDays <= 0 || !today.isAfter(last.plusDays(cooldownDays));
    }

    public void recordReminder(String letterRef, LocalDate on) {
        remindedOn.put(letterRef, on);
    }

    /** @return the incremented reminder count for the letter. */
    public int nextReminderCount(String letterRef, Integer incoming) {
        int base = incoming != null ? incoming : reminderCounts.getOrDefault(letterRef, 0);
        int next = base + 1;
        reminderCounts.merge(letterRef, next, Math::max);
        return next;
    }

    public int reminderCountFor(String letterRef) {
        return reminderCounts.getOrDefault(letterRef, 0);
    }

    public Map<String, Integer> reminderCounts() {
        return Map.copyOf(reminderCounts);
    }

    // ------------------------------------------------------------------ payments

    /**
     * Remembers that {@code paymentReference} has been seen for this patient.
     *
     * @return {@code true} when the exact same reference had already been recorded, i.e. this is a
     *         repeat charge for the same patient.
     */
    public boolean markPaymentReference(String patientRef, String paymentReference) {
        if (patientRef == null || paymentReference == null) {
            return false;
        }
        Set<String> references = paymentReferences.computeIfAbsent(patientRef, key -> ConcurrentHashMap.newKeySet());
        return !references.add(paymentReference);
    }

    public boolean paymentReferenceSeen(String patientRef, String paymentReference) {
        Set<String> references = paymentReferences.get(patientRef);
        return references != null && references.contains(paymentReference);
    }

    public Set<String> paymentReferences(String patientRef) {
        Set<String> references = paymentReferences.get(patientRef);
        return references == null ? Set.of() : Set.copyOf(new LinkedHashSet<>(references));
    }

    /** What the (simulated) payment provider recorded against a hospital payment reference. */
    public void recordProviderPayment(String patientRef, String paymentReference, String status, double amount) {
        Map<String, Object> record = new LinkedHashMap<>();
        record.put("status", status);
        record.put("amount", amount);
        record.put("recordedAt", OffsetDateTime.now(ZoneOffset.UTC).toString());
        providerPayments.put(Ids.key(patientRef, paymentReference), record);
    }

    public Optional<Map<String, Object>> providerPayment(String patientRef, String paymentReference) {
        return Optional.ofNullable(providerPayments.get(Ids.key(patientRef, paymentReference))).map(Map::copyOf);
    }

    // ------------------------------------------------------------------ housekeeping

    /** Clears every store. Only used by tests / a fresh demo run. */
    public void reset() {
        appointments.clear();
        treatmentSeries.clear();
        confirmedSeries.clear();
        clinicLetters.clear();
        monitoring.clear();
        reminderCounts.clear();
        remindedOn.clear();
        paymentReferences.clear();
        providerPayments.clear();
    }

    public Map<String, Object> summary() {
        Map<String, Object> summary = new LinkedHashMap<>();
        summary.put("appointments", appointments.size());
        summary.put("treatmentSeries", treatmentSeries.size());
        summary.put("clinicLetters", new ArrayList<>(clinicLetters.keySet()));
        summary.put("monitoring", monitoring.size());
        summary.put("reminderCounts", reminderCounts());
        return summary;
    }
}
