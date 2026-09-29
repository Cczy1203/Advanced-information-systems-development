# Evidence index

Every image and log in this folder, what it shows, and which release captured it.
This folder is the demonstration evidence for the portfolio; the checks that can
be re-run at any time are in `static-checks-v14.txt` (current file) and
`static-checks-v7.0.txt` (the previous one).

> **The v14 runs are the `*-v14.log` files — eight of them.** They were captured
> against the shipped file (`model/UFCEP6-0-3_Hospital_Patient_Pathway_v14.bpmn`,
> SHA-256 `7bd812ad...`) on c8run 8.10.0-alpha5 and cover everything the model
> carries: the happy path, the unreadable pack, declined payment, confirmation
> lost, both letter-escalation rungs, compensation, and all six outside
> participants — every one with `incidents: none`. **The images are still v7.0's**:
> there are no Operate, Tasklist or Modeler screenshots of the white-box release.
> Read the images as evidence for the nine hospital processes, which v14 did not
> change.

## Re-runnable right now

| File | What it is |
|---|---|
| `static-checks-v14.txt` | **The current file's static evidence**: the build's own consistency checks, bpmn-moddle parse, `bpmnlint` (0 errors, 31 warnings), `tools/verify_preservation.py` (70/70) and `tools/analyse_layout.py` (0 overlaps, 0 diagonals, 0 lines through a shape, 95 crossings), each with its command line, plus the SHA-256 (`7bd812ad...`) of the model they were run against - and section 8 is the engine record: the deployment, the measured batch-ceiling rejection, the six outside participants completing, and the two integrations firing. |
| `static-checks-v7.0.txt` | The output of the same four gates run against v7.0: `tools/analyse_layout.py`, `tools/verify_preservation.py`, `tools/validate_model.js` (bpmn-moddle with the Zeebe descriptor) and `bpmnlint` under the project's own `bpmnlint:recommended` config. It carries the SHA-256 of the file it was run against, so it can be re-verified rather than trusted. |
| `run-happy-path-v14.log` | **v14**: the normal path driven end to end on the shipped file, exit 0, `incidents: none` at all three checkpoints |
| `run-exception-path-v14.log` | **v14**: the unreadable referral pack, caught by the boundary event and routed into the missing-information loop, `incidents: none` |
| `run-external-participants-v14.log` | **v14**: all six outside participants started and driven to `COMPLETED` with no incident, and both integrations fired (referrer to Medical Secretaries, patient to Consultants). Produced by `tools/check_external_participants.py` |
| `run-declined-payment-v14.log` | **v14**: the provider declines, the treatment team works the review task, the retry is approved, `incidents: none` |
| `run-confirmation-lost-v14.log` | **v14**: the provider never confirms — Finance investigates and a clinician authorises urgent treatment, `incidents: none` |
| `run-overdue-escalation-v14.log` | **v14**: the letter ladder to higher management (short-timer variant), `incidents: none` |
| `run-escalation-manager-v14.log` | **v14**: the same ladder to the Administrative Manager (`DEMO_LETTER_OVERDUE_DAYS=45`), `incidents: none` |
| `run-compensation-v14.log` | **v14**: capacity never arrives, the retry reaches its cap and **the compensation handler runs** (`TRT_Comp_ReleaseSeries`), `incidents: none` |
| `run-happy-path.log` | The normal path driven end to end on the shipped file, `incidents: none` at every stage, 8 forms submitted |
| `run-exception-path.log` | The unreadable-pack path on the shipped file: the boundary event catches `REFERRAL_PACK_UNREADABLE` and the case joins the missing-information loop instead of reaching a clinician |
| `run-declined-payment.log` | The declined-payment branch driven on the shipped file: the provider declines, the treatment team works the review task, the retry is approved, 9 forms submitted, `incidents: none` |
| `run-overdue-escalation.log` | The escalation ladder, higher-management rung: the weekly review and `ADM_Task_ReferHigher` both driven, the Administrative Management instance reaches `COMPLETED`, `incidents: none` |
| `run-escalation-manager.log` | The same ladder on the middle rung (`DEMO_LETTER_OVERDUE_DAYS=45`): `ADM_Task_ContactConsultant` driven, instance `COMPLETED` |
| `run-compensation.log` | `external-resources.check-availability` forced to fail: the capacity retry counts to its cap and the **compensation handler runs** (`TRT_Comp_ReleaseSeries`), `incidents: none` |

All four were run against the SHA-256 recorded in `static-checks-v7.0.txt`, and all
four end `incidents: none`. A normal run now ends with **no active elements at
all**: earlier logs listed leftovers because the harness was completing tasks
that belonged to abandoned instances from previous sessions (DEF-19). The
demo now scopes its evidence twice: to the newest deployed version of each pool
process, and to the instances the run itself creates. The shared engine keeps the
history of every earlier session, so without that the log would list leftovers
from models that are not in this folder.

## Captured from a running system

| File | What it shows | Release |
|---|---|---|
| `operate-dashboard.png` | Operate: *"Your processes are healthy — There are no incidents on any instances"* across 21 running instances | v2.1 |
| `operate-processes.png` | Operate: the deployed process definitions | v2.1 |
| `operate-instance-completed.png` | A completed instance with its executed steps and real variables | v2.1 |
| `operate-instance-diagram.png` | The instance diagram for a running instance | v2.1 |
| `operate-instance-medical-secretaries.png` | The Medical Secretaries instance, showing the hand-off | v2.1 |
| `tasklist-open-tasks.png` | Tasklist: the open user tasks the model produced | v2.1 |
| `tasklist-camunda-form.png` | A Camunda Form rendered open in Tasklist, captured on a clean engine against the shipped model — the evidence DEF-17 was raised for | v7.0 |
| `camunda-forms-rendered.png` | The form-js render census — `TOTAL=36 FAILED=0`, the renderer Tasklist uses | v2.1 |
| `camunda-modeler-v2.1-status-bar.png` | Camunda Modeler 5.51.0 status bar on platform Camunda 8.10 (alpha) | v2.1 |
| `camunda-modeler-v2.1-model.png` | The collaboration open in the Modeler | v2.1 |
| `camunda-modeler-v2.1-open.png` | The same, at 100% zoom | v2.1 |
| `camunda-modeler-v2-status-bar.png` | The Modeler status bar for the v2.0 increment | v2.0 |
| `camunda-modeler-v2-model.png` | The v2.0 collaboration in the Modeler | v2.0 |
| `camunda-modeler-form.png` | A form open in the Modeler during the v1.0 round | v1.0 |

## Currency of this evidence

`static-checks-v14.txt`, the three `*-v14.log` runs and everything in `diagram/`
were produced against the current file
(`model/UFCEP6-0-3_Hospital_Patient_Pathway_v14.bpmn`, SHA-256 `7bd812ad...`) and
are current. `static-checks-v7.0.txt` describes the previous file. Everything
else in this folder - the Operate, Tasklist, Modeler images and the v7.0 run logs
- was captured against v7.0 and is evidence for the nine hospital processes,
which v14 did not change.

The screenshots above were captured from the running system during the v1.0,
v2.0 and v2.1 rounds. They are kept because they are the only captured record of
the deployment, the Tasklist and the two driven paths, and because
`docs/10-sprint-reviews-and-feedback.md` reports those reviews against them.
They show the v2.1 drawing, not the v7.0 drawing: the three routing changes in
this release are drawing-only, and the engine, the forms, the workers and the
paths they demonstrate are unchanged. The v7.0 drawing itself is in `../diagram/`.

One citation is known to be broken: `docs/03-test-record.md` §F2 cites
`screenshots/tasklist-camunda-form.png`, which does not exist. It is recorded as
DEF-17 in `docs/08-test-plan.md` §9.

**Note for the next capture.** The Tasklist and Operate form login answered on
this run and `tasklist-open-tasks.png` and `operate-dashboard.png` were both
recaptured against the current deployment, so the authentication problem that
blocked DEF-17 is no longer reproducing. `tasklist-camunda-form.png` can now be
taken and the defect closed.
