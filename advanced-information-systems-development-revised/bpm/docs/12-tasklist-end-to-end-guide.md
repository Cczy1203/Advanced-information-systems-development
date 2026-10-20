# 12 — Driving the forms by hand in Tasklist

> Applies to the shipped **v16.0** release: one hospital pool with 3 responsibility
> lanes holding 9 team lanes, 37 Camunda Forms on 38 user tasks, and the Java
> external workers. Engine: Camunda 8 c8run on `localhost:8080`.

The point of this guide is the manual path: **a person sits in Tasklist and fills
the forms one after another**, while the driver only queues the work, waits and
keeps the record. That is the one test an automated run cannot perform — see
`docs/20-accessibility-and-the-forms.md` for what the API-driven runs do and do not
prove.

---

## 1. The two ways to drive it

| Mode | Command | Who fills the forms | Use it for |
| --- | --- | --- | --- |
| Fully automatic | `python3 tools/run_v16.py --scenario normal` | the driver calls the same REST endpoint Tasklist uses | regression, a quick end-to-end check |
| **Manual / UI** | `python3 tools/run_v16.py --scenario normal --manual-forms` | **you, in Tasklist** | the demonstration, the viva, screenshots |

In `--manual-forms` mode the driver **never** calls the completion endpoint. It
announces each open task, records whichever ones you complete in the UI, and moves
on when the scenario's tasks are covered or the timeout expires.

---

## 2. Pre-flight check (30 seconds)

```bash
# 1) the engine is up (expect gatewayVersion 8.10.0-alpha5)
curl -s http://localhost:8080/v2/topology | head -c 120

# 2) exactly one worker JVM is running - two copies steal each other's jobs
ps aux | grep hospital-external-workers | grep -v grep

# 3) open the task list
open http://localhost:8080/tasklist
```

- Start the worker from the repository:
  `cd bpm/workers && java -jar target/hospital-external-workers-1.0.0.jar`
- **Do not close either terminal.** If the worker stops, the service tasks park and
  no form ever appears.

---

## 3. One command to start

```bash
cd bpm
python3 tools/run_v16.py --scenario normal --manual-forms
```

Useful extras: `--scenario <name>` (`--help` lists the eight), `--max-steps`,
`--correlation-key`, `--form-timeout` (how long it waits for you, default 1800 s),
`--resume <processInstanceKey>`.

What you will see:

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
  97  you filled  SEC_Task_CheckPack
```

- A `YOUR TURN` block is **the form the process is blocked on** — do that one first.
- `service` lines are work the Java workers just did; there is nothing for you there.
- `you filled` means your click was seen and recorded.
- `... still waiting` is a 30-second heartbeat so you know it is alive.

---

## 4. The standard routine in the UI

Every task follows the same five steps:

1. Filter the list to **Assigned to me / Unassigned**, status **Created**.
2. Open the task, click **Assign to me**, and fill in the fields.
3. Click **Complete**; the list refreshes and the next task appears.
4. Back in the terminal, confirm the matching `you filled ...` line printed.
5. If the driver is still waiting, it is waiting on a different element — read the
   next `YOUR TURN` block rather than guessing.

There is no single right answer for most fields. The driver sets the business
variables the process needs (patient reference, amounts, priority and so on), and
the choices in each form are worded so that a sensible option is obvious.

---

## 5. How you know it worked

The run ends with a coverage summary:

```
--- coverage ---
forms covered: 37 / 37
```

`37 / 37` with no `missing forms:` line means every bound form was genuinely
completed through the interface. The run also writes a JSON report naming, per form,
the task name, the element id and the process instance key — that is what goes into
`docs/03-test-record.md` and `docs/08-test-plan.md`.

---

## 6. When something goes wrong

| Symptom | Cause | What to do |
| --- | --- | --- |
| The terminal prints `started(...)` but Tasklist stays empty | no worker running, or the worker was closed | restart the worker; keep exactly one copy |
| A scenario times out with `missing=[...]` | a form was missed in the UI | re-run that scenario: `--scenario <name> --manual-forms`; names come from `--help` |
| The task list keeps growing | earlier test instances are still ACTIVE | cancel them in Operate, or with the command below |
| An instance shows a red incident in Operate | a service task threw - often a stale worker jar | open the incident, read the stack, retry after fixing |
| The same form appears twice | a start message was published twice | run only the scenario you need; cancel the spare instance |

To find and cancel stray instances — **check the key before you cancel, it cannot be
undone**:

```bash
curl -s -X POST http://localhost:8080/v2/process-instances/search \
  -H 'Content-Type: application/json' \
  -d '{"filter":{"state":"ACTIVE"},"page":{"limit":20}}' | python3 -m json.tool | grep processInstanceKey

# only after confirming the key is the one you want to drop:
# curl -X POST http://localhost:8080/v2/process-instances/<key>/cancellation
```

---

## 7. Why the shipped model is one pool and not nine

An earlier release drew each hospital desk as its own pool, so a hand-off between
two desks was a message between two process instances. The shipped model draws the
desks as **lanes inside one hospital pool**, so those hand-offs are sequence flows
and the pathway runs as a single process instance. The reasoning and the
measurements are in `docs/17-single-pool-operational-model.md`.

Two consequences for a manual run:

- **One instance per scenario.** There is no chain of nine processes to keep alive,
  so a scenario does not depend on a message relay between pools.
- **The outside participants are drawn, not deployed.** The referring organisation,
  the patient and the four outside services appear as non-executable pools. The
  messages the workers publish are the hand-offs to them; nothing runs on their
  side, which is stated as a limitation in `docs/17` §7 and in
  `workers/README.md` ("Simplifications and known gaps").
