# Product backlog, sprint backlogs and Definition of Done

Planning counterpart to the delivered portfolio. Every item below is traced to an
artefact that exists in this folder. The model file, the 36 forms and the worker
sources are the source of truth; where a planning value (owner, estimate, sprint
date) is not derivable from an artefact it is marked as a planning value and
listed in the Assumptions section at the end.

Read with: `docs/01-gap-audit.md` (the measured starting point), `docs/02-status.md`
(what is done and not done), `docs/03-test-record.md` (the execution record),
`docs/04-modelling-decisions.md` (why the model is shaped as it is),
`docs/05-v2.1-changes.md` (the second release), `docs/06-diagram-engineering.md`
(the drawing: how it is routed, and what the third release changed).

---

## 1. Product vision and scope statement

> Build one runnable BPMN collaboration of the hospital referral, treatment and
> administration pathway in which every hand-off between the named hospital teams
> is a real, correlated message; every clinical, administrative and financial
> decision sits with the correct role; every modelled failure has an owner and an
> exit; and the whole thing can be regenerated, deployed and demonstrated from the
> files in one shared workspace.

**In scope for the product.** The fifteen participants in the case study; the
whole pathway from referral receipt to follow-up; the nine hospital processes
that carry executable work; the six outside participants as white-box pools of
their own since v14 (`docs/11-white-box-external-participants.md`)
at the boundary; the nine named exception conditions; compensation for the two
resources that are committed and can be released; the clinic-letter escalation
ladder; the CAMUNDA Forms and their validation; the external workers that
automate 35 job types; and the evidence that all of it runs.

**Out of scope for the product (this module).** Real integrations with any
scheduling, correspondence, treatment, laboratory, imaging or payment provider;
production identity, RBAC and persistence; a production database; and any
deployment outside a local c8run cluster. See `docs/04-modelling-decisions.md` §7
and `workers/README.md` ("Simplifications and known gaps").

**Module learning outcomes used in this document** (legend only; the wording of
the outcomes is not reproduced in the workspace, see Assumption A7):

| Code | Short form used here |
|---|---|
| LO1 | User-centred forms and data capture |
| LO2 | A runnable, correct model and working automation |
| LO3 | Project and test planning; configuration management |
| LO4 | Business behaviour, exceptions and evidence of execution |
| LO5 | Reflective, consistent, well-governed delivery |

---

## 2. Releases

Two releases exist, matching the two sprints and the two Sprint Reviews.

| Release | Name | Files | What it adds | Backlog items |
|---|---|---|---|---|
| R1 | **Initial Release** (v2.0) | `model/UFCEP6-0-3_Hospital_Patient_Pathway_v2.bpmn`, `model/forms/*.form` | Measured rebuild: new layout engine, lanes, collapsed subprocesses, exception branches with owners, compensation, capped retry, forms, workers, both run paths | PB-01 – PB-24 |
| R2 | **Second Release** (v2.1) | same filenames, regenerated | Visual compaction only: message-flow thinning, routine end-event merge, lane consolidation; nothing scored removed | PB-25 – PB-29 |

**Definition of the Initial Release (R1).** The Initial Release is accepted when:
the v2.0 collaboration deploys to a local c8run 8.10.0-alpha5 cluster as 9 process
definitions and 36 forms in one batch; the workers build and subscribe to every
job type the model defines; the normal path and the unreadable-pack exception
path each run to a stable state with `incidents: none`; and the layout measures
zero sequence-flow overlaps and zero message-flow overlaps. All five conditions
are evidenced in `docs/03-test-record.md` §C, §D, §E and §H.

---

## 3. Priority scheme

MoSCoW is used, and within each band items are ranked 1 = first. Rank drives
sprint selection; MoSCoW drives the release decision.

| Band | Meaning for this product |
|---|---|
| Must | Without it the release is not accepted (see §2) |
| Should | Required for the 70%+ rubric band; carried as a committed stretch item |
| Could | Improves the portfolio; carried only if the Must and Should items are done |
| Won't (this release) | Explicitly deferred, with the reason recorded |

---

## 4. Product backlog

Estimates are in story points (SP) and ideal days (d). Owners are the five-person
team: **A** model lead, **B** layout and visualisation lead, **C** workers lead,
**D** forms and UX lead, **E** test and configuration lead. Every item has a first
owner (accountable) and a second owner (reviewer and cover).

### 4.1 Sprint 1 items — delivery of the Initial Release (R1)

| ID | Rk | Pri | Item | Why (LO) | SP | d | 1st | 2nd | Acceptance criteria | Depends on | Status | Evidence |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PB-01 | 1 | Must | Measure v1.0 against every 70%+ rubric descriptor and list the gaps | LO3, LO5 | 5 | 1.5 | E | A | Every descriptor in the gap audit has either a measurement or an artefact reference; every gap is numbered and actionable | — | Done | `docs/01-gap-audit.md`; `tools/analyse_layout.py` |
| PB-02 | 2 | Must | One BPMN collaboration with the 15 case-study participants; 9 executable hospital processes and 6 outside participants | LO2, LO4 | 8 | 2 | A | E | 15 `bpmn:participant` elements with the case-study names; 9 processes with `isExecutable="true"`; originally the 6 external bodies were black-box pools, **superseded in v14** — all 15 now carry a process and every outside participant is connected to another pool | PB-01 | Done, extended in v14 | model file participants; `docs/04-modelling-decisions.md` §1; `docs/11-white-box-external-participants.md` |
| PB-03 | 3 | Must | Correlated message hand-off for every cross-pool transfer | LO2, LO4 | 8 | 2 | A | C | 68 message throw events and 10 catch events; every throw carries a `correlationKey` input mapping; message names are unique | PB-02 | Done | model file; `docs/03-test-record.md` §B1; `docs/04-modelling-decisions.md` §2 |
| PB-04 | 4 | Must | Lanes inside pools that cover more than one desk | LO2 | 5 | 1.5 | A | B | Every pool that covers more than one sub-role carries named lanes; participant names unchanged | PB-02 | Done | 14 lanes, e.g. `consultants_L0` / `consultants_L1`; `docs/03-test-record.md` §A7 |
| PB-05 | 5 | Must | Orthogonal layout engine: grid columns/rows, one track per flow, dedicated message channel | LO2, LO4 | 13 | 4 | B | A | Sequence-flow overlap 0 pairs, message-flow overlap 0 pairs, 0 diagonal px; both `hospital-patient-pathway-v2.svg` and `.png` regenerate | PB-02 | Done | `tools/layout_engine.py`; `docs/03-test-record.md` §A1–A3; `diagram/` |
| PB-06 | 6 | Must | Contain repetitive administration in collapsed sub-processes | LO2 | 8 | 2 | A | B | 3 collapsed sub-processes, each with a `<bpmn:documentation>` note; their steps remain in the XML and executable | PB-05 | Done | `SUB_Secretaries_Dispatch`, `SUB_CallHandling_Contact`, `SUB_Pathway_Report`; `docs/03-test-record.md` §A8 |
| PB-07 | 7 | Must | Every exception branch has an owner and an exit | LO4 | 13 | 4 | A | C | All 9 `bpmn:error` codes reachable from 18 boundary events; no exception branch terminates without an owner task, a retry, a timer or an escalation | PB-03 | Done | `docs/04-modelling-decisions.md` §4; `docs/03-test-record.md` §H1 |
| PB-08 | 8 | Must | Clinic-letter delay timers and the three-rung escalation ladder | LO4 | 8 | 2 | A | E | Boundary timers `P7D` and `R/PT168H` present; `letter.escalation-admin-manager` and `letter.escalation-higher-management` message chain present | PB-07 | Done | model boundary events; `docs/03-test-record.md` §H1 |
| PB-09 | 9 | Must | A Camunda Form on every user task | LO1 | 8 | 2.5 | D | A | 39/39 user tasks carry `zeebe:formDefinition`; 36 distinct forms exist and every bound form is defined | PB-02 | Done | `model/forms/` (36 `.form`); `docs/03-test-record.md` §H1, §H5d |
| PB-10 | 10 | Must | Role-based candidate group on every user task | LO1, LO5 | 5 | 1.5 | D | E | 39/39 user tasks carry `zeebe:assignmentDefinition` with a candidate group matching the pool's role | PB-09 | Done | `docs/03-test-record.md` §H1, §H5d |
| PB-11 | 11 | Must | Validation rules on the forms | LO1 | 5 | 1.5 | D | B | Required, length and numeric-range rules present on the fields that need them; long text is bounded | PB-09 | Done | 172 `validate` blocks across the 36 forms; `docs/01-gap-audit.md` §C2 |
| PB-12 | 12 | Should | Accessibility: field descriptions on every field, and grouping on long forms | LO1, LO5 | 5 | 1.5 | D | E | Every field has a description; forms longer than ~8 fields are split by group heading | PB-09 | **Partly done** — 71 descriptions across 230 fields; 0 `group` components emitted | form JSON census; `docs/01-gap-audit.md` §C3 |
| PB-13 | 13 | Must | One external worker per job type the model uses | LO2, LO4, LO5 | 21 | 6 | C | A | Every job type in the model has a subscribing worker; build green; subscriptions observed on the live gateway | PB-02 | Done | `workers/src/.../tasks/` (36 classes); `workers/README.md`; `docs/03-test-record.md` §E1–E2 |
| PB-14 | 14 | Must | Simulated external services with documented forced-failure switches | LO4 | 8 | 2.5 | C | E | The 5 simulated job types can each be forced to succeed or fail without editing code, through `application.yaml` or an environment variable | PB-13 | Done | `SimulatedFailureRegistry`; `workers/src/main/resources/application.yaml`; `workers/README.md` |
| PB-15 | 15 | Must | Duplicate suppression for bookings, charges and hand-offs | LO2, LO4 | 8 | 2 | C | B | Repeating a booking returns the same reference; a duplicate charge is detected before payment; the correlation-key purpose tag prevents a duplicate hand-off | PB-03, PB-13 | Done | `HospitalStore`; `workers/README.md`; `docs/04-modelling-decisions.md` §2 |
| PB-16 | 16 | Must | No storage or emission of complete card data | LO5 | 3 | 1 | C | E | No payment worker reads or writes a card-number, CVV or expiry variable; only a payment reference and status are returned | PB-13 | Done | `workers/README.md` job types 13 and 24 ("Never emits card data") |
| PB-17 | 17 | Must | Audit-trail workers that do not overwrite clinical variables | LO4, LO5 | 5 | 1.5 | C | A | Clinical and financial decisions produce an audit reference and timestamp; the audit workers refuse a blank `patientRef` and write no clinical variable back | PB-13 | Done | `workers/README.md` job types 2 and 3 |
| PB-18 | 18 | Must | Compensation for the two committed resources | LO2, LO4 | 13 | 4 | A | C | A compensation boundary event and `isForCompensation` handler on the appointment series and on the cycle booking; a compensation throw on the path that gives up; handlers typed `treatment.release-series` and `treatment.release-cycle-booking` | PB-07, PB-13 | Done for modelling; **not triggered live** | model `TRT_Bnd_CompSeries`, `TRT_Bnd_CompCycle`, `TRT_Comp_ReleaseSeries`, `TRT_Comp_ReleaseCycle`; `docs/04-modelling-decisions.md` §5 |
| PB-19 | 19 | Must | Counted retry with a cap and an escalation for unavailable external capacity | LO4 | 8 | 2 | A | C | A counted retry capped at 3; on exhaustion the provisional series is released and the case is handed to the pathway team, then retried in three days | PB-07 | Done | `TRT_Auto_RecordRetry` (`treatment.record-capacity-retry`); `docs/04-modelling-decisions.md` §4 |
| PB-20 | 20 | Must | Deploy the model and all forms in one batch, repeatably | LO5 | 5 | 1.5 | E | C | One command deploys 9 process definitions and 36 forms with no error, from a clean checkout, against `http://localhost:8080` | PB-05, PB-09 | Done | `tools/deploy.sh`; `docs/03-test-record.md` §C1, §H2a |
| PB-21 | 21 | Must | Normal-path run evidence | LO4 | 5 | 1.5 | E | C | Eleven steps reached; `incidents: none` reported at the end of each stage; log retained | PB-20 | Done | `screenshots/run-happy-path.log` |
| PB-22 | 22 | Must | Exception-path run evidence | LO4 | 5 | 1.5 | E | A | `REFERRAL_PACK_UNREADABLE` is thrown by the worker, caught by `SEC_Bnd_DocumentsUnreadable`, and the case joins the missing-information loop with no incident | PB-20 | Done | `screenshots/run-exception-path.log` |
| PB-23 | 23 | Must | Prove every form renders | LO1, LO5 | 3 | 1 | D | E | All 36 forms import and render in `@bpmn-io/form-js` with no unsupported field type | PB-09 | Done | `screenshots/camunda-forms-rendered.png`; `docs/03-test-record.md` §F4 |
| PB-24 | 24 | Must | Written test record and modelling decisions document | LO3, LO5 | 8 | 2.5 | E | A | Expected vs actual for every check run; every defect recorded; limitations stated before a reviewer finds them | PB-21, PB-22 | Done | `docs/03-test-record.md`, `docs/04-modelling-decisions.md` |

### 4.2 Sprint 2 items and deferred work

| ID | Rk | Pri | Item | Why (LO) | SP | d | 1st | 2nd | Acceptance criteria | Depends on | Status | Evidence |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PB-25 | 25 | Must | Preservation audit as executable checks | LO3, LO5 | 8 | 2.5 | E | B | Parsed checks over pools, user tasks, forms, candidate groups, job types, gateway types, error codes, timers and Camunda 7 attributes; all pass before a rebuild is accepted | PB-24 | Done | `tools/verify_preservation.py` — 62 checks, 62 passed; `docs/03-test-record.md` §H1 |
| PB-26 | 26 | Must | Thin the drawn message flows to one line per pool pair, keeping exception hand-offs | LO2 | 8 | 2.5 | B | A | Message flows 66 → 31; dashed-line length 421,424 → 174,820 px; both run paths still clean afterwards | PB-25 | Done | `docs/05-v2.1-changes.md` §1; `docs/03-test-record.md` §H3 |
| PB-27 | 27 | Must | Merge routine end events, never exception ends | LO2 | 5 | 1.5 | B | E | End events 60 → 32; `_exception_ends()` keeps every exception end distinct | PB-26 | Done | `docs/05-v2.1-changes.md` §2 |
| PB-28 | 28 | Should | Consolidate single-step lanes into a neighbour lane of the same pool | LO2 | 3 | 1 | B | A | Lanes 20 → 14; no participant renamed or removed | PB-26 | Done | `docs/05-v2.1-changes.md` §3 |
| PB-29 | 29 | Must | Re-validate in the Modeler and export the diagram and per-pool sections | LO4, LO5 | 8 | 2.5 | B | E | Camunda Modeler 5.51.0 reports 0 errors on Camunda 8.10 (alpha); SVG and PNG regenerate; 15 section crops refreshed | PB-26 | Done | `screenshots/camunda-modeler-v2.1-status-bar.png`; `tools/render_diagram.sh`; `tools/export_sections.py`; `diagram/sections/` |
| PB-30 | 30 | Should | Drive the three branches that are modelled but not run: declined payment, confirmation lost, three-month escalation | LO4 | 8 | 2.5 | E | C | Each branch driven to its end state on the live engine, with a retained log and an Operate screenshot | PB-20 | **Carried over — not run** | `docs/03-test-record.md` §D3, §G, §H6e; `docs/02-status.md` ("Not done") |
| PB-31 | 31 | Should | Trigger compensation in a live run | LO4 | 5 | 1.5 | C | E | A compensation handler completes inside a real process instance, visible in Operate | PB-18, PB-20 | **Carried over — not run** | `docs/03-test-record.md` §D3 |
| PB-32 | 32 | Could | Fix the c8run Tasklist authentication so the forms draw in Tasklist | LO1, LO5 | 3 | 1.5 | E | D | The Tasklist Task tab renders a v2.0 form for a claimed task | PB-20 | **Carried over** — Tasklist gets `401` from `/v2/authentication/me`; environmental | `docs/03-test-record.md` §F5; `docs/02-status.md` |
| PB-33 | 33 | Could | Reduce message start events to ≤ 2 per pool by changing the message protocol | LO2 | 13 | 4 | A | C | Every hand-off publishes `Msg_<pool>` plus a `requestType` discriminator and each pool has one start event feeding a dispatch gateway | PB-03 | Not started — deferred, see `docs/05-v2.1-changes.md` §4 | arithmetic in `docs/05-v2.1-changes.md` §4 |
| PB-34 | 34 | Could | Crossing-reduction pass | LO2 | 8 | 2.5 | B | A | Sequence-flow crossings reduced from 197 without reintroducing an overlap | PB-27 | **Done in R3** — 94 crossings (−52%), 0 clipped lines, 0 overlaps held | `docs/06-diagram-engineering.md` §3.1, §3.4 |
| PB-35 | 35 | Should | Readable terminals and hand-offs: one end event per terminating path, and dashed lines cut to the hand-offs that carry an outcome | LO2, LO4 | 5 | 1.5 | B | D | Every end event has exactly one incoming sequence flow; no end event unreachable; every exception hand-off still drawn; no more than 15 message flows drawn | PB-27 | **Done in R3** — 66 end events, none merged; 15 drawn message flows. **v14 raises the message-flow ceiling to 22** to connect the six outside participants | `docs/06-diagram-engineering.md` §3.5, §3.6; `docs/11-white-box-external-participants.md` |
| PB-35 | 35 | Won't (this release) | Replace the five simulated external services with real provider APIs | LO4 | — | — | C | E | Not applicable — out of scope for a local portfolio release | PB-14 | Won't (this release) | `workers/README.md` ("Simplifications and known gaps") |

---

## 5. Sprint backlogs

Sprint lengths, stand-up dates and review dates are planning values; no calendar
record exists in the workspace (Assumption A3).

### 5.1 Sprint 1 — to Sprint Review 1, delivering the Initial Release (R1)

**Sprint Goal (agreed at planning).**
> Replace the v1.0 drawing with a measured layout engine and close the two
> behavioural gaps the gap audit found — exception branches with an owner and
> compensation for committed resources — then prove the whole collaboration runs
> on a live engine with no incidents.

**Selection and control.** All 24 Sprint 1 items entered the sprint; PB-01 to
PB-05 were completed first because every later item depends on the structure and
the layout, and the sprint was deliberately not expanded when the forms defect
(§B of `docs/03-test-record.md`) was found. PB-12 was descoped during the sprint
to descriptions only; the grouping half is retained as unfinished.

| Sprint 1 selection | Items | State at Sprint Review 1 |
|---|---|---|
| Analysis and structure | PB-01, PB-02, PB-03, PB-04, PB-06 | Completed |
| Drawing | PB-05 | Completed |
| Behaviour | PB-07, PB-08, PB-18, PB-19 | Completed for modelling; PB-18 not triggered live |
| Forms | PB-09, PB-10, PB-11, PB-12 | PB-09/10/11 completed; **PB-12 partly done** |
| Workers | PB-13, PB-14, PB-15, PB-16, PB-17 | Completed |
| Release and evidence | PB-20, PB-21, PB-22, PB-23 | Completed |
| Documentation | PB-24 | Completed |

**Completed at Sprint Review 1 (22 of 24).** PB-01 – PB-11, PB-13 – PB-17,
PB-18 (modelling only), PB-19 – PB-24. PB-12 was partly done; PB-18 was not
triggered live.

**Carried over out of Sprint 1.**

| Item | Carried because | Where it went |
|---|---|---|
| PB-12 (grouping half) | The field-description half was delivered; grouping was not implemented and no `group` component is emitted in any form | Not selected in Sprint 2; recorded as an open gap in `docs/08-test-plan.md` and `docs/10-sprint-reviews-and-feedback.md` |
| PB-18 (live trigger) | Compensation is modelled and the handlers exist; no live run exercised it | Re-framed as PB-31 in Sprint 2, still not run |

### 5.2 Sprint 2 — to Sprint Review 2, delivering the second release (R2)

**Sprint Goal (agreed at planning).**
> Reduce the drawn density of the shipped model without removing a single scored
> element, and re-prove the behaviour afterwards on the rebuilt file.

**Selection and control.** The committed set was PB-25 – PB-29, with PB-30 – PB-34
held as stretch items behind the Must items. PB-25 (the executable preservation
audit) was built first so that every later change could be proved non-destructive.
PB-30 – PB-34 were not started, and no committed item was dropped.

| Sprint 2 selection | Items | State at Sprint Review 2 |
|---|---|---|
| Committed | PB-25, PB-26, PB-27, PB-28, PB-29 | Completed |
| Stretch | PB-30, PB-31, PB-32, PB-33, PB-34 | None started |
| Deferred by decision | PB-35 | Won't (this release) |

**Completed at Sprint Review 2 (5 of 5 committed).** PB-25 – PB-29.

**Carried over out of Sprint 2.** PB-30, PB-31, PB-32, PB-33, PB-34, PB-35. Each
carry-over keeps its MoSCoW band and its owner; the reason is recorded in the
table in §4.2 and repeated in `docs/10-sprint-reviews-and-feedback.md`.

---

## 6. Definition of Done

An item is Done only when every applicable line below is true. The gates are the
real commands in `tools/`; a claim without a gate result is not Done.

| # | DoD condition | How it is proved | Applies to |
|---|---|---|---|
| DoD-1 | The generator accepts the change: `python3 tools/build_v2.py` exits 0 with no check failure | Build output; the check refuses unbound forms, shared grid cells and mixed boolean/text comparisons | Model, forms |
| DoD-2 | Layout gates hold: sequence-flow and message-flow overlaps are 0 pairs; no diagonals | `python3 tools/analyse_layout.py model/UFCEP6-0-3_Hospital_Patient_Pathway_v2.bpmn` | Drawing |
| DoD-3 | Nothing scored was lost by a regeneration: 67 parsed checks pass | `python3 tools/verify_preservation.py` | Any model change after R1 |
| DoD-4 | The model parses clean in the Modeler's own parser: 0 warnings, 0 unresolved references, 0 dangling flows, 0 user tasks without a form or candidate group, 0 service tasks without a job type | `node tools/validate_model.js model/UFCEP6-0-3_Hospital_Patient_Pathway_v2.bpmn` | Model |
| DoD-5 | The model opens in Camunda Modeler 5.51.0 with 0 errors on Camunda 8.10 (alpha) | Modeler status bar, screenshot retained | Release |
| DoD-6 | The deployment is accepted: 9 process definitions and 36 forms in one batch | `bash tools/deploy.sh` output | Release |
| DoD-7 | The workers build and subscribe to every model job type | `mvn -q -o clean package`; start-up subscription log | Workers |
| DoD-8 | Both scripted paths reach their expected end state with `incidents: none` | `python3 tools/demo_scenario.py` and `--exception`; logs retained | Release |
| DoD-9 | Every form imports and renders in `@bpmn-io/form-js` | Render census, `TOTAL=36 FAILED=0`; screenshot retained | Forms |
| DoD-10 | Expected result, actual result and evidence file are written down | The test record is updated in the same change | Every item |
| DoD-11 | The second owner has read the change and the evidence, and their name is against the item | Hand-over log in §7 | Every item |
| DoD-12 | Any limitation introduced is stated in `docs/04-modelling-decisions.md` §7 or `docs/02-status.md` | Document review at the sprint review | Every item that leaves a gap |

---

## 7. How the two owners work, and the hand-over log

**The pattern.** The first owner is accountable: they make the change, run the
gates that apply to it, and write the evidence line. The second owner is the
reviewer and the cover: they reproduce at least one gate result themselves, read
the evidence rather than the claim, and are expected to be able to take the item
over within one working session. No item is Done with only one owner's name on it
(DoD-11). Where the two owners disagree, the item stays In progress and the
disagreement is raised at the stand-up; it is not resolved by the first owner
alone. For cross-boundary items the second owner is deliberately chosen from the
other side of the boundary — the forms items are second-owned by the test lead,
the worker items by the model lead — so that a claim of integration is checked by
someone who did not build the integration.

**Cadence of hand-over.** A hand-over is an explicit act, not an email: the
artefact moves into the shared workspace, the gate output is pasted into the test
record, and the row in the log below is closed in the same session. The log is the
record of who held an item and when.

| HO | From → To | Artefact handed over | Trigger | Accepted how | Status |
|---|---|---|---|---|---|
| HO-01 | A → B | `tools/spec_v2.py` structure (pools, lanes, nodes, flows) | Structure frozen for Sprint 1 | B builds the layout from the spec and returns the overlap measures | Closed |
| HO-02 | B → A | Layout engine geometry and the analyse_layout output | After the first zero-overlap run | A confirms every node and flow is placed and no element moved between lanes | Closed |
| HO-03 | A → C | Model job types and error codes | Before worker work | C confirms every service task type and every BPMN error has a worker behaviour | Closed (three v2.0 types added afterwards, logged as HO-08) |
| HO-04 | D → E | 36 `.form` files | Before the render census | E runs the form-js census and reports failures | Closed — first run failed, see `docs/03-test-record.md` §F4 |
| HO-05 | E → D | Form render failure report (`date` field type) | Same day as HO-04 | D fixes `tools/forms_spec.py` and the build re-emits the forms | Closed |
| HO-06 | E → C | Deployment result (9 definitions, 36 forms) | Before the path runs | C runs the paths and returns the incident count | Closed |
| HO-07 | C → E | Path logs | End of Sprint 1 | E signs off the expected-vs-actual table | Closed |
| HO-08 | A → C | Three v2.0 job types (`treatment.release-series`, `treatment.release-cycle-booking`, `treatment.record-capacity-retry`) | After compensation and capped retry were modelled | C confirms the three workers build and register | Closed |
| HO-09 | B → E | v2.1 rebuilt model | Start of the compaction pass | E runs the 62-check preservation audit before anything else is accepted | Closed |
| HO-10 | E → A | Preservation result and Modeler status bar | End of Sprint 2 | A confirms the release note and the carried-over list | Closed |

---

## 8. Agile working notes

**Cadence.** Two timeboxed sprints. Each sprint runs a graded stand-up at its
midpoint and a graded Sprint Review at the end, so the demonstration is rehearsed
once before it is graded. Planning is a single short session at the start of each
sprint; the sprint backlog is frozen after it except for a removal, which must be
agreed by both owners and recorded in §5.

**Stand-up format (timeboxed, 10 minutes).** Each of the five members answers in
turn, with the artefact open rather than from memory: (1) which backlog item did
you move, and which gate output proves it; (2) which item will you move next;
(3) what is blocking you, and from whom. Blockers are written into the feedback
action log in `docs/10-sprint-reviews-and-feedback.md` with a first and second
owner before the stand-up ends. Status is only ever one of: Not started, In
progress, Blocked, Done (per DoD), Carried over.

**Review format (timeboxed).** For each demonstrated item: the sprint goal, the
increment actually shown, the acceptance evidence file, what was not finished,
the decisions taken, and the limitations stated. The review runs the live path,
not a slide. Anything not shown at the review is not counted as Done at that
review even if it is finished afterwards.

**Retrospective format (timeboxed, after each review).** Three columns — what went
well, what did not, and one improvement action. The action must name a first
owner, a second owner and the sprint it lands in; an action with no owner is not
recorded. The retrospectives are in `docs/10-sprint-reviews-and-feedback.md` §3 and
§6.

**Continuous integration of contributions.** The workspace is integrated after
every accepted item, not at the deadline: the generator is re-run, the layout gate
and the preservation gate are executed, and the test record is updated in the same
change. The deterministic build is the integration mechanism — `build_v2.py` is
documented as producing byte-identical output for the same inputs
(`docs/05-v2.1-changes.md` §5), so any unexplained diff is a real change to be
reviewed rather than an accident of the tooling.

---

## 9. Assumptions

1. **A1 — Team identity.** The five members are referred to as team members A–E with the roles in §4. No real names appear in any artefact in the workspace, or in this document.
2. **A2 — Estimates.** Story points, ideal days and ranks are planning values authored for this document. No estimate exists in any artefact in the workspace.
3. **A3 — Dates.** Sprint length, stand-up dates and review dates are not recorded anywhere in the workspace. They are treated here as planning values for two timeboxed sprints.
4. **A4 — Repository.** There is no `.git` directory or other version-control metadata in the folder (checked). The shared workspace is therefore the folder itself, and the configuration-management plan in `docs/09-risk-contingency-and-config-management.md` describes the scheme as it exists rather than assuming a VCS.
5. **A5 — Job-type counts.** The model defines 47 service tasks across **35 distinct job types**, plus `publish-message` on the 68 message throw events. The worker sources contain 36 task classes producing **37 job-type subscriptions** (35 model types, one alias `pathway.find-overdue-clinic-letters`, and `publish-message`), which reconciles the "37 subscriptions" figure in `docs/03-test-record.md` §E2 and §H2b. The table in `workers/README.md` documents only 32 domain types and its summary line ("33 job workers = 1 + 32") is stale by three classes; this is recorded as a documentation defect in `docs/08-test-plan.md` §9.
6. **A6 — Diagram document (closed in R3).** The earlier `docs/06-visual-compaction.md` described a compaction that was never in the shipped model. In the third release that file was **deleted** and replaced by `docs/06-diagram-engineering.md`, which describes the drawing that is actually shipped and records the abandoned compaction as a rejected experiment with its measurements. The model file remains the source of truth; the drift is closed rather than carried.
7. **A7 — Learning-outcome legend.** The full outcome wording is not reproduced in the workspace; the short forms in §1 are inferred from the descriptor/LO mapping used in `docs/01-gap-audit.md`.
8. **A8 — Release naming.** "Initial Release" is R1 (v2.0) and the "second release" is R2 (v2.1). Both filenames are the same in the folder; the distinction is the content and the deployment version, not the path.
