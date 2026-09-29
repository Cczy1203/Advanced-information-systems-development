package uk.ac.uwe.ufcep603.hospital.tasks;

import io.camunda.zeebe.client.ZeebeClient;
import uk.ac.uwe.ufcep603.hospital.AbstractHospitalWorker;
import uk.ac.uwe.ufcep603.hospital.BpmnErrorException;
import uk.ac.uwe.ufcep603.hospital.JobContext;
import uk.ac.uwe.ufcep603.hospital.WorkerContext;
import uk.ac.uwe.ufcep603.hospital.support.Ids;

import java.util.List;
import java.util.Map;

/**
 * {@code correspondence.dispatch-letter} - <b>simulated</b> External Correspondence Service,
 * "Dispatch the letter over the agreed channel".
 *
 * <p>Deterministic stand-in for a print house / digital letter provider. Honours the post, digital
 * and accessible-format channels produced by {@code correspondence.prepare-dispatch} and returns a
 * dispatch reference. Completes with {@code dispatchStatus = SENT} normally.
 *
 * <p>Throws the BPMN error {@code CORRESPONDENCE_SERVICE_FAILED} - which the model catches with an
 * error boundary event and turns into {@code correspondence.failed} - when the dispatch is rejected:
 * either because the simulated failure injection is switched on for this job type, or because there
 * is nobody to send the letter to.
 *
 * <p>Limitation: nothing is actually printed or posted, and delivery is not confirmed. A real
 * implementation would call the provider's API and would need a separate delivery-receipt message.
 */
public final class CorrespondenceDispatchLetterWorker extends AbstractHospitalWorker {

    public static final String JOB_TYPE = "correspondence.dispatch-letter";

    private static final String CORRESPONDENCE_SERVICE_FAILED = "CORRESPONDENCE_SERVICE_FAILED";

    public CorrespondenceDispatchLetterWorker(WorkerContext context, ZeebeClient client) {
        super(JOB_TYPE, context, client);
    }

    @Override
    protected Map<String, Object> execute(JobContext job) {
        job.rejectCardData();

        List<String> recipients = job.optStringList("dispatchRecipients");
        if (recipients.isEmpty()) {
            recipients = job.optStringList("letterRecipients");
        }
        recipients = recipients.stream().filter(recipient -> recipient != null && !recipient.isBlank()).toList();
        if (recipients.isEmpty()) {
            throw new BpmnErrorException(CORRESPONDENCE_SERVICE_FAILED,
                    "Correspondence service rejected the dispatch: there are no recipients to send '"
                            + job.optFirst("dispatchPayloadRef", "correspondencePurpose", "letterType")
                            + "' to (element " + job.elementId() + "). Check 'dispatchRecipients' /"
                            + " 'letterRecipients' on the dispatch request.");
        }

        String channel = job.optFirst("dispatchChannel", "dispatchChannel", "patientPreferredChannel");
        if (channel == null) {
            channel = "POST";
        }
        String format = CorrespondencePrepareDispatchWorker.formatFor(channel);

        Map<String, Object> output = job.output();
        output.put("dispatchStatus", "SENT");
        output.put("dispatchReference",
                Ids.reference("LTR", job.opt("dispatchPayloadRef"), channel, recipients));
        output.put("dispatchedAt", context().clock().timestamp());
        output.put("dispatchFormat", format);
        output.put("dispatchChannelUsed", channel);
        output.put("dispatchRecipientCount", recipients.size());
        output.put("dispatchProvider", "SIMULATED-CORRESPONDENCE-SERVICE");
        return output;
    }
}
