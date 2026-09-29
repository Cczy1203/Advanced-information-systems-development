package uk.ac.uwe.ufcep603.hospital.tasks;

import io.camunda.zeebe.client.ZeebeClient;
import uk.ac.uwe.ufcep603.hospital.AbstractHospitalWorker;
import uk.ac.uwe.ufcep603.hospital.JobContext;
import uk.ac.uwe.ufcep603.hospital.WorkerContext;

import java.util.Map;

/**
 * {@code pathway.add-to-monitoring} - Patient Pathway Coordinators,
 * "Add the letter to pathway monitoring".
 *
 * <p>Triggered when a Consultant flags a clinic letter as delayed. Adding the same letter twice
 * returns the same {@code monitoringRef}, so the monitoring list cannot grow duplicates.
 */
public final class PathwayAddToMonitoringWorker extends AbstractHospitalWorker {

    public static final String JOB_TYPE = "pathway.add-to-monitoring";

    public PathwayAddToMonitoringWorker(WorkerContext context, ZeebeClient client) {
        super(JOB_TYPE, context, client);
    }

    @Override
    protected Map<String, Object> execute(JobContext job) {
        String letterRef = job.requireFirst("letterRef", "letterRef", "letterReference", "clinicLetterRef");
        String consultationDate = job.optDateFirst("consultationDate", "consultationDate", "clinicDate",
                "appointmentDate").orElse(context().clock().today()).toString();

        String monitoringRef = context().store().addToMonitoring(letterRef, consultationDate);

        Map<String, Object> output = job.output();
        output.put("monitoringRef", monitoringRef);
        output.put("addedToMonitoring", true);
        output.put("monitoringLetterRef", letterRef);
        output.put("monitoringAddedAt", context().clock().timestamp());
        output.put("monitoringConsultationDate", consultationDate);
        return output;
    }
}
