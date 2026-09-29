package uk.ac.uwe.ufcep603.hospital.tasks;

import io.camunda.zeebe.client.ZeebeClient;
import uk.ac.uwe.ufcep603.hospital.AbstractHospitalWorker;
import uk.ac.uwe.ufcep603.hospital.JobContext;
import uk.ac.uwe.ufcep603.hospital.WorkerContext;

import java.time.DayOfWeek;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * {@code external-resources.check-availability} - <b>simulated</b> External Treatment, Laboratory and
 * Imaging Services, "Check treatment, laboratory and imaging capacity".
 *
 * <p>Reports, per requested resource, whether capacity is available around the treatment start date,
 * and rolls that up into {@code externalResourcesAvailable} for the model's gateway.
 *
 * <p>Throws the BPMN error {@code EXTERNAL_RESOURCE_UNAVAILABLE} when the simulated failure injection
 * is switched on; the boundary event then ends that pool without confirming capacity, so the caller's
 * timer handles the delay.
 *
 * <p>Limitations: capacity is decided by two deterministic rules (resources named in
 * {@code demo.external.unavailable-resources} are unavailable, and laboratory / imaging work is not
 * available at a weekend) rather than by any real capacity system.
 */
public final class ExternalResourcesCheckAvailabilityWorker extends AbstractHospitalWorker {

    public static final String JOB_TYPE = "external-resources.check-availability";

    private static final List<String> WEEKEND_SENSITIVE_MARKERS =
            List.of("lab", "imaging", "mri", "ct", "pet", "xray", "x-ray", "radiology", "endoscopy");

    public ExternalResourcesCheckAvailabilityWorker(WorkerContext context, ZeebeClient client) {
        super(JOB_TYPE, context, client);
    }

    @Override
    protected Map<String, Object> execute(JobContext job) {
        List<String> resources = new ArrayList<>();
        for (Object entry : job.optList("specialResources").orElse(List.of())) {
            if (entry == null) {
                continue;
            }
            if (entry instanceof Map<?, ?> map) {
                Object name = map.get("resourceName") != null ? map.get("resourceName") : map.get("name");
                if (name != null) {
                    resources.add(String.valueOf(name).trim());
                }
            } else {
                String text = String.valueOf(entry).trim();
                if (!text.isEmpty()) {
                    resources.add(text);
                }
            }
        }
        // A single resource is allowed as well, e.g. specialResource: "MRI".
        if (resources.isEmpty()) {
            String single = job.optFirst("specialResource", "specialResource", "resourceName");
            if (single != null) {
                resources.add(single);
            }
        }

        LocalDate treatmentStart = job.optDateFirst("treatmentStartDate", "treatmentStartDate",
                "treatmentStart", "startDate").orElseGet(() -> context().clock().today().plusDays(7));

        List<String> configuredUnavailable = new ArrayList<>(context().config().unavailableResources());
        configuredUnavailable.addAll(job.optStringList("unavailableResources"));
        List<String> requestedUnavailable = job.optStringList("simulateUnavailableResources");

        Map<String, Object> availability = new LinkedHashMap<>();
        List<String> notes = new ArrayList<>();
        boolean available = true;
        for (String resource : resources) {
            boolean resourceAvailable = true;
            String reason = "capacity confirmed";
            if (matches(resource, configuredUnavailable) || matches(resource, requestedUnavailable)) {
                resourceAvailable = false;
                reason = "reported unavailable by the simulated service";
            } else if (isWeekendSensitive(resource)
                    && (treatmentStart.getDayOfWeek() == DayOfWeek.SATURDAY
                    || treatmentStart.getDayOfWeek() == DayOfWeek.SUNDAY)) {
                resourceAvailable = false;
                reason = "no weekend capacity for " + resource + " on " + treatmentStart;
            }
            availability.put(resource, resourceAvailable);
            notes.add(resource + ": " + reason);
            available = available && resourceAvailable;
        }

        Map<String, Object> output = job.output();
        output.put("externalResourcesAvailable", available);
        output.put("resourceAvailability", availability);
        output.put("resourceAvailabilityNotes", notes);
        output.put("externalResourcesChecked", resources);
        output.put("externalResourcesStartDate", treatmentStart.toString());
        return output;
    }

    private static boolean matches(String resource, List<String> names) {
        String lower = resource.toLowerCase(Locale.ROOT);
        return names.stream().anyMatch(name -> lower.contains(name.toLowerCase(Locale.ROOT)));
    }

    private static boolean isWeekendSensitive(String resource) {
        String lower = resource.toLowerCase(Locale.ROOT);
        return WEEKEND_SENSITIVE_MARKERS.stream().anyMatch(lower::contains);
    }
}
