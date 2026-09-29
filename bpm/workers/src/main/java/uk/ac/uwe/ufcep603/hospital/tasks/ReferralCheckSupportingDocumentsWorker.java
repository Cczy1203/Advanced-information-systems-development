package uk.ac.uwe.ufcep603.hospital.tasks;

import io.camunda.zeebe.client.ZeebeClient;
import uk.ac.uwe.ufcep603.hospital.AbstractHospitalWorker;
import uk.ac.uwe.ufcep603.hospital.BpmnErrorException;
import uk.ac.uwe.ufcep603.hospital.JobContext;
import uk.ac.uwe.ufcep603.hospital.WorkerContext;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

/**
 * {@code referral.check-supporting-documents} - Medical Secretaries,
 * "Validate supporting documents and flag missing items".
 *
 * <p>Reads the document list, matches it against the checklist for the referral speciality and
 * returns {@code referralPackComplete} plus {@code missingDocuments}. The Medical Secretaries only
 * check the pack; they never record a view on clinical suitability.
 *
 * <table>
 *   <caption>Outcomes</caption>
 *   <tr><th>Situation</th><th>Result</th></tr>
 *   <tr><td>{@code supportingDocuments} absent or not a list</td>
 *       <td>BPMN error {@code REFERRAL_PACK_UNREADABLE} - the upload could not be read at all</td></tr>
 *   <tr><td>a document entry is blank, null or carries an unreadable marker</td>
 *       <td>BPMN error {@code REFERRAL_PACK_INCOMPLETE} - the pack is readable but damaged</td></tr>
 *   <tr><td>the list is readable</td>
 *       <td>completed with {@code referralPackComplete} and {@code missingDocuments}</td></tr>
 * </table>
 */
public final class ReferralCheckSupportingDocumentsWorker extends AbstractHospitalWorker {

    public static final String JOB_TYPE = "referral.check-supporting-documents";

    private static final String REFERRAL_PACK_UNREADABLE = "REFERRAL_PACK_UNREADABLE";
    private static final String REFERRAL_PACK_INCOMPLETE = "REFERRAL_PACK_INCOMPLETE";

    /** Markers that mean "the upload exists but cannot be used". */
    private static final Set<String> UNREADABLE_MARKERS = Set.of(
            "unreadable", "corrupt", "corrupted", "illegible", "damaged", "unopenable", "unusable");

    private static final List<String> DEFAULT_CHECKLIST =
            List.of("referral-letter", "blood-tests", "imaging-report");

    /** Accepted names for the document list; {@code supportingDocuments} is the canonical one. */
    private static final List<String> DOCUMENT_VARIABLES = List.of(
            "supportingDocuments", "supportingDocument", "documentChecklist", "receivedDocuments",
            "referralDocuments", "documentsReceived", "documentList");

    private static final Map<String, List<String>> CHECKLISTS = Map.of(
            "oncology", List.of("referral-letter", "histology-report", "imaging-report", "blood-tests", "consent-form"),
            "chemotherapy", List.of("referral-letter", "histology-report", "imaging-report", "blood-tests", "consent-form"),
            "cardiology", List.of("referral-letter", "ecg", "echo-report", "blood-tests"),
            "respiratory", List.of("referral-letter", "chest-xray", "lung-function-tests", "blood-tests"),
            "neurology", List.of("referral-letter", "imaging-report", "blood-tests"),
            "dermatology", List.of("referral-letter", "photographs", "biopsy-report"),
            "gastroenterology", List.of("referral-letter", "endoscopy-report", "blood-tests"));

    /** Synonyms a clinician or secretary might type, mapped onto the canonical checklist entry. */
    private static final Map<String, String> SYNONYMS = Map.ofEntries(
            Map.entry("bloods", "blood-tests"),
            Map.entry("blood-test", "blood-tests"),
            Map.entry("bloodtest", "blood-tests"),
            Map.entry("histology", "histology-report"),
            Map.entry("biopsy", "biopsy-report"),
            Map.entry("imaging", "imaging-report"),
            Map.entry("mri", "imaging-report"),
            Map.entry("ct", "imaging-report"),
            Map.entry("ct-scan", "imaging-report"),
            Map.entry("xray", "chest-xray"),
            Map.entry("chest-x-ray", "chest-xray"),
            Map.entry("ecg", "ecg"),
            Map.entry("echo", "echo-report"),
            Map.entry("lung-function", "lung-function-tests"),
            Map.entry("spirometry", "lung-function-tests"),
            Map.entry("consent", "consent-form"),
            Map.entry("referral", "referral-letter"),
            Map.entry("referralletter", "referral-letter"));

    public ReferralCheckSupportingDocumentsWorker(WorkerContext context, ZeebeClient client) {
        super(JOB_TYPE, context, client);
    }

    @Override
    protected Map<String, Object> execute(JobContext job) {
        String speciality = job.optFirst("referralSpeciality", "referralSpecialty", "speciality", "specialty");
        String normalisedSpeciality = speciality == null ? "general" : speciality.toLowerCase(Locale.ROOT);

        // ---- the unreadable case: the variable itself is missing or is not a list of documents.
        String documentsVariable = null;
        Object rawDocuments = null;
        for (String candidate : DOCUMENT_VARIABLES) {
            if (job.has(candidate)) {
                documentsVariable = candidate;
                rawDocuments = job.get(candidate);
                break;
            }
        }
        if (documentsVariable == null) {
            throw new BpmnErrorException(REFERRAL_PACK_UNREADABLE,
                    "Referral pack unreadable: no document list was supplied for speciality '"
                            + normalisedSpeciality + "'. Expected a list in 'supportingDocuments' (accepted"
                            + " aliases " + DOCUMENT_VARIABLES + ") on element " + job.elementId());
        }
        if (!(rawDocuments instanceof List<?> documentList)) {
            throw new BpmnErrorException(REFERRAL_PACK_UNREADABLE,
                    "Referral pack unreadable: '" + documentsVariable + "' must be a list of document names but"
                            + " was " + rawDocuments.getClass().getSimpleName() + " for speciality '"
                            + normalisedSpeciality + "' (element " + job.elementId() + ")");
        }

        // ---- the incomplete case: a readable list containing a damaged entry.
        List<String> received = new ArrayList<>();
        int index = 0;
        for (Object entry : documentList) {
            index++;
            if (entry == null) {
                throw new BpmnErrorException(REFERRAL_PACK_INCOMPLETE,
                        "Referral pack incomplete: entry " + index + " of '" + documentsVariable + "' is null"
                                + " (element " + job.elementId() + ")");
            }
            String text = String.valueOf(entry).trim();
            if (text.isEmpty()) {
                throw new BpmnErrorException(REFERRAL_PACK_INCOMPLETE,
                        "Referral pack incomplete: entry " + index + " of '" + documentsVariable + "' is blank"
                                + " (element " + job.elementId() + ")");
            }
            String lower = text.toLowerCase(Locale.ROOT);
            for (String marker : UNREADABLE_MARKERS) {
                if (lower.contains(marker)) {
                    throw new BpmnErrorException(REFERRAL_PACK_INCOMPLETE,
                            "Referral pack incomplete: entry " + index + " of '" + documentsVariable + "' ('"
                                    + text + "') is marked as " + marker + " (element " + job.elementId() + ")");
                }
            }
            received.add(canonical(text));
        }

        List<String> required = checklistFor(normalisedSpeciality);
        List<String> missing = new ArrayList<>();
        for (String expected : required) {
            if (!received.contains(expected)) {
                missing.add(expected);
            }
        }

        Map<String, Object> output = job.output();
        output.put("referralPackComplete", missing.isEmpty());
        output.put("missingDocuments", missing);
        output.put("referralChecklist", required);
        output.put("referralDocumentsReceived", received);
        output.put("referralSpecialityChecked", normalisedSpeciality);
        return output;
    }

    private static List<String> checklistFor(String normalisedSpeciality) {
        for (Map.Entry<String, List<String>> entry : CHECKLISTS.entrySet()) {
            if (normalisedSpeciality.contains(entry.getKey())) {
                return entry.getValue();
            }
        }
        return DEFAULT_CHECKLIST;
    }

    /** Lower case, spaces and underscores to dashes, then synonym lookup. */
    static String canonical(String document) {
        String normalised = document.toLowerCase(Locale.ROOT).trim()
                .replace('_', '-')
                .replace(' ', '-');
        while (normalised.contains("--")) {
            normalised = normalised.replace("--", "-");
        }
        String synonym = SYNONYMS.get(normalised);
        if (synonym != null) {
            return synonym;
        }
        Set<String> candidates = new LinkedHashSet<>();
        candidates.add(normalised);
        String withoutSuffix = normalised.replace("-report", "").replace("-form", "").replace("-tests", "");
        candidates.add(withoutSuffix);
        for (Map.Entry<String, String> entry : SYNONYMS.entrySet()) {
            if (candidates.contains(entry.getKey())) {
                return entry.getValue();
            }
        }
        return normalised;
    }
}
