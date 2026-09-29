package uk.ac.uwe.ufcep603.hospital;

import uk.ac.uwe.ufcep603.hospital.config.AppConfig;
import uk.ac.uwe.ufcep603.hospital.config.SimulatedFailureRegistry;
import uk.ac.uwe.ufcep603.hospital.support.DemoClock;
import uk.ac.uwe.ufcep603.hospital.support.HospitalStore;

/**
 * Everything a worker needs besides the job itself: configuration, the in-memory store, the demo
 * clock and the simulated-failure switches. One instance is shared by all workers.
 */
public final class WorkerContext {

    private final AppConfig config;
    private final SimulatedFailureRegistry failures;
    private final HospitalStore store;
    private final DemoClock clock;

    public WorkerContext(AppConfig config, SimulatedFailureRegistry failures, HospitalStore store, DemoClock clock) {
        this.config = config;
        this.failures = failures;
        this.store = store;
        this.clock = clock;
    }

    public AppConfig config() {
        return config;
    }

    public SimulatedFailureRegistry failures() {
        return failures;
    }

    public HospitalStore store() {
        return store;
    }

    public DemoClock clock() {
        return clock;
    }
}
