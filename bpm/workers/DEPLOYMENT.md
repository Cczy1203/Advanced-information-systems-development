# Deploying and running the hospital external workers

`hospital-external-workers` is the Java half of the UFCEP6-0-3 deliverable: one Camunda 8 (Zeebe)
external job worker for every service task in the BPMN collaboration, plus a single
`publish-message` dispatcher that completes every BPMN message throw event.

* **33 worker classes / 34 job type subscriptions** = 1 message dispatcher + 32 domain service tasks,
  with `pathway.find-overdue-letters` accepted as an alias of `pathway.find-overdue-clinic-letters`
  so the `PCW_Auto_FindOverdue` step is covered whichever name the model uses.
* Every service task in the model is `retries="3"`, so transient problems fail the job and let the
  engine retry; only the business conditions listed in the model's `bpmn:error` definitions are
  thrown as BPMN errors.
* Nothing here needs Spring, Docker or a database: it is a plain `main()` that talks gRPC to the
  gateway.

---

## 1. Prerequisites

| Tool | Version used | Notes |
|---|---|---|
| JDK | 25 (builds to Java 21 bytecode) | `maven.compiler.release=21`, so a JDK 21 runtime also works |
| Maven | 3.9.9 | uses `~/.m2/settings.xml` as-is |
| Camunda 8 cluster | c8run 8.10.0-alpha5 | gRPC `localhost:26500`, REST `http://localhost:8080` |

Dependencies are pinned in `pom.xml`:

* `io.camunda:zeebe-client-java:8.9.0` (gRPC client)
* `com.fasterxml.jackson.core:jackson-databind:2.21.2` (+ `jackson-core`, `jackson-dataformat-yaml`)
* `org.slf4j:slf4j-api:2.0.17`, `ch.qos.logback:logback-classic:1.5.32`

---

## 2. Build

```bash
cd workers
mvn -q clean package
```

This produces a runnable fat jar:

```
target/hospital-external-workers-1.0.0.jar          # shaded, executable
target/original-hospital-external-workers-1.0.0.jar # thin jar (dependencies not bundled)
```

The shade plugin merges `META-INF/services` (needed by gRPC/netty), appends
`META-INF/io.netty.versions.properties`, and strips signature files and `module-info.class`.

## 3. Run

Any one of:

```bash
# 1. fat jar
java -jar target/hospital-external-workers-1.0.0.jar

# 2. convenience script (builds first when the jar is missing)
./run-workers.sh
REBUILD=1 ./run-workers.sh          # force a clean rebuild

# 3. Maven
mvn -q exec:java
mvn -q exec:java -Dexec.args="--config=/tmp/demo.yaml"
```

Start up prints the effective configuration and one line per subscribed job type, so the whole
worker set can be checked in one screen:

```
10:41:01.871 INFO  u.a.u.u.h.WorkersApplication - Connected to localhost:26500 - gateway version 8.10.0-alpha5, 1 broker(s), 1 partition(s)
10:41:01.871 INFO  u.a.u.u.h.WorkersApplication - Subscribing 33 job workers:
10:41:01.880 INFO  u.a.u.u.h.WorkersApplication -   publish-message        every pool / every message throw event (...)
10:41:01.881 INFO  u.a.u.u.h.WorkersApplication -   referral.check-supporting-documents  Medical Secretaries / SEC_Auto_ValidateDocuments - validate the referral pack
...
10:41:01.884 INFO  u.a.u.u.h.WorkersApplication - 33 job workers subscribed on localhost:26500. Waiting for jobs - press Ctrl-C to stop.
```

`Ctrl-C` (SIGINT) closes every job worker and the gRPC client through a shutdown hook.

---

## 4. Configuration

`src/main/resources/application.yaml` is the template that ships inside the jar. A different file can
be layered on top of it:

```bash
java -jar target/hospital-external-workers-1.0.0.jar --config=/etc/hospital/workers.yaml
WORKERS_CONFIG=/etc/hospital/workers.yaml java -jar target/hospital-external-workers-1.0.0.jar
```

Resolution order (highest wins): **environment variable → `--config` file → classpath
`application.yaml` → built-in default.**

An environment variable name is the key path in upper case with dots and dashes replaced by
underscores.

### Camunda client

| Key | Env var | Default | Meaning |
|---|---|---|---|
| `camunda.client.zeebe.gateway-address` | `CAMUNDA_CLIENT_ZEEBE_GATEWAY_ADDRESS` (also `ZEEBE_GATEWAY_ADDRESS`) | `localhost:26500` | gRPC gateway |
| `camunda.client.zeebe.plaintext` | `CAMUNDA_CLIENT_ZEEBE_PLAINTEXT` (also `ZEEBE_PLAINTEXT`) | `true` | plaintext gRPC, no TLS |
| `camunda.client.zeebe.request-timeout-ms` | `CAMUNDA_CLIENT_ZEEBE_REQUEST_TIMEOUT_MS` | `20000` | timeout on every gRPC call |

### Workers

| Key | Env var | Default | Meaning |
|---|---|---|---|
| `workers.name-prefix` | `WORKERS_NAME_PREFIX` | `hospital-external-workers` | worker name prefix in Zeebe |
| `workers.max-jobs-active` | `WORKERS_MAX_JOBS_ACTIVE` | `32` | jobs held at once per worker |
| `workers.job-timeout-ms` | `WORKERS_JOB_TIMEOUT_MS` | `30000` | job lock duration |
| `workers.poll-interval-ms` | `WORKERS_POLL_INTERVAL_MS` | `100` | poll interval |
| `workers.execution-threads` | `WORKERS_EXECUTION_THREADS` | `4` | shared worker threads |

### Demo switches

| Key | Env var | Default | Meaning |
|---|---|---|---|
| `demo.simulated-failure.enabled` | `DEMO_SIMULATED_FAILURE_ENABLED` | `false` | master switch for failure injection |
| `demo.simulated-failure.job-types` | `DEMO_SIMULATED_FAILURE_JOB_TYPES` | `[]` | comma separated `job.type` or `job.type:ERROR_CODE` |
| `demo.simulated-failure.mode` | `DEMO_SIMULATED_FAILURE_MODE` | `always` | `always` = every activation fails; `once` = first activation fails only |
| `demo.payment.status` | `DEMO_PAYMENT_STATUS` | `APPROVED` | `APPROVED` / `DECLINED` / `DUPLICATE` / `NO_CONFIRMATION` |
| `demo.payment.status-once` | `DEMO_PAYMENT_STATUS_ONCE` | `true` | forced status applies to the first transaction only |
| `demo.payment.confirmation-lost-mode` | `DEMO_PAYMENT_CONFIRMATION_LOST_MODE` | `bpmn-error` | `bpmn-error` = throw `PAYMENT_CONFIRMATION_LOST`; `retry` = fail the job and let the engine retry |
| `demo.payment.refund-status` | `DEMO_PAYMENT_REFUND_STATUS`, `DEMO_REFUND_STATUS` | `REFUNDED` | `REFUNDED` / `REJECTED` |
| `demo.scheduling.force-no-slots` | `DEMO_SCHEDULING_FORCE_NO_SLOTS`, `DEMO_SCHEDULING_NO_SLOTS` | `false` | force `NO_SLOTS` |
| `demo.external.unavailable-resources` | `DEMO_EXTERNAL_UNAVAILABLE_RESOURCES`, `DEMO_EXTERNAL_UNAVAILABLE` | `[]` | resource names reported unavailable, e.g. `MRI,PET-CT` |
| `demo.pathway.scenario` | `DEMO_PATHWAY_SCENARIO` | `THREE_MONTHS` | `SEVEN_DAYS` / `ONE_MONTH` / `THREE_MONTHS` seeded clinic letters |
| `demo.pathway.reminder-cooldown-days` | `DEMO_PATHWAY_REMINDER_COOLDOWN_DAYS` | `0` | `0` = never remind the same letter twice |
| `demo.clock.today` | `DEMO_CLOCK_TODAY` | *(empty)* | freeze "today" (ISO date) so day counts are reproducible |
| `demo.clock.offset-days` | `DEMO_CLOCK_OFFSET_DAYS` | `0` | shift the demo clock |

Example: run with a declining payment provider and a frozen demo date.

```bash
DEMO_PAYMENT_STATUS=DECLINED DEMO_PAYMENT_STATUS_ONCE=false \
DEMO_CLOCK_TODAY=2025-06-16 \
java -jar target/hospital-external-workers-1.0.0.jar
```

### Pointing at a different cluster

**Local c8run / docker-compose (plaintext, no auth)** - the default:

```yaml
camunda:
  client:
    zeebe:
      gateway-address: localhost:26500
      plaintext: true
```

**Camunda SaaS or any TLS gateway** - turn plaintext off and use the cluster's gRPC address:

```bash
CAMUNDA_CLIENT_ZEEBE_GATEWAY_ADDRESS=<cluster-id>.<region>.zeebe.camunda.io:443 \
CAMUNDA_CLIENT_ZEEBE_PLAINTEXT=false \
java -jar target/hospital-external-workers-1.0.0.jar
```

The client will pick up the standard `ZEEBE_CLIENT_ID` / `ZEEBE_CLIENT_SECRET` OAuth credentials
from the environment for SaaS. `applyEnvironmentVariableOverrides(false)` is set, so the values in
`application.yaml` (and the `CAMUNDA_CLIENT_*` variables above) are authoritative rather than being
silently overridden by other `ZEEBE_*` names; authentication variables are still read by the client.

**Non-default REST port** (only used by the smoke-test curls, not by the workers):
`http://localhost:8080`.

---

## 5. Simulated external services

Five job types stand in for systems the hospital does not own. They are deterministic, they never
touch the network, and each has a BPMN error boundary event in the model.

| Job type | Stands in for | BPMN error | Limitation |
|---|---|---|---|
| `correspondence.dispatch-letter` | print house / digital letter provider | `CORRESPONDENCE_SERVICE_FAILED` | nothing is printed or posted; no delivery receipt, no retry of a soft bounce |
| `scheduling.find-appointment-slots` | clinic scheduling system | `SCHEDULING_SERVICE_UNAVAILABLE` | slots are synthetic and evenly spaced; no clinic diary, no clinician roster, no cap on offering the same slot twice |
| `external-resources.check-availability` | treatment / laboratory / imaging capacity | `EXTERNAL_RESOURCE_UNAVAILABLE` | capacity is decided by two rules (configured unavailable list, no weekend laboratory/imaging work) rather than a real booking system |
| `payment.process-transaction` | card payment service provider | `PAYMENT_PROVIDER_UNAVAILABLE`, `PAYMENT_CONFIRMATION_LOST` | no real money moves; no card data is accepted or returned; a declined payment is not retried by the provider itself |
| `payment.process-refund` | payment service provider refunds | `PAYMENT_PROVIDER_UNAVAILABLE` | as above; no partial-refund settlement, no chargeback handling |

Everything else is hospital-internal bookkeeping, but several workers still keep state so that a
retry cannot double-book:

| Worker | Idempotency mechanism |
|---|---|
| `booking.create-appointment` | deterministic `appointmentRef` + in-memory store keyed on patient + reference; a repeat returns the existing appointment with `duplicateSuppressed = true` |
| `treatment.create-appointment-series` | series stored against `treatmentBookingRef`; a retry returns the same cycle references |
| `treatment.confirm-appointments` | confirmations keyed on the hash of the provisional reference set; confirming twice cannot change the count |
| `finance.check-duplicate-payment` | a `paymentReference` already recorded for the same patient is reported as a duplicate, and the resolved reference becomes an investigation reference |
| `pathway.suppress-duplicate-reminders` | reminded letters are remembered; re-running suppresses them (`suppressedReminderCount`) |
| `letter.record-reminder` | reminder count is incremented against the letter, never reset |
| `audit.record-*`, all reference generation | references are SHA-256 hashes of their inputs, so retries reuse the same audit/reference identifier |

**Store limitation:** all of this lives in one `HospitalStore` in the worker JVM. It is lost when the
process stops, and it is not shared between two worker instances. A production implementation would
put these tables in the PAS database (with unique constraints), and the worker would query it
instead.

---

## 6. Demonstrating the failure branches

### Business errors (BPMN error boundary events)

```bash
DEMO_SIMULATED_FAILURE_ENABLED=true \
DEMO_SIMULATED_FAILURE_JOB_TYPES=correspondence.dispatch-letter,scheduling.find-appointment-slots \
DEMO_SIMULATED_FAILURE_MODE=always \
java -jar target/hospital-external-workers-1.0.0.jar
```

Each listed job type throws its canonical BPMN error, so the model's boundary event is taken. A job
type can be pinned to a different code with `job.type:ERROR_CODE`, e.g.
`DEMO_SIMULATED_FAILURE_JOB_TYPES=referral.check-supporting-documents:REFERRAL_PACK_UNREADABLE`.
Any job type can be forced, not only the simulated services. With no code configured for a
non-service job type the job is failed instead (no boundary event exists for it), and the engine
retry policy applies.

`mode=once` (rather than `always`) is the interesting setting: the first activation fails, the BPMN
error boundary is taken, and if the same job type comes round again an attempt succeeds - which
demonstrates the `retries="3"` retry policy at the same time.

### Retry policy without a boundary event

Force a validation failure, e.g. a refund larger than the amount paid:

```
finance.prepare-refund: "Refund of 500.0 exceeds the 100.0 that was actually taken ... "
```

The job is failed with `remainingRetries` 2, 1, 0 and then becomes an incident, with the message
naming the offending variable. No BPMN error is thrown, because the model defines no boundary event
for that step.

### Payment outcomes

| `DEMO_PAYMENT_STATUS` | Result |
|---|---|
| `APPROVED` (default) | `paymentStatus = APPROVED`, `paidAmount = chargeAmount`, the transaction is recorded for duplicate detection |
| `DECLINED` | `paymentStatus = DECLINED`, `paidAmount = 0`, model routes to `TRT_Task_ReviewDeclinedPayment` |
| `DUPLICATE` | `paymentStatus = DUPLICATE`, model routes to `finance.check-duplicate-payment` |
| `NO_CONFIRMATION` | `PAYMENT_CONFIRMATION_LOST` is thrown, model routes to Finance for investigation (`TRT_Bnd_ConfirmationLost`). Set `DEMO_PAYMENT_CONFIRMATION_LOST_MODE=retry` to fail the job instead, which is the behaviour to use with a model whose caller waits on a timer |

### Overdue clinic letters (7 day / 1 month / 3 month bands)

```bash
DEMO_CLOCK_TODAY=2025-06-16 DEMO_PATHWAY_SCENARIO=THREE_MONTHS java -jar target/hospital-external-workers-1.0.0.jar
```

The in-memory letter store is seeded relative to the demo clock, so `outstandingLetters` contains
all three bands at once and `letterOverdueDays` (the worst case, which the model's gateway escalates
on) is 120. `SEVEN_DAYS` gives 9, `ONE_MONTH` gives 45. Passing `consultationDate` in the process
variables, or a `clinicLetters` list, overrides the seeded data.

---

## 7. Verifying a deployment

```bash
# is the cluster reachable?
curl -s http://localhost:8080/v2/topology | python3 -m json.tool

# deploy the model
curl -s -X POST http://localhost:8080/v2/deployments -F "resources=@../model/UFCEP6-0-3_Hospital_Patient_Pathway.bpmn"

# start an instance
curl -s -X POST http://localhost:8080/v2/process-instances \
  -H 'Content-Type: application/json' \
  -d '{"processDefinitionId":"medical-secretaries","variables":{"patientRef":"DEMO-1","referralSpeciality":"Cardiology","supportingDocuments":["referral-letter","ecg","echo-report","blood-tests"]}}'

# what did the workers write back?
curl -s -X POST http://localhost:8080/v2/variables/search \
  -H 'Content-Type: application/json' \
  -d '{"filter":{"processInstanceKey":"<key>"}}'

# anything stuck?
curl -s -X POST http://localhost:8080/v2/incidents/search \
  -H 'Content-Type: application/json' -d '{"filter":{}}'
```

Operate: <http://localhost:8080/operate> - Tasklist: <http://localhost:8080/tasklist>.

---

## 8. Model-side prerequisites for these workers

The workers were written against the BPMN collaboration and were verified end to end on a throwaway
model (see the notes in `README.md`). Two model details matter to the dispatcher and are worth
double-checking whenever the model is regenerated:

0. **`PCW_Auto_FindOverdue` job type name.** The worker subscribes to both
   `pathway.find-overdue-clinic-letters` and `pathway.find-overdue-letters`, so either name in the
   model is served. Pick one in the model for clarity.
1. **Every message throw event must map a `correlationKey` process variable.** The dispatcher
   publishes `client.newPublishMessageCommand().messageName(<header>).correlationKey(<variable>)`.
   The `<zeebe:subscription correlationKey="..."/>` on the `bpmn:message` element only tells the
   *catching* side what to correlate on; the throwing task must put the value into a
   `correlationKey` variable, for example
   `<zeebe:input source="=patientRef + &quot;-referral-review&quot;" target="correlationKey" />`.
   Without it the job fails with a message naming `correlationKey` (three times, then an incident) -
   deliberately a failed job rather than a BPMN error, because a broken hand-off has no boundary
   event in the model.
2. **`patientRef` (and `appointmentOutcome` before `booking.record-appointment-outcome`) must be on
   the process.** The audit workers fail, by design, when `patientRef` is blank; other workers fall
   back to the business reference they carry (`referralRef`, `treatmentBookingRef`, `enquiryRef`,
   `letterRef`). A blank `appointmentOutcome` fails that job naming the variable.
