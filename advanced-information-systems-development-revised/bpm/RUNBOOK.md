# RUNBOOK — bring the system up and run the pathway end to end


> **Citations to files that are not in this tree.** An audit found 39 paths cited across 19 documents that no longer exist: the fourteen-pool model, the v1/v2 generators and the drawing scripts that went with them, and the Sprint 0 Node scaffold. Nothing was lost: all of it is in git history, and every citation is listed with what replaced it in [docs/18-cited-files-no-longer-present.md](18-cited-files-no-longer-present.md).

Applies to **v16.0** (model `model/UFCEP6-0-3_Hospital_Patient_Pathway_v16.bpmn`,
one executable hospital process with 3 responsibility lanes holding 9 team lanes,
6 drawn outside participants, 37 Camunda Forms, Java external workers). Everything
here is run from a macOS shell.

Eight scenarios cover the pathway: the normal path, a declined treatment, an
incomplete referral pack, no appointment slot, a refund, no refund, compensation,
and an enquiry through the second start event. Every user task in those scenarios
has a form: 37 form files across 38 user tasks, so one form serves two equivalent
tasks.

| Mode                                      | Who fills the forms               | Command                                                     |
| ----------------------------------------- | --------------------------------- | ----------------------------------------------------------- |
| **Full auto** (regression)                | the driver calls the Tasklist API | `python3 tools/run_v16.py --all`                            |
| **Manual / UI** (demonstration, evidence) | **you click in Tasklist**         | `python3 tools/run_v16.py --scenario normal --manual-forms` |

---

## 0. Prerequisites

| Item                 | Where it is expected                                                                         |
| -------------------- | -------------------------------------------------------------------------------------------- |
| c8run 8.10.0-alpha5  | `~/Desktop/camunda8-getting-started-bundle-8.10.0-alpha5-darwin-aarch64/c8run-8.10.0-alpha5` |
| This project         | the repository root; the commands below are run from its `bpm/` directory                    |
| Java                 | JDK 21 or 25 (`java -version`)                                                               |
| Python 3 + curl      | used by `tools/deploy.sh` and `tools/run_v16.py`                                              |
| External workers JAR | `workers/target/hospital-external-workers-1.0.0.jar`, built with `mvn -gs maven-settings.xml -s maven-settings.xml -o package` |

Set the bundle path once per shell so the commands below can be pasted as they are:

```bash
export C8RUN=~/Desktop/camunda8-getting-started-bundle-8.10.0-alpha5-darwin-aarch64/c8run-8.10.0-alpha5
export PROJ=~/Desktop/Advanced-information-systems-development-main/bpm
```

---

## 1. Start Camunda 8 (c8run)

```bash
cd "$C8RUN" && ./c8run start
```

- First start takes ~1–2 minutes. Leave this terminal open for the whole session.
- Endpoints once it is up: Tasklist <http://localhost:8080/tasklist>, Operate
  <http://localhost:8080/operate>, REST `/v2/*` on `localhost:8080`, gRPC gateway on `26500`.
- Verify from a second terminal:

```bash
curl -s http://localhost:8080/v2/topology | head -c 120
# -> {"brokers":[{"nodeId":0,...,"version":"8.10.0-alpha5"}],"clusterId":...}
```

- Shut it down with `./c8run stop` (or Ctrl-C in its terminal).

## 2. Start the external workers — one copy only

```bash
cd "$PROJ/workers" && ./run-workers.sh
```

- First run builds the JAR with Maven (`REBUILD=1 ./run-workers.sh` to force a clean build).
- Check that exactly **one** worker process is alive:

```bash
ps aux | grep hospital-external-workers | grep -v grep   # expect a single PID
```

> More than one copy is not fatal, but they compete for the same job types and make
> the logs unreadable. Kill the extras before a demonstration.

## 3. Deploy the model and the 37 forms

```bash
cd "$PROJ" && ./tools/deploy.sh
```

Expected output: `deployment key: ...`, then 9 `process ...` lines and 37 `form ...` lines.

> Deploy the BPMN **on its own, once**. Two files carrying the same process ids in
> one request are rejected with `Duplicated process id`
> (in Modeler: use *Deploy current diagram*, never *Deploy all diagrams* while two
> versions of the model are open).

---

## 4. Run the scenarios

### 4.1 Full auto (regression run)

```bash
cd "$PROJ"
python3 tools/run_v16.py --scenario normal
```

One scenario, no human input. The driver creates the instance from the model's none
start event (or publishes the start message for `--scenario enquiry`), leaves every
service task to the Java workers, and completes each user task through the same REST
call Tasklist makes.

Useful extras: `--scenario <name>` (14 in all; `--help` lists them), `--max-steps`,
`--correlation-key`, `--form-timeout`.

> **The `auto_driver.py` and `demo_scenario.py` commands in older notes belong to the
> v14.0 fourteen-pool model.** They drive nine separate pool processes, so they cannot
> drive the shipped v16.0 single-pool model. The v16.0 driver is `run_v16.py`.

### 4.2 Manual / UI mode — you fill every form, everything else is automatic

```bash
cd "$PROJ"
python3 tools/run_v16.py --scenario normal --manual-forms
```

The driver **never** completes a user task in this mode, and it never asks you to do
anything a person would not do in the real system. Everything else stays automatic:

| Element | Who does it |
| --- | --- |
| Service tasks (48) | **the Java workers**, exactly as in 4.1; the driver only reports them |
| Messages the model waits for | **the driver**, on each catch event and event-based gateway |
| User tasks (38) | **you**, in Tasklist |

It announces each form once and waits for you:

```
scenario: normal
  created from the none start event  (correlationKey=P-1001)
  instance 2251799814812345

   1  service     SEC_Auto_ValidateDocuments
   1  YOUR TURN  Check the referral pack against the document checklist
        element : SEC_Task_CheckPack
        form    : check-referral-pack
        open    : http://localhost:8080/tasklist
        fill the form there and complete the task; waiting up to 1800 s
        ... still waiting for SEC_Task_CheckPack (30 s)
  97  you filled  SEC_Task_CheckPack
```

How to read it:

| Line | Meaning |
| --- | --- |
| `YOUR TURN` | the form the process is blocked on; go and fill this one |
| `element` / `form` | the user task id in the model and the `.form` file bound to it |
| `service` | a service task a worker just completed; nothing for you to do |
| `message in` | the driver fed a message the model was waiting for |
| `you filled` | your click was seen; the process has moved on |
| `... still waiting` | a 30-second heartbeat so you know it is alive |

`--form-timeout` (default 1800 s) is the time allowed for **one** form; `--max-steps`
does not apply in this mode, so you can take as long as you like. The driver exits 0
when the instance completes, 4 if a form times out, and 3 on an incident.

### 4.3 Picking up a case that is already running

If a case is part-way through, for example one parked at *Waiting for the missing
information* because the referral pack failed the checklist, do not start a new one.
Attach to it:

```bash
python3 tools/run_v16.py --resume <processInstanceKey> --manual-forms
```

`--resume` reads the instance's `patientRef` back off the engine and publishes the
messages under the correlation key that instance is actually waiting on, so you do
not have to know or retype it. It then behaves exactly as 4.2: the workers do the
service tasks, you fill the forms.

The instance key is on the Operate instance page (**Process Instance Key**), or in
`Operate → Processes → <definition> → Instances`.

### 4.4 The Tasklist routine — same five clicks for every task

1. Open <http://localhost:8080/tasklist>.
2. Filter state **Created**, and **Unassigned** (or *Assigned to me*).
3. Open the task → **Assign to me** → fill the fields. The business variables
   (patient reference, amounts, priorities) are already seeded by the driver or the
   workers, and most fields offer selectable options, so pick a sensible value.
4. Click **Complete**. The next task appears.
5. Glance at the terminal: the matching `you filled <element>` line must appear.
   If it does not, you completed a different task than the one announced under
   `YOUR TURN`; keep going with that one.

---

### 4.5 The failure paths — four minutes, four commands

Failure handling is assessed, and a demonstration that only shows the happy path shows
half of it. These are the shortest paths that put a defect boundary in front of the
audience. The full record, including the two that fail, is
`screenshots/v16/failure-path-runs.md`; the worker-side log lines are in
`run-failure-paths-v16.log` beside it.

| What the audience sees | Worker start | Scenario |
|---|---|---|
| Payment taken, confirmation never came, investigation opened | `DEMO_PAYMENT_STATUS=NO_CONFIRMATION` | `lost-confirmation` |
| Correspondence provider rejects the job, letter re-routed | `DEMO_SIMULATED_FAILURE_ENABLED=true`<br>`DEMO_SIMULATED_FAILURE_MODE=once`<br>`DEMO_SIMULATED_FAILURE_JOB_TYPES=correspondence.dispatch-letter:CORRESPONDENCE_SERVICE_FAILED` | `normal` |
| Charge cannot be calculated, manual charge raised | same three, with `DEMO_SIMULATED_FAILURE_JOB_TYPES=finance.calculate-charge:CHARGE_CALCULATION_FAILED` | `normal` |
| No capacity at the source, booking released cleanly | `DEMO_EXTERNAL_UNAVAILABLE_RESOURCES=Laboratory` | `no-capacity` |
| Payment refused by the provider (gateway outcome) | `DEMO_PAYMENT_STATUS=DECLINED` | `declined-payment` |

Each row needs its own worker restart, because the flag is read at start-up:

```bash
# shell 1 — exactly one worker, with the flag for the row
cd bpm/workers
DEMO_PAYMENT_STATUS=NO_CONFIRMATION \
  java --enable-native-access=ALL-UNNAMED -jar target/hospital-external-workers-1.0.0.jar

# shell 2 — drive the case to its terminal state
cd bpm
python3 tools/run_v16.py --scenario lost-confirmation --form-fields-only \
  --total-timeout 240
```

`mode=once` matters: the task carries `retries="3"`, so the audience sees the engine
retry and *then* the boundary event take over, which is the point being demonstrated.
With `mode=always` every activation fails and the retry is not visible.

Then `grep "BPMN ERROR" <worker log>` and show the line: it names the code and the
element that caught it. Two further rows are in the record rather than in the script:
`SCHEDULING_SERVICE_UNAVAILABLE` (the instance does not finish, defect D-1) and
`TREATMENT_REQUEST_UNAUTHORISED` (the worker raises an incident instead of the declared
error, defect D-2). Both are worth saying out loud in the demonstration: the group found
them by running the paths, and `docs/03-test-record.md` §K5.8–K5.9 records them.

## 5. Reading the result

```
--- coverage ---
forms covered: 36 / 36
```

- `37 / 37` with no `missing forms:` line = every bound form was really driven (and,
  in manual mode, really filled by hand).
- The JSON report lists, per form: task name, element id, pool, process instance key
  and completion time. That is ready to paste into `docs/03-test-record.md` and `docs/08-test-plan.md`.
- Exit code is `0` when nothing is missing, `1` when forms are missing, `2` when the
  engine is unreachable.

---

## 6. Troubleshooting

| Symptom                                                                  | Cause                                                                                                    | Fix                                                                                                                 |
| ------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| `Engine not reachable on http://localhost:8080`                          | c8run not running                                                                                        | go back to §1, check `/v2/topology`                                                                                 |
| Terminal prints `started(...)` but Tasklist stays empty                  | workers are down, so the service task never reaches the user task                                        | restart the workers (§2)                                                                                            |
| `409 no none start event` on `POST /v2/process-instances`                | the process has no none start event, so it cannot be started bare                                        | v16.0 does have one (`Start_Referral`), so this should not appear. If it does, you are publishing a start *message* for a process that only has message start events. `run_v16.py` handles both cases                                       |
| Publishing `referral.received` starts nothing                            | v16.0 removed that message: the pathway opens at a none start event                                      | start a case by creating an instance (`run_v16.py`, or `POST /v2/process-instances` with the case variables). Only `enquiry.received` is still a start message                        |
| A downstream pool never starts                                           | the hand-off message was published with a `correlationKey`, which a message *start* event does not match | publish start messages **without** `correlationKey` (put the patient reference in `variables`)                      |
| Duplicate tasks / two instances of the same pool                         | a start message was published twice, or an earlier test instance is still ACTIVE                         | clean up with §7, then re-run                                                                                       |
| Instance shows a red incident in Operate                                 | a service task threw (usually a worker/JAR mismatch)                                                     | open the incident, read the stack, fix, then **Retry** in Operate                                                   |
| Only some scenarios pass (`missing=[...]`)                               | those forms were never completed                                                                         | re-run just those: `python3 tools/run_v16.py --scenario <name> --manual-forms` (names from `--help`)                  |

---

## 7. Housekeeping — a clean starting point before a demonstration

List what is still running (read-only):

```bash
curl -s -X POST http://localhost:8080/v2/process-instances/search \
  -H 'Content-Type: application/json' \
  -d '{"filter":{"state":"ACTIVE"},"page":{"limit":100}}' \
  | python3 -c "import sys,json,collections; d=json.load(sys.stdin); \
c=collections.Counter(i['processDefinitionId'] for i in d['items']); \
print('ACTIVE:', len(d['items']), '| incidents:', sum(1 for i in d['items'] if i.get('hasIncident'))); \
[print('  %-28s %d' % (k,v)) for k,v in c.most_common()]"
```

Cancel one instance runs only if you have checked the key. Cancellation cannot be undone:

```bash
curl -X POST http://localhost:8080/v2/process-instances/<processInstanceKey>/cancellation
```

---

## 8. Why the driver works the way it does

- The shipped model is **one hospital process**, not nine. The nine teams are lanes
  inside that one pool, so a hand-off between them is a sequence flow, not a message
  between two process instances. The six outside participants are drawn in the same
  file as non-executable pools, reached by the message throws the workers publish.
- The driver covers **scenarios**, not forms. One scenario follows one route through
  the model; the route decides which user tasks it meets, and therefore which forms
  it needs. The eight scenarios between them exercise the main path, a declined
  treatment, an incomplete pack, no availability, a refund decision either way,
  compensation and an enquiry.
- In manual mode the driver keeps the messages flowing and
  queues every branch in turn, while Tasklist collects the tasks in one list for you
  to work through. A pool that finishes its path simply ends. That is the design,
  not a broken chain.

*Companion guide for the manual path, with the UI routine step by step: `docs/12-tasklist-end-to-end-guide.md`.*
