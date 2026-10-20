-- =====================================================================================
-- Persistence database schema (H2)
-- Hospital Patient Referral, Treatment and Administration System - persistence schema
-- =====================================================================================
--
-- Why this file exists
-- -------------------------------------------------------------------------------------
-- Tutor feedback (Group Feedback, line 7, item 3):
--     "Implement database integration to support data persistence."
-- Before v15, all worker state was held in a ConcurrentHashMap inside HospitalStore, so
-- it was lost as soon as the process stopped. This schema moves that state into the H2
-- database, so it survives across processes and restarts.
--
-- Design notes
-- -------------------------------------------------------------------------------------
-- 1) Foreign keys into patient / gp_practice are deliberately omitted. Those two tables
--    hold reference data, used for business checks such as "does this patient exist" and
--    "does this GP practice still accept referrals", while the keys of operational
--    tables such as appointment and referral come from process variables (the demo
--    script supplies its own patientRef). A foreign key would make the process fail for
--    any patient missing from the reference data, tying demo data and business
--    constraints together. Kept apart, reference data only serves validation and never
--    decides whether a process can run.
-- 2) Every CREATE statement uses IF NOT EXISTS, so this file can be run repeatedly
--    (idempotent) on each worker start without an additional migration framework.
-- 3) Time columns use TIMESTAMP / DATE rather than time-zone aware types, avoiding
--    time-zone differences between demo machines.
-- =====================================================================================


-- -------------------------------------------------------------------------------------
-- 1) Reference data: GP practices and the patient master index
-- -------------------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS gp_practice (
    practice_code       VARCHAR(24)  PRIMARY KEY,
    name                VARCHAR(120) NOT NULL,
    city                VARCHAR(80),
    -- Whether this practice still accepts new referrals. This column answers the tutor
    -- feedback at line 14: "Add GP validation by checking details against the database".
    accepting_referrals BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS patient (
    patient_ref   VARCHAR(40)  PRIMARY KEY,
    -- An NHS number is always 10 digits, the tenth being a modulus 11 check digit. It is
    -- nullable because not every demo patient has one.
    nhs_number    VARCHAR(10),
    full_name     VARCHAR(120) NOT NULL,
    date_of_birth DATE,
    practice_code VARCHAR(24),
    created_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- An NHS number must be unique: one number cannot be attached to two patient records.
CREATE UNIQUE INDEX IF NOT EXISTS ux_patient_nhs_number ON patient (nhs_number);


-- -------------------------------------------------------------------------------------
-- 2) Appointments: maps to HospitalStore.createAppointment / appointment
--    store_key is the idempotency key (derived from process variables) and reference is
--    the appointment number issued to the patient.
-- -------------------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS appointment (
    store_key             VARCHAR(160) PRIMARY KEY,
    reference             VARCHAR(60)  NOT NULL,
    appointment_date_time VARCHAR(40),
    location              VARCHAR(160),
    created_at            TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);


-- -------------------------------------------------------------------------------------
-- 3) Treatment series: maps to createOrGetSeries / series and confirmAppointments
--    The parent table holds the idempotency key; the child table holds each item in order.
-- -------------------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS treatment_series (
    booking_ref VARCHAR(80) PRIMARY KEY,
    created_at  TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS treatment_series_item (
    booking_ref VARCHAR(80) NOT NULL,
    item_index  INT         NOT NULL,
    item_ref    VARCHAR(80) NOT NULL,
    PRIMARY KEY (booking_ref, item_index)
);

CREATE TABLE IF NOT EXISTS confirmed_series (
    signature  VARCHAR(400) PRIMARY KEY,
    created_at TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS confirmed_series_item (
    signature  VARCHAR(400) NOT NULL,
    item_index INT          NOT NULL,
    item_ref   VARCHAR(80)  NOT NULL,
    PRIMARY KEY (signature, item_index)
);


-- -------------------------------------------------------------------------------------
-- 4) Clinic letters: maps to letters / putLetter / letter / seedClinicLetters
--    days_outstanding / overdue_band / requires_reminder are classification results
--    computed against today. They are persisted rather than recomputed so that the
--    consumer (PathwaySuppressDuplicateRemindersWorker) always sees the same decision
--    as when the letter was written; otherwise reminder behaviour would change between
--    run dates.
-- -------------------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS clinic_letter (
    letter_ref        VARCHAR(40)  PRIMARY KEY,
    consultation_date VARCHAR(20),
    subject           VARCHAR(160),
    approved          BOOLEAN      NOT NULL DEFAULT FALSE,
    days_outstanding  INT,
    overdue_band      VARCHAR(40),
    requires_reminder BOOLEAN,
    created_at        TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);


-- -------------------------------------------------------------------------------------
-- 5) Pathway monitoring: maps to addToMonitoring / monitoringEntries
-- -------------------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS pathway_monitoring (
    letter_ref     VARCHAR(40) PRIMARY KEY,
    monitoring_ref VARCHAR(80) NOT NULL,
    created_at     TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP
);


-- -------------------------------------------------------------------------------------
-- 6) Reminders: maps to alreadyReminded / recordReminder / nextReminderCount
-- -------------------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS letter_reminder (
    letter_ref       VARCHAR(40) PRIMARY KEY,
    reminder_count   INT         NOT NULL DEFAULT 0,
    last_reminded_on DATE
);


-- -------------------------------------------------------------------------------------
-- 7) Payments: maps to markPaymentReference / paymentReferenceSeen / recordProviderPayment
--    The payment_reference primary key (patient_ref, payment_reference) is the duplicate
--    charge test: an insert conflict means this payment was seen before. The test still
--    holds after a process restart, which is the key gain over the previous in-memory map.
-- -------------------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS payment_reference (
    patient_ref       VARCHAR(40) NOT NULL,
    payment_reference VARCHAR(60) NOT NULL,
    first_seen_at     TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (patient_ref, payment_reference)
);

CREATE TABLE IF NOT EXISTS provider_payment (
    patient_ref       VARCHAR(40)   NOT NULL,
    payment_reference VARCHAR(60)   NOT NULL,
    status            VARCHAR(30),
    amount            DECIMAL(12,2),
    recorded_at       TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (patient_ref, payment_reference)
);


-- -------------------------------------------------------------------------------------
-- 8) Role and permission matrix (the code-side layer of RBAC)
--    Camunda's own authorisation tables govern who may operate engine resources; this
--    layer governs whether a business role may perform a class of business action, and
--    the worker checks it against the database at runtime and writes an audit record.
-- -------------------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS app_role (
    role_id     VARCHAR(60)  PRIMARY KEY,
    name        VARCHAR(120) NOT NULL,
    description VARCHAR(400)
);

CREATE TABLE IF NOT EXISTS role_permission (
    role_id       VARCHAR(60) NOT NULL,
    resource_type VARCHAR(60) NOT NULL,
    action        VARCHAR(60) NOT NULL,
    PRIMARY KEY (role_id, resource_type, action)
);


-- -------------------------------------------------------------------------------------
-- 9) Audit log: one row per controlled business action, covering both allow and deny.
--    This is the auditable evidence that role permissions really are enforced, and it
--    meets the traceability requirements of a healthcare system.
-- -------------------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS audit_log (
    audit_id             BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    occurred_at          TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actor                VARCHAR(80),
    role_id              VARCHAR(60),
    job_type             VARCHAR(80),
    process_instance_key BIGINT,
    action               VARCHAR(60)   NOT NULL,
    resource_type        VARCHAR(60)   NOT NULL,
    resource_id          VARCHAR(160),
    decision             VARCHAR(10)   NOT NULL,
    detail               VARCHAR(900)
);

CREATE INDEX IF NOT EXISTS ix_audit_log_occurred_at ON audit_log (occurred_at);
CREATE INDEX IF NOT EXISTS ix_audit_log_resource    ON audit_log (resource_type, resource_id);
