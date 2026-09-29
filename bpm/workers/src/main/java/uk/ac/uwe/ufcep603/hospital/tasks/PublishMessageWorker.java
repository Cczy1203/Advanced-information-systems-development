package uk.ac.uwe.ufcep603.hospital.tasks;

import io.camunda.zeebe.client.ZeebeClient;
import io.camunda.zeebe.client.api.response.PublishMessageResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import uk.ac.uwe.ufcep603.hospital.AbstractHospitalWorker;
import uk.ac.uwe.ufcep603.hospital.JobContext;
import uk.ac.uwe.ufcep603.hospital.TransientJobException;
import uk.ac.uwe.ufcep603.hospital.ValidationException;
import uk.ac.uwe.ufcep603.hospital.WorkerContext;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * The message dispatcher: <b>one</b> worker that completes every BPMN message throw event in the
 * collaboration.
 *
 * <p>The model gives every throw event {@code <zeebe:taskDefinition type="publish-message" />} plus
 * a {@code messageName} task header, and an input mapping that sets the {@code correlationKey}
 * process variable. This worker therefore has to exist exactly once and covers all 85 throw events,
 * which keeps the throw/intermediate events and the {@code publish-message} job type in step with
 * each other automatically.
 *
 * <p>Behaviour:
 * <ol>
 *   <li>read the {@code messageName} header;</li>
 *   <li>read the {@code correlationKey} process variable - a missing or blank key fails the job
 *       with a message naming the variable, it is never turned into a BPMN error, because the model
 *       has no boundary event for a broken hand-off and retrying is the correct response;</li>
 *   <li>publish the message with the whole process variable map forwarded, so the receiving pool
 *       receives the same data the throwing pool held;</li>
 *   <li>log element id, message name and correlation key;</li>
 *   <li>complete the job with the published message key so the outcome can be inspected in Operate.</li>
 * </ol>
 *
 * <p>A publish failure is re-thrown, so the job fails and the engine retry policy applies.
 */
public final class PublishMessageWorker extends AbstractHospitalWorker {

    public static final String JOB_TYPE = "publish-message";

    private static final Logger LOG = LoggerFactory.getLogger(PublishMessageWorker.class);

    public PublishMessageWorker(WorkerContext context, ZeebeClient client) {
        super(JOB_TYPE, context, client);
    }

    @Override
    protected Map<String, Object> execute(JobContext job) {
        String messageName = job.header("messageName");
        if (messageName == null || messageName.isBlank()) {
            throw new ValidationException("messageName",
                    "Task header 'messageName' is missing or blank on element '" + job.elementId()
                            + "'. Every message throw event must declare it, e.g."
                            + " <zeebe:header key=\"messageName\" value=\"referral.review-requested\" />"
                            + " (job type " + JOB_TYPE + ")");
        }
        messageName = messageName.trim();

        String correlationKey = job.opt("correlationKey");
        if (correlationKey == null) {
            throw new ValidationException("correlationKey",
                    "Process variable 'correlationKey' is missing or blank for message '" + messageName
                            + "' on element '" + job.elementId() + "'. Add an input mapping"
                            + " <zeebe:input source=\"=patientRef + &quot;-...&quot;\""
                            + " target=\"correlationKey\" /> to the throw event"
                            + " (job type " + JOB_TYPE + "). The job is failed rather than throwing a"
                            + " BPMN error because a broken hand-off is not a business condition.");
        }

        // Forward the whole variable map: the receiving pool needs the same data the sender held.
        Map<String, Object> forwarded = new LinkedHashMap<>(job.rawVariables());

        PublishMessageResponse response;
        try {
            response = client().newPublishMessageCommand()
                    .messageName(messageName)
                    .correlationKey(correlationKey)
                    .variables(forwarded)
                    .send()
                    .join();
        } catch (Exception publishFailure) {
            throw new TransientJobException("could not publish message '" + messageName + "' with correlation key '"
                    + correlationKey + "' from element '" + job.elementId() + "': " + publishFailure, publishFailure);
        }

        LOG.info("PUBLISHED message elementId={} messageName={} correlationKey={} messageKey={} processInstanceKey={}"
                        + " variables={}",
                job.elementId(), messageName, correlationKey, response.getMessageKey(),
                job.processInstanceKey(), forwarded.keySet());

        Map<String, Object> output = job.output();
        output.put("publishedMessageName", messageName);
        output.put("publishedCorrelationKey", correlationKey);
        output.put("publishedMessageKey", response.getMessageKey());
        return output;
    }
}
