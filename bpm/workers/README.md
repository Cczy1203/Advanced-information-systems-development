# Hospital external workers (UFCEP6-0-3)

Java Camunda 8 (Zeebe) **external job workers** for the *Hospital Patient Referral, Treatment and
Administration System* BPMN collaboration.

One worker handles the single message dispatcher job type, and one small, focused class handles each
of the 35 domain service task types. All 36 extend `AbstractHospitalWorker`, which centralises the
job type subscription, logging (job key / element id / process instance key), variable extraction and
validation, job completion, and the fail-vs-BPMN-error decision.

```
36 job workers = 1 publish-message dispatcher + 35 service tasks
```

Those 35 domain types are exactly the 35 distinct `zeebe:taskDefinition type` values the
collaboration uses. To count them from the model:

```bash
python3 -c "import xml.etree.ElementTree as ET; Z='{http://camunda.org/schema/zeebe/1.0}'; \
B='{http://www.omg.org/spec/BPMN/20100524/MODEL}'; r=ET.parse('model/UFCEP6-0-3_Hospital_Patient_Pathway_v2.bpmn').getroot(); \
print(len({e.find('.//'+Z+'taskDefinition').get('type') for e in r.iter(B+'serviceTask')}))"
```

* Build: `mvn -q clean package` → `target/hospital-external-workers-1.0.0.jar`
* Run: `java -jar target/hospital-external-workers-1.0.0.jar` or `./run-workers.sh` or `mvn exec:java`
* Configuration, demo switches and cluster options: **[DEPLOYMENT.md](DEPLOYMENT.md)**

---

## Layout

```
workers/
├── pom.xml                       # Maven build, shade plugin (fat jar), exec plugin
├── run-workers.sh                # convenience runner
├── README.md                     # this file
├── DEPLOYMENT.md                 # build / run / configure / verify
└── src/main/
    ├── resources/
    │   ├── application.yaml      # configuration template + documented env overrides
    │   └── logback.xml           # plain console logging
    └── java/uk/ac/uwe/ufcep603/hospital/
        ├── WorkersApplication.java          # main(): build client, subscribe 33 workers, SIGINT shutdown
        ├── Workers.java                     # explicit worker catalogue + BPMN pool/step mapping
        ├── AbstractHospitalWorker.java       # shared base: subscribe, log, complete, fail, throw error
        ├── JobContext.java                   # variable extraction / validation helpers
        ├── WorkerContext.java                # config + store + clock + failure registry
        ├── ValidationException.java          # bad input -> failed job naming the variable
        ├── BpmnErrorException.java           # business condition -> BPMN error
        ├── TransientJobException.java        # transient problem -> failed job, engine retries
        ├── config/
        │   ├── AppConfig.java                # YAML + env-var configuration
        │   └── SimulatedFailureRegistry.java # demo failure injection + forced payment outcomes
        ├── support/
        │   ├── DemoClock.java                # freezable/shiftable clock for reproducible demos
        │   ├── HospitalStore.java            # in-memory idempotency store
        │   └── Ids.java                      # deterministic reference generation
        └── tasks/                            # 36 worker classes, 35 domain types + 1 alias
```

## Job types in the model

Every service task in the collaboration has `retries="3"`, and every message throw event carries
`<zeebe:taskDefinition type="publish-message" />` plus a `messageName` task header.

| # | Job type | BPMN pool / step | Returns |
|---|---|---|---|
| 0 | `publish-message` | **every pool** - all message throw events (element id is logged) | `publishedMessageName`, `publishedCorrelationKey`, `publishedMessageKey`; publishes the message with all process variables forwarded |
| 1 | `referral.check-supporting-documents` | Medical Secretaries - *Validate supporting documents and flag missing items* (`SEC_Auto_ValidateDocuments`) | `referralPackComplete`, `missingDocuments`, `referralChecklist`, `referralDocumentsReceived`. BPMN errors `REFERRAL_PACK_UNREADABLE` (list missing/not a list) and `REFERRAL_PACK_INCOMPLETE` (blank or unreadable entry) |
| 2 | `audit.record-clinical-decision` | Consultants - *Write the clinical decision to the audit trail* (`CON_Auto_AuditDecision`, `CON_Auto_AuditCycle`) | `clinicalDecisionAuditRef`, `clinicalDecisionAuditAt`. Clinical variables are never written back; blank `patientRef` fails the job |
| 3 | `audit.record-financial-decision` | Finance - *Record the funding / refund decision for audit* (`FIN_Auto_AuditFunding`, `FIN_Auto_AuditRefund`) | `financialDecisionAuditRef`, `financialDecisionAuditAt`. Same no-overwrite rule |
| 4 | `booking.check-priority-and-contact-rule` | Outpatient Bookings - *Work out priority, timeframe and contact rule* (`OUT_Auto_CheckPriority`) | `appointmentPriority`, `requiresPhoneCall`, `contactRule`, `twoWeekRuleApplied`, `daysUntilAppointment` |
| 5 | `booking.create-appointment` | Outpatient Bookings - *Create the appointment record / follow-up* (`OUT_Auto_CreateAppointment`, `OUT_Auto_CreateFollowUp`) | `appointmentRef`, `appointmentDateTime`, `appointmentLocation`, `duplicateSuppressed`. Idempotent: a repeat returns the same appointment |
| 6 | `booking.record-appointment-outcome` | Outpatient Bookings - *Record the appointment outcome* (`OUT_Auto_RecordOutcome`) | `appointmentOutcomeRecordedAt`, `outcomeCategory` (`ADMINISTRATIVE` / `CLINICAL_ACTION_REQUIRED`) |
| 7 | `treatment.validate-request` | Treatment Bookings - *Check the request is complete and authorised* (`TRT_Auto_ValidateRequest`) | `requestValidated`, `validatedCycleCount`. BPMN error `TREATMENT_REQUEST_UNAUTHORISED` |
| 8 | `treatment.authorise-request` | Consultants - *Authorise the treatment booking request* (`CON_Auto_AuthoriseRequest`) | `treatmentAuthorised`, `treatmentAuthorisedBy`, `treatmentAuthorisedAt`. Fails the job when consent is not true |
| 9 | `treatment.create-appointment-series` | Treatment Bookings - *Create the provisional appointment series* (`TRT_Auto_CreateSeries`) | `provisionalAppointmentRefs`, `seriesReference`, `provisionalAppointmentDates`. Idempotent on `treatmentBookingRef` |
| 10 | `treatment.confirm-appointments` | Treatment Bookings - *Confirm the treatment appointments* (`TRT_Auto_ConfirmAppointments`) | `confirmedAppointmentRefs`, `appointmentsConfirmed`, `confirmedAppointmentCount`. Idempotent on the reference set |
| 11 | `treatment.schedule-next-cycle` | Treatment Bookings - *Schedule the next cycle* (`TRT_Auto_ScheduleCycle`) | `nextCycleNumber`, `cycleScheduledFor` |
| 12 | `treatment.apply-modification` | Treatment Bookings - *Apply the treatment change to the schedule* (`TRT_Auto_ApplyModification`) | `modificationAppliedRef`, `modifiedAppointmentRefs` |
| 13 | `payment.prepare-request` | Treatment Bookings - *Prepare the secure payment request / next attempt* (`TRT_Auto_PreparePayment`, `TRT_Auto_NextAttempt`) | `paymentReference`, `paymentRequestedAt`, `paymentAttempt` (preserved when already set). Never emits card data |
| 14 | `finance.calculate-charge` | Finance - *Work out the charge payable* (`FIN_Auto_CalculateCharge`) | `chargeAmount`, `currency`, `chargeTariffMatched`, `chargeCategoryApplied`. BPMN error `CHARGE_CALCULATION_FAILED` |
| 15 | `finance.record-funding-approval` | Finance - *Record the funding approval* (`FIN_Auto_RecordApproval`) | `fundingApprovalRecordedRef`, `approvedAmountRecorded`, `funderNameRecorded`. A payer-funded route without a payer or an authorisation reference fails the job |
| 16 | `finance.check-duplicate-payment` | Treatment Bookings - *Check the charge has not already been taken* (`TRT_Auto_Deduplicate`) | `duplicateChargeFound`, `resolvedPaymentReference`, `duplicateChargeEvidence` |
| 17 | `finance.record-payment-outcome` | Finance - *Record the payment against the account* (`FIN_Auto_RecordPayment`) | `paymentRecordedRef`, `paymentConfirmed` (true only for APPROVED/CONFIRMED) |
| 18 | `finance.prepare-refund` | Finance - *Prepare the approved refund* (`FIN_Auto_PrepareRefund`) | `refundReference`, `approvedRefundAmount`. A refund larger than the amount paid fails the job (see *simplifications*) |
| 19 | `finance.record-refund` | Finance - *Record the refund / record that no refund is due* (`FIN_Auto_RecordRefund`, `FIN_Auto_RecordNoRefund`) | `refundRecordedRef`, `refundCompleted`, `refundedAmount` |
| 20 | `correspondence.prepare-dispatch` | Medical Secretaries - *Prepare the letter for distribution* (`SEC_Auto_PrepareDispatch`) | `dispatchChannel`, `dispatchRecipients`, `dispatchPayloadRef`, `dispatchFormat` |
| 21 | `correspondence.dispatch-letter` | Secretaries / Outpatient Bookings / Treatment Bookings / Pathway Coordinators - *Dispatch the letter* (5 elements) | `dispatchStatus` (`SENT`), `dispatchReference`, `dispatchedAt`, `dispatchFormat`. **Simulated.** BPMN error `CORRESPONDENCE_SERVICE_FAILED` on injected failure or an empty recipient list |
| 22 | `scheduling.find-appointment-slots` | Outpatient Bookings / Treatment Bookings - *Search the external scheduling service* (4 elements) | `slotCount`, `slotOptions` (`slotRef`, `start`, `location`), `schedulingOutcome` (`SLOTS_FOUND` / `NO_SLOTS`). **Simulated.** BPMN error `SCHEDULING_SERVICE_UNAVAILABLE` |
| 23 | `external-resources.check-availability` | Treatment Bookings - *Check external treatment and diagnostic capacity* (`TRT_Auto_CheckExternalResources`) | `externalResourcesAvailable`, `resourceAvailability` (map), `resourceAvailabilityNotes`. **Simulated.** BPMN error `EXTERNAL_RESOURCE_UNAVAILABLE` |
| 24 | `payment.process-transaction` | Treatment Bookings - *Take the payment through the payment provider* (`TRT_Auto_ProcessPayment`) | `paymentStatus`, `paymentRef`, `paymentDate`, `paidAmount`. **Simulated.** BPMN errors `PAYMENT_PROVIDER_UNAVAILABLE` and `PAYMENT_CONFIRMATION_LOST`. Never emits card data |
| 25 | `payment.process-refund` | Finance - *Send the refund to the payment provider* (`FIN_Auto_ProcessRefund`) | `refundStatus` (`REFUNDED` / `REJECTED` / `PENDING`), `refundProcessedAt`, `refundedAmount`. **Simulated.** BPMN error `PAYMENT_PROVIDER_UNAVAILABLE` |
| 26 | `pathway.find-overdue-clinic-letters` (alias `pathway.find-overdue-letters`) | Pathway Coordinators - *Find clinic letters that are overdue* (`PCW_Auto_FindOverdue`) | `outstandingLetters` (with `daysOutstanding` and `overdueBand`), `letterOverdueDays` (worst case, drives the escalation gateway), `lettersRequiringReminder` |
| 27 | `pathway.suppress-duplicate-reminders` | Pathway Coordinators - *Drop letters that no longer need chasing* (`PCW_Auto_SuppressDuplicates`) | `lettersToRemind`, `suppressedReminderCount`. Re-running never reminds the same letter twice |
| 28 | `pathway.add-to-monitoring` | Pathway Coordinators - *Add the letter to pathway monitoring* (`PCW_Auto_AddToMonitoring`) | `monitoringRef`, `addedToMonitoring` |
| 29 | `letter.record-reminder` | Consultants - *Record the reminder against the letter* (`CON_Auto_RecordReminder`) | `reminderRecordedRef`, `reminderCount` (incremented, never reset) |
| 30 | `enquiry.close-record` | Call Handling - *Close the enquiry record* (`CALL_Auto_CloseEnquiry`) | `enquiryClosedAt`, `enquiryStatus` (`RESOLVED` / `OPEN`) |
| 31 | `enquiry.record-contact-attempt` | Call Handling - *Log the contact attempt* (`CALL_Auto_LogAttempt`) | `contactAttempts` (incremented), `lastContactAttemptAt`, `contactOutcome`. Must be `REACHED` / `NO_ANSWER` / `WRONG_NUMBER` / `WANTS_ALTERNATIVE` |
| 32 | `cns.record-clinical-advice` | Clinical Nurse Specialists - *Record the advice given* (`CNS_Auto_RecordAdvice`) | `clinicalAdviceRecordedRef`, `adviceRecordedAt` |
| 33 | `treatment.record-capacity-retry` | Treatment Bookings - *Record another capacity attempt* (`TRT_Auto_RecordRetry`) | `externalResourceAttempts`, `lastCapacityAttemptAt`, `capacityAttemptsRemaining`, `capacityExhausted`. Counts the attempts so the retry loop stops at three instead of filling the incident queue |
| 34 | `treatment.release-series` | Treatment Bookings - *Release the provisional appointment series* (`TRT_Comp_ReleaseSeries`, a **compensation handler**, `isForCompensation="true"`) | `seriesReleased`, `releasedAppointmentRefs`, `releasedAppointmentCount`, `seriesReleasedAt`, `seriesReleaseReason`, `releasedBookingRef`. Frees every appointment in the series when a booking has to be undone |
| 35 | `treatment.release-cycle-booking` | Treatment Bookings - *Release the provisional cycle booking* (`TRT_Comp_ReleaseCycle`, a **compensation handler**) | `cycleReleased`, `releasedCycleNumber`, `releasedCycleRef`, `cycleReleasedAt`. The cycle-level counterpart of type 34 |

## How a worker behaves

```
job activated
  └─ forced demo failure?            -> BPMN error (configured/canonical code) or failed job
  └─ validate input                  -> ValidationException("...variable 'x' must be ...")  -> FAILED job
  └─ business condition              -> BpmnErrorException("CODE", msg)                     -> BPMN error
  └─ transient problem               -> TransientJobException                              -> FAILED job
  └─ otherwise                       -> COMPLETED with the output variable map
```

* **Failed job** = `newFailCommand().retries(job.getRetries() - 1)`, so the model's `retries="3"` is
  honoured: three attempts, then an incident. Used for bad input and transient problems.
* **BPMN error** = `newThrowErrorCommand().errorCode(...).errorMessage(...)`, used *only* for the
  business conditions listed above, whose codes match the `bpmn:error` definitions in the model.

## Verified against the running engine

Validation was performed against the live c8run 8.10.0-alpha5 cluster (gRPC `localhost:26500`, REST
`http://localhost:8080`) using throwaway models in `/tmp`, never inside this directory:

* `referral.check-supporting-documents`: success, `REFERRAL_PACK_INCOMPLETE` and
  `REFERRAL_PACK_UNREADABLE` branches, plus the incomplete-pack output.
* `publish-message`: a message throw event in one process started a second process through its
  message start event; a blank `correlationKey` failed the job three times and produced an incident
  naming the variable (no BPMN error).
* All 35 domain job types in one 34-task process, completing with no incidents, including the
  idempotency repeats.
* Failure injection for any job type (`always` and `once`), the canonical simulated-service codes,
  empty-recipient dispatch, and a malformed-variable job failure.

See the exact commands and observed output in the task report.

## Simplifications and known gaps

* **Simulated services** (`correspondence.dispatch-letter`, `scheduling.find-appointment-slots`,
  `external-resources.check-availability`, `payment.process-transaction`, `payment.process-refund`)
  are deterministic stubs. They produce plausible data and genuinely exercise the success and failure
  branches, but they never call anything and they do not confirm delivery or settlement.
* **`finance.prepare-refund`** reports "refund larger than the amount paid" as a **failed job**, not
  a BPMN error: the model attaches no boundary error event to that step, so a BPMN error would have
  nowhere to go. Failing the job raises an incident for Finance to resolve, which is the safe
  outcome when money is involved.
* **`payment.process-transaction` with `NO_CONFIRMATION`** throws `PAYMENT_CONFIRMATION_LOST` by
  default, matching `TRT_Bnd_ConfirmationLost` in the model. Set
  `DEMO_PAYMENT_CONFIRMATION_LOST_MODE=retry` to fail the job instead (the behaviour to use with a
  model whose caller waits on a timer).
* **Idempotency state is in memory** in one JVM (see [DEPLOYMENT.md](DEPLOYMENT.md) §5).
* **`referral.check-supporting-documents`** treats an unreadable/corrupt document entry as
  `REFERRAL_PACK_INCOMPLETE` and only a missing/not-a-list `supportingDocuments` as
  `REFERRAL_PACK_UNREADABLE`, as specified.
* **Job type alias**: the model currently gives `PCW_Auto_FindOverdue` the shorter job type
  `pathway.find-overdue-letters`, so that worker subscribes to **both** names
  (`AbstractHospitalWorker.jobTypes()`); 36 worker classes therefore produce **37 job type
  subscriptions**: the 35 model types, the one alias, and `publish-message`.
* **Variable aliases**: because the hospital forms and the model variables are developed separately,
  several workers accept documented aliases (for example `amountTaken` for `paidAmount`,
  `matchedTransactionRef` for `paymentRef`, `cycleReviewOutcome` for `clinicalDecision`). The
  canonical name is always the one in the table above; `JobContext.patientKey()` falls back from
  `patientRef` to the business reference on the job, while the two audit workers insist on a real
  `patientRef`.
* Not verified: the workers have not been run against the full generated collaboration BPMN (it was
  still being regenerated while this was built). Worker behaviour was verified on equivalent
  throwaway models instead.
