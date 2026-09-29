package uk.ac.uwe.ufcep603.hospital.tasks;

import io.camunda.zeebe.client.ZeebeClient;
import uk.ac.uwe.ufcep603.hospital.AbstractHospitalWorker;
import uk.ac.uwe.ufcep603.hospital.JobContext;
import uk.ac.uwe.ufcep603.hospital.ValidationException;
import uk.ac.uwe.ufcep603.hospital.WorkerContext;
import uk.ac.uwe.ufcep603.hospital.support.Ids;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * {@code correspondence.prepare-dispatch} - Outpatient Bookings Team (also used for treatment
 * confirmation, delay notifications and appointment letters),
 * "Assemble the appointment letter".
 *
 * <p>Turns the recipient list, the patient's preferred channel and any accessibility need into the
 * three things the (simulated) correspondence service needs: the channel to use, the recipients and
 * a reference for the assembled payload.
 *
 * <p>An accessibility need always wins over the preferred channel - a patient who needs large print
 * or braille is not sent a standard PDF just because that was the recorded preference.
 */
public final class CorrespondencePrepareDispatchWorker extends AbstractHospitalWorker {

    public static final String JOB_TYPE = "correspondence.prepare-dispatch";

    public CorrespondencePrepareDispatchWorker(WorkerContext context, ZeebeClient client) {
        super(JOB_TYPE, context, client);
    }

    @Override
    protected Map<String, Object> execute(JobContext job) {
        job.rejectCardData();

        String preferredChannel = job.optFirst("patientPreferredChannel",
                "patientPreferredChannel", "preferredChannel", "contactPreference", "patientContactPreference");
        String accessibility = job.optFirst("patientAccessibilityNeeds",
                "patientAccessibilityNeeds", "accessibilityNeeds", "accessibilityRequirement");
        String purpose = job.optFirst("correspondencePurpose", "correspondencePurpose", "letterPurpose",
                "letterType");

        List<String> recipients = recipients(job);

        String channel = channelFor(preferredChannel, accessibility);
        String payloadRef = Ids.reference("DSP", job.opt("patientRef"), channel, recipients, purpose);

        Map<String, Object> output = job.output();
        output.put("dispatchChannel", channel);
        output.put("dispatchRecipients", recipients);
        output.put("dispatchPayloadRef", payloadRef);
        output.put("dispatchFormat", formatFor(channel));
        output.put("dispatchPurpose", purpose == null ? "GENERAL" : purpose);
        output.put("accessibilityRequirements", accessibility == null ? List.of() : List.of(accessibility));
        output.put("preparedAt", context().clock().timestamp());
        return output;
    }

    private List<String> recipients(JobContext job) {
        List<Object> raw = List.of();
        for (String variable : List.of("letterRecipients", "letterRecipient", "recipients", "recipientList",
                "dispatchRecipients")) {
            if (job.has(variable)) {
                raw = job.optList(variable).orElse(List.of());
                break;
            }
        }
        List<String> recipients = new ArrayList<>();
        for (Object entry : raw) {
            if (entry == null) {
                continue;
            }
            if (entry instanceof Map<?, ?> map) {
                String address = firstString(map, "address", "email", "postalAddress", "recipientAddress");
                String name = firstString(map, "name", "recipientName", "patientName");
                if (address != null && name != null) {
                    recipients.add(name + " <" + address + ">");
                } else if (address != null) {
                    recipients.add(address);
                } else if (name != null) {
                    recipients.add(name);
                }
            } else {
                String text = String.valueOf(entry).trim();
                if (!text.isEmpty()) {
                    recipients.add(text);
                }
            }
        }

        if (recipients.isEmpty()) {
            // Fall back to the patient on the process, so a letter is still addressed to somebody.
            String fallback = job.optFirst("recipientAddress", "patientAddress", "patientEmail",
                    "patientName", "patientRef");
            if (fallback != null) {
                recipients.add(fallback);
            }
        }
        if (recipients.isEmpty()) {
            throw ValidationException.missing("letterRecipients", JOB_TYPE);
        }
        return recipients;
    }

    private static String firstString(Map<?, ?> map, String... keys) {
        for (String key : keys) {
            Object value = map.get(key);
            if (value != null && !String.valueOf(value).isBlank()) {
                return String.valueOf(value).trim();
            }
        }
        return null;
    }

    /** Accessibility need wins; otherwise the preferred channel; otherwise standard post. */
    static String channelFor(String preferredChannel, String accessibility) {
        String need = accessibility == null ? "" : accessibility.toUpperCase(Locale.ROOT);
        if (need.contains("braille")) {
            return "ACCESSIBLE_BRAILLE";
        }
        if (need.contains("large") || need.contains("large-print") || need.contains("large_print")) {
            return "ACCESSIBLE_LARGE_PRINT";
        }
        if (need.contains("audio") || need.contains("read out") || need.contains("spoken")) {
            return "ACCESSIBLE_AUDIO";
        }
        if (need.contains("easy read") || need.contains("easy-read") || need.contains("easyread")) {
            return "ACCESSIBLE_EASY_READ";
        }
        if (need.contains("interpreter") || need.contains("translation") || need.contains("language")) {
            return "ACCESSIBLE_TRANSLATED";
        }
        String channel = preferredChannel == null ? "" : preferredChannel.toUpperCase(Locale.ROOT).trim();
        if (channel.contains("email") || channel.contains("digital") || channel.contains("app")
                || channel.contains("portal") || channel.contains("sms")) {
            return "DIGITAL";
        }
        return "POST";
    }

    static String formatFor(String channel) {
        if (channel.startsWith("ACCESSIBLE_")) {
            return "ACCESSIBLE_" + channel.substring("ACCESSIBLE_".length());
        }
        return "DIGITAL".equals(channel) ? "DIGITAL" : "POSTAL";
    }
}
