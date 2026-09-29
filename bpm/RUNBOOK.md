# RUNBOOK — bring the system up and run all 36 forms end to end

Applies to **v14.0** (model `model/UFCEP6-0-3_Hospital_Patient_Pathway_v14.bpmn`,
9 executable hospital processes + 5 documented outside participants, 36 Camunda
Forms, Java external workers). Everything here is run from a macOS shell.

Two ways to cover the 36 forms:

| Mode                                      | Who fills the forms               | Command                                                     |
| ----------------------------------------- | --------------------------------- | ----------------------------------------------------------- |
| **Full auto** (regression)                | the driver calls the Tasklist API | `python3 auto_driver.py --all`                              |
| **Manual / UI** (demonstration, evidence) | **you click in Tasklist**         | `python3 auto_driver.py --all --manual-forms --timeout 600` |

---

## 0. Prerequisites

| Item                 | Where it is expected                                                                         |
| -------------------- | -------------------------------------------------------------------------------------------- |
| c8run 8.10.0-alpha5  | `~/Desktop/camunda8-getting-started-bundle-8.10.0-alpha5-darwin-aarch64/c8run-8.10.0-alpha5` |
| This project         | `~/Desktop/Advanced-information-systems-development-main/bpm`                                                                            |
| Java                 | JDK 21 or 25 (`java -version`)                                                               |
| Python 3 + curl      | used by `tools/deploy.sh` and `tools/auto_driver.py`                                         |
| External workers JAR | `workers/target/hospital-external-workers-1.0.0.jar` (built on first `run-workers.sh`)       |

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

## 3. Deploy the model and the 36 forms

```bash
cd "$PROJ" && ./tools/deploy.sh
```

Expected output: `deployment key: ...`, then 9 `process ...` lines and 36 `form ...` lines.

> Deploy the BPMN **on its own, once**. Two files carrying the same process ids in
> one request are rejected with `Duplicated process id`
> (in Modeler: use *Deploy current diagram*, never *Deploy all diagrams* while two
> versions of the model are open).

---

## 4. Run all 36 forms

### 4.1 Full auto (regression run)

```bash
cd "$PROJ/tools"
python3 auto_driver.py --all --report driver_report.json
```

- 34 scenarios, roughly 80 seconds, no human input.
- The driver starts each pool and replays the pool-to-pool messages, then completes
  every user task through the API. It can also play any job the Java worker has not
  claimed, but only with `--with-jobs` and only when the workers are stopped.
- Useful extras: `--list` (scenarios + form names), `--scenario <id>` (repeatable),
  `--timeout <seconds>`, `--report <path>`.

### 4.2 Manual / UI mode — you fill every form in Tasklist

```bash
cd "$PROJ/tools"
python3 auto_driver.py --all --manual-forms --timeout 600
```

The driver **never** completes a user task in this mode. It announces the task and
waits for a human, then records what the human did.

```
MANUAL MODE: user tasks stay open. Finish them in Camunda Tasklist (http://localhost:8080/tasklist) - the driver waits and records each one.
== SEC-pack  (medical-secretaries)
  >> Tasklist task: Check referral pack against the document checklist form=check-referral-pack pool=medical-secretaries
  form DONE check-referral-pack                        (Tasklist)
  -> PASS  gained=['check-referral-pack'] missing=[]  (17 rounds, 14.1s)
```

How to read it:

| Line                                  | Meaning                                                                       |
| ------------------------------------- | ----------------------------------------------------------------------------- |
| `>> ... form=<id> pool=<pool>`        | **the form this scenario is waiting for, so do this one first**               |
| a line without `>>`                   | another pool's task, queued for a later scenario; completing it early is fine |
| `form DONE <id>`                      | your click was recorded, the coverage list gained one form                    |
| `-> PASS`                             | every form of that scenario is done; the driver moves on immediately          |
| `-> PARTIAL / FAIL ... missing=[...]` | the timeout expired before someone finished those forms                       |

`--timeout 600` gives each scenario 10 minutes of human time (the default in manual
mode; overridable). The driver only ever waits. You can work at any pace, and it
advances the moment the scenario's own forms are complete.

### 4.3 The Tasklist routine — same five clicks for every task

1. Open <http://localhost:8080/tasklist>.
2. Filter state **Created**, and **Unassigned** (or *Assigned to me*).
3. Open the task → **Assign to me** → fill the fields. The business variables
   (patient reference, amounts, priorities) are already seeded by the driver, and
   most fields offer selectable options, so pick a sensible value.
4. Click **Complete**. The next task appears.
5. Glance at the terminal: the corresponding `form DONE ...` line must appear.
   If it does not, you completed a different pool's task. Keep going with the `>>` one.

---

## 5. Reading the result

```
--- coverage ---
forms covered: 36 / 36
```

- `36 / 36` with no `missing forms:` line = all 36 forms were really driven (and, in
  manual mode, really filled by hand).
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
| `409 no none start event` / `400 unsupported element type 'START_EVENT'` | pool has several start events, so it cannot be started bare                                              | the driver already starts such pools at a user task via `startInstructions`; do the same if you trigger one by hand |
| A downstream pool never starts                                           | the hand-off message was published with a `correlationKey`, which a message *start* event does not match | publish start messages **without** `correlationKey` (put the patient reference in `variables`)                      |
| Duplicate tasks / two instances of the same pool                         | a start message was published twice, or an earlier test instance is still ACTIVE                         | clean up with §7, then re-run                                                                                       |
| Instance shows a red incident in Operate                                 | a service task threw (usually a worker/JAR mismatch)                                                     | open the incident, read the stack, fix, then **Retry** in Operate                                                   |
| Only some scenarios pass (`missing=[...]`)                               | those forms were never completed                                                                         | re-run just those: `python3 auto_driver.py --scenario SEC-pack --manual-forms` (ids from `--list`)                  |

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

## 8. Why "all 36 in one go" works the way it does

- The nine hospital processes are **nine independent instances**. They are joined by
  message hand-offs, not by one giant flow. The outside participants are documented
  in the same file: four suppliers, each with the single step it performs, and the
  patient, who owns the referral entry point.
- One run of the driver covers 34 **scenarios**, not 34 forms. 36 forms sit on
  different branches (main path, declined referral, funding failure, escalation,
  enquiry, chemotherapy), and a scenario deliberately blanks or un-sets variables to
  force a branch. All branches together = all 36 forms.
- In manual mode "all 36 in one go" means the driver keeps the messages flowing and
  queues every branch in turn, while Tasklist collects the tasks in one list for you
  to work through. A pool that finishes its path simply ends. That is the design,
  not a broken chain.

*Chinese companion version of this guide: `docs/12-tasklist-end-to-end-guide.md`.*
