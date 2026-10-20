# Product backlog, sprint backlogs and Definition of Done

> **This is the planning record for releases R1 (v2.0) and R2 (v2.1). It is kept
> as history, not as the current plan.**
>
> The delivered plan is **`../../docs/GroupMj Product-Backlog.xlsx`** (`Mj01`–`Mj58`).
> That workbook is the activity-level record the brief asks for: every item has a
> first owner, a second owner, an estimate, acceptance conditions, a dependency and
> a status. The sprint workbooks are
> `../../docs/GroupMj Sprint-1-Backlog.xlsx` and
> `../../docs/GroupMj Sprint-2-Backlog.xlsx`.
>
> This document used `PB-nn` identifiers for a differently-scoped set of items and
> referred to owners as "team members A–E". Both caused the two plans to read as
> competing records of the same thing. The identifiers are retained below because
> they are the history of how the releases were planned, and because
> [08-test-plan.md](08-test-plan.md) originally traced against them. **§11 is the
> crosswalk** between them: every `PB-nn` here, the `Mj-nn` row in the delivered
> workbook that now carries it, and the test cases that exercise it. Traceability
> for new work runs against `Mj-nn` and nothing else.
>
> Where this document and the workbook disagree on a count, the workbook and the
> measured artefact win. The known disagreements are listed in §11.3.

> **Citations to files that are not in this tree.** An audit found 39 paths cited across 19 documents that no longer exist — the fourteen-pool model, the v1/v2 generators and the drawing scripts that went with them, and the Sprint 0 Node scaffold. Nothing was lost: all of it is in git history, and every citation is listed with what replaced it in [18-cited-files-no-longer-present.md](18-cited-files-no-longer-present.md).

Every item below is traced to an artefact. The model file, the forms and the worker
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
> administration pathway. Every hand-off between the named hospital teams is a
> real, correlated message. Clinical, administrative and financial decisions all
> sit with the correct role, and every modelled failure has an owner and an exit.
> The whole thing can be regenerated, deployed and demonstrated from the files in
> one shared workspace.

**In scope for the product.** The fifteen participants in the case study, and the
whole pathway from referral receipt to follow-up. The scope also covers the nine
hospital processes that carry executable work, the six outside participants as
white-box pools of their own since v14
(`docs/11-white-box-external-participants.md`) at the boundary, and the nine named
exception conditions. Beyond the model itself: compensation for the two resources
that are committed and can be released, the clinic-letter escalation ladder, the
CAMUNDA Forms and their validation, the external workers that automate 35 job
types, and the evidence that all of it runs.

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

Estimates are in story points (SP) and ideal days (d). The workpackage owners for
R1 and R2 were recorded as role letters: **A** model lead, **B** layout and
visualisation lead, **C** workers lead, **D** forms and UX lead, **E** test and
configuration lead. Every item has a first owner (accountable) and a second owner
(reviewer and cover).

> **Role letters are history.** The R1/R2 letters map onto the four members and the
> initials the delivered workbook uses: **A** model lead — Lorrey (**L**);
> **B** layout and visualisation lead — Lorrey (**L**); **C** workers lead —
> Lorrey (**L**); **D** forms and UX lead — Damon (**D**); **E** test and
> configuration lead — Young (**Y**). Project management and the submission
> package were carried by Tommy (**T**), who does not appear as a letter here.
> The letters below are kept only so that the historical rows can still be read;
> new work is owned by initials.

### 4.1 Sprint 1 items: delivery of the Initial Release (R1)

| ID | Rk | Pri | Item | Why (LO) | SP | d | 1st | 2nd | Acceptance criteria | Depends on | Status | Evidence |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PB-01 | 1 | Must | Measure v1.0 against every 70%+ rubric descriptor and list the gaps | LO3, LO5 | 5 | 1.5 | E | A | Every descriptor in the gap audit has either a measurement or an artefact reference; every gap is numbered and actionable | — | Done | `docs/01-gap-audit.md`; `tools/analyse_layout.py` |
| PB-02 | 2 | Must | One BPMN collaboration with the 15 case-study participants; 9 executable hospital processes and 6 outside participants | LO2, LO4 | 8 | 2 | A | E | 15 `bpmn:participant` elements with the case-study names; 9 processes with `isExecutable="true"`; originally the 6 external bodies were black-box pools, superseded in v14: all 15 now carry a process and every outside participant is connected to another pool | PB-01 | Done, extended in v14 | model file participants; `docs/04-modelling-decisions.md` §1; `docs/11-white-box-external-participants.md` |
| PB-03 | 3 | Must | Correlated message hand-off for every cross-pool transfer | LO2, LO4 | 8 | 2 | A | C | 68 message throw events and 10 catch events; every throw carries a `correlationKey` input mapping; message names are unique | PB-02 | Done | model file; `docs/03-test-record.md` §B1; `docs/04-modelling-decisions.md` §2 |
| PB-04 | 4 | Must | Lanes inside pools that cover more than one desk | LO2 | 5 | 1.5 | A | B | Every pool that covers more than one sub-role carries named lanes; participant names unchanged | PB-02 | Done | 14 lanes, e.g. `consultants_L0` / `consultants_L1`; `docs/03-test-record.md` §A7 |
| PB-05 | 5 | Must | Orthogonal layout engine: grid columns/rows, one track per flow, dedicated message channel | LO2, LO4 | 13 | 4 | B | A | Sequence-flow overlap 0 pairs, message-flow overlap 0 pairs, 0 diagonal px; both `hospital-patient-pathway-v2.svg` and `.png` regenerate | PB-02 | Done | `tools/layout_engine.py`; `docs/03-test-record.md` §A1–A3; `diagram/` |
| PB-06 | 6 | Must | Contain repetitive administration in collapsed sub-processes | LO2 | 8 | 2 | A | B | 3 collapsed sub-processes, each with a `<bpmn:documentation>` note; their steps remain in the XML and executable | PB-05 | Done | `SUB_Secretaries_Dispatch`, `SUB_CallHandling_Contact`, `SUB_Pathway_Report`; `docs/03-test-record.md` §A8 |
| PB-07 | 7 | Must | Every exception branch has an owner and an exit | LO4 | 13 | 4 | A | C | All 9 `bpmn:error` codes reachable from 18 boundary events; no exception branch terminates without an owner task, a retry, a timer or an escalation | PB-03 | Done | `docs/04-modelling-decisions.md` §4; `docs/03-test-record.md` §H1 |
| PB-08 | 8 | Must | Clinic-letter delay timers and the three-rung escalation ladder | LO4 | 8 | 2 | A | E | Boundary timers `P7D` and `R/PT168H` present; `letter.escalation-admin-manager` and `letter.escalation-higher-management` message chain present | PB-07 | Done | model boundary events; `docs/03-test-record.md` §H1 |
| PB-09 | 9 | Must | A Camunda Form on every user task | LO1 | 8 | 2.5 | D | A | 39/39 user tasks carry `zeebe:formDefinition`; 36 distinct forms exist and every bound form is defined | PB-02 | Done | `model/forms/` (36 `.form`); `docs/03-test-record.md` §H1, §H5d |
| PB-10 | 10 | Must | Role-based candidate group on every user task | LO1, LO5 | 5 | 1.5 | D | E | 39/39 user tasks carry `zeebe:assignmentDefinition` with a candidate group matching the pool's role | PB-09 | Done | `docs/03-test-record.md` §H1, §H5d |
| PB-11 | 11 | Must | Validation rules on the forms | LO1 | 5 | 1.5 | D | B | Required, length and numeric-range rules present on the fields that need them; long text is bounded | PB-09 | Done | 172 `validate` blocks across the 36 forms; `docs/01-gap-audit.md` §C2 |
| PB-12 | 12 | Should | Accessibility: field descriptions on every field, and grouping on long forms | LO1, LO5 | 5 | 1.5 | D | E | Every field has a description; forms longer than ~8 fields are split by group heading | PB-09 | **Partly done**: 71 descriptions across 230 fields; 0 `group` components emitted | form JSON census; `docs/01-gap-audit.md` §C3 |
| PB-13 | 13 | Must | One external worker per job type the model uses | LO2, LO4, LO5 | 21 | 6 | C | A | Every job type in the model has a subscribing worker; build green; subscriptions observed on the live gateway | PB-02 | Done | `workers/src/.../tasks/` (36 classes); `workers/README.md`; `docs/03-test-record.md` §E1–E2 |
| PB-14 | 14 | Must | Simulated external services with documented forced-failure switches | LO4 | 8 | 2.5 | C | E | The 5 simulated job types can each be forced to succeed or fail without editing code, through `application.yaml` or an environment variable | PB-13 | Done | `SimulatedFailureRegistry`; `workers/src/main/resources/application.yaml`; `workers/README.md` |
| PB-15 | 15 | Must | Duplicate suppression for bookings, charges and hand-offs | LO2, LO4 | 8 | 2 | C | B | Repeating a booking returns the same reference; a duplicate charge is detected before payment; the correlation-key purpose tag prevents a duplicate hand-off | PB-03, PB-13 | Done | `HospitalStore`; `workers/README.md`; `docs/04-modelling-decisions.md` §2 |
| PB-16 | 16 | Must | No storage or emission of complete card data | LO5 | 3 | 1 | C | E | No payment worker reads or writes a card-number, CVV or expiry variable; only a payment reference and status are returned | PB-13 | Done | `workers/README.md` job types 13 and 24 ("Never emits card data") |
| PB-17 | 17 | Must | Audit-trail workers that do not overwrite clinical variables | LO4, LO5 | 5 | 1.5 | C | A | Clinical and financial decisions produce an audit reference and timestamp; the audit workers refuse a blank `patientRef` and write no clinical variable back | PB-13 | Done | `workers/README.md` job types 2 and 3 |
| PB-18 | 18 | Must | Compensation for the two committed resources | LO2, LO4 | 13 | 4 | A | C | A compensation boundary event and `isForCompensation` handler on the appointment series and on the cycle booking; a compensation throw on the path that gives up; handlers typed `treatment.release-series` and `treatment.release-cycle-booking` | PB-07, PB-13 | Done for modelling; not triggered live | model `TRT_Bnd_CompSeries`, `TRT_Bnd_CompCycle`, `TRT_Comp_ReleaseSeries`, `TRT_Comp_ReleaseCycle`; `docs/04-modelling-decisions.md` §5 |
| PB-19 | 19 | Must | Counted retry with a cap and an escalation for unavailable external capacity | LO4 | 8 | 2 | A | C | A counted retry capped at 3; on exhaustion the provisional series is released and the case is handed to the pathway team, then retried in three days | PB-07 | Done | `TRT_Auto_RecordRetry` (`treatment.record-capacity-retry`); `docs/04-modelling-decisions.md` §4 |
| PB-20 | 20 | Must | Deploy the model and all forms in one batch, repeatably | LO5 | 5 | 1.5 | E | C | One command deploys 9 process definitions and 36 forms with no error, from a clean checkout, against `http://localhost:8080` | PB-05, PB-09 | Done | `tools/deploy.sh`; `docs/03-test-record.md` §C1, §H2a |
| PB-21 | 21 | Must | Normal-path run evidence | LO4 | 5 | 1.5 | E | C | Eleven steps reached; `incidents: none` reported at the end of each stage; log retained | PB-20 | Done | `screenshots/run-happy-path.log` |
| PB-22 | 22 | Must | Exception-path run evidence | LO4 | 5 | 1.5 | E | A | `REFERRAL_PACK_UNREADABLE` is thrown by the worker, caught by `SEC_Bnd_DocumentsUnreadable`, and the case joins the missing-information loop with no incident | PB-20 | Done | `screenshots/run-exception-path.log` |
| PB-23 | 23 | Must | Prove every form renders | LO1, LO5 | 3 | 1 | D | E | All 36 forms import and render in `@bpmn-io/form-js` with no unsupported field type | PB-09 | Done | `screenshots/camunda-forms-rendered.png`; `docs/03-test-record.md` §F4 |
| PB-24 | 24 | Must | Written test record and modelling decisions document | LO3, LO5 | 8 | 2.5 | E | A | Expected vs actual for every check run; every defect recorded; limitations stated before a reviewer finds them | PB-21, PB-22 | Done | `docs/03-test-record.md`, `docs/04-modelling-decisions.md` |

### 4.2 Sprint 2 items and deferred work

| ID | Rk | Pri | Item | Why (LO) | SP | d | 1st | 2nd | Acceptance criteria | Depends on | Status | Evidence |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PB-25 | 25 | Must | Preservation audit as executable checks | LO3, LO5 | 8 | 2.5 | E | B | Parsed checks over pools, user tasks, forms, candidate groups, job types, gateway types, error codes, timers and Camunda 7 attributes; all pass before a rebuild is accepted | PB-24 | Done | `tools/verify_preservation.py` (62 checks, 62 passed); `docs/03-test-record.md` §H1 |
| PB-26 | 26 | Must | Thin the drawn message flows to one line per pool pair, keeping exception hand-offs | LO2 | 8 | 2.5 | B | A | Message flows 66 → 31; dashed-line length 421,424 → 174,820 px; both run paths still clean afterwards | PB-25 | Done | `docs/05-v2.1-changes.md` §1; `docs/03-test-record.md` §H3 |
| PB-27 | 27 | Must | Merge routine end events, never exception ends | LO2 | 5 | 1.5 | B | E | End events 60 → 32; `_exception_ends()` keeps every exception end distinct | PB-26 | Done | `docs/05-v2.1-changes.md` §2 |
| PB-28 | 28 | Should | Consolidate single-step lanes into a neighbour lane of the same pool | LO2 | 3 | 1 | B | A | Lanes 20 → 14; no participant renamed or removed | PB-26 | Done | `docs/05-v2.1-changes.md` §3 |
| PB-29 | 29 | Must | Re-validate in the Modeler and export the diagram and per-pool sections | LO4, LO5 | 8 | 2.5 | B | E | Camunda Modeler 5.51.0 reports 0 errors on Camunda 8.10 (alpha); SVG and PNG regenerate; 15 section crops refreshed | PB-26 | Done | `screenshots/camunda-modeler-v2.1-status-bar.png`; `tools/render_diagram.sh`; `tools/export_sections.py`; `diagram/sections/` |
| PB-30 | 30 | Should | Drive the three branches that are modelled but not run: declined payment, confirmation lost, three-month escalation | LO4 | 8 | 2.5 | E | C | Each branch driven to its end state on the live engine, with a retained log and an Operate screenshot | PB-20 | **Carried over**, not run | `docs/03-test-record.md` §D3, §G, §H6e; `docs/02-status.md` ("Not done") |
| PB-31 | 31 | Should | Trigger compensation in a live run | LO4 | 5 | 1.5 | C | E | A compensation handler completes inside a real process instance, visible in Operate | PB-18, PB-20 | **Carried over**, not run | `docs/03-test-record.md` §D3 |
| PB-32 | 32 | Could | Fix the c8run Tasklist authentication so the forms draw in Tasklist | LO1, LO5 | 3 | 1.5 | E | D | The Tasklist Task tab renders a v2.0 form for a claimed task | PB-20 | **Carried over**: Tasklist gets `401` from `/v2/authentication/me`; environmental | `docs/03-test-record.md` §F5; `docs/02-status.md` |
| PB-33 | 33 | Could | Reduce message start events to ≤ 2 per pool by changing the message protocol | LO2 | 13 | 4 | A | C | Every hand-off publishes `Msg_<pool>` plus a `requestType` discriminator and each pool has one start event feeding a dispatch gateway | PB-03 | Not started; deferred, see `docs/05-v2.1-changes.md` §4 | arithmetic in `docs/05-v2.1-changes.md` §4 |
| PB-34 | 34 | Could | Crossing-reduction pass | LO2 | 8 | 2.5 | B | A | Sequence-flow crossings reduced from 197 without reintroducing an overlap | PB-27 | **Done in R3**: 94 crossings (−52%), 0 clipped lines, 0 overlaps held | `docs/06-diagram-engineering.md` §3.1, §3.4 |
| PB-35 | 35 | Should | Readable terminals and hand-offs: one end event per terminating path, and dashed lines cut to the hand-offs that carry an outcome | LO2, LO4 | 5 | 1.5 | B | D | Every end event has exactly one incoming sequence flow; no end event unreachable; every exception hand-off still drawn; no more than 15 message flows drawn | PB-27 | **Done in R3**: 66 end events, none merged; 15 drawn message flows. v14 raises the message-flow ceiling to 22 to connect the six outside participants | `docs/06-diagram-engineering.md` §3.5, §3.6; `docs/11-white-box-external-participants.md` |
| PB-52 | 52 | Won't (this release) | Replace the five simulated external services with real provider APIs | LO4 | — | — | C | E | Not applicable: out of scope for a local portfolio release | PB-14 | Won't (this release) | `workers/README.md` ("Simplifications and known gaps") |

---

## 5. Sprint backlogs

Sprint lengths, stand-up dates and review dates are planning values; no calendar
record exists in the workspace (Assumption A3).

### 5.1 Sprint 1, to Sprint Review 1, delivering the Initial Release (R1)

**Sprint Goal (agreed at planning).**
> Replace the v1.0 drawing with a measured layout engine and close the two
> behavioural gaps the gap audit found (exception branches with an owner, and
> compensation for committed resources), then prove the whole collaboration runs
> on a live engine with no incidents.

**Selection and control.** All 24 Sprint 1 items entered the sprint. PB-01 to
PB-05 came first, because every later item depends on the structure and the
layout; the sprint was deliberately not expanded when the forms defect (§B of
`docs/03-test-record.md`) was found. PB-12 was descoped during the sprint to
descriptions only, and the grouping half is retained as unfinished.

| Sprint 1 selection | Items | State at Sprint Review 1 |
|---|---|---|
| Analysis and structure | PB-01, PB-02, PB-03, PB-04, PB-06 | Completed |
| Drawing | PB-05 | Completed |
| Behaviour | PB-07, PB-08, PB-18, PB-19 | Completed for modelling; PB-18 not triggered live |
| Forms | PB-09, PB-10, PB-11, PB-12 | PB-09/10/11 completed; PB-12 partly done |
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

### 5.2 Sprint 2, to Sprint Review 2, delivering the second release (R2)

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
gates that apply to it, and write the evidence line. The second owner reviews and
covers. They reproduce at least one gate result themselves, read the evidence
rather than the claim, and should be able to take the item over within one working
session. No item is Done with only one owner's name on it (DoD-11). Where the two
owners disagree, the item stays In progress and the disagreement goes to the
stand-up; the first owner does not settle it alone. Cross-boundary items get a
second owner from the other side of the boundary: the forms items are second-owned
by the test lead, the worker items by the model lead. A claim of integration is
then checked by someone who did not build the integration.

**Cadence of hand-over.** A hand-over is an explicit act, not an email: the
artefact moves into the shared workspace, the gate output is pasted into the test
record, and the row in the log below is closed in the same session. The log is the
record of who held an item and when.

| HO | From → To | Artefact handed over | Trigger | Accepted how | Status |
|---|---|---|---|---|---|
| HO-01 | A → B | `tools/spec_v2.py` structure (pools, lanes, nodes, flows) | Structure frozen for Sprint 1 | B builds the layout from the spec and returns the overlap measures | Closed |
| HO-02 | B → A | Layout engine geometry and the analyse_layout output | After the first zero-overlap run | A confirms every node and flow is placed and no element moved between lanes | Closed |
| HO-03 | A → C | Model job types and error codes | Before worker work | C confirms every service task type and every BPMN error has a worker behaviour | Closed (three v2.0 types added afterwards, logged as HO-08) |
| HO-04 | D → E | 36 `.form` files | Before the render census | E runs the form-js census and reports failures | Closed; the first run failed, see `docs/03-test-record.md` §F4 |
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

**Retrospective format (timeboxed, after each review).** Three columns: what went
well, what did not, and one improvement action. The action must name a first
owner, a second owner and the sprint it lands in; an action with no owner is not
recorded. The retrospectives are in `docs/10-sprint-reviews-and-feedback.md` §3 and
§6.

**Continuous integration of contributions.** The workspace is integrated after
every accepted item, not at the deadline. The generator is re-run, the layout gate
and the preservation gate are executed, and the test record is updated in the same
change. The deterministic build does the integrating: `build_v2.py` is documented
as producing byte-identical output for the same inputs
(`docs/05-v2.1-changes.md` §5), so an unexplained diff is a real change to review,
not an accident of the tooling.

---

## 9. Assumptions

1. **A1. Team identity.** Owners in §§4–5 are recorded as the role letters described in §4. The four members of the group are named in `../../docs/Contribution-Matrix.md` and are identified by their initials in the delivered workbook. *Corrected:* this assumption previously read "no real names appear in any artefact in the workspace, or in this document", which was untrue — the contribution matrix names all four members and gives each a share.
2. **A2. Estimates.** Story points, ideal days and ranks in this document are planning values authored for it. Estimates also exist in the delivered workbook, whose `Workload` sheet records an estimate for each of its 58 items (397 SP; 151 in Sprint 1 and 246 in Sprint 2). *Corrected:* this assumption previously read "no estimate exists in any artefact in the workspace", which the workbook disproves.
3. **A3. Dates.** Sprint length, stand-up dates and review dates are not recorded anywhere in the workspace. They are treated here as planning values for two timeboxed sprints.
4. **A4. Repository.** The workspace is a Git repository, and it is the version record: commits are releases and `v14.0-final`, `sr1-snapshot` and `sr2-snapshot` are the release and review snapshots. This document was first written when that was not true — it said "There is no `.git` directory … (checked)". The configuration-management plan it points at, `docs/09-risk-contingency-and-config-management.md` §4.1 and A1, carries the same correction.
5. **A5. Job-type counts.** The shipped v16.0 model defines 48 service tasks drawing on 35 distinct job types, and 4 elements throw `publish-message`. The worker sources contain 36 task classes producing 37 job-type subscriptions (35 model types, one alias `pathway.find-overdue-clinic-letters`, and `publish-message`). The v2.0-era figures quoted in this document (47 service tasks, 68 throw events) describe the releases this document planned, not the shipped file. `workers/README.md` §4 carries the current catalogue and agrees with the counts above.
6. **A6. Diagram document (closed in R3).** The earlier `docs/06-visual-compaction.md` described a compaction that was never in the shipped model. In the third release that file was deleted and replaced by `docs/06-diagram-engineering.md`, which describes the drawing that is actually shipped and records the abandoned compaction as a rejected experiment with its measurements. The model file remains the source of truth; the drift is closed rather than carried.
7. **A7. Learning-outcome legend.** The full outcome wording is not reproduced in the workspace; the short forms in §1 are inferred from the descriptor/LO mapping used in `docs/01-gap-audit.md`.
8. **A8. Release naming.** "Initial Release" is R1 (v2.0) and the "second release" is R2 (v2.1). Both filenames are the same in the folder; the distinction is the content and the deployment version, not the path.

---

## 11. Crosswalk: the `PB-nn` items here and the delivered `Mj-nn` plan

The group planned the work twice, in two records with different scopes and different
identifier schemes. That was a mistake: it left the test plan tracing against
identifiers that the delivered workbook does not contain. The workbook is now the
plan of record. This section exists so the history stays readable and so no
`PB-nn` reference elsewhere in the folder is a dead key.

**Reading the table.** `Mj` is the row in `../../docs/GroupMj Product-Backlog.xlsx`
that carries the same work today. Where a `PB-nn` item describes an intermediate
step — a v2.0/v2.1 planning release, or a measurement now recorded inside one of the
delivered documents — it maps onto the item that owns that outcome.

### 11.1 Item crosswalk

| `PB-nn` | What it planned | `Mj-nn` today | Note |
|---|---|---|---|
| PB-01 | Gap audit against the 70%+ descriptors | Mj50 | The measurement lives in `01-gap-audit.md`; Mj50 owns the plan |
| PB-02 | One collaboration of the case-study participants | Mj15 | Scope changed: v16.0 ships one hospital pool + 6 outside participants, not 15 processes |
| PB-03 | Correlated message hand-off per cross-pool transfer | Mj15, Mj28 | 15 message flows on the shipped file |
| PB-04 | Lanes inside multi-desk pools | Mj15 | 3 responsibility lanes holding 9 team lanes |
| PB-05 | Orthogonal layout engine | Mj15 | `06-diagram-engineering.md` |
| PB-06 | Collapsed sub-processes for repetitive admin | Mj15 | |
| PB-07 | Every exception branch has an owner and an exit | Mj16, Mj21, Mj23 | |
| PB-08 | Letter delay timers and escalation ladder | Mj25 | |
| PB-09 | A form bound to every user task | Mj36–Mj44 | 38 user tasks, 37 forms |
| PB-10 | Candidate group on every user task | Mj15, Mj46 | |
| PB-11 | Form validation | Mj45 | |
| PB-12 | Accessibility and field descriptions | Mj45 | Delivered: 237/237 fields described, 15 groups |
| PB-13 | A worker per job type | Mj29–Mj34 | |
| PB-14 | Simulated services and forced-failure switches | Mj29–Mj33, Mj53 | |
| PB-15 | Duplicate suppression | Mj22, Mj33 | |
| PB-16 | No card data in any variable | Mj41, Mj48 | |
| PB-17 | Audit workers that do not overwrite | Mj47 | |
| PB-18 | Compensation for committed resources | Mj20 | |
| PB-19 | Capped external-capacity retry | Mj20, Mj33 | |
| PB-20 | Deployment configuration | Mj28, Mj58 | |
| PB-21 | Normal-path run evidence | Mj52, Mj56 | |
| PB-22 | Exception-path run evidence | Mj52 | |
| PB-23 | Form rendering census | Mj44, Mj53 | |
| PB-24 | Test record and modelling decisions | Mj50, Mj51, Mj55 | |
| PB-25 | Preservation audit | Mj55 | The tool that ran it has been removed; see §11.3 |
| PB-26 | Message-flow thinning | Mj15 | |
| PB-27 | One end event per terminating path | Mj15 | |
| PB-28 | Lane consolidation | Mj15 | |
| PB-29 | Modeler validation and export | Mj54, Mj57 | |
| PB-30 | Driving the undriven branches | Mj52 | Partly: 8 scenarios on v16.0; the worker failure paths remain **not run** |
| PB-31 | Live compensation trigger | Mj20, Mj52 | Achieved on v16.0: `screenshots/run-v16-compensation.log` |
| PB-32 | Tasklist form display | Mj45, Mj54 | Achieved on v16.0: `screenshots/v16/tasklist-form-rendered.png` |
| PB-33 | Start-event reduction | Mj15 | Deferred, with the arithmetic recorded in `05-v2.1-changes.md` §4 |
| PB-34 | Crossing-reduction pass | Mj15, Mj57 | Measured in `screenshots/v16/convergence-audit.txt` |
| PB-35 | Readable terminals and hand-offs | Mj15 | |
| PB-36 | Rebuild the model as one hospital pool | Mj15 | Achieved; `17-single-pool-operational-model.md` |
| PB-37 | Deploy and drive every scenario | Mj52 | 8 scenarios COMPLETED |
| PB-38 | Build checks on the form↔model contract | Mj28, Mj53 | `tools/spec_v3.py` |
| PB-39 | Accessibility pass, contrast measured | Mj45, Mj54 | |
| PB-40 | Stand-up and sprint-review records | Mj05, Mj09, Mj06, Mj10 | Partly: reconstructed, not contemporaneous |
| PB-41 | Rebuild the worker jar from shipped source | Mj35, Mj58 | |
| PB-42 | Repair the two results their evidence contradicted | Mj46, Mj55 | |
| PB-43 | Index citations to files no longer in the tree | Mj58 | `18-cited-files-no-longer-present.md` |
| PB-44 | Correct the falsely-Done backlog rows | Mj45, Mj46, Mj47 | Those three now read "Partly done" |
| PB-45 | Worker unit tests and an engine integration test | Mj35 | 52 tests; the 38 domain `execute()` methods still have none |
| PB-46 | A recorded demonstration with a person filling forms | Mj56, Mj57 | **Not done:** no person has completed a form through Tasklist |
| PB-47 | Worker failure paths on v16.0 | Mj55 | 4 pass, 1 loops, 1 never thrown, 2 without a run — `docs/03` §K3 |
| PB-48 | Grouped forms submitted fields one level deep | Mj45 | Fixed and guarded |
| PB-49 | A textarea read as a list | Mj39, Mj45 | Fixed and guarded |
| PB-50 | A hidden required field submitted empty | Mj39, Mj45 | Fixed and guarded |
| PB-51 | Empty document checklist | Mj36 | Fixed |
| PB-53 | The six rows that still read Done without meeting their acceptance criteria | Mj01, Mj33, Mj35, Mj54, Mj56, Mj57 | Done 53 → 47, Partly done 3 → 9 |
| PB-52 | Real provider APIs instead of simulated services | — | Out of scope, stated as a limitation |

### 11.2 Test cases by delivered item

`08-test-plan.md` §8 traces against `Mj-nn`. The `PB-nn` keys below are the
historical ones; the test-case identifiers are unchanged.

| `Mj-nn` | `PB-nn` | Test cases |
|---|---|---|
| Mj15 | PB-02, PB-03, PB-04, PB-05, PB-06, PB-26, PB-27, PB-28, PB-33, PB-34, PB-35, PB-36 | TC-BPMN-01…-09, -13, -15, -18, -20, -21, -22, -24, -25 |
| Mj16 | PB-07 | TC-BPMN-16, TC-WRK-05, TC-E2E-02 |
| Mj20 | PB-18, PB-19, PB-31 | TC-BPMN-16, TC-E2E-06 |
| Mj25 | PB-08 | TC-E2E-05 |
| Mj28 | PB-20, PB-38 | TC-DEP-01…-04 |
| Mj33 | PB-15, PB-19 | TC-WRK-07, -08, -09 |
| Mj36–Mj44 | PB-09, PB-23 | TC-BPMN-19, TC-FRM-01, TC-FRM-02, TC-FRM-06 |
| Mj41 | PB-16 | TC-NFR-01, TC-NFR-08 |
| Mj45 | PB-11, PB-12, PB-32 | TC-FRM-03, -04, -05, -07, -08 |
| Mj46 | PB-10 | TC-BPMN-10, TC-NFR-02 |
| Mj47 | PB-17 | TC-NFR-02, TC-NFR-03 |
| Mj50, Mj51 | PB-01, PB-24 | TC-BPMN-11, TC-E2E-08 |
| Mj52 | PB-21, PB-22, PB-30 | TC-E2E-01…-05 |
| Mj54 | PB-29, PB-32 | TC-BPMN-10, TC-BPMN-11, TC-NFR-06 |
| Mj55 | PB-25, PB-45 | TC-BPMN-12, -13, -14, -17, -18 |
| Mj57 | PB-29, PB-34 | TC-BPMN-04, -09, -22 |

### 11.3 Known disagreements between this document and the delivered artefacts

Corrections are applied here rather than carried, so that a reader does not have to
work out which record to trust:

| This document said | The delivered artefact says | Where |
|---|---|---|
| Team of five, owners A–E | Four members, initials T/D/Y/L | `../../docs/Contribution-Matrix.md`; the workbook |
| No real names in any artefact | All four are named with shares | Corrected in A1 above |
| No estimate in any artefact | 397 SP over 58 items | Corrected in A2 above |
| 47 service tasks, 68 throw events | 48 service tasks, 4 throw events | Corrected in A5 above |
| 9 executable processes, 36 forms | 1 executable process, 37 forms | §2; `README.md` |
| PB-35 used for two different items | — | The deferred integration item is now PB-52 |
| Traceability keyed to `PB-nn` | The workbook uses `Mj-nn` | §11.2; `08-test-plan.md` §8 |

---

## v16.0 rows (the R5 change set)

> **Read §11 first.** These rows are the release history of the v16.0 rebuild. Their
> `PB-nn` identifiers crosswalk to the delivered workbook in §11.1. The columns are
> the same as §4.1, so an item here can be read the same way.

The audit that started this increment found the v16.0 model absent from version
control, a regression of DEF-02, two results contradicted by their own cited evidence
and a shipped jar built from an earlier release; PB-36 to PB-44 are the response, and
PB-48 to PB-51 are the defects a person found afterwards by using Tasklist.

| ID | Rk | Pri | Item | Why (LO) | SP | d | 1st | 2nd | Acceptance criteria | Depends on | Status | Evidence |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PB-36 | 36 | Must | Rebuild the operational model as one hospital pool with responsibility lanes | LO2, LO4 | 21 | 6 | A | B | One executable process; 3 responsibility lanes holding 9 team lanes; 7 participants; every user task bound to a form and a candidate group; every service task bound to a job type | PB-07 | **Done** | `model/UFCEP6-0-3_Hospital_Patient_Pathway_v16.bpmn`; `docs/17-single-pool-operational-model.md` |
| PB-37 | 37 | Must | Deploy the rebuilt model and drive every scenario end to end | LO2, LO4, LO5 | 13 | 4 | E | A | Each scenario ends `COMPLETED` with no incident left open, driven only by the fields of the bound forms | PB-36 | **Done for the eight scenarios in `docs/03` K2; NOT RUN for the worker failure paths in K3** | `screenshots/run-v16-*.log`; `screenshots/v16/engine-record.txt` |
| PB-38 | 38 | Must | Build checks that refuse a model whose conditions do not match its forms | LO2, LO5 | 8 | 2.5 | A | C | A generator that emits a model whose gateway conditions disagree with the bound form fails the build, with the offending condition named | PB-36 | **Done** | `tools/spec_v3.py` (`check_conditions`, `check_gateway_variables`, `check_gateway_sources`, `check_option_values`, `check_form_worker_types`) |
| PB-39 | 39 | Should | Accessibility pass over every form | LO1, LO5 | 8 | 2.5 | D | E | Every field carries a description; every control carries a human label; every choice offers words; every long form is grouped **and the contrast of the rendered form is measured** | PB-36 | **Done** | `tools/audit_accessibility.py`; `tools/audit_rendered_contrast.py`; `screenshots/v16/accessibility-report.json`; `screenshots/v16/tasklist-contrast.json`; `docs/20-accessibility-and-the-forms.md` |
| PB-40 | 40 | Must | Stand-up and sprint-review records | LO3, LO5 | 5 | 1.5 | E | A | Both stand-ups recorded with progress, evidence, next action, blocker and handover; both reviews recorded with the increment, the decisions and what was carried | PB-37 | **Partly done** — reconstructed from the commit log; no contemporaneous notes existed | `docs/19-standups.md`; `docs/10-sprint-reviews-and-feedback.md` §R5 |
| PB-41 | 41 | Must | Rebuild the worker jar from the shipped source | LO4, LO5 | 3 | 1 | C | E | The jar in the tree contains `hospital/db/`, `DateRuleValidator`, `JobSecurity`, the H2 driver and the current `date-rules.json`, and the documented run command starts the shipped code | PB-36 | **Done** | `workers/target/hospital-external-workers-1.0.0.jar` (32,058,075 bytes) |
| PB-42 | 42 | Must | Repair the two results whose cited evidence contradicted them | LO5 | 5 | 1.5 | E | A | The RBAC capture that reads all zeros is headed as such and its citations repointed; the compensation claim is corrected in place and compensation is modelled and run | PB-37 | **Done** | `screenshots/v15/users-roles-authorizations.txt`; `docs/14-feedback-response.md` §1; `docs/16-acceptance-criteria.md` §6 |
| PB-43 | 43 | Should | Index every citation to a file that is no longer in the tree | LO5 | 3 | 1 | E | B | Every cited path that no longer exists is listed with what replaced it, and the affected documents point at the index | — | **Done** | `docs/18-cited-files-no-longer-present.md` |
| PB-44 | 44 | Must | Correct the backlog rows the team had recorded as falsely Done | LO3, LO5 | 2 | 0.5 | E | A | Mj45, Mj46 and Mj47 no longer read Done | — | **Done** | `docs/GroupMj Product-Backlog.xlsx`; `docs/16-acceptance-criteria.md` §5 |
| PB-45 | 45 | Must | Worker-layer unit tests and an engine integration test | LO5 | 13 | 4 | C | E | `AbstractHospitalWorker`'s complete / BPMN-error / fail-with-retries mapping is covered, `JobContext` validation is covered, and at least one `execute()` is covered end to end against an engine | PB-41 | **Partly done** — 52 tests, of which `JobContext` (16) and `AbstractHospitalWorker` (6) are new, so the base class is covered; no engine integration test, and the 38 `execute()` methods still have none | `workers/src/test/`; `TestJob.java` and `RecordingJobClient.java` for the doubles; `docs/03` §K6 |
| PB-46 | 46 | Should | A recorded demonstration with a person filling the forms in Tasklist | LO1, LO4, LO5 | 5 | 1.5 | E | D | A recording of a case driven through Tasklist by hand, with the service tasks visibly completing behind it | PB-37, PB-39 | **Partly done** — the form is now opened, measured and photographed in the real Tasklist (`docs/20`), but no person has completed one. A scripted attempt to fill the pack-check form could not satisfy it: `Complete Task` stayed disabled, which is the clearest statement of why this one needs a person | `screenshots/v16/tasklist-form-rendered.png`; `screenshots/v16/tasklist-contrast.json`; `docs/20` |
| PB-47 | 47 | Must | Worker failure paths on v16 | LO4, LO5 | 8 | 2.5 | E | C | Each of the nine error codes driven on the shipped model, with a retained log and the incident count | PB-37 | **Partly done** — run on 2026-10-18: `PAYMENT_CONFIRMATION_LOST`, `CORRESPONDENCE_SERVICE_FAILED`, `CHARGE_CALCULATION_FAILED` and `EXTERNAL_RESOURCE_UNAVAILABLE` pass; `SCHEDULING_SERVICE_UNAVAILABLE` is caught but sits in an unbounded retry loop (K5.8); `TREATMENT_REQUEST_UNAUTHORISED` is never thrown (K5.9); `PAYMENT_PROVIDER_UNAVAILABLE` has no scenario run and `INVALID_DATE` is exercised only by unit test | `docs/03-test-record.md` §K3; `screenshots/v16/failure-path-runs.md` |
| PB-48 | 48 | Must | Grouped forms submitted their fields one level deep, so no worker could read them | LO1, LO2, LO5 | 5 | 1.5 | D | C | No form field is submitted under a group prefix; the grouping stays for the reader | PB-39 | **Done** — found by a person using Tasklist; every automated run filled the forms over the API and never rendered one | `tools/fix_form_group_paths.py`; guard `forms_inventory.py` `KEY_NESTED_BY_GROUP_PATH`; `docs/20` |
| PB-49 | 49 | Must | A textarea read as a list broke the funding approval | LO2, LO5 | 3 | 1 | C | D | A free-text answer is accepted wherever a limitation is recorded, and no worker reads a list from a field that submits a string | PB-41 | **Done** | `JobContext.stringListOrText`; guard `spec_v3.check_form_worker_types`; `docs/20` |
| PB-50 | 50 | Must | A hidden required field submitted empty and failed two steps later | LO1, LO2, LO5 | 3 | 1 | D | C | No conditional compares a string-valued field against an unquoted boolean; a required field that is hidden is reported | PB-39 | **Done** | `model/forms/record-consent-and-treatment-request.form`; guard `forms_inventory.py` `CONDITIONAL_TYPE_MISMATCH`; `docs/20` |
| PB-51 | 51 | Must | The document checklist could be submitted empty, sending the case round the missing-information loop | LO1, LO4 | 2 | 0.5 | D | E | The referral pack check cannot be submitted with no documents stated | PB-48 | **Done** | `model/forms/check-referral-pack.form` (`supportingDocuments` required) |
| PB-53 | 53 | Must | Six backlog rows read Done while a clause of their acceptance criterion had no evidence | LO3, LO5 | 2 | 0.5 | E | A | A row reads Done only when every clause of its acceptance criterion has evidence; where a clause is missing the row reads Partly done and names the missing clause | PB-44 | **Done** — Mj01, Mj33, Mj35, Mj54, Mj56 and Mj57 moved to Partly done on 2026-10-18; Done 53 → 47, Partly done 3 → 9 | `docs/GroupMj Product-Backlog.xlsx` ("Product Backlog" sheet, Description column); `docs/16-acceptance-criteria.md` §5 |
