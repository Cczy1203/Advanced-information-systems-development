# Failure paths that were actually run — v16.0

Every row below was produced by running the shipped model against c8run 8.10.0-alpha5 on
2026-10-18. Nothing here is a plan or an intention: the instance key, the terminal state and
the worker log line are the evidence.

Engine: `localhost:26500` (c8run), REST `localhost:8080`, basic auth `demo/demo`.
Workers: `bpm/workers/target/hospital-external-workers-1.0.0.jar`, **one** instance at a time.
That single-instance rule is deliberate: two workers sharing the same H2 file is what made the
earlier failure-path attempts fall over silently (limitation L-2 in
`docs/03-test-record.md` §K5.4), so before each run below every other worker was stopped.

Driver: `python3 tools/run_v16.py --scenario <name> --form-fields-only --total-timeout 240`.
`--form-fields-only` means nothing was seeded: every variable came from a form or from a worker.

## What was run

| # | Failure the model must survive | How the failure was forced | Instance | Terminal state | Verdict |
|---|---|---|---|---|---|
| 1 | Payment taken but no confirmation returned (`PAYMENT_CONFIRMATION_LOST`) | `DEMO_PAYMENT_STATUS=NO_CONFIRMATION`, scenario `lost-confirmation` | `2251799815002570` | `COMPLETED` after 21 steps, via `FIN_Task_InvestigatePayment` | **PASS** |
| 2 | External correspondence service rejects the job (`CORRESPONDENCE_SERVICE_FAILED`) | `demo.simulated-failure.job-types=correspondence.dispatch-letter`, scenario `normal` | `2251799815006753` | `COMPLETED` after 23 steps, via `OUT_Task_ChaseLetter` (re-route to another channel) | **PASS** |
| 3 | Applicable charge cannot be calculated (`CHARGE_CALCULATION_FAILED`) | `demo.simulated-failure.job-types=finance.calculate-charge`, scenario `normal` | `2251799815006753` | `COMPLETED` after 23 steps, via `FIN_Task_ManualCharge` | **PASS** |
| 4 | External treatment/lab/imaging resource unavailable (`EXTERNAL_RESOURCE_UNAVAILABLE`) | `demo.simulated-failure.job-types=external-resources.check-availability`, scenario `normal` | `2251799815006753` | `COMPLETED` after 23 steps, via `TRT_Auto_ReleaseSeries` → `End_BookingReleased` | **PASS** |
| 5 | Scheduling service unavailable (`SCHEDULING_SERVICE_UNAVAILABLE`) | `demo.simulated-failure.job-types=scheduling.find-appointment-slots`, scenario `service-down` | `2251799815005557` | **`ACTIVE`, did not finish**: repeated `OUT_Task_ReviewAvailability` until `--max-steps 60` | **PARTIAL, defect D-1** |
| 6 | Payment declined by the provider (business outcome, not a BPMN error) | `DEMO_PAYMENT_STATUS=DECLINED`, scenario `declined-payment` | `2251799815001501` | `COMPLETED` after 22 steps, via `TRT_Task_ReviewDeclinedPayment` | **PASS** (see note 1) |
| 7 | External resource genuinely unavailable at the source (business outcome) | `DEMO_EXTERNAL_UNAVAILABLE_RESOURCES=Laboratory`, scenario `no-capacity` | `2251799815003889` | `COMPLETED` after 19 steps, via `TRT_GW_ExternalAvailable` → `TRT_Auto_ReleaseSeries` | **PASS** (see note 1) |
| 8 | Unauthorised treatment request (`TREATMENT_REQUEST_UNAUTHORISED`) | scenario `unauthorised-request` (no authorising consultant supplied) | `2251799815007894` | **`ACTIVE` with incident `JOB_NO_RETRIES`**: `Required process variable 'decidingClinician' is missing or blank` | **FAIL, defect D-2** |

Five of the nine declared BPMN error codes now have a real run behind them:
`PAYMENT_CONFIRMATION_LOST`, `SCHEDULING_SERVICE_UNAVAILABLE` (thrown, see D-1),
`CORRESPONDENCE_SERVICE_FAILED`, `CHARGE_CALCULATION_FAILED`, `EXTERNAL_RESOURCE_UNAVAILABLE`.
Two of those five share instance `2251799815006753`, because the model recovered from all three
injected errors inside one walk of the pathway, which is itself the strongest single piece of
evidence that the boundary events are wired correctly.

### Note 1 — two of the rows are business outcomes, not BPMN errors

`PAYMENT_STATUS=DECLINED` and `DEMO_EXTERNAL_UNAVAILABLE_RESOURCES` do not throw a BPMN
error. The worker completes the job and returns a status; the exclusive gateway after the task
routes on that status. The model defines no `PAYMENT_DECLINED` error, so the earlier test
record was wrong to list "declined payment" among the error codes. Rows 6 and 7 are kept
because they are still failure branches that were exercised, but they are labelled as gateway
outcomes in `docs/03-test-record.md` §K3, not as error codes.

## Defects found by running

### D-1 — a recovered scheduling failure leaves the instance looping

When `scheduling.find-appointment-slots` throws `SCHEDULING_SERVICE_UNAVAILABLE`, the boundary
event routes to `OUT_Task_ReviewAvailability`. In `--form-fields-only` mode the reviewer picks
`RETRY`, the pathway returns to `OUT_Auto_FindSlots`, and the run turns into the loop visible in
`run-service-down-v16.log`: nineteen consecutive `OUT_Task_ReviewAvailability` completions and an
instance that never reaches an end event.

The failure injection is `ONCE`, so the scheduling worker succeeds from the second activation
onward; the loop is therefore not a fault-injection artefact. The run proves that the service
task is wrapped, that the boundary event fires, and that the reviewer task is reachable — and it
proves that nothing bounds the retry. The honest reading is: handled, but not terminated.

Not fixed in this submission. The fix is a boundary timer on the review task (or a retry counter
variable in the gateway condition), and it needs a model change plus a re-run of the eight
scenario logs, which is not something to slip in on the submission commit.

### D-2 — `TREATMENT_REQUEST_UNAUTHORISED` has a catcher but no thrower

`bpmn:error Error_TREATMENT_REQUEST_UNAUTHORISED` and its boundary event exist in the model, and
`docs/03-test-record.md` §K3 declared the code as exercised. It has never been thrown:
`TreatmentAuthoriseRequestWorker` validates `consentGiven` and, separately, requires
`decidingClinician`/`authorisingClinician` through `JobContext.requireFirst`, which raises a job
failure. With both clinician variables blank the job fails with `JOB_NO_RETRIES`, the incident is
raised on `CON_Auto_AuthoriseRequest`, and the model's boundary event is never reached.

The reason this matters beyond one test row: the model promises a business refusal ("send it back
for authorisation") and the worker delivers an incident ("stop, a human must look at this"). Both
are defensible, but they are not the same behaviour, and only one of them is wired.

Recorded as a defect. The repair is small, refuse in the worker with
`ValidationException` → BPMN error `TREATMENT_REQUEST_UNAUTHORISED` once `decidingClinician` is
present but the request is not authorised. But it changes worker behaviour after the assessed
runs, so it is documented here rather than applied.

## How to reproduce one row

```bash
# 1. stop every worker, then start exactly one with the flag from the table
cd bpm/workers
DEMO_PAYMENT_STATUS=NO_CONFIRMATION \
  java --enable-native-access=ALL-UNNAMED -jar target/hospital-external-workers-1.0.0.jar

# 2. in a second shell
cd bpm
python3 tools/run_v16.py --scenario lost-confirmation --form-fields-only --total-timeout 240

# 3. the error line to look for in the worker log
grep "BPMN ERROR" <worker log>   # code=PAYMENT_CONFIRMATION_LOST, elementId=FIN_Auto_ProcessPayment
```

The worker log lines for rows 1–5 are reproduced verbatim in
`run-failure-paths-v16.log`, which sits beside this file.
