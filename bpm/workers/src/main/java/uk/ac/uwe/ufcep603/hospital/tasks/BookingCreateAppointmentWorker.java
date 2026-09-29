package uk.ac.uwe.ufcep603.hospital.tasks;

import io.camunda.zeebe.client.ZeebeClient;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import uk.ac.uwe.ufcep603.hospital.AbstractHospitalWorker;
import uk.ac.uwe.ufcep603.hospital.JobContext;
import uk.ac.uwe.ufcep603.hospital.ValidationException;
import uk.ac.uwe.ufcep603.hospital.WorkerContext;
import uk.ac.uwe.ufcep603.hospital.support.HospitalStore;
import uk.ac.uwe.ufcep603.hospital.support.Ids;

import java.time.LocalDate;
import java.util.Map;

/**
 * {@code booking.create-appointment} - Outpatient Bookings Team,
 * "Create the appointment record" and "Create the follow-up appointment".
 *
 * <p>Idempotent: the appointment reference is a deterministic function of the booking reference (or
 * the referral reference) and the appointment slot, and the in-memory store keys issued appointments
 * on {@code patientRef} plus that reference. Re-running the job for the same key - which the engine
 * does up to three times, and which happens again when a follow-up is re-offered - returns the
 * appointment that already exists and sets {@code duplicateSuppressed = true} instead of creating a
 * second one.
 */
public final class BookingCreateAppointmentWorker extends AbstractHospitalWorker {

    public static final String JOB_TYPE = "booking.create-appointment";

    private static final Logger LOG = LoggerFactory.getLogger(BookingCreateAppointmentWorker.class);

    public BookingCreateAppointmentWorker(WorkerContext context, ZeebeClient client) {
        super(JOB_TYPE, context, client);
    }

    @Override
    protected Map<String, Object> execute(JobContext job) {
        String bookingReference = job.optFirst("treatmentBookingRef", "treatmentBookingRef", "referralRef",
                "referralReference", "followUpRef");
        if (bookingReference == null) {
            // Neither booking reference exists, so fall back to the patient plus the slot; the job
            // still fails clearly if there is nothing at all to identify the booking by.
            bookingReference = job.optFirst("patientRef", "appointmentRef", "schedulingPurpose");
        }
        if (bookingReference == null) {
            throw ValidationException.missing("treatmentBookingRef", JOB_TYPE);
        }

        String slot = job.optFirst("appointmentDateTime", "chosenSlotStart", "slotStart",
                "selectedSlotStart", "appointmentSlot");
        String location = job.optFirst("appointmentLocation", "chosenLocation", "clinicLocation",
                "slotLocation", "appointmentClinic", "location");

        LocalDate fallbackDate = context().clock().today().plusDays(7);
        String appointmentDate = slot == null ? fallbackDate + "T09:30:00Z" : slot;
        String appointmentLocation = location == null ? "OUTPATIENT-CLINIC-1" : location;

        String reference = Ids.reference("APT", bookingReference, appointmentDate, appointmentLocation);
        String storeKey = Ids.key(job.optFirst("patientRef", "patientRef"), reference);

        HospitalStore.AppointmentResult result = context().store().createAppointment(storeKey,
                () -> new HospitalStore.Appointment(reference, appointmentDate, appointmentLocation));

        if (!result.created()) {
            LOG.info("duplicate appointment suppressed for booking {} (patient {}) - reusing {}",
                    bookingReference, job.opt("patientRef"), result.appointment().reference());
        }

        Map<String, Object> output = job.output();
        output.put("appointmentRef", result.appointment().reference());
        output.put("appointmentDateTime", result.appointment().dateTime());
        output.put("appointmentLocation", result.appointment().location());
        output.put("duplicateSuppressed", !result.created());
        output.put("appointmentBookingBasis", bookingReference);
        return output;
    }
}
