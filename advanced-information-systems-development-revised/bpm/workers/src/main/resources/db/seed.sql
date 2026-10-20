-- =====================================================================================
-- Demo and reference data
-- =====================================================================================
--
-- This file writes with MERGE ... KEY(...), so it can be run repeatedly (idempotent):
-- it runs on every worker start, existing rows are updated and missing rows are inserted,
-- so no duplicate data is produced.
--
-- The NHS numbers below are valid numbers computed from the modulus 11 check digit rule,
-- not arbitrary digits:
--   multiply the first 9 digits by 10,9,8,7,6,5,4,3,2, sum them and take the remainder
--   modulo 11; the check digit = 11 - remainder (11 becomes 0; 10 means an invalid number).
--   Example: 9434765919 -> 90+36+24+28+42+30+20+27+2 = 299, 299 mod 11 = 2, 11-2 = 9
-- =====================================================================================


-- -------------------------------------------------------------------------------------
-- GP practices.
-- GP-5580 deliberately no longer accepts new referrals, to demonstrate that
-- database-driven business validation blocks the referral.
-- -------------------------------------------------------------------------------------
MERGE INTO gp_practice (practice_code, name, city, accepting_referrals) KEY (practice_code) VALUES
    ('GP-4471', 'Harbourside Medical Practice', 'Bristol',  TRUE),
    ('GP-5580', 'Old Market Surgery',           'Bristol',  FALSE),
    ('GP-6620', 'Sea Mills Family Doctors',     'Bristol',  TRUE);


-- -------------------------------------------------------------------------------------
-- Patient master index.
-- PAT-2026-0001 is the patient used by the end-to-end driver script
-- (bpm/tools/auto_driver.py), ensuring that the patient found in the database is the
-- same one the process runs with.
-- -------------------------------------------------------------------------------------
MERGE INTO patient (patient_ref, nhs_number, full_name, date_of_birth, practice_code) KEY (patient_ref) VALUES
    ('PAT-2026-0001', '9434765919', 'Jordan Ellis',   DATE '1979-04-12', 'GP-4471'),
    ('PAT-2026-0002', '4010232137', 'Amara Okafor',   DATE '1988-11-30', 'GP-6620'),
    ('PAT-2026-0003', '4000000004', 'Peter Whitlock', DATE '1961-02-08', 'GP-5580');


-- -------------------------------------------------------------------------------------
-- Role to permission matrix, least privilege.
--
-- resource_type here is this system's own business resource. It is a different layer
-- from Camunda's engine resources (PROCESS_DEFINITION / USER_TASK and so on, configured
-- in bpm/camunda/application.yaml):
--   * Camunda layer: whether this role may see / claim / complete user tasks in the engine;
--   * this layer   : whether this role may perform a class of business action (for example,
--                    whether Finance may issue a refund).
-- The worker checks this table at runtime and writes both allows and denials to audit_log.
--
-- Note that auditor has only READ on AUDIT_LOG. This is the role used to demonstrate that
-- an action beyond a role's privileges is rejected and audited.
-- -------------------------------------------------------------------------------------
MERGE INTO app_role (role_id, name, description) KEY (role_id) VALUES
    ('medical-secretaries',        'Medical Secretaries',        'Referral intake, correspondence and dispatch'),
    ('consultants',                'Consultants',                'Clinical decisions, letter approval, treatment authorisation'),
    ('finance',                    'Finance Team',               'Charging, funding approval and refunds'),
    ('outpatient-bookings',        'Outpatient Bookings',        'Creating and changing outpatient appointments'),
    ('treatment-bookings',         'Treatment Bookings',         'Creating and confirming treatment series'),
    ('clinical-nurse-specialists', 'Clinical Nurse Specialists', 'Triaging and answering clinical enquiries'),
    ('call-handling',              'Call Handling',              'Logging and classifying telephone enquiries'),
    ('pathway-coordinators',       'Patient Pathway Coordinators', 'Tracking and monitoring pathway delays'),
    ('administrative-management',  'Administrative Management',  'Handling escalated correspondence'),
    ('auditor',                    'Auditor (read only)',        'Read-only audit; may not modify business data'),
    ('admin',                      'Administrator',              'System administrator with all business permissions');

MERGE INTO role_permission (role_id, resource_type, action) KEY (role_id, resource_type, action) VALUES
    -- Medical secretaries: create referrals, process and dispatch letters,
    -- read-only access to patient records
    ('medical-secretaries', 'REFERRAL',          'READ'),
    ('medical-secretaries', 'REFERRAL',          'WRITE'),
    ('medical-secretaries', 'CLINIC_LETTER',     'READ'),
    ('medical-secretaries', 'CLINIC_LETTER',     'WRITE'),
    ('medical-secretaries', 'CLINIC_LETTER',     'DISPATCH'),
    ('medical-secretaries', 'PATIENT_RECORD',    'READ'),

    -- Consultants: clinical decisions and approvals
    ('consultants', 'REFERRAL',          'READ'),
    ('consultants', 'REFERRAL',          'APPROVE'),
    ('consultants', 'CLINIC_LETTER',     'READ'),
    ('consultants', 'CLINIC_LETTER',     'APPROVE'),
    ('consultants', 'TREATMENT_SERIES',  'READ'),
    ('consultants', 'TREATMENT_SERIES',  'APPROVE'),
    ('consultants', 'PATIENT_RECORD',    'READ'),

    -- Finance: charging, approval, refunds
    ('finance', 'PAYMENT',        'READ'),
    ('finance', 'PAYMENT',        'WRITE'),
    ('finance', 'PAYMENT',        'REFUND'),
    ('finance', 'PATIENT_RECORD', 'READ'),

    -- Outpatient bookings: creating and changing appointments
    ('outpatient-bookings', 'APPOINTMENT',    'READ'),
    ('outpatient-bookings', 'APPOINTMENT',    'WRITE'),
    ('outpatient-bookings', 'REFERRAL',       'READ'),
    ('outpatient-bookings', 'CLINIC_LETTER',  'READ'),

    -- Treatment bookings: treatment series and the corresponding appointments
    ('treatment-bookings', 'TREATMENT_SERIES', 'READ'),
    ('treatment-bookings', 'TREATMENT_SERIES', 'WRITE'),
    ('treatment-bookings', 'APPOINTMENT',      'READ'),
    ('treatment-bookings', 'APPOINTMENT',      'WRITE'),
    ('treatment-bookings', 'PAYMENT',          'READ'),

    -- Clinical nurse specialists: enquiry triage
    ('clinical-nurse-specialists', 'ENQUIRY',        'READ'),
    ('clinical-nurse-specialists', 'ENQUIRY',        'WRITE'),
    ('clinical-nurse-specialists', 'PATIENT_RECORD', 'READ'),
    ('clinical-nurse-specialists', 'CLINIC_LETTER',  'READ'),

    -- Call handling: logging incoming calls
    ('call-handling', 'ENQUIRY',        'READ'),
    ('call-handling', 'ENQUIRY',        'WRITE'),
    ('call-handling', 'APPOINTMENT',    'READ'),
    ('call-handling', 'PATIENT_RECORD', 'READ'),

    -- Pathway coordinators: delay tracking and monitoring
    ('pathway-coordinators', 'PATHWAY_MONITORING', 'READ'),
    ('pathway-coordinators', 'PATHWAY_MONITORING', 'WRITE'),
    ('pathway-coordinators', 'CLINIC_LETTER',      'READ'),

    -- Administrative management: handling escalated letters
    ('administrative-management', 'CLINIC_LETTER',      'READ'),
    ('administrative-management', 'CLINIC_LETTER',      'APPROVE'),
    ('administrative-management', 'PATHWAY_MONITORING', 'READ'),

    -- Auditor: read-only access to the audit log, nothing else
    ('auditor', 'AUDIT_LOG', 'READ'),

    -- Administrator: all business resources
    ('admin', 'REFERRAL',           'READ'), ('admin', 'REFERRAL',           'WRITE'),
    ('admin', 'REFERRAL',           'APPROVE'),
    ('admin', 'APPOINTMENT',        'READ'), ('admin', 'APPOINTMENT',        'WRITE'),
    ('admin', 'TREATMENT_SERIES',   'READ'), ('admin', 'TREATMENT_SERIES',   'WRITE'),
    ('admin', 'TREATMENT_SERIES',   'APPROVE'),
    ('admin', 'CLINIC_LETTER',      'READ'), ('admin', 'CLINIC_LETTER',      'WRITE'),
    ('admin', 'CLINIC_LETTER',      'APPROVE'), ('admin', 'CLINIC_LETTER',   'DISPATCH'),
    ('admin', 'PAYMENT',            'READ'), ('admin', 'PAYMENT',            'WRITE'),
    ('admin', 'PAYMENT',            'REFUND'),
    ('admin', 'ENQUIRY',            'READ'), ('admin', 'ENQUIRY',            'WRITE'),
    ('admin', 'PATHWAY_MONITORING', 'READ'), ('admin', 'PATHWAY_MONITORING', 'WRITE'),
    ('admin', 'PATIENT_RECORD',     'READ'), ('admin', 'PATIENT_RECORD',     'WRITE'),
    ('admin', 'AUDIT_LOG',          'READ');
