# Test record — v2.0, v2.1 and v7.0

What was tested, what was expected, what actually happened, and what was fixed as
a result. Machine: local c8run **8.10.0-alpha5** (`GET /v2/topology` → 200),
Camunda Modeler 5.51.0, JDK 25, Maven 3.9.9.

> **Where the current file stands.** Sections A–H were run against v2.0/v2.1,
> section I against v7.0 (`model/UFCEP6-0-3_Hospital_Patient_Pathway_v13.bpmn`),
> and **section J against v14, the shipped file**, which was deployed and driven
> on c8run 8.10.0-alpha5. Two rows below are superseded for v14: the deployment is
> nine processes plus a second file for the six outside participants rather than
> one file of nine, and the drawn message flows are 22 rather than 15. The five
> exception-branch runs in section I have not been repeated on v14 — the hospital
> processes are unchanged, but see section J3.

Section H covers the v2.1 re-run. Everything before it is the v2.0 round, which
v2.1 inherited unchanged.

## A. Layout checks — `tools/analyse_layout.py`

Run after every rebuild. The build is not accepted until the first two rows are
zero.

| # | Test | Expected | v1.0 | v2.0 | v2.1 | Pass |
|---|---|---|---|---|---|---|
| A1 | Sequence-flow segments overlapping or parallel within 6 px | 0 | 142 pairs / 18,951 px | 0 pairs / 0 px | **0 pairs / 0 px** | yes |
| A2 | Message-flow segments overlapping or parallel within 6 px | 0 | 448 pairs / 507,620 px | 0 pairs / 0 px | **0 pairs / 0 px** | yes |
| A3 | Diagonal segments | 0 | 0 px | 0 px | **0 px** | yes |
| A4 | Lines running through a shape they are not connected to | 0 | 730 pairs | 4 pairs | 4 pairs | **no** |
| A5 | Bends per sequence flow | ≤ 4 | mean 0.7, max 4 | mean 0.9, max 4 | mean 1.1, max 4 | yes |
| A6 | Pools separated by a routing channel | yes | 60 px, no channel | 88–113 px | 104 px | yes |
| A7 | Lanes present where a pool covers several desks | yes | 0 | 20 across 8 pools | 14 across 6 pools | yes |
| A8 | Repetitive administration contained | yes | 0 subprocesses | 3 collapsed subprocesses | 3 collapsed subprocesses | yes |

A4 is the one outstanding item: 4 flows still clip a boundary event sitting next
to the one they belong to. They are cosmetic — a few pixels at the edge of a
36 px circle — and were left rather than shifting the boundary events further,
which would have detached them from the host edge. v2.1 did not make this worse:
still 4, now out of 311 sequence flows.

**Crossings** went 42 (v1.0) → 147 (v2.0) → **197 (v2.1)**. The v2.1 rise is the
measured cost of merging 28 routine end events, and it was confirmed by A/B
rather than assumed: same model with the merge switched off gives 147 crossings
and 60 end events. See `05-v2.1-changes.md` §4.

## B. Structural defects found and fixed while testing

These were all found by running the model, not by reading it.

| # | Symptom | Cause | Fix |
|---|---|---|---|
| B1 | `JOB_NO_RETRIES` incident on the first message throw | Camunda 8 publishes a message from a job worker, and the worker needs the correlation key as a process variable | The builder now writes a `correlationKey` input mapping onto every throw event |
| B2 | Incident at `CON_GW_ConsentGiven`: *Can't compare `"true"` with `true`* | Yes/No radios submit the **text** `"true"`; ten conditions compared against a boolean, giving a FEEL null | All ten conditions now compare against `"true"`, and `build.py` refuses a model that mixes the two |
| B3 | `booking.record-appointment-outcome` failed | It ran before the form that captures the outcome | Task order swapped |
| B4 | `SUB_CallHandling_Contact` forked: two tasks active at once | A node inside the collapsed subprocess had two unconditional outgoing flows, so both fired | An exclusive gateway added inside the subprocess with a condition and a default |
| B5 | Lines drawn as long diagonals | Same-row links used port offsets, tilting a 300 px run by 7 px | Straight runs now take a single level |
| B6 | Every flow out of a boundary event routed to the far-left channel | Boundary events inherited `col = 0` from the port; their host's grid cell was applied after routing had been planned | Boundary events inherit their host's cell during the row phase |
| B7 | Message risers landing on top of each other | All pools share a column grid, so channel 5 in one pool sat at the same x as channel 5 in another | Message flows get their own half of every channel, allocated globally per column |
| B8 | Riser lookup collapsing | One message has two risers, which can share a column, so keying the table by message index merged them | The lookup key identifies the segment, not just the message |
| B9 | Two new elements drawn on top of existing ones | Compensation handlers and the retry chain were given grid cells already in use | Cells remapped, and `build_v2.py` now refuses a model where two elements share a cell |
| B10 | Message lines running behind the note boxes | Notes sat at the foot of each pool, in the path of the risers | Notes moved into one panel below the collaboration |
| B11 | Compensating for a booking that was never made | Compensation handlers were attached before the confirm step in one place | Handlers attached to the activities that actually commit the booking |

## C. Deployment

| # | Test | Expected | Actual |
|---|---|---|---|
| C1 | Deploy model + 36 forms to c8run | accepted, no errors | **9 process definitions, 36 forms** |
| C2 | Re-deploy after every change | accepted | accepted, currently v3 |
| C3 | 4 MB append batch | within limit | 397 KB resource × 9 processes — inside the limit, but this is the ceiling that forced the external suppliers to become black-box pools |

## D. Path runs

Both driven by `tools/demo_scenario.py`, which fills in each form over the REST
API exactly as a person would in Tasklist.

### D1 — Normal path (`screenshots/run-happy-path.log`)

Referral message → Medical Secretaries document check → Consultant decision
(accept) → Outpatient Bookings slot choice → Call Handling telephone contact →
attendance and consent → authorised treatment request → Finance funding decision
→ payment → treatment confirmation → clinic letter drafted and processed.

**Expected:** every step reached, no incidents.
**Actual:** all eleven steps reached, `incidents: none` at the end of each stage.
Four pools exchanged messages successfully (`medical-secretaries`, `consultants`,
`outpatient-bookings`, `call-handling`, then `treatment-bookings` and
`finance-team`).

### D2 — Exception path (`screenshots/run-exception-path.log`)

`--exception` sends `["referral-letter", "corrupt-scan"]` instead of a complete
pack.

**Expected:** `referral.check-supporting-documents` throws
`REFERRAL_PACK_UNREADABLE`, the boundary event catches it, and the case leaves the
main line rather than reaching a clinician.
**Actual:** exactly that, with `incidents: none` — the BPMN error was caught, not
escalated. In v2.0 the branch joins the missing-information loop
(`SEC_EGW_InfoRequest`) rather than ending in a bare end event, which is the
change the gap audit called for.

### D3 — Not run

- The payment-declined and payment-confirmation-lost branches were not driven
  end to end.
- The compensation handlers were not triggered in a live run.
- The three-month letter escalation was not driven.

## E. Workers

| # | Test | Expected | Actual |
|---|---|---|---|
| E1 | `mvn -q -o clean package` | BUILD SUCCESS | success, 29 MB fat jar |
| E2 | Start up | one subscription per job type | **37 subscriptions** on `localhost:26500` |
| E3 | New v2.0 job types resolve | — | `treatment.release-series`, `treatment.release-cycle-booking`, `treatment.record-capacity-retry` all registered |
| E4 | Jobs completed during D1 and D2 | no incidents | no incidents in either run |

## F. UI evidence

Captured through headless Chrome driving the real webapps, logging in as `demo`.

| # | Screenshot | What it shows | Result |
|---|---|---|---|
| F1 | `screenshots/tasklist-open-tasks.png` | Tasklist open tasks | "Check referral pack against the document checklist — Medical Secretaries" and "Attempt to telephone the patient — Call Handling Team". Our v2.0 tasks, grouped under the right pool names |
| F2 | `screenshots/tasklist-camunda-form.png` | A claimed v2.0 task | Task opens, candidate group shown as `medical-secretaries`, assignable and claimable |
| F3 | `screenshots/operate-processes.png` | Operate dashboard | "Medical Secretaries — 2 instances", "Call Handling Team — 1 instance", and **"Your processes are healthy — There are no incidents on any instances."** |

### F4 — every form renders: 36 of 36, no failures

The Task tab in Tasklist stayed empty, so the forms were checked directly with
`@bpmn-io/form-js` — the same renderer Tasklist uses — in headless Chrome:

```
TOTAL=36 FAILED=0
```

`screenshots/camunda-forms-rendered.png` shows six of them drawn as real widgets:
labels, required markers, descriptions, date pickers, radio groups, checklists
and select boxes.

**Getting there found a genuine defect in the forms.**

The first run reported:

```
render error: form field of type <date> not supported
```

17 fields across the 36 forms used `"type": "date"`. **Camunda Forms has no
`date` field type.** The supported types are textfield, textarea, number,
checkbox, checklist, radio, select, taglist, datetime, group, dynamiclist, table,
text, image, iframe, html, separator, spacer and button — a date-only field is a
`datetime` field with `subtype: "date"`. Every form containing a date was
therefore unrenderable, which is what left the Tasklist pane blank.

Fixed in `tools/forms_spec.py`; the build now emits `datetime` with a subtype and
the field-type census is clean:

```
textfield 69  radio 35  textarea 47  select 25  number 17
datetime 19  checkbox 12  checklist 6      (no "date")
```

This is the single most valuable thing the test round found. It would have cost
the whole Camunda Forms mark.

A second, smaller defect surfaced at the same time: `build_v2.py` imported
`spec_v2` before `forms_spec`, and `spec_v2` puts the v1.0 tools directory on
`sys.path` to port the model — so the v1.0 `forms_spec.py` was being loaded and
the fix silently did not reach the generated files. Import order corrected.

### F5 — Tasklist still cannot display them, and that part is environmental

Tasklist requests `/v2/authentication/me` and gets **401**, including when the
request carries basic credentials, so it cannot fetch the schema to draw:

```
no auth   : 401
basic auth: 401
```

Tasklist's web session is not accepted by the orchestration API in this local
c8run setup. That is a configuration matter, not a model one — and with F4
proving all 36 forms render, the Forms deliverable no longer depends on it.

## G. Still to test

- Open the file in Camunda Modeler and confirm it reports zero problems. It has
  been deployed through the API and rendered with bpmn-js, but not opened by hand
  in the Modeler since the v2.0 changes.
- The compensation, payment-failure and three-month escalation branches.
- The form rendering in Tasklist, once authentication is sorted out (F4).

## H. v2.1 re-run

v2.1 only changes the drawing, so the risk was that the thinning had quietly
broken a hand-off. Everything below was re-run against the rebuilt file.

### H1 — Preservation, by parsing

`python3 tools/verify_preservation.py` compares v2.0 and v2.1 directly.

```
62 checks, 62 passed, 0 failed
```

It asserts the 15 participant names, all 39 user tasks with their
`zeebe:formDefinition` and `zeebe:assignmentDefinition`, all 47 service tasks with
their job types byte-identical, all four gateway types, nine named boundary
events, nine error codes, the 7-day and weekly chase timers, the four-rung letter
escalation chain, and the absence of Camunda 7 attributes in both files. The full
table is in `05-v2.1-changes.md` §3.

### H2 — Deployment

| # | Test | Expected | Actual |
|---|---|---|---|
| H2a | Deploy rebuilt model + 36 forms | accepted | **9 process definitions at v17, 36 forms at v18** |
| H2b | Workers rebuilt and started | 37 subscriptions | **37 subscriptions on `localhost:26500`** |

### H3 — Both paths re-run

| # | Test | Expected | Actual |
|---|---|---|---|
| H3a | `demo_scenario.py` (normal) | every step reached, no incidents | **all steps reached, `incidents: none`** |
| H3b | `demo_scenario.py --exception` | `REFERRAL_PACK_UNREADABLE` caught by the boundary event, case joins the missing-information loop | **exactly that, `incidents: none`** |

Logs: `screenshots/run-happy-path.log`, `screenshots/run-exception-path.log`.

The message-flow thinning is safe at run time precisely because Camunda 8 does
not read message flows: the hand-off is the throw event's
`<zeebe:taskDefinition type="publish-message">`. Both runs completing with zero
incidents is the evidence that removing 35 drawn dashed lines removed only
drawing.

### H4 — UI evidence, re-captured

| # | Screenshot | What it shows |
|---|---|---|
| H4a | `screenshots/operate-dashboard.png` | **21 running instances, 0 with incident**, "Your processes are healthy" |
| H4b | `screenshots/operate-processes.png` | Instance list: `Medical Secretaries` v17, `Call Handling Team` v17 |
| H4c | `screenshots/operate-instance-completed.png` | A completed Medical Secretaries instance (started 14:18:40, ended 14:18:46) with the Instance History showing the executed steps, and the Variables tab listing the real run variables — `adminChecksCarriedOut`, `approvingClinician`, `authorizingClinician`, `chargeAmount`, `appointmentDate` |
| H4d | `screenshots/tasklist-open-tasks.png` | Tasklist open tasks: "Attempt to telephone the patient — Call Handling Team", "Provide treatment decision information — Hospital Patient Administration System" |

H4c is the useful one: it is a real completed instance with the actual executed
path and the actual variables, not a dashboard summary.

Note that Operate's instance list also shows `Team A process` and `Hospital
Patient Administration System`. Those are **not ours** — they are leftovers from
the c8run bundled demo still sitting in the same engine. Neither name appears in
any file in this project.

### H5 — Camunda Modeler and diagram export

| # | Test | Expected | Actual |
|---|---|---|---|
| H5a | Open the model in Camunda Modeler 5.51.0 | no parse error, right platform | opened on **Camunda 8.10 (alpha)**, target **Local C8Run** |
| H5b | Status bar error count | 0 | **0 errors** (`screenshots/camunda-modeler-v2.1-status-bar.png`) |
| H5c | Status bar warning count | — | 30 warnings, all one rule: `no-bpmndi` on the collapsed subprocess steps. **Superseded in R3**: DI is now written for those steps and the warning family is gone — see §I2b |
| H5d | `node tools/validate_model.js` | 0 warnings, 0 unresolved refs | **0 warnings, 0 unresolved refs, 0 dangling flows, 0 user tasks without a form, 0 user tasks without a candidate group, 0 service tasks without a job type** |
| H5e | `tools/render_diagram.sh` | SVG + high-res PNG, no import errors | **SVG 7,484 x 14,028, PNG 2.1 MB** |
| H5f | `tools/export_sections.py` | one crop per pool | 15 section crops refreshed |

H5c is the one thing worth reading twice. The 30 warnings are not modelling
mistakes — running the same lint rule set the Modeler uses shows all 30 are
`no-bpmndi`, raised against the steps inside the three collapsed sub-processes.
Drawing those boxes open clears all 30 and costs 17 lines through an unrelated
shape, which was judged the worse trade. The full breakdown is in
`05-v2.1-changes.md` §4.

H5d is the strongest form of the "no errors" claim: it parses with the same
bpmn-moddle the Modeler uses, with the Zeebe descriptor loaded so that
`zeebe:formDefinition` and `zeebe:assignmentDefinition` are understood rather
than treated as unknown elements.

### H6 — Known gaps after v2.1

| # | Gap | Detail |
|---|---|---|
| H6a | Start events still 43 | Target was ≤2 per pool. Needs a message-protocol change; see `05-v2.1-changes.md` §4 |
| H6b | Crossings 197 | Up from 147. **Closed in R3**: 94 — see §I |
| H6c | 4 lines clip a boundary event | Unchanged from v2.0. **Closed in R3**: 0 — the sibling boundary events were 34 px apart on 36 px circles — see §I |
| H6d | Sub-process boxes stay closed | Drawing them open measured 21 lines through a shape against 4; the boxes stay closed on the main plane, but their steps now carry DI so they open correctly in the Modeler — see §I2b |
| H6e | Three exception branches still not driven live | Payment declined, payment confirmation lost, 3-month escalation |

---

## I. R3 (v7.0) re-run — the drawing

The third release changed routing only. Nothing scored was added, removed or
re-pointed: `tools/verify_preservation.py` now answers 67 parsed checks, and
`tools/validate_model.js` still reports the same result as §H5.

`python3 tools/analyse_layout.py model/UFCEP6-0-3_Hospital_Patient_Pathway_v2.bpmn`

| # | Test | Expected | v2.0 | v2.1 | **R3 (v7.0)** | Pass |
|---|---|---|---|---|---|---|
| I1 | Sequence-flow segments overlapping or parallel within 6 px | 0 | 0 pairs / 0 px | 0 pairs / 0 px | **0 pairs / 0 px** | yes |
| I2 | Message-flow segments overlapping or parallel within 6 px | 0 | 0 pairs / 0 px | 0 pairs / 0 px | **0 pairs / 0 px** | yes |
| I3 | Diagonal segments | 0 | 0 px | 0 px | **0 px** | yes |
| I4 | Lines running through a shape they are not connected to | 0 | 4 pairs | 4 pairs | **0 pairs** | yes |
| I5 | Sequence-flow crossings | minimise | 147 | 197 | **95** | yes — −52% |
| I6 | Bends per sequence flow (mean / max) | low | 1.1 / 4 | 1.1 / 4 | **0.9 / 5** | yes — fewer bends on average |
| I7 | Total ink drawn | low | 421,424 px | 378,475 px | **182,317 px** | yes — −52% |
| I8 | Canvas | — | 8,928 × 14,418 | 7,496 × 13,736 | **5,332 × 14,176** | yes — 2,164 px narrower |
| I9 | Pools / lanes / shapes / sequence flows | unchanged | 15 / 14 / — / 298 | — | **15 / 14 / 357 / 298** | yes |
| I10 | Deterministic build | same input, same bytes | — | — | **identical SHA-256 over two consecutive runs** | yes |
| I16 | End events | **one incoming flow each** | 59 | 32, several merged | **65, none with more than one incoming, none unreachable** | yes |
| I17 | Drawn message flows | only those that inform | 66 | 31 | **15** (11 exception hand-offs + 4 system-boundary hand-offs) | yes |
| I18 | Nothing meaningful lost with the thinned message flows | retention rule holds | — | — | **all 11 exception hand-offs still drawn; nothing but an exception or boundary hand-off is drawn** | yes |

What changed, and the A/B behind it:

1. **Corridor choice is measured, not guessed.** The v2.1 router picked the
   least-loaded corridor nearest the middle of a jump. The R3 router evaluates
   the corridors a dogleg's own rows allow and keeps the one whose polyline cuts
   fewest other segments, repeating until a round changes nothing. A/B: with the
   optimiser disabled the same model measures 197 crossings; enabled, 123. Ink
   falls at the same time, 378,475 → 358,892 px, so the reduction is not bought
   with longer lines.
2. **Boundary events no longer sit under the tracks.** Sibling circles were 34 px
   apart on 36 px circles, so they overlapped and a line leaving the left one
   crossed the right one; the pitch is now `EVT + 6` = 42 px. A row that hosts
   boundary events is also grown by `BND_DEPTH` = 40 px so the corridor beneath
   it has room. A/B: canvas +440 px tall (3.1%).
3. **A verified `_unclip` pass** removes any run still drawn across a shape, by
   shifting it 18–36 px and closing the gap with a short vertical stub. Every
   candidate move is checked against all boxes and all other segments first, so
   the pass can only remove a defect. A/B: 4 → 0 clipped lines, 0 new overlaps.

Rejected: a much smaller compaction (canvas 2,398 × 6,858) was measured and
discarded — it cost 2,702 overlapping segment pairs, 397 crossings and 751 lines
through a shape. The measurements are in `06-diagram-engineering.md` §5.

### I1b — The two modelling changes behind the numbers

I16 is not a drawing change. v2.1 merged routine end events that sat near each
other (60 → 32) and that is what made several flows converge on one circle. The
merge is switched off, and the five joins inherited from v1.0 were split too.
Measured on its own, before the message-flow thinning, un-merging the ends took
crossings from 123 to 98 and the canvas from 7,496 to 6,774 px wide — a path that
ends where it finishes needs a shorter run than a path that ends at a shared
circle.

I17/I18 are a modelling decision, not a rendering one. A message flow is
documentation in Camunda 8: the throw event's `publish-message` job performs the
hand-off. Thinning from 31 to 15 removes 16 dashed lines that a reader can infer
from the pools themselves, and keeps the ones that carry an outcome. Every
dropped flow remains a working throw/catch pair in the XML; both paths were
re-run afterwards and still report `incidents: none`.

### I2 — Evidence re-captured

`diagram/hospital-patient-pathway-v2.svg` (7,484 × 14,468 vector),
`...-v2.png` and `...-v2-overview.png`, and `diagram/sections/` — one PNG per
pool, which is how a single team's row is actually read.

### I2b — Static checks

| # | Test | Expected | v2.1 | **R3 (v7.0)** | Pass |
|---|---|---|---|---|---|
| I11 | `bpmnlint model/*.bpmn` under the project's `bpmnlint:recommended` config | 0 errors | 39 errors / 43 warnings | **0 errors / 32 warnings** | yes — DEF-18 closed |
| I12 | `node tools/validate_model.js` with the Zeebe descriptor | clean | clean | **`parse warnings 0 / unresolved refs 0 / dangling seq refs 0 / user tasks no form 0 / user tasks no group 0 / service tasks no job type 0`** | yes |
| I13 | `tools/verify_preservation.py` | all pass | 61 of 62 | **67 of 67** | yes |
| I14 | Diagram interchange complete | every element | 30 elements without DI | **0 elements without DI** — the steps inside the three collapsed sub-processes now carry DI so the box can be opened in the Modeler | yes |
| I15 | Build determinism | same bytes | — | **identical SHA-256 over two consecutive runs** | yes |

The 37-error fall in I11 is one change: the steps inside the collapsed
sub-processes were given diagram interchange and the inner start/end events were
named. Removing the unreachable `SEC_End_PackIncomplete` circle in the same
release cleared the `no-disconnected` error that appeared once the end-event
merges were undone. `no-bpmndi` fires when DI is *missing*, so removing the DI in the earlier
compaction pass (as `06-visual-compaction.md` §5 described) was what produced the
warnings, not what cured them.

### I2c — Live runs on the shipped file

Every run below is against the SHA-256 recorded in
`screenshots/static-checks-v7.0.txt`, on c8run 8.10.0-alpha5, with the nine
process definitions and 36 forms from this folder.

| # | Run | Result |
|---|---|---|
| I19 | Normal path, `screenshots/run-happy-path.log` | 8 forms submitted, **0 active elements at the end**, `incidents: none` |
| I20 | Exception path, `screenshots/run-exception-path.log` | `REFERRAL_PACK_UNREADABLE` caught by the boundary event, the case joins the missing-information loop, `incidents: none` |
| I21 | Declined payment, `screenshots/run-declined-payment.log` | provider declines, the failed-payment review is worked, the retry is approved, 9 forms submitted, `incidents: none` |
| I22 | Overdue letter, `screenshots/run-overdue-escalation.log` | the letter is added to pathway monitoring and the pool's workers run clean, `incidents: none` — see I23 for what could not be driven |

I19 is the one to check the harness against: before this round the log listed
leftover active elements at the end. Those were not the model misbehaving — the
demo was completing tasks belonging to abandoned instances from earlier sessions,
because it looked user tasks up by process definition id with no run scoping. The
lookup is now scoped to the deployment and to the instances the run itself
creates, and a clean run ends with nothing active (DEF-19).

I22b. **The short-timer variant.** `model/demo/` holds the shipped model with
three timers shortened (`R/PT168H`, `P3D`, `P7D` → `PT15S`) so the clock-gated
branches can be shown. It is not the deliverable; it is deployed with
`BPMN=model/demo/… ./tools/deploy.sh`. Two things came out of using it, both of
which only a live run could have produced:

* **The capacity retry is live.** `TRT_Auto_RecordRetry` and
  `TRT_Throw_BookingPending` executed for the first time — before this release
  that whole chain was unreachable code (DEF-18), so the "capped retry" the
  modelling document describes had never run.
* **The escalation ladder is blocked, and the reason is a real defect.** The
  weekly review task was driven (`SUB_Pathway_Report_Review` completed), but
  `PCW_Throw_EscalateHigher` failed three times with *"Process variable
  'correlationKey' is missing or blank"*: a timer-started review has no
  `patientRef` to key the escalation on. DEF-21.

I22c. **The same runs on a clean engine.** The short-timer variant leaves a
repeating gateway-running every 15 seconds and Camunda 8.10.0-alpha5 exposes no
resource-deletion endpoint, so a demonstration engine accumulates pending review
instances and cannot be cleaned through the API. The engine was therefore
restarted with an emptied exporter database **and** an emptied Zeebe log
directory (`camunda-data` *and* `camunda-zeebe-8.10.0-alpha5/data`; clearing only
the first leaves the exporter replaying a million old positions and the search
API answers nothing). On the clean engine:

| # | Run | Result |
|---|---|---|
| I24 | Escalation, higher-management rung | `ADM_Task_ReferHigher` driven, Administrative Management instance **COMPLETED**, `incidents: none` |
| I25 | Escalation, manager rung (`DEMO_LETTER_OVERDUE_DAYS=45`) | `ADM_Task_ContactConsultant` driven, instance **COMPLETED**, `incidents: none` |
| I26 | Compensation (`external-resources.check-availability` forced to fail) | retry counted 8 times, **`TRT_Comp_ReleaseSeries` executed 6 times**, `incidents: none` |
| I27 | Tasklist | form captured open at `/tasklist/2251799813689594` — DEF-17 closed |

I26 is the first live execution of compensation in this portfolio: before this
release the retry chain that leads to it was unreachable code (DEF-18) and its
counter raised an incident before the cap could be reached (DEF-22).

I23. **Two harness limits, recorded rather than hidden.** The demo's task lookup
had to be made newest-first with a full page: a shared engine accumulates pending
tasks, and the default page returns the oldest first, so the task a run creates
can sit beyond the first page and never be seen. And right after a fresh engine
start the search API lags the deployment by a few seconds, so a script that
deploys and immediately queries can read an empty definition list.

The clinic-letter escalation ladder and the
compensation handlers are gated on engine timers — `PCW_Start_WeeklyReview` is a
`R/PT168H` timer start event and the capacity retry waits on `P3D`. They are
modelled, drawn and unit-checked, and they cannot be shown live without a
short-timer variant or an engine clock the API does not expose (DEF-20).

### I3 — Still not covered

The gaps in §G are unchanged. §H6a (43 start events) and §H6e (three exception
branches not driven live) remain open; §H6b and §H6c are closed above. The end
events added by I16 carry names from the paths that reach them, and two of them
reuse the label of the circle they were split from, so a reader sees the same
outcome named on two branches — that is intended, not duplication.

---

## J. R4 (v14) re-run — the white-box outside participants

Machine: local c8run **8.10.0-alpha5**, workers built from `workers/` with Maven
3.9.16 on JDK 21. Model SHA-256 `7bd812ad…`
(`model/UFCEP6-0-3_Hospital_Patient_Pathway_v14.bpmn`). Logs:
`screenshots/run-happy-path-v14.log`, `run-exception-path-v14.log`,
`run-external-participants-v14.log`; the static gates are in
`screenshots/static-checks-v14.txt`.

| # | Test | Expected | Actual | Pass |
|---|---|---|---|---|
| J1 | Deploy the shipped file | nine hospital processes and 36 forms | **9 process definitions v2 and 36 forms v2**, deployment key `2251799813952610` | yes |
| J2 | Deploy all fifteen executable | rejected, batch ceiling | **rejected**: `Can't append entry ... valueType=PROCESS ... with size: 405002 this would exceed the maximum batch size ... currentBatchSize: 4095764`. Nine fit, the tenth does not | as expected |
| J3 | Deploy the outside participants separately | six processes | **6 process definitions** from a 30,279-byte file, all `v1` | yes |
| J4 | Happy path on v14 | `incidents: none` | exit 0, `incidents: none` at all three checkpoints, **19 instances on the deployment** | yes |
| J5 | Unreadable-referral pack on v14 | boundary event catches, case joins the missing-information loop | exit 0, `incidents: none`, `SEC_EGW_InfoRequest` reached as expected | yes |
| J6 | `referring-organisation` runs and completes | COMPLETED, no incident | COMPLETED, no incident | yes |
| J7 | `patient-representative` runs and completes | COMPLETED, no incident | COMPLETED, no incident | yes |
| J8 | The four suppliers run and complete | COMPLETED, no incident | `external-scheduling-service`, `external-correspondence-service`, `external-payment-service`, `external-clinical-services` all COMPLETED, no incident | yes — **after DEF-21 and DEF-22 were fixed** |
| J9 | The referrer integration | throw of `referral.received` starts Medical Secretaries | 1 new `medical-secretaries` instance | yes |
| J10 | The patient integration | throw of `appointment.attended` starts Consultants | 1 new `consultants` instance | yes |
| J11 | Declined-payment branch | provider declines, review task worked, retry approved | `TRT_GW_PaymentOutcome` → `TRT_Task_ReviewDeclinedPayment` driven, `incidents: none` | yes |
| J12 | Confirmation-lost branch | `PAYMENT_CONFIRMATION_LOST` → Finance investigates, clinician authorises urgent care | `FIN_Task_InvestigatePayment` and `CON_Task_AuthoriseUrgentTreatment` both driven, `incidents: none` | yes |
| J13 | Letter escalation, higher rung | weekly review + `ADM_Task_ReferHigher` | both driven, `incidents: none` | yes |
| J14 | Letter escalation, manager rung | `letterOverdueDays = 45` → `ADM_Task_ContactConsultant` | driven, `ADM_Task_ReferHigher` correctly not reached | yes |
| J15 | Compensation | capacity never available → retry cap → `TRT_Comp_ReleaseSeries` | `TRT_Throw_CompSeries`, `TRT_Bnd_CompSeries`, `TRT_Comp_ReleaseSeries` all COMPLETED, `incidents: none` | yes |

Logs: `run-declined-payment-v14.log`, `run-confirmation-lost-v14.log`,
`run-overdue-escalation-v14.log`, `run-escalation-manager-v14.log`,
`run-compensation-v14.log`. J13–J15 need the short-timer variant
(`model/demo/…_v14_demo-timers.bpmn`) deployed, because the weekly review and the
three-day capacity retry are clock-gated (DEF-20); the shipped file was redeployed
afterwards.

### J1 — Defects found by running v14

**DEF-21 — `documentation` written after `extensionElements`. Critical, fixed.**
The BPMN XSD requires `bpmn:documentation` before `bpmn:extensionElements` in
`tBaseElement`. bpmn-moddle imports either order and bpmn-js renders either
order, so the whole static tool chain passed; the Camunda deployer validates
against the XSD and rejected the entire collaboration:

```
'UFCEP6-0-3_Hospital_Patient_Pathway_v14.bpmn': cvc-complex-type.2.4.a:
Invalid content was found starting with element 'documentation'.
```

Latent since the first release, because no process carried process-level
documentation until the six outside participants did. Fixed in
`tools/bpmn_builder_v2.py`; the order is now asserted by the deployment itself.

**DEF-22 — supplier steps inherited an input contract they could not satisfy. High, fixed.**
The suppliers' steps reuse the hospital's job types, so they inherit the workers'
validation. `correspondence.dispatch-letter` rejects a dispatch with no recipients
with `CORRESPONDENCE_SERVICE_FAILED`, and `payment.process-transaction` requires a
payment reference and a charge amount. Inside the hospital process those come from
upstream; inside a supplier process started by a bare request message they do not,
so the first run produced two incidents — exactly the class of defect that only a
run finds. Both steps now carry a `zeebe:ioMapping` defaulting the fields and
using the message's value when it supplies one.

**DEF-23 — the check reused correlation keys. Test-harness defect, fixed.**
Camunda 8 does not start a second instance on a message start event while an
instance with the same correlation key is active — the duplicate suppression the
model relies on (`docs/04-modelling-decisions.md` §2). The harness published a
fixed reference and reported three processes as "did not start". Fixed by using a
fresh reference per run; the behaviour it tripped over is itself evidence the
design works.

**DEF-24 — the demo's branch window was a fixed 20 seconds. Test-harness defect, fixed.**
`demo_scenario.py` waited 20 s for an exception-branch task after the step that
precedes it. On a cold worker JVM the payment transaction alone took 60 s, so the
run reported `TRT_Task_ReviewDeclinedPayment` as "not reached" when the engine
history showed the model had reached it — a false negative that would have hidden
a working branch. The wait is now `DEMO_BRANCH_TIMEOUT` (default 60 s), and J11–J15
were driven with 120 s where the provider branch is involved.

### J2 — What the run confirms about the drawing

The six outside participants are not decoration: each one started, ran its step
through the same Java worker the hospital's own service task calls, published its
response and completed. The two plain-start participants are integrations rather
than diagrams — their throw is what starts a hospital process, and both did.

### J3 — Still not covered on v14

Operate, Tasklist and Modeler screenshots of v14 have not been captured;
`screenshots/` still holds the v7.0 images for those. Everything that runs has
been run: the two hospital paths, the six outside participants, and all five
exception branches (J11–J15) now have v14 logs. The Tasklist authentication
problem (DEF-14) and the job-type table gap (DEF-16) are unchanged by this
release. See `docs/11` §5.
