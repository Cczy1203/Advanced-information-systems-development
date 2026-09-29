# Sprint reviews, retrospectives and the feedback action log

This is the review and feedback record for the two sprints. Sprint goals and item
IDs come from `docs/07-product-backlog.md`; acceptance evidence is the file named
in `docs/03-test-record.md` and present in `screenshots/` or `diagram/`. No dates,
attendee lists or verbatim quotation of stakeholder remarks survive in the
workspace, so the document records *what was shown, decided and agreed*. It makes
no claim about who said it or when; the gaps are listed under Assumptions.

Read with: `docs/07-product-backlog.md` (goals, owners, Definition of Done),
`docs/08-test-plan.md` (test results quoted here), `docs/02-status.md` (what is
not done), `docs/04-modelling-decisions.md` §7 (limitations),
`docs/05-v2.1-changes.md` (the R2 change set).

---

## 1. Sprint Review 1: Initial Release (R1)

**Sprint goal.**
> Replace the v1.0 drawing with a measured layout engine and close the two
> behavioural gaps the gap audit found (exception branches with an owner, and
> compensation for committed resources). Then prove the whole collaboration runs
> on a live engine with no incidents.

**Increment shown.** The v2.0 build: the collaboration, the regenerated forms,
the rebuilt workers, and both scripted paths run live against c8run
8.10.0-alpha5.

### 1.1 Acceptance evidence presented

| Item | Acceptance evidence shown | Reviewer outcome |
|---|---|---|
| PB-01 gap audit | `docs/01-gap-audit.md`, with the v1.0 measurements from `tools/analyse_layout.py` | Accepted: every rubric descriptor answered with a number or an artefact |
| PB-02 – PB-04 structure, lanes, messages | Model opened in the Modeler; 15 participants, 14 lanes, 9 executable processes | Accepted |
| PB-05 layout | `python3 tools/analyse_layout.py` output: sequence-flow overlaps 0 pairs, message-flow overlaps 0 pairs, 0 diagonal px | Accepted, because the two rows the build is gated on are zero |
| PB-06 collapsed sub-processes | 3 collapsed sub-processes, steps still in the XML | Accepted |
| PB-07 – PB-08 exception owners and letter timers | 9 error codes, 18 boundary events; `P7D` and `R/PT168H` present | Accepted |
| PB-09 – PB-11 forms | 36 forms on 39 user tasks, candidate group on every task, validation present | Accepted |
| PB-12 accessibility | Descriptions on some fields; **no grouping headings** | **Not accepted as complete**: recorded as partly done |
| PB-13 – PB-17 workers | `mvn` build green; subscriptions observed; the three v2.0 job types registered; card-data and audit rules inspected | Accepted |
| PB-18 compensation | Model wiring shown (2 boundary compensation events, 2 handlers, 2 throws) | Accepted for modelling; **live trigger not shown** |
| PB-19 capped retry | `TRT_Auto_RecordRetry` and the cap-3 chain | Accepted |
| PB-20 – PB-22 deployment and paths | Deploy output (9 process definitions, 36 forms); `run-happy-path.log` (11 steps, `incidents: none`); `run-exception-path.log` (`REFERRAL_PACK_UNREADABLE` caught, case joins the missing-information loop, no incident) | Accepted; demonstrated live |
| PB-23 form rendering | `TOTAL=36 FAILED=0` against form-js; `screenshots/camunda-forms-rendered.png` | Accepted |
| PB-24 records | `docs/03-test-record.md`, `docs/04-modelling-decisions.md` | Accepted |

### 1.2 What was demonstrated

The normal path was driven end to end: referral message → Medical Secretaries
document check → Consultant decision → Outpatient Bookings slot choice →
Call Handling telephone contact → attendance and consent → authorised treatment
request → Finance funding decision → payment → treatment confirmation → clinic
letter drafted, processed and sent. The unreadable-referral exception path was
then driven and held at `SEC_EGW_InfoRequest` with no incident. The model was
opened in Camunda Modeler 5.51.0 on Camunda 8.10 (alpha) and the layout analyser
was run in front of the review.

### 1.3 What was not finished

| Item | State | Stated at the review |
|---|---|---|
| PB-12 (grouping half) | Descriptions on some fields only; no group headings emitted | Not delivered; no `group` component exists in any form |
| PB-18 (live trigger) | Compensation modelled, handlers registered, never fired | Modelled and testable; not demonstrated |
| PB-30 scope (branch runs) | Declined payment, confirmation lost and the three-month escalation not driven | Not reviewed in this sprint; they were not in the Sprint 1 committed set but were named as the remaining behavioural gap |
| PB-32 scope (Tasklist) | Tasklist Task pane blank; `401` from `/v2/authentication/me` | Environmental; forms proven by the renderer census instead |

### 1.4 Decisions made

| # | Decision | Reasoning |
|---|---|---|
| D1 | Zero overlaps is prioritised over crossing count | The brief names overlap and parallel adjacency as the fault and crossing only as something to minimise; spreading routes across corridors removes the overlaps but creates crossings |
| D2 | The four external suppliers stay black-box participants | The 4 MB deployment batch ceiling makes a further executable process expensive, and their internals cannot be verified from the case study |
| D2 (revisited, v14) | **Reversed.** All six outside participants now carry a small message-driven process and a drawn hand-off in each direction | The case study *does* describe the boundary well enough to draw it: slots returned, dispatch result returned, payment status and reference returned, capacity reported. Three of the six pools had no drawn connection at all, which read as a modelling mistake. The batch ceiling is now an explicit, open risk, no longer the reason for the omission: `docs/11-white-box-external-participants.md` §5, `docs/09` R-01 |
| D3 | The three embedded sub-processes stay collapsed | No `no-bpmndi` warnings inside a collapsed box; drawing them open was measured against the closed form and deferred |
| D4 | The Tasklist authentication `401` is treated as environmental | All 36 forms render in the renderer Tasklist uses, so the Forms deliverable does not depend on the webapp |
| D5 | Collapsed sub-process steps are not given their own diagram interchange | The warnings they produce are `no-bpmndi`, which is a drawing omission rather than a modelling error |

### 1.5 Questions raised

| # | Question | Immediate answer | Followed up as |
|---|---|---|---|
| Q1 | How many dashed message lines does the diagram actually carry, and are they all needed? | 66 at the time; Camunda 8 does not read a message flow at run time, so the drawing can carry one per pool pair | FB-01 → carried into Sprint 2 as PB-26 |
| Q2 | Why did crossings rise from 42 to 148? | The measured price of removing overlaps; A/B will confirm | FB-02 |
| Q3 | What are the 30 Modeler warnings? | All one rule, `no-bpmndi`, inside the collapsed sub-processes | FB-04 |
| Q4 | Can the forms be proven without Tasklist? | Yes: form-js is the renderer Tasklist uses | FB-05 |
| Q5 | Why are there 43 start events when the target was two per pool? | A Camunda 8 message start subscribes to one message name; collapsing them changes the message protocol | FB-06 |
| Q6 | Does compensation work? | It is wired and the handlers register; it has not been triggered | FB-07 / PB-31 |

### 1.6 Limitations stated at the review

Taken from `docs/04-modelling-decisions.md` §7 and `docs/02-status.md`: crossings
rose; four flows clip a boundary event; the canvas is a single very large diagram
(exported as SVG and per-pool crops for that reason); the four external suppliers
are deterministic stubs; idempotency state is in memory; the deployment batch
ceiling constrains the design; three branches are modelled but not run; and
Tasklist cannot draw the forms because of the local `401`.

---

## 2. Retrospective 1

| What went well | What did not | Improvement action for Sprint 2 |
|---|---|---|
| The gap audit was measured rather than asserted, so the rebuild had a target list instead of a redraw | The forms `date` field-type defect (DEF-12) and the import-order defect (DEF-13) were found very late, by accident of checking the renderer, not by a planned test | Add the form-js render census to the standing gate set so a field-type defect cannot survive to the end again. Owner D, second E. |
| Running the model, not reading it, found eleven real structural defects (DEF-01 to DEF-11), several of which would have broken a live demonstration | A drawing-only change in Sprint 2 could silently drop a scored element; nothing checked that a rebuild preserved the previous release | Build the executable preservation audit before any Sprint 2 drawing change (owner E, second B). |
| The layout gate is objective and cheap: two numbers must be zero before a build is accepted | The crossing regression (42 → 148) was only explained after the review raised it; the trade-off was not written down before the change was accepted | Record a written trade-off (the A/B numbers) in `docs/05-v2.1-changes.md` for any measure that gets worse; owner B, second A. |
| The two-owner pattern worked: every hand-over in `docs/07-product-backlog.md` §7 was accepted by someone who did not make the change | The three undriven branches were known at the Sprint 1 review and still were not run | Drive the three branches early in Sprint 2, before the compaction work: owner C, second E (see FB-07, not carried out). |

**Actions agreed at Retrospective 1.** Three of the four were completed. The
fourth, running the three undemonstrated branches early in Sprint 2, was not
carried out; committed compaction work and the preservation gate displaced it.
The reason is recorded, and the outstanding impact is that `TC-E2E-03` to
`TC-E2E-05` remain `NOT RUN` and risk R-05 stays open. It stays on the list
as FB-07.

---

## 3. Sprint Review 2: second release (R2)

**Sprint goal.**
> Reduce the drawn density of the shipped model without removing a single scored
> element, and re-prove the behaviour afterwards on the rebuilt file.

**Increment shown.** The v2.1 rebuild: thinner drawing, same elements, both paths
re-run, model re-validated in the Modeler.

### 3.1 Acceptance evidence presented

| Item | Acceptance evidence shown | Reviewer outcome |
|---|---|---|
| PB-25 preservation gate | `python3 tools/verify_preservation.py` → **62 checks, 62 passed, 0 failed** | Accepted: the gate ran before the change, as agreed at Retrospective 1 |
| PB-26 message-flow thinning | Message flows 66 → 31; dashed line 421,424 px → 174,820 px (−59%); exception hand-offs kept in preference to routine ones | Accepted |
| PB-27 end-event merge | End events 60 → 32; `_exception_ends()` walks forward from every boundary event so exception ends stay distinct | Accepted |
| PB-28 lane consolidation | Lanes 20 → 14; the 15 participants and their names untouched | Accepted |
| PB-29 Modeler and export | Camunda Modeler 5.51.0 on Camunda 8.10 (alpha), **0 errors**; `tools/validate_model.js` 0 warnings, 0 unresolved references; SVG and PNG regenerated; 15 section crops refreshed | Accepted |
| Behaviour re-proof | Both paths re-run on the rebuilt file: normal path all steps with `incidents: none`; exception path held at `SEC_EGW_InfoRequest` with `incidents: none` | Accepted |
| Deployment | 9 process definitions at v17 and 36 forms at v18 | Accepted |
| Evidence refresh | `operate-dashboard.png` (21 running instances, 0 with an incident), `operate-instance-completed.png` (executed steps and real variables), `tasklist-open-tasks.png` | Accepted |

### 3.2 What was demonstrated

Both paths from Sprint 1 were re-run on the rebuilt v2.1 file. That is the
substantive claim of R2: removing 35 drawn dashed lines and 28 end circles
changed only the drawing. The preservation audit and the two clean runs are the
evidence. The Modeler was opened live to show the status bar at 0 errors.

### 3.3 What was not finished

| Item | State | Stated at the review |
|---|---|---|
| PB-30 three branches | Not started | Still modelled, still not run; the reason is that the committed compaction work and the preservation gate took the sprint |
| PB-31 live compensation | Not started | Same reason |
| PB-32 Tasklist authentication | Not started | `401` unresolved; forms proven by the renderer census |
| PB-33 start-event reduction | Deferred | Requires a message-protocol change; arithmetic recorded in `docs/05-v2.1-changes.md` §4 |
| PB-34 crossing reduction | Deferred | Crossings are 197, up from 147, as the measured cost of merging end events |
| PB-12 grouping | Still not delivered | Open gap |

### 3.4 Decisions made

| # | Decision | Reasoning |
|---|---|---|
| D6 | Accept the crossing rise (147 → 197) as the price of 28 fewer end circles | A/B measured: pool-wide merge gives 27 ends and 208 crossings; the lane-scoped variant gives 32 ends and 197 crossings and was chosen as the better of the two |
| D7 | Keep the three sub-process boxes collapsed | Drawing them open measured 21 lines through a shape against 4, and added 3 overlaps; the closed form is the better read |
| D8 | Treat the model file as the source of truth and fix the prose that disagreed with it | The shipped file matches `README.md`, `docs/02-status.md`, `docs/03-test-record.md` and `docs/05-v2.1-changes.md`; the drifted document was a configuration-management item, not a model change. **Executed in R3:** it was deleted and replaced by `docs/06-diagram-engineering.md` |
| D9 | Do not bump `versionTag` for this release | Left as a recorded shortcoming; the engine deployment versions identify the release in the meantime |
| D10 | Carry PB-30 to PB-35 into the next cycle, with no attempt to compress them into the remaining time | They are Should or Could items; the Must items of both releases are delivered |

### 3.5 Questions raised

| # | Question | Immediate answer | Followed up as |
|---|---|---|---|
| Q7 | If 30 Modeler warnings remain, is the model valid? | Yes: all 30 are `no-bpmndi` inside the collapsed sub-processes; nothing is reported as an error, and the parser gate is clean | FB-04 closed |
| Q8 | Does the thinner drawing still run? | Both paths re-run with `incidents: none`; Camunda 8 does not read a message flow at run time | Closed |
| Q9 | Why is the worker README table short of job types? | The three v2.0 types were added to the code and the model but not to the table, whose summary line is also stale | FB-09 |
| Q10 | Is the version tag right for this release? | No, it still reads 2.0.0 | FB-10 |
| Q11 | Which document describes the shipped diagram? | The model file; `docs/06` described a further pass that was not in it. R3 replaced that document | FB-11 (closed) |
| Q12 | Where is the version-control history? | There is no repository in the workspace | FB-12 |

### 3.6 Limitations stated at the review

Everything from Sprint Review 1 §1.6 still applies, plus two reduction targets
that remain unmet (43 start events, 197 crossings), the four clipped lines and the
30 accepted Modeler warnings. The three undriven branches, the un-triggered
compensation, the Tasklist gap and the documentation drift items are unchanged.
The whole model remains a local, single-instance demonstration over simulated
external services.

---

## 4. Retrospective 2

| What went well | What did not | Improvement action for the next cycle |
|---|---|---|
| The preservation gate was built first, exactly as agreed at Retrospective 1, and it caught the question of whether a drawing change had touched anything scored | The documentation drifted from the artefact: one document described a diagram state that was never shipped, the worker README table was three job types short, and a cited screenshot does not exist | Correct the drift items before submission. Owner E, second A. R3 closed three of the four: the drifted diagram document was deleted and replaced by `docs/06-diagram-engineering.md`, the worker catalogue was completed, and the drawing itself was re-engineered (197 → 94 crossings, 4 → 0 clipped lines). Two readability changes followed, one end event per terminating path (32 → 65, none merged) and dashed lines cut from 31 to 15. The missing screenshot (DEF-17) stays open |
| The compaction was measured before and after, and the one regression (crossings) was confirmed by A/B | The three undriven branches were known for two sprints and still were not run | Schedule the branch runs as the first item of the next cycle, before any drawing work; owner C, second E. |
| Re-opening the model in the Modeler cleared the open question from the gap audit, and the parser gate now reports 0 warnings and 0 unresolved references | No version-control repository exists, so the baseline depends on folder copies | Initialise a repository and commit the released state as the baseline (owner E, second A). |
| Both paths were re-run on the rebuilt file, so R2 is backed by behaviour and not only by measurement | Accessibility remains partly delivered: no grouping headings and no WCAG check | Emit `group` components in `tools/forms_spec.py` for the long forms and re-run the render census; owner D, second E. |

**Actions agreed at Retrospective 2.** All four are open actions carried into the
next cycle; none is claimed as done. They sit in the feedback action log below so
that the next sprint starts with them.

---

## 5. Feedback action log

Consolidated log for both reviews, both retrospectives, and the two internal
planning reviews held while writing `docs/07`–`docs/10`. **Source** distinguishes a
review item from an internal one; an internal item is not presented as stakeholder
feedback.

| FB | Source | Issue raised | Agreed response | 1st owner | 2nd owner | Completion evidence | Status |
|---|---|---|---|---|---|---|---|
| FB-01 | Sprint Review 1 (Q1) | The diagram carries 66 dashed message lines; the review asked whether that many are needed | Draw one representative message flow per pool pair, preferring exception hand-offs, and prove the paths still run | B | E | `docs/05-v2.1-changes.md` §1 (66 → 31; 421,424 → 174,820 px); `docs/03-test-record.md` §H3 (both paths clean) | **Complete** |
| FB-02 | Sprint Review 1 (Q2) | Crossings rose from 42 to 148 and were not explained at the time | Confirm by A/B measurement, document it as an accepted trade, and defer a crossing-reduction pass | A | B | `docs/05-v2.1-changes.md` §4 A/B table; backlog PB-34 | **Complete** (explained and accepted; not fixed) |
| FB-03 | Sprint Review 1 | Four flows clip a boundary event | Record the clipping; moving the boundary events would detach them from their host edge | B | A | `docs/05-v2.1-changes.md` §4 (named flows); `docs/03-test-record.md` §A4 | **Not carried out as a fix.** Reason: moving the events costs more than the few clipped pixels. Outstanding impact is cosmetic, tracked as risk R-10 and test `TC-BPMN-04` |
| FB-04 | Sprint Review 1 (Q3) | The Modeler reports 30 warnings | Analyse them, establish whether they are errors, and decide the closed-vs-open sub-process question with measurements | A | B | `docs/05-v2.1-changes.md` §4 (30 `no-bpmndi`, 0 errors; open variant measured at 21 lines through a shape vs 4); `screenshots/camunda-modeler-v2.1-status-bar.png` | **Complete** |
| FB-05 | Sprint Review 1 (Q4) | The Tasklist Task pane is blank | Prove the forms with the renderer Tasklist uses, fix any real defect found, and treat the residual authentication failure as environmental | D | E | `docs/03-test-record.md` §F4 (DEF-12 and DEF-13 fixed; `TOTAL=36 FAILED=0`); `screenshots/camunda-forms-rendered.png` | **Partly complete**: form defects fixed; the `401` remains (FB-14, PB-32) |
| FB-06 | Sprint Review 1 (Q5) | Start events are 43 against a target of ≤ 2 per pool | Record the arithmetic and the protocol change required, and defer it; the message contract of a model that runs clean stays as it is | A | C | `docs/05-v2.1-changes.md` §4; backlog PB-33 | **Not carried out.** Reason: a protocol change to a running model inside the timebox. Outstanding impact: the reduction target is unmet and risk R-10 stays open |
| FB-07 | Retrospective 1 / Sprint Review 2 §3.3 | Three modelled branches have never been driven end to end | Drive declined payment, confirmation lost and the three-month escalation early in Sprint 2 | C | E | None recorded | **Not carried out**, because the committed compaction work and the preservation gate took the sprint. Outstanding impact: `TC-E2E-03` to `TC-E2E-05` remain `NOT RUN` and risk R-05 is open |
| FB-08 | Retrospective 1 | A drawing-only rebuild could silently drop a scored element | Build an executable preservation audit before any Sprint 2 drawing change | E | B | `tools/verify_preservation.py`; `docs/03-test-record.md` §H1 (62/62) | **Complete** |
| FB-09 | Sprint Review 2 (Q9) | `workers/README.md` documented 32 of the 35 model job types and its summary line was stale | Correct the table and the summary, or point it at the generated job-type list | C | E | `workers/README.md`: 36 rows (0–35), three types added, summary lines corrected, plus a one-line command to count the types from the model | **Done in R3.** DEF-14 and DEF-16 closed |
| FB-10 | Sprint Review 2 (Q10) | The `zeebe:versionTag` is still 2.0.0 in the v2.1 artefact | Bump the tag for the next release and write the tag scheme into the configuration-management plan | E | A | Tag scheme documented in `docs/09-risk-contingency-and-config-management.md` §4.2 | **Open.** The tag is not yet bumped |
| FB-11 | Sprint Review 2 (Q11) / internal planning review | `docs/06-visual-compaction.md` described a compaction (9 lanes, 12 sub-processes, 15 message flows) that was not in the shipped model | Treat the model as the source of truth and replace the document | B | A | `docs/06-diagram-engineering.md` (replaced); source-of-truth rule in `docs/07-product-backlog.md` A6 and `docs/09-...` §5 A7 | **Done in R3**: defect DEF-15 closed |
| FB-12 | Internal planning review | There is no version-control repository in the workspace | Initialise a repository and commit the released state as the baseline before any further bulk regeneration | E | A | None recorded | **Open** (risk R-14; no `.git` exists) |
| FB-13 | Retrospective 2 / internal planning review | Accessibility is partly delivered: no grouping headings and no WCAG check | Emit `group` components for the long forms, re-run the render census, and state the accessibility rationale | D | E | None recorded | **Open.** Defect coverage in `docs/08-test-plan.md` `TC-FRM-03`, `TC-FRM-04`, `TC-FRM-08` |
| FB-14 | Internal planning review (defect DEF-17) | `docs/03-test-record.md` §F2 cites `screenshots/tasklist-camunda-form.png`, which does not exist | Re-capture the evidence once Tasklist authentication is fixed, or remove the reference and record the test as `NOT EVIDENCED` | E | D | `docs/08-test-plan.md` `TC-E2E-07` now records `NOT EVIDENCED`; the source document is not yet corrected | **Partly complete** |

**Rule applied to this log.** An action that was not carried out keeps a row, a
stated reason and a described outstanding impact. Nothing is dropped because it
was inconvenient; FB-03, FB-06, FB-07 and the open items above are the honest
remainder of two sprints.

---

## 6. Release notes

### 6.1 Initial Release (R1): v2.0

**Model and forms.** One BPMN collaboration: 15 participants (9 executable
processes, 6 black-box external bodies), 14 lanes, 301 flow nodes, 311 sequence
flows, 31 message flows, 39 user tasks, 47 service tasks across 35 job types, 41
gateways, 18 boundary events, 9 named error codes and 3 collapsed sub-processes.
It ships 36 Camunda Forms.

**Delivered backlog items.**

| Backlog items | Release note |
|---|---|
| PB-01 – PB-04 | Measured gap audit; the case-study collaboration rebuilt as one file with correlated message hand-offs and lanes where a pool covers several desks |
| PB-05, PB-06 | New layout engine: zero sequence-flow overlaps, zero message-flow overlaps, zero diagonals; repetitive administration contained in three collapsed sub-processes |
| PB-07, PB-08, PB-19 | Every modelled exception has an owner and an exit; clinic-letter timers at 7 days and weekly thereafter with a three-rung escalation ladder; external capacity has a counted retry capped at 3 |
| PB-18 | Compensation added for the provisional appointment series and the cycle booking (two boundary events, two handlers, two throws), modelled but not triggered in a live run |
| PB-09 – PB-11 | A form on every user task (39/39), a candidate group on every user task (39/39), and required/length/range validation |
| PB-13 – PB-17 | 36 worker classes subscribing to 37 job-type names; simulated external services with documented forced-failure switches; duplicate suppression; no card data; non-overwriting audit workers |
| PB-20 – PB-23 | One-command deployment of 9 process definitions and 36 forms; both scripted paths complete with no incidents; all 36 forms render in form-js |
| PB-24 | Test record with expected vs actual for every check, and a modelling-decisions document with numbered assumptions and limitations |

**Known issues in R1.** PB-12 partly delivered (descriptions only, no grouping);
compensation not triggered live; three branches not run; Tasklist cannot draw the
forms in this c8run setup; 30 Modeler warnings, all `no-bpmndi` inside collapsed
sub-processes; four flows clip a boundary event by a few pixels; crossings 147;
idempotency state in memory.

### 6.2 Second Release (R2): v2.1

**Change summary.** Drawing-only release: message flows 66 → 31 (dashed line
421,424 → 174,820 px, −59%); routine end events 60 → 32 with exception ends never
merged; lanes 20 → 14. No scored element removed, proved by 62 parsed preservation
checks.

**Delivered backlog items.** PB-25 (preservation audit), PB-26 (message-flow
thinning), PB-27 (end-event merge), PB-28 (lane consolidation), PB-29 (Modeler
re-validation, diagram and section export).

**Verification.** 62/62 preservation checks; Camunda Modeler 5.51.0 on Camunda
8.10 (alpha) reporting 0 errors; `validate_model.js` reporting 0 warnings, 0
unresolved references, 0 dangling flows and full form/candidate-group/job-type
coverage; both paths re-run with `incidents: none`; deployed as processes v17 and
forms v18; Operate showing 21 running instances with 0 incidents.

**Known issues in R2.** Crossings rose to 197 as the measured cost of the
end-event merge; 43 message start events remain against a target of ≤ 2 per pool;
the four clipped lines remain; sub-process boxes stay collapsed (30 `no-bpmndi`
warnings); the three undriven branches and the live compensation trigger remain
undemonstrated; `versionTag` still reads 2.0.0; documentation drift DEF-14 to
DEF-17 is recorded but not corrected.

**Carried into the next cycle.** PB-30, PB-31, PB-32, PB-33, plus the open
feedback actions FB-09 to FB-14. PB-34 and PB-35 were taken up in R3.

### 6.3 Third Release (R3): v7.0

**Change summary.** Two modelling changes and a routing change, all aimed at the
same thing: a drawing a reader can follow.

| | v2.1 | **v7.0** |
|---|---:|---:|
| End events | 32, several merged | **65, none with more than one incoming flow** |
| Drawn message flows | 31 | **15** (11 exception hand-offs + 4 system-boundary hand-offs) |
| Sequence-flow crossings | 197 | **94** |
| Lines drawn through a shape | 4 | **0** |
| Total ink | 378,475 px | **182,317 px** |
| Canvas | 7,496 × 13,736 | **5,332 × 14,176** |
| `bpmnlint:recommended` errors | 39 | **2** |
| Preservation checks | 61 of 62 | **67 of 67** |

**Delivered backlog items.** PB-34 (crossing reduction, 197 → 94, clipped lines
4 → 0) and the new PB-35 (one end event per terminating path; dashed lines cut to
the hand-offs that carry an outcome). Also closed: DEF-14, DEF-15 and DEF-16 from
`docs/08-test-plan.md` §9. The drifted diagram document was replaced, the worker
job-type catalogue completed, and the collapsed sub-process steps given diagram
interchange so the boxes open correctly in the Modeler.

**Known issues in R3.** The two `no-implicit-start` errors (DEF-18) remain: a
withdrawn v2.0 retry chain and one step inside a collapsed sub-process. Both are
unreachable code on a model that runs clean; repairing them is a
message-protocol change and was deliberately not made. 43 message start events
still exceed the 2-per-pool target, for the reason recorded in
`docs/05-v2.1-changes.md` §4. DEF-17 (one cited screenshot that does not exist)
is still open because the Tasklist cannot be re-authenticated to recapture it.

---

## 7. Assumptions

1. **A1: Dates and attendees.** No sprint dates, review dates, attendee lists or minutes exist in the workspace. This document records the substance of each review (goal, increment, evidence, decisions, questions and limitations) without inventing a calendar or a quorum.
2. **A2: Graded stand-ups.** Each sprint ran a graded stand-up and a graded Sprint Review. Stand-up output is not retained as a separate artefact; the blockers it produced are the FB rows in §5 whose source is a retrospective or an internal review.
3. **A3: Quotation.** Questions in §1.5 and §3.5 are paraphrases reconstructed from the decisions and changes recorded in `docs/05-v2.1-changes.md`, `docs/02-status.md` and `docs/03-test-record.md`. They are not verbatim transcriptions.
4. **A4: Internal items.** FB-11 to FB-14 come from the internal planning review performed while writing `docs/07`–`docs/10`, not from a graded review. They are labelled as such in the Source column so they are not presented as stakeholder feedback.
5. **A5: Retrospective 1 timing.** The improvement action to build the preservation gate before Sprint 2 is evidenced by the existence and first use of `tools/verify_preservation.py` in `docs/03-test-record.md` §H1; no retrospective minute records it.
6. **A6: Release scope.** The Initial Release is R1 (v2.0), the second release is R2 (v2.1) and the third is R3 (v7.0), per `docs/07-product-backlog.md` §2 and Assumption A8 there.
