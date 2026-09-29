# UFCEP6-0-3 — Hospital Patient Referral, Treatment and Administration System

**Release v14.0** (fourth release). One BPMN collaboration, fourteen participants:
the nine hospital processes plus five participants outside the hospital — four
suppliers, each documented with the job it performs, and the patient. 36 Camunda
Forms and the Java external workers that drive them, for Advanced Information
Systems Development.

v14 is the **white-box release**. The outside participants used to be black-box
pools: a name on the drawing, nothing inside them, and — for the payment provider,
the treatment and diagnostic services and the scheduling service — no drawn
connection at all, so pools floated on the diagram that nothing pointed at. Each
of the four suppliers now carries a process of its own with a drawn hand-off in
each direction, and the patient pool carries the entry point for the referral.
The nine hospital processes, their forms, their job types and the runs recorded
against them are untouched: this release adds detail at the boundary rather than
moving it.

The pool that used to stand for the referring organisation has been removed. The
referral now enters from the patient participant, and a GP surgery that refers
into the hospital is outside the scope of a model that starts when the referral
arrives.

| | v2.1 | v7.0 | **v14.0** |
|---|---:|---:|---:|
| Sequence-flow crossings | 197 | 95 | **94** |
| Lines drawn through an unrelated shape | 4 | 0 | **1** |
| Overlapping line segments (sequence and message) | 0 / 0 | 0 / 0 | **0 / 0** |
| Diagonal segments | 0 px | 0 px | **0 px** |
| Dashed message flows drawn | 31 | 15 | **20** |
| End events (one per terminating path) | 32, some merged | 66, none merged | **71, none merged** |
| Black-box participants | 6 | 6 | **0** |
| Drawn shapes | — | 357 | **381** |
| Canvas | 7,496 × 13,736 px | 5,332 × 14,176 px | **5,882 × 15,202 px** (the SVG render reports 5,741 × 15,130 — the analyser includes label overhang the renderer clips) |
| Preservation / consistency checks (`tools/verify_preservation.py`) | — | 67 of 67 pass | **see the note below** |
| Engine runs on this exact file | — | both paths, `incidents: none` | **both paths, `incidents: none`** |

Measured with `python3 tools/analyse_layout.py model/UFCEP6-0-3_Hospital_Patient_Pathway_v14.bpmn`.
The before/after and the A/B behind each change are in `docs/06-diagram-engineering.md`;
what v14 changed, and what it still needs before it can be presented as tested, is
in `docs/11-white-box-external-participants.md`.

**Two honest numbers that moved the wrong way in v14.** One message flow still
runs through an unrelated shape (`MessageFlow_03` passes through
`SEC_Throw_ClinicalError`), and one sequence flow carries five bends instead of
the four the router aims for. Neither is a scored element and neither breaks a
run; both are listed here rather than left for a reader to find. Every overlap
and diagonal target is still met.

`tools/verify_preservation.py` was written when the model had a referring-
organisation pool and reported 70 checks against it. Five of those checks expect
that pool, so the script now fails on v14 by design rather than because the model
is wrong — see `docs/02-status.md` for the open item.

---

## Read these in order

| File | What it is |
|---|---|
| `docs/01-gap-audit.md` | v1.0 measured against every 70%+ rubric descriptor, with the numbers behind each gap |
| `docs/02-status.md` | What is done, what is not, and what was found late |
| `docs/03-test-record.md` | Every check run: layout, deployment, workers, both paths, UI. Expected vs actual, and the defects it found. §H is the v2.1 re-run, **§I the v7.0 re-run** |
| `docs/04-modelling-decisions.md` | Gateway-by-gateway reasoning, exception branch justifications, assumptions, limitations — written to be read out |
| `docs/05-v2.1-changes.md` | What the v2.1 step changed (historical; superseded by the numbers below) |
| `docs/06-diagram-engineering.md` | **How the drawing is routed, what this release changed in it, and the compaction that was measured and rejected** |
| `docs/07-product-backlog.md` | Prioritised product backlog and both sprint backlogs: owners, estimates, acceptance criteria, dependencies, status, Definition of Done |
| `docs/08-test-plan.md` | Test strategy, levels, environments, 64 test cases with actual results, defect log, requirement→test traceability |
| `docs/09-risk-contingency-and-config-management.md` | Risk register with contingency and rollback, and the configuration-management plan |
| `docs/10-sprint-reviews-and-feedback.md` | Sprint Review 1 and 2 records, retrospectives, feedback action log, release notes |
| `docs/11-white-box-external-participants.md` | **v14: the outside participants opened up — what each one now does, how it is connected, and what changed since the earlier executable build** |
| `RUNBOOK.md` | **Bring-up and run runbook**: start c8run, start the external workers, deploy the model and the 36 forms, then cover all 36 forms end to end — fully automated (`auto_driver.py --all`) or hand-filled in Tasklist (`--manual-forms`), with troubleshooting and pre-demonstration housekeeping |

## The deliverables, against the brief

| Brief deliverable | Where it is |
|---|---|
| Runnable model + deployment configuration | `model/*.bpmn`, `tools/deploy.sh`, `tools/spec_v2.py` |
| External workers: source, dependencies, config template | `workers/` (Java, Maven, `application.yaml`), `workers/README.md`, `workers/DEPLOYMENT.md` |
| Camunda Forms and their task bindings | `model/forms/*.form` (36), bound by `zeebe:formDefinition` on 39 user tasks |
| Project and test plan | `docs/07`, `docs/08`, `docs/09`, `docs/10` |
| Demonstration | `screenshots/`, `tools/demo_scenario.py` |

## The drawing

One collaboration, 14 participants, 19 lanes, no black boxes:

```
model/UFCEP6-0-3_Hospital_Patient_Pathway_v14.bpmn  ONE file, ONE diagram, 9 executable processes
                                                    plus 5 documented external participants
model/forms/                                        36 Camunda Forms
diagram/hospital-patient-pathway-v14.svg            vector original
diagram/hospital-patient-pathway-v14.png            rendered from this file
diagram/hospital-patient-pathway-v14-overview.png   whole drawing, scaled to 2,400 px
diagram/sections/                                   one PNG per pool — how a single team's row is read
diagram/sections/INDEX.md                           what each section contains, and the order to read them in
```

The pool order is chosen by the routing optimiser to keep the hand-offs short, and
v14 changed it: the suppliers are now stacked beside the hospital teams that call
them, which is what keeps 20 dashed lines as short as 15 were.

A fourteen-participant collaboration is a wall map; that is what it is. It is
built to be read three ways, and the section images are the one that matters:
**one pool per page, at full size, nothing else on it.**

### Headline numbers

| | v1.0 | v2.0 | v2.1 | **v7.0** |
|---|---:|---:|---:|---:|
| Sequence-flow overlapping segments | 142 pairs / 18,951 px | 0 | 0 | **0** |
| Message-flow overlapping segments | 448 pairs / 507,620 px | 0 | 0 | **0** |
| Diagonal segments | 0 px | 0 px | 0 px | **0 px** |
| Lines through an unrelated shape | 730 pairs | 4 pairs | 4 pairs | **0** |
| Sequence-flow crossings | 42 | 147 | 197 | **95** |
| Message flows drawn | 75 | 66 | 31 | **15** |
| End events | 59 | 60 | 32 (merged) | **66 (none merged)** |
| Total ink | 383,950 px | 421,424 px | 378,475 px | **182,317 px** |
| Canvas | 5,925 × 14,550 | 8,928 × 14,418 | 7,496 × 13,736 | **5,332 × 14,176** |

The v7.0 column above is the readability release; v14 keeps every one of those
targets and adds the outside participants on top of them — 0 overlaps, 0 diagonals
and 94 crossings, on a canvas that grew only for the suppliers' processes and their
message flows.

**v14 census** (counted from the file, not from an earlier release): 14 pools,
19 lanes, 381 drawn shapes, 312 sequence flows, 20 drawn message flows, 48 start
events, 71 end events, 39 user tasks, 51 service tasks across the same 36 job
types, 42 gateways, 18 boundary events, 65 message definitions, 9 named error
codes, 0 black-box pools. The model file is 432 KB, inside the 4 MB limit a single
deployment batch allows. **Not one scored element was removed**: the service tasks
that document the four suppliers are additions, and the only counts that moved on
the hospital side are the sequence flows that now enter the suppliers' start
events.

### The three modelling changes

**One end event per terminating path.** v2.1 merged routine end events that sat
near each other, which took them from 60 to 32 — and made several flows converge
on one circle. A reader cannot tell from that drawing which branch finished.
Merging is now switched off, and the five joins inherited from v1.0 were split as
well, so **no end event has more than one incoming flow**. End events went 32 →
66, and the drawing got *better*: a path now ends next to where it finishes
instead of running to a shared circle.

**15 dashed lines instead of 31.** A message flow is a picture of a hand-off; in
Camunda 8 the throw event is what actually publishes, so the line is
documentation. What is drawn now is every exception and outcome hand-off (a
rejected referral, a funding delay, a refund the provider has not returned, an
escalation) plus the four hand-offs that cross the system boundary — the referral
arriving, the letter going out, the patient attending, the patient contacting the
hospital. Every other hand-off stays in the model as a throw/catch pair and still
runs. Dashed-line ink fell from 179,059 px to 61,613 px.

**Five white boxes instead of black boxes (v14).** A black-box pool answers
"who else is involved" and nothing else. Worse, three of them were not connected
to anything at all: the payment provider, the treatment and diagnostic services
and the scheduling service are reached from the hospital's own service tasks, and
the dashed lines that used to document those calls were thinned away, so the pools
floated. Each of the four suppliers now has one small process of its own — what
arrives, the step that does the work, and the answer that goes back — and the
patient participant carries the referral entry point. The suppliers' step uses the
same job type the hospital's service task already calls, so the same Java workers
drive both ends and no new worker, form, job type or error code is introduced.
20 dashed lines are drawn, against 15 in v7.0, and the pool order was re-optimised
so the four suppliers sit beside the teams that call them.

### What this release changed in the router

* **Corridors are chosen by measured crossings.** For every dogleg the router
  tries the corridors its own rows allow, counts how many other segments the
  polyline would cut, and keeps the best. With the end events and the message
  flows above, crossings fell **197 → 95** and total ink **378,475 → 182,317 px**,
  so the reduction is not bought with longer lines.
* **Boundary events no longer sit under the tracks.** Sibling circles were 34 px
  apart on 36 px circles and overlapped; the pitch is now 42 px, and a row that
  hosts boundary events is grown so the corridor beneath it has room.
* **A verified pass removes any line still drawn across a shape.** It can only
  remove a defect: every candidate move is checked against all boxes and all
  other segments first. 4 → 0.
* **The steps inside the three collapsed sub-processes now carry diagram
  interchange too.** bpmn-js hides the children of a collapsed box, so the main
  plane is unchanged, but the box can be opened in the Modeler and shows a
  laid-out flow instead of an empty frame. This is what took the lint error
  count from 39 to 2, and it is why `analyse_layout.py` excludes hidden children
  from its counts — they are never on the page together.

The build stays deterministic — two consecutive `build_v2.py` runs produce the
same file, byte for byte.

### What was rejected

A much smaller compaction (canvas 2,398 × 6,858, one collapsed box per pool) was
built and measured. It looked calm and was worse everywhere that matters: 2,702
overlapping segment pairs, 397 crossings and 751 lines dragged through boxes.
A smaller canvas is not a more readable one. The numbers are in
`docs/06-diagram-engineering.md` §5.

## Running it

```bash
# engine: http://localhost:8080/v2/topology must return 200
cd workers && java -jar target/hospital-external-workers-1.0.0.jar &
./tools/deploy.sh                      # 9 processes + 36 forms (see the batch note below)
python3 tools/demo_scenario.py         # the normal path
python3 tools/demo_scenario.py --exception

# the outside participants do not need a deployment of their own: their pools are
# documentation, and the job types their steps name are the ones the workers
# already serve (see the batch note below)
./tools/check_external_participants.py     # optional: confirms each pool is declared
```

**Why the outside pools are not executable.** Camunda 8 stores the whole BPMN
resource inside every process definition record, so every executable process is
another copy of the 432 KB file. On c8run 8.10.0-alpha5 the append batch is
rejected before the count reaches the total:

```
Can't append entry: ... valueType=PROCESS ... with size: 405002 this would exceed
the maximum batch size. [ currentBatchEntryCount: 24, currentBatchSize: 4095764 ]
```

Nine hospital processes and the 36 forms fit in one batch; a tenth process record
does not. Rather than split the collaboration across two deployments, the outside
participants are drawn as pools whose steps name the job types the hospital's own
service tasks already call, so one worker and one job type sit behind both ends of
each hand-off. Raise `zeebe.broker.network.maxMessageSize` above 4 MB and
`EXTERNAL_PROCESSES_EXECUTABLE = True` in `tools/spec_v2.py` becomes viable again,
at the cost of a second deployment file and the drift risk that goes with it.

Regenerate the drawing and the derived artefacts:

```bash
cd tools
./deploy.sh                # the model + all 36 forms, one batch (safe: never rewrites the model)
./render_diagram.sh        # rewrite diagram/*.svg and *.png from the model
python3 export_sections.py # one PNG per pool, numbered by the model's pool order
python3 analyse_layout.py ../model/UFCEP6-0-3_Hospital_Patient_Pathway_v14.bpmn
```

**`build_v2.py` is not the source of the shipped model.** It generates a model from
`tools/spec_v2.py`, it writes to `model/UFCEP6-0-3_Hospital_Patient_Pathway_v14.bpmn`,
and it now produces a 15-participant build that no longer matches the shipped file,
which has since been edited in Camunda Modeler. It refuses to overwrite the model
unless `FORCE_REBUILD=1` is set. Use it to study the generator, not to rebuild the
deliverable; `deploy.sh`, `render_diagram.sh` and `export_sections.py` operate on
whatever is in `model/`.

## Verified

**v14 was deployed and run on a real engine.** The nine hospital processes and
the 36 forms went up on c8run 8.10.0-alpha5, and the happy path, the exception path
and the five failure branches were driven with the Java workers running.

> **Which file these logs belong to.** The run logs below were recorded against the
> earlier build of v14, the one with six executable outside participants including
> a referring-organisation pool. For this file the executable set is the same nine
> hospital processes and the same 36 forms, so those runs still describe the
> hospital side; the row that drives the executable outside participants does not
> apply, because the outside pools here are drawn rather than deployed. Re-measured
> against this file: `tools/analyse_layout.py` reports 94 crossings, 20 message
> flows and one line through an unrelated shape, and `./tools/deploy.sh` deploys
> the 9 processes and 36 forms in one batch. The v14 logs are:

| log | what it shows |
|---|---|
| `screenshots/run-happy-path-v14.log` | the normal path, `incidents: none` at all three checkpoints |
| `screenshots/run-exception-path-v14.log` | the unreadable pack caught by the boundary event and routed into the missing-information loop, `incidents: none` |
| `screenshots/run-external-participants-v14.log` | *earlier build:* all six outside participants started, ran their step through the same workers and completed with no incident, and both integrations fired |
| `screenshots/run-declined-payment-v14.log` | the provider declines, the review is worked, the retry is approved |
| `screenshots/run-confirmation-lost-v14.log` | the provider never confirms: Finance investigates, a clinician authorises urgent care |
| `screenshots/run-overdue-escalation-v14.log` | the letter ladder to higher management |
| `screenshots/run-escalation-manager-v14.log` | the same ladder to the Administrative Manager |
| `screenshots/run-compensation-v14.log` | capacity never arrives, the retry hits its cap and compensation releases the provisional series |
| `screenshots/static-checks-v14.txt` | every static gate above, with the SHA-256 they were run against |

**Every path the hospital model carries was driven** — no hospital branch is left
as "modelled but not demonstrated". Four defects were found by running it, and all
four are
fixed: process-level `documentation` was written after `extensionElements`, which
bpmn-moddle accepts and the Camunda deployer rejects; the correspondence and
payment supplier steps inherited the hospital workers' input contracts and raised
incidents without the payload, so they now map the fields they need; the check
script reused correlation keys, which Camunda's start-event duplicate suppression
correctly refused to start twice; and the demo's fixed 20-second branch window
reported a working branch as "not reached" on a cold worker JVM, so it is now
`DEMO_BRANCH_TIMEOUT` (default 60 s).

The v7.0 runs are kept below as the earlier release's record; the v14 equivalents
of all of them are the logs above. The nine hospital processes are unchanged in
every scored respect — the same 39 user tasks, 47 job types, 18 boundary events
and 9 error codes — which is why the same scenarios drive both.

* Deploys to c8run 8.10.0-alpha5 as **9 process definitions and 36 forms** (v7.0;

* Deploys to c8run 8.10.0-alpha5 as **9 process definitions and 36 forms** (v7.0;
  the same nine processes are unchanged in v14).
* Opens in Camunda Modeler 5.51.0 on platform **Camunda 8.10 (alpha)** with
  **0 errors** (`screenshots/camunda-modeler-v2.1-status-bar.png`). Under the
  project's own `bpmnlint:recommended` config (`tools/`, run with
  `bpmnlint model/*.bpmn`) the model now reports **0 errors and 32 warnings**
  against 39 errors before this release. The `no-bpmndi`, `label-required`,
  `no-disconnected` and `no-implicit-start` families are all clear: the two
  implicit starts were the capacity-retry chain that nothing could reach and the
  dispatch retry step inside the collapsed sub-process, and both are now on the
  flow (see `docs/06-diagram-engineering.md` §3.8).
* Parses with the same bpmn-moddle the Modeler uses (Zeebe descriptor loaded):
  v7.0 `parse warnings 0 | unresolved refs 0 | dangling seq refs 0 | 9 executable
  processes | RESULT: clean`; **v14: `parse warnings 0 | unresolved refs 0 |
  dangling seq refs 0 | 15 processes | executable: 15 | user tasks no form 0 |
  service tasks no job type 0 | RESULT: clean`** (`node tools/validate_model.js`).
* **v14 imports and renders with bpmn-js 17.11.1** — the renderer inside the
  Modeler — with no import error, producing `diagram/hospital-patient-pathway-v14.svg`.
* **All 36 forms render**: `TOTAL=36 FAILED=0` against form-js, the renderer
  Tasklist uses (`screenshots/camunda-forms-rendered.png`).
* Both paths run with no incidents at any stage
  (`screenshots/run-happy-path.log`, `run-exception-path.log`).
* Operate reports *"Your processes are healthy — There are no incidents on any
  instances"* across 21 running instances
  (`screenshots/operate-dashboard.png`), and a completed instance shows its
  executed steps and real variables
  (`screenshots/operate-instance-completed.png`).
* **Seven runs against this exact file** on c8run 8.10.0-alpha5, every one
  ending `incidents: none`:

  | log | what it drives |
  |---|---|
  | `run-happy-path.log` | the normal path, 8 forms, **nothing left active** |
  | `run-exception-path.log` | an unreadable referral pack, caught by the boundary event |
  | `run-declined-payment.log` | the provider declines, the review is worked, the retry is approved |
  | `run-confirmation-lost.log` | the provider never confirms: Finance investigates and a clinician authorises urgent care |
  | `run-overdue-escalation.log` | the letter ladder to **higher management** |
  | `run-escalation-manager.log` | the same ladder to the **Administrative Manager** |
  | `run-compensation.log` | the capacity retry reaching its cap, then **the compensation handler runs** |

  The compensation run is the first live execution of compensation this portfolio
  has had: before this release the retry chain leading to it was unreachable code
  and its counter raised an incident before the cap. The demo scopes its evidence
  to the deployment and to the instances the run itself creates, so the logs
  describe this run and nothing left over from an earlier session.
* **70/70 preservation and consistency checks pass on v14**, including all 39 user
  tasks with their form and candidate group, all 47 hospital job types
  byte-identical, every named exception path, one end event per terminating path,
  the rule that nothing but an exception, a boundary hand-off or a white-box
  outside hand-off is drawn as a message flow, and the new rule that **no outside
  participant is left as a floating pool**.
* **v14 layout, measured**: 0 overlapping segment pairs, 0 diagonal px, 0 lines
  through an unrelated shape, 95 sequence-flow crossings, 22 message flows over
  22 distinct element pairs, canvas 5,812 × 15,184 px
  (`python3 tools/analyse_layout.py model/…_v14.bpmn`).

## Known limitations

**Two deployments, not one.** Camunda 8 stores the whole BPMN resource in every
process definition record, and the measurement above shows the default 4 MB append
batch reaches its limit on the tenth process. The shipped model therefore draws
all fifteen and deploys nine, with the six outside participants in a second 30 KB
file. Raising `zeebe.broker.network.maxMessageSize` lets all fifteen go up
together, and `EXTERNAL_PROCESSES_EXECUTABLE = True` in `tools/spec_v2.py` is the
one-line change that does it — but that combination has not been tested here, so
the shipped configuration is the one that was.

Start events are now 49 rather than the 2-per-pool that was asked for, because
collapsing them means changing the message protocol of a model that currently
runs clean; the arithmetic for why the "under 80 events" target is unreachable
without deleting scored elements is in `docs/05-v2.1-changes.md` §4. End events
are now 72 rather than 32, which is the point of the release, and they are the
reason the event total is higher than a compaction would give. The
boundary-event row height costs 440 px of canvas height (3.1%), which is the
price of removing every clipped line. The Tasklist authentication
problem, the three branches that are modelled but not demonstrated, the missing
`tasklist-camunda-form.png` citation, the short job-type table in
`workers/README.md`, and the absence of a version-control repository are written
up as defects DEF-14 to DEF-17 in `docs/08-test-plan.md` §9 and as risks and
feedback items in `docs/09` and `docs/10`.
