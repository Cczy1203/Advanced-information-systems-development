package uk.ac.uwe.ufcep603.hospital.tasks;

import io.camunda.zeebe.client.ZeebeClient;
import uk.ac.uwe.ufcep603.hospital.AbstractHospitalWorker;
import uk.ac.uwe.ufcep603.hospital.JobContext;
import uk.ac.uwe.ufcep603.hospital.WorkerContext;

import java.util.Map;

/**
 * {@code enquiry.close-record} - Call Handling Team, "Close the enquiry record".
 *
 * <p>Closes the enquiry once the specialist team has answered it. {@code enquiryResolved} is
 * optional: this task is reached from the "enquiry resolved" message, so an absent flag means
 * resolved, while an explicit {@code false} leaves the record OPEN and visible to the call handlers.
 */
public final class EnquiryCloseRecordWorker extends AbstractHospitalWorker {

    public static final String JOB_TYPE = "enquiry.close-record";

    public EnquiryCloseRecordWorker(WorkerContext context, ZeebeClient client) {
        super(JOB_TYPE, context, client);
    }

    @Override
    protected Map<String, Object> execute(JobContext job) {
        String enquiryRef = job.requireFirst("enquiryRef", "enquiryRef", "enquiryReference", "enquiryId",
                "enquiryNumber");
        boolean resolved = job.boolOr("enquiryResolved", true);

        Map<String, Object> output = job.output();
        output.put("enquiryClosedAt", context().clock().timestamp());
        output.put("enquiryStatus", resolved ? "RESOLVED" : "OPEN");
        output.put("enquiryRefClosed", enquiryRef);
        return output;
    }
}
