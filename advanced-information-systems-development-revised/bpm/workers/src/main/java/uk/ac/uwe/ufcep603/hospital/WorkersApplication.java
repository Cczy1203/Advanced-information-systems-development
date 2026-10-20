package uk.ac.uwe.ufcep603.hospital;

import io.camunda.zeebe.client.ZeebeClient;
import io.camunda.zeebe.client.api.response.Topology;
import io.camunda.zeebe.client.api.worker.JobWorker;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import uk.ac.uwe.ufcep603.hospital.config.AppConfig;
import uk.ac.uwe.ufcep603.hospital.config.SimulatedFailureRegistry;
import uk.ac.uwe.ufcep603.hospital.db.AccessControl;
import uk.ac.uwe.ufcep603.hospital.db.HospitalDatabase;
import uk.ac.uwe.ufcep603.hospital.db.ReferenceData;
import uk.ac.uwe.ufcep603.hospital.support.DemoClock;
import uk.ac.uwe.ufcep603.hospital.support.HospitalStore;
import uk.ac.uwe.ufcep603.hospital.support.ReferralRegistry;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CountDownLatch;

/**
 * Entry point for the hospital external workers.
 *
 * <p>Builds the Zeebe client, subscribes the message dispatcher plus all 32 domain service task
 * workers, logs the subscribed job types together with the pool and BPMN step each one serves, and
 * shuts down cleanly when the process is interrupted (SIGINT / Ctrl-C).
 *
 * <p>Run it with {@code java -jar target/hospital-external-workers-1.0.0.jar} or
 * {@code mvn exec:java}. See {@code DEPLOYMENT.md} for the configuration keys and the demo switches.
 */
public final class WorkersApplication {

    private static final Logger LOG = LoggerFactory.getLogger(WorkersApplication.class);

    private WorkersApplication() {
    }

    public static void main(String[] args) {
        AppConfig config = AppConfig.load(args);

        LOG.info("==============================================================");
        LOG.info(" UFCEP6-0-3 Hospital Patient Referral, Treatment and Administration");
        LOG.info(" Camunda 8 external job workers");
        LOG.info("==============================================================");
        for (Map.Entry<String, Object> entry : config.summary().entrySet()) {
            LOG.info("  {}", pad(entry.getKey(), 22) + " " + entry.getValue());
        }

        ZeebeClient client = buildClient(config);

        // ---- H2 persistence. External feedback (Group Feedback sheet, R7 item 3): "Implement
        //      database integration to support data persistence." Opens the database, creates the
        //      tables and loads the reference data, then wires every database-backed component
        //      into the WorkerContext. When the database is unavailable it falls back to a
        //      non-persistent mode with an explicit warning rather than silently dropping data,
        //      so whether persistence is really active is obvious at a glance in the log.
        HospitalDatabase activeDatabase = null;
        ReferenceData referenceData = null;
        ReferralRegistry referralRegistry = null;
        AccessControl accessControl = null;
        if (config.databaseEnabled()) {
            try {
                activeDatabase = HospitalDatabase.open(config.databaseUrl(), config.databaseUser(),
                        config.databasePassword(), config.databaseSeed(), config.databaseMaxConnections());
                referenceData = new ReferenceData(activeDatabase);
                referralRegistry = new ReferralRegistry(config, referenceData);
                accessControl = new AccessControl(activeDatabase);
                logDatabaseState(activeDatabase, referenceData, accessControl);
            } catch (RuntimeException e) {
                LOG.error("Database failed to open; falling back to a non-persistent store: {}",
                        e.toString());
                activeDatabase = null;
                referenceData = null;
                referralRegistry = null;
                accessControl = null;
            }
        } else {
            LOG.warn("database.enabled=false - idempotency state is in-process only and is lost when the process restarts.");
        }
        if (activeDatabase == null) {
            // Fallback: run the same SQL code against an in-memory database, so that "no database"
            // and "database" both follow exactly the same code path, and no defect can appear only
            // in degraded mode. The price is that the data is gone as soon as the process stops,
            // which the ERROR/WARN above already states plainly.
            activeDatabase = HospitalDatabase.open("jdbc:h2:mem:hospital-ephemeral;DB_CLOSE_DELAY=-1",
                    "sa", "", true, 4);
        }
        HospitalStore store = new HospitalStore(activeDatabase);
        final HospitalDatabase openDatabase = activeDatabase;

        WorkerContext context = new WorkerContext(
                config,
                new SimulatedFailureRegistry(config),
                store,
                new DemoClock(config),
                referenceData,
                referralRegistry,
                accessControl);

        List<AbstractHospitalWorker> workers = Workers.all(context, client);
        Map<String, String> owners = Workers.bpmnOwners();

        logTopology(client, config);

        int subscriptionCount = workers.stream().mapToInt(worker -> worker.jobTypes().size()).sum();
        List<JobWorker> subscriptions = new ArrayList<>(subscriptionCount);
        LOG.info("Subscribing {} worker classes as {} job type subscriptions:", workers.size(), subscriptionCount);
        for (AbstractHospitalWorker worker : workers) {
            try {
                subscriptions.addAll(worker.subscribeAll());
                for (String type : worker.jobTypes()) {
                    LOG.info("  {}", pad(type, 42) + " " + owners.getOrDefault(type, "-"));
                }
            } catch (RuntimeException e) {
                LOG.error("  {}", pad(worker.jobType(), 42) + " FAILED to subscribe: " + e);
            }
        }
        LOG.info("{} job worker subscriptions on {}. Waiting for jobs - press Ctrl-C to stop.",
                subscriptions.size(), config.gatewayAddress());

        CountDownLatch shutdown = new CountDownLatch(1);
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            LOG.info("Shutdown requested - closing {} job workers", subscriptions.size());
            for (JobWorker subscription : subscriptions) {
                try {
                    subscription.close();
                } catch (RuntimeException e) {
                    LOG.debug("error closing job worker", e);
                }
            }
            try {
                client.close();
                LOG.info("Zeebe client closed. Bye.");
            } catch (RuntimeException e) {
                LOG.warn("error closing the Zeebe client: {}", e.toString());
            }
            if (openDatabase != null) {
                try {
                    openDatabase.close();
                } catch (RuntimeException e) {
                    LOG.warn("error closing the database: {}", e.toString());
                }
            }
            shutdown.countDown();
        }, "hospital-workers-shutdown"));

        try {
            shutdown.await();
        } catch (InterruptedException interrupted) {
            Thread.currentThread().interrupt();
            LOG.info("Interrupted - stopping");
        }
    }

    /**
     * Prints what the database actually contains into the start-up banner.
     *
     * <p>This is not decoration: the most common persistence problem is believing that something
     * was stored when it was not, so the table names and row counts are printed at start-up and,
     * together with the direct queries in {@code bpm/tools/verify-engine.ps1}, become evidence that
     * can be checked independently.
     */
    @SuppressWarnings("unchecked")
    private static void logDatabaseState(HospitalDatabase database, ReferenceData referenceData,
                                         AccessControl accessControl) {
        LOG.info("--------------------------------------------------------------");
        LOG.info(" H2 persistence enabled");
        LOG.info("  {}", database.describe());
        Object rows = database.summary().get("rows");
        LOG.info("  Business table rows: {}", rows instanceof Map ? rows : database.summary());
        LOG.info("  Reference data: {}", referenceData.summary());
        LOG.info("  Role matrix and audit: {}", accessControl.summary());
        LOG.info("--------------------------------------------------------------");
    }

    private static ZeebeClient buildClient(AppConfig config) {
        var builder = ZeebeClient.newClientBuilder()
                .gatewayAddress(config.gatewayAddress())
                // Explicit configuration wins; do not let ZEEBE_* variables silently override it.
                .applyEnvironmentVariableOverrides(false)
                .defaultRequestTimeout(config.requestTimeout())
                .defaultJobWorkerMaxJobsActive(config.maxJobsActive())
                .defaultJobTimeout(config.jobTimeout())
                .defaultJobPollInterval(config.pollInterval())
                .numJobWorkerExecutionThreads(config.executionThreads())
                .defaultJobWorkerName(config.workerNamePrefix());
        if (config.plaintext()) {
            builder = builder.usePlaintext();
        }
        return builder.build();
    }

    private static void logTopology(ZeebeClient client, AppConfig config) {
        try {
            Topology topology = client.newTopologyRequest().send().join();
            LOG.info("Connected to {} - gateway version {}, {} broker(s), {} partition(s)",
                    config.gatewayAddress(), topology.getGatewayVersion(),
                    topology.getClusterSize(), topology.getPartitionsCount());
        } catch (RuntimeException e) {
            // Workers keep polling and will connect as soon as the cluster is reachable, so this is a
            // warning rather than a fatal error.
            LOG.warn("Could not read the cluster topology from {} yet: {}. The workers will keep trying.",
                    config.gatewayAddress(), e.toString());
        }
    }

    /** slf4j has no field-width syntax, so pad by hand for the start-up table. */
    private static String pad(String value, int width) {
        if (value.length() >= width) {
            return value;
        }
        return value + " ".repeat(width - value.length());
    }
}
