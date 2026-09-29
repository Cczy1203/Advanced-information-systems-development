package uk.ac.uwe.ufcep603.hospital;

import io.camunda.zeebe.client.ZeebeClient;
import io.camunda.zeebe.client.api.response.Topology;
import io.camunda.zeebe.client.api.worker.JobWorker;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import uk.ac.uwe.ufcep603.hospital.config.AppConfig;
import uk.ac.uwe.ufcep603.hospital.config.SimulatedFailureRegistry;
import uk.ac.uwe.ufcep603.hospital.support.DemoClock;
import uk.ac.uwe.ufcep603.hospital.support.HospitalStore;

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

        WorkerContext context = new WorkerContext(
                config,
                new SimulatedFailureRegistry(config),
                new HospitalStore(),
                new DemoClock(config));

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
            shutdown.countDown();
        }, "hospital-workers-shutdown"));

        try {
            shutdown.await();
        } catch (InterruptedException interrupted) {
            Thread.currentThread().interrupt();
            LOG.info("Interrupted - stopping");
        }
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
