package uk.ac.uwe.ufcep603.hospital;

import uk.ac.uwe.ufcep603.hospital.config.AppConfig;
import uk.ac.uwe.ufcep603.hospital.config.SimulatedFailureRegistry;
import uk.ac.uwe.ufcep603.hospital.db.AccessControl;
import uk.ac.uwe.ufcep603.hospital.db.ReferenceData;
import uk.ac.uwe.ufcep603.hospital.support.DemoClock;
import uk.ac.uwe.ufcep603.hospital.support.HospitalStore;
import uk.ac.uwe.ufcep603.hospital.support.ReferralRegistry;

/**
 * Everything a worker needs beyond the job in hand: configuration, persistent storage,
 * reference data, permission decisions, the demo clock and the simulated failure switches.
 * All workers share the same instance.
 *
 * <p>The changes in v15 relative to v14 are all of one kind: components that used to live in memory
 * are now backed by the database ({@link HospitalStore} now sits on H2, and {@link ReferenceData},
 * {@link ReferralRegistry} and {@link AccessControl} are new).
 * Every accessor stays immutable and does not change after construction, so the instance can safely
 * be shared by multiple job worker threads.
 */
public final class WorkerContext {

    private final AppConfig config;
    private final SimulatedFailureRegistry failures;
    private final HospitalStore store;
    private final DemoClock clock;
    /** Master patient index and GP practices (read-only reference data). {@code null} when the
     * database is disabled. */
    private final ReferenceData referenceData;
    /** Verifies referral details against the database: whether the patient exists, whether the GP
     * still accepts referrals, and whether the NHS number is valid. */
    private final ReferralRegistry referralRegistry;
    /** Role permission decisions and the audit log. {@code null} when the database is disabled. */
    private final AccessControl accessControl;

    public WorkerContext(AppConfig config, SimulatedFailureRegistry failures, HospitalStore store, DemoClock clock) {
        this(config, failures, store, clock, null, null, null);
    }

    public WorkerContext(AppConfig config,
                         SimulatedFailureRegistry failures,
                         HospitalStore store,
                         DemoClock clock,
                         ReferenceData referenceData,
                         ReferralRegistry referralRegistry,
                         AccessControl accessControl) {
        this.config = config;
        this.failures = failures;
        this.store = store;
        this.clock = clock;
        this.referenceData = referenceData;
        this.referralRegistry = referralRegistry;
        this.accessControl = accessControl;
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

    /** Master patient index and GP practices; {@code null} when the database is disabled, so
     * callers must check for null first. */
    public ReferenceData referenceData() {
        return referenceData;
    }

    /** Database-driven referral checks; {@code null} when the database is disabled. */
    public ReferralRegistry referralRegistry() {
        return referralRegistry;
    }

    /** Role permission decisions and auditing; {@code null} when the database is disabled. */
    public AccessControl accessControl() {
        return accessControl;
    }

    /** Whether the database is available. Every optional database feature should check it first. */
    public boolean hasDatabase() {
        return referenceData != null && accessControl != null;
    }
}
