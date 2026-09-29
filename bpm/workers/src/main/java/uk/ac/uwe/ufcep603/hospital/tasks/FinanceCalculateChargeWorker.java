package uk.ac.uwe.ufcep603.hospital.tasks;

import io.camunda.zeebe.client.ZeebeClient;
import uk.ac.uwe.ufcep603.hospital.AbstractHospitalWorker;
import uk.ac.uwe.ufcep603.hospital.BpmnErrorException;
import uk.ac.uwe.ufcep603.hospital.JobContext;
import uk.ac.uwe.ufcep603.hospital.WorkerContext;

import java.util.LinkedHashMap;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;

/**
 * {@code finance.calculate-charge} - Finance Team, "Work out the charge payable".
 *
 * <p>Applies the tariff for the treatment plan plus the patient's funding category. When the plan is
 * missing, or does not match any tariff the hospital holds, the tariff lookup has failed and the
 * model's {@code CHARGE_CALCULATION_FAILED} boundary event sends the case to manual pricing - a
 * financial decision that must not be guessed by a worker.
 *
 * <p>Returns the amount only. Card data is refused.
 */
public final class FinanceCalculateChargeWorker extends AbstractHospitalWorker {

    public static final String JOB_TYPE = "finance.calculate-charge";

    private static final String CHARGE_CALCULATION_FAILED = "CHARGE_CALCULATION_FAILED";

    /** plan keyword -> tariff in GBP. */
    private static final Map<String, Double> TARIFFS = new LinkedHashMap<>();

    /** patient category -> multiplier applied to the tariff. */
    private static final Map<String, Double> CATEGORY_MULTIPLIERS = Map.of(
            "STANDARD", 1.0,
            "INSURER", 1.0,
            "INSURED", 1.0,
            "EXEMPT", 0.0,
            "CHARITY", 0.5,
            "OVERSEAS", 1.5,
            "SELF_PAYING", 1.0);

    static {
        TARIFFS.put("chemotherapy", 2450.00);
        TARIFFS.put("chemo", 2450.00);
        TARIFFS.put("radiotherapy", 3800.00);
        TARIFFS.put("immunotherapy", 5100.00);
        TARIFFS.put("surgery", 7200.00);
        TARIFFS.put("diagnostic", 640.00);
        TARIFFS.put("endoscopy", 1250.00);
        TARIFFS.put("follow-up", 180.00);
        TARIFFS.put("followup", 180.00);
        TARIFFS.put("consultation", 210.00);
    }

    public FinanceCalculateChargeWorker(WorkerContext context, ZeebeClient client) {
        super(JOB_TYPE, context, client);
    }

    @Override
    protected Map<String, Object> execute(JobContext job) {
        job.rejectCardData();

        String plan = job.optFirst("treatmentPlan", "treatmentPlan", "treatmentRegimen", "plan",
                "chargeBasis", "tariffCode");
        if (plan == null) {
            throw new BpmnErrorException(CHARGE_CALCULATION_FAILED,
                    "Charge could not be calculated: no treatment plan or tariff code was supplied"
                            + " (element " + job.elementId() + ")");
        }

        Optional<Map.Entry<String, Double>> tariff = lookup(plan);
        if (tariff.isEmpty()) {
            throw new BpmnErrorException(CHARGE_CALCULATION_FAILED,
                    "Charge could not be calculated: no tariff is held for treatment plan '" + plan
                            + "' (element " + job.elementId() + ", known plans " + TARIFFS.keySet() + ")");
        }

        String category = job.optFirst("patientCategory", "patientCategory", "fundingCategory", "patientType");
        String normalisedCategory = category == null ? "STANDARD" : category.toUpperCase(Locale.ROOT).replace(' ', '_');
        if (!CATEGORY_MULTIPLIERS.containsKey(normalisedCategory)) {
            throw new BpmnErrorException(CHARGE_CALCULATION_FAILED,
                    "Charge could not be calculated: unknown patient category '" + category
                            + "' (element " + job.elementId() + ", known categories "
                            + CATEGORY_MULTIPLIERS.keySet() + ")");
        }

        double multiplier = CATEGORY_MULTIPLIERS.get(normalisedCategory);
        double amount = round(tariff.get().getValue() * multiplier);
        String currency = job.optFirst("currency", "currency", "currencyCode");
        currency = currency == null ? "GBP" : currency.toUpperCase(Locale.ROOT);

        Map<String, Object> output = job.output();
        output.put("chargeAmount", amount);
        output.put("currency", currency);
        output.put("chargeTariffMatched", tariff.get().getKey());
        output.put("chargeCategoryApplied", normalisedCategory);
        String fundingRoute = job.optFirst("fundingRoute", "fundingRoute", "fundingSource");
        output.put("chargeFundingRoute", fundingRoute == null ? "UNKNOWN" : fundingRoute);
        return output;
    }

    private static Optional<Map.Entry<String, Double>> lookup(String plan) {
        String normalised = plan.toLowerCase(Locale.ROOT).trim();
        return TARIFFS.entrySet().stream()
                .filter(entry -> normalised.contains(entry.getKey()))
                .findFirst();
    }

    private static double round(double amount) {
        return Math.round(amount * 100.0) / 100.0;
    }
}
