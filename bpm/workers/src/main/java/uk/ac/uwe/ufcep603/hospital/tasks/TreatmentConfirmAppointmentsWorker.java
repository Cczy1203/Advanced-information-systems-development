package uk.ac.uwe.ufcep603.hospital.tasks;

import io.camunda.zeebe.client.ZeebeClient;
import uk.ac.uwe.ufcep603.hospital.AbstractHospitalWorker;
import uk.ac.uwe.ufcep603.hospital.JobContext;
import uk.ac.uwe.ufcep603.hospital.ValidationException;
import uk.ac.uwe.ufcep603.hospital.WorkerContext;
import uk.ac.uwe.ufcep603.hospital.support.Ids;

import java.util.List;
import java.util.Map;
import java.util.Optional;

/**
 * {@code treatment.confirm-appointments} - Treatment and Chemotherapy Bookings Team,
 * "Confirm the treatment appointments".
 *
 * <p>Idempotent on the <em>set</em> of provisional references: the store is keyed on a hash of that
 * set, so confirming twice returns exactly the same list and {@code appointmentsConfirmed} never
 * changes. The confirmed references are only issued for appointments that were actually created, so
 * a confirmation cannot invent one.
 */
public final class TreatmentConfirmAppointmentsWorker extends AbstractHospitalWorker {

    public static final String JOB_TYPE = "treatment.confirm-appointments";

    public TreatmentConfirmAppointmentsWorker(WorkerContext context, ZeebeClient client) {
        super(JOB_TYPE, context, client);
    }

    @Override
    protected Map<String, Object> execute(JobContext job) {
        Optional<List<Object>> raw = job.optList("provisionalAppointmentRefs");
        if (raw.isEmpty() || raw.get().isEmpty()) {
            throw ValidationException.missing("provisionalAppointmentRefs", JOB_TYPE);
        }
        List<String> provisional = job.optStringList("provisionalAppointmentRefs");
        for (String reference : provisional) {
            if (reference == null || reference.isBlank()) {
                throw new ValidationException("provisionalAppointmentRefs",
                        "Process variable 'provisionalAppointmentRefs' contains a blank entry (job type "
                                + JOB_TYPE + ")");
            }
        }

        String signature = Ids.key(provisional.toArray());
        List<String> confirmed = context().store().confirmAppointments(signature, () -> List.copyOf(provisional));

        Map<String, Object> output = job.output();
        output.put("confirmedAppointmentRefs", confirmed);
        output.put("appointmentsConfirmed", true);
        output.put("confirmedAppointmentCount", confirmed.size());
        output.put("confirmationSignature", signature);
        return output;
    }
}
