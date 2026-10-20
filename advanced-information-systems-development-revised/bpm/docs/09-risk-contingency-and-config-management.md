# Risk, contingency and configuration management


> **Citations to files that are not in this tree.** An audit found 39 paths cited across 19 documents that no longer exist — the fourteen-pool model, the v1/v2 generators and the drawing scripts that went with them, and the Sprint 0 Node scaffold. Nothing was lost: all of it is in git history, and every citation is listed with what replaced it in [18-cited-files-no-longer-present.md](18-cited-files-no-longer-present.md).

Risk register, demonstration contingency and rollback, and the
configuration-management plan for the delivered portfolio. Every risk below is
grounded in an artefact in this folder or in a documented limitation; every
control names the file or command that implements it.

Read with: `docs/07-product-backlog.md` (owners and Definition of Done),
`docs/08-test-plan.md` (what is tested and what is not), `docs/02-status.md` and
`docs/04-modelling-decisions.md` §7 (known limitations), `workers/DEPLOYMENT.md`
(build, configuration and failure switches).

---

## 1. Risk register

**Scoring.** Likelihood and impact are H/M/L; exposure is the product on a
3-point scale (H=3, M=2, L=1), so exposure runs 1–9. A risk at exposure ≥ 6 needs
a named contingency as well as a mitigation.

| ID | Risk | Category | L | I | Exp | Mitigation (what is already in place) | Contingency / fallback | Owner (1st / 2nd) | Status | Trigger |
|---|---|---|---|---|---|---|---|---|---|---|
| R-01 | The collaboration is too large for the Camunda 8 deployment batch ceiling: the whole BPMN resource is stored in every process definition record, so 15 processes mean 15 copies | Technical | H | H | 6 | v7.0 avoided this by keeping the four external suppliers as black-box participants; v14 has taken the risk on deliberately to connect them (`docs/11-white-box-external-participants.md` §5). Mitigations, in order: raise `ZEEBE_MAX_MESSAGE_SIZE` above the batch; deploy the nine hospital processes and the six outside participants in two batches; or keep the six outside participants as drawn but non-executable pools, which is what v16.0 ships. Verified against c8run 8.10.0-alpha5: fifteen executable processes are rejected (nine records fit, the tenth is refused at 4,095,764 bytes). The shipped configuration implements the second mitigation: nine in the main file, the six outside participants in a 30 KB file, and both deployments succeed | Split the supplier work into a separate deployable file, or reduce diagram interchange payload; the walk-away is the smaller v1.0 collaboration with black-box suppliers | C / E | Mitigated and verified; the v16.0 figure is in `screenshots/v16/engine-record.txt`. Residual: a further executable pool added to the shipped file | Deployment rejected for size, or a new pool is added to the same file without a second batch | **Closed by v16.0.** The rebuild collapses the nine hospital processes into one, so the shipped file is a single deployable process definition with six non-executable outside participants; there is no batch to fit and no second file to deploy. See `17-single-pool-operational-model.md`.
| R-02 | A message throw has no correlation key, producing a live `JOB_NO_RETRIES` incident and a stalled pathway | Technical | M | H | 6 | The builder writes a `correlationKey` input mapping onto every throw event (fix for DEF-01); TC-WRK-06 verifies a blank key fails safely; both paths run with `incidents: none` | Re-deploy the last known-good resource; add the missing mapping by hand in the Modeler and re-run the path | A / C | Mitigated; fixed and re-tested | An incident named `JOB_NO_RETRIES`, or a message that never correlates |
| R-03 | Correlation-key design lets a second hand-off for the same patient and purpose go uncorrelated, so a patient does not receive a second letter or funding decision | Technical / data | M | M | 4 | Purpose tags (`patientRef + "-referral-review"`, `+ "-funding"`, `+ "-refund"`) separate concurrent work; the key itself is the duplicate-suppression mechanism (`docs/04-modelling-decisions.md` §2) | Re-publish with a corrected key after cancelling the stale instance in Operate; if the purpose set is incomplete, add a tag and re-deploy | A / E | Monitored | A message is deliberately sent twice and only one instance is expected |
| R-04 | Five external services are deterministic stubs, so passing tests are read as proof of real integration | Quality / technical | H | M | 6 | The simulation is stated in `workers/README.md` and repeated in `docs/08-test-plan.md` §5 and the limitations; forced-failure switches make the boundary branches genuinely testable | Replace one worker class per service when a real API exists; until then every claim is scoped to "simulated" | C / E | Accepted as a documented limitation | A review or a marker treats a green run as real provider integration |
| R-05 | Three modelled branches have never been driven end to end (declined payment, payment confirmation lost, three-month letter escalation) | Quality | H | M | 6 | Branches are modelled, the workers support them, and the switches to drive them are documented in `workers/DEPLOYMENT.md` §6 | Drive each branch with `demo.payment.status` / `demo.pathway.scenario` and keep the log; if it cannot be done, state the gap at the review before a reviewer finds it | E / C | Open, carried as PB-30 | A Sprint Review or the final demonstration asks for one of the three |
| R-06 | Compensation is modelled and statically asserted but has never fired in a live run | Quality | M | M | 4 | Two compensation boundary events, two `isForCompensation` handlers, two compensation throws; the three worker types exist and register (`docs/03-test-record.md` §E3) | Force the giving-up path with `demo.external.unavailable-resources` and cap 3, and capture the handler completing in Operate | C / E | Open; carried as PB-31 | A reviewer asks to see compensation work rather than read that it is wired |
| R-07 | The Tasklist Task pane cannot draw the forms because c8run returns `401` from `/v2/authentication/me` | Technical / tooling | H | M | 6 | Forms are proven to render with `@bpmn-io/form-js`, the renderer Tasklist uses (`TOTAL=36 FAILED=0`), so the deliverable no longer depends on it (`docs/03-test-record.md` §F4–F5) | Demonstrate the form through the form-js render page and the Operate instance variables; treat Tasklist as an environmental gap, not a model gap | E / D | Open, carried as PB-32 | A graded review requires a task completed in the Tasklist UI |
| R-08 | No performance, load or concurrency testing has been done, and no target exists | Quality | M | M | 4 | Single-instance runs are deterministic and reproducible with `DemoClock`; operation counts are small and the workers use 32 max jobs and 4 threads | If a load claim is needed, build a small parallel driver against the REST API; otherwise make no performance claim at all | E / C | Accepted, out of scope | A review expects evidence of behaviour under concurrent pathway load |
| R-09 | The accessibility expectation is not met: 0 grouping headings, only 71 descriptions across 230 form components, and no WCAG check | Quality | H | M | 6 | Field-level descriptions and validation are present; single-column layout; the gap was identified in `docs/01-gap-audit.md` §C3 | Emit `group` components in `tools/forms_spec.py` for the long forms and re-run the form-js census; state the gap honestly until then | D / E | Open; PB-12 partly done | A marker inspects a long form or asks for the accessibility rationale |
| R-10 | Two brief reduction targets remain unmet: 43 message start events against a target of ≤2 per pool, and 197 crossings against 42 in v1.0 | Quality | H | M | 6 | The arithmetic that makes "under 80 events" unreachable without deleting scored elements is documented (`docs/05-v2.1-changes.md` §4); the crossing rise is confirmed by A/B measurement rather than asserted | Accept and explain, or spend the effort on the message-protocol change (PB-33) that would take start events to about 18; a crossing pass is PB-34 | A / B | Accepted, with the trade documented | A reviewer measures the model and asks why the target was missed |
| R-11 | Idempotency state lives in memory in one JVM, so a worker restart can allow a repeat that a persistent store would prevent | Technical / data | L | H | 3 | In-memory `HospitalStore` plus deterministic reference generation; the limitation is stated in `docs/04-modelling-decisions.md` §7 item 5 | Restart the workers between runs and re-verify the reference; for a real deployment, move idempotency to database constraints on booking and payment references | C / A | Accepted; the limitation is documented | A worker JVM restarts mid-path, or the same patient is booked twice |
| R-12 | Tooling versions are unusually specific and partly pre-release: c8run 8.10.0-alpha5, Camunda Modeler 5.51.0, `zeebe-client-java` 8.9.0 against an 8.10 engine, jar built under JDK 25 targeting Java 21 | Technical | M | M | 4 | Versions are recorded in the test record and the plan; the jar targets Java 21 so it runs on a 21 JVM; the model declares `Camunda Cloud` / `8.10.0` and exporter 5.51.0 | Pin every version in writing; if the engine moves, re-run the two paths and the preservation audit before claiming anything; a mismatch in an alpha feature is the first thing to suspect | C / E | Monitored | An engine or Modeler upgrade, or a client/engine incompatibility at start-up |
| R-13 | Documentation drifts from the artefact: one document described a diagram state that was never shipped; the worker README's job-type table is three types short; one cited screenshot does not exist | Quality / CM | H | M | 6 | The preservation audit and the parser gate compare the file with its predecessor rather than with prose; the drift items are logged as DEF-14 to DEF-17 | Correct the docs or complete the pass before submission. Executed in R3: the drifted diagram document was deleted and replaced by `docs/06-diagram-engineering.md`, and the `workers/README.md` job-type catalogue was completed and its counts corrected. DEF-14, DEF-15 and DEF-16 are closed; DEF-17 (one cited screenshot that does not exist) stays open | E / A | Mitigated: three of four drift items closed, the fourth tracked | A reviewer opens the worker README or a cited screenshot beside the model |
| R-14 | Contributions were integrated late: the delivered work entered version control in three bulk commits, two of them after the submission date, so the history does not evidence continuous integration | CM / schedule | H | M | 6 | The repository exists and every release is tagged (§4.1, §4.2). The ordering of the commits is a fact of the history and is not presented otherwise | Treat the snapshot tags as the release identity and state plainly which commit each review saw; for the next increment, commit per accepted item so the history carries the integration. The tag dates and what each tag points at are recorded in §4.2 | E / A | **Open, carried into submission.** Version control exists; what it does not show is integration throughout the sprint | A reviewer reads `git log` against the sprint dates |
| R-15 | Single point of failure: one member holds the layout engine, one holds the worker catalogue, and one holds the generator | People | M | H | 6 | Every backlog item has a second owner; the hand-over log records ten explicit hand-overs with an acceptance step; the tools are committed in `tools/` and documented in `README.md` | The second owner re-runs the relevant gate and takes the item; the generator is deterministic so the output can be reproduced without the original author | A / B / C (each is 2nd owner for the others) | Mitigated by the two-owner rule | The first owner is unavailable at a graded stand-up or review |
| R-16 | Cross-team hand-offs are ambiguous: the case study does not say who owns some tasks, and two teams share a form | People / quality | M | M | 4 | Candidate groups match the pool roles (39/39); shared forms are deliberate and checked by the build; the ambiguity in the case study is recorded as six numbered assumptions in `docs/04-modelling-decisions.md` §6 | Where the case study is silent, present the assumption as an assumption; do not defend it as a requirement | A / D | Accepted and documented | A reviewer disputes which team owns a task |
| R-17 | The system processes sensitive personal, clinical and financial data | Data protection | L | H | 3 | Test data is synthetic (`PAT-DEMO-…`); the payment workers never read or emit card data; audit workers do not write clinical variables back; no real provider is contacted | If any real data is ever introduced, stop and handle it under the hospital's own policy; for this portfolio, keep the synthetic-data rule and say so | C / E | Accepted with the synthetic-data control | Any real patient identifier appears in a form, log or screenshot |
| R-18 | A rollback is misunderstood: Camunda 8 keeps every deployed version and cannot delete one, so "rolling back" means re-deploying the earlier file, which creates a further version | Technical / CM | M | M | 4 | Deployment versions are recorded (v17 processes, v18 forms after the v2.1 rebuild); the previous files exist in the sibling folders; instances are cancelled rather than deleted | Re-deploy the previous resource, then cancel any instances created by the faulty version in Operate; tell the audience the version number being shown | E / C | Understood; the mechanism is documented here | A live demonstration shows a defect and the previous resource is needed |
| R-19 | The timebox is missed and the release is not finished | Schedule | M | H | 6 | MoSCoW with explicit carry-over; the Must list is the release; PB-30 to PB-35 were held as stretch items and not started, so no committed item was dropped | Submit the last complete held release. `docs/02-status.md` records that v1.0 is untouched, still deploys, still runs both paths, and has its own evidence, so v1.0 is the safer submission if v2.x cannot be finished | E / A | Monitored | A committed item is still In progress at the review |
| R-20 | The engine or cluster is unavailable at the demonstration | Technical / schedule | M | H | 6 | Both scripted paths are deterministic and re-runnable; logs and Operate screenshots are retained in `screenshots/`; `DemoClock` makes runs reproducible | Restart c8run, re-run `tools/deploy.sh`, restart the workers, then re-run the path; if the engine will not start, present the retained log and screenshots and say plainly that the run is recorded rather than live | E / C | Mitigated by retained evidence | `GET /v2/topology` does not return 200, or the deployment is rejected |
| R-21 | No data-protection impact assessment exists, although the case study expects the information and authorisation requirements to be analysed | Data protection / quality | M | M | 4 | The data-protection rules that *are* implemented are stated and testable: no card data (TC-NFR-01), synthetic test data (TC-NFR-08), role separation (TC-NFR-02), non-overwritable audit records (TC-NFR-03) | Produce a short DPIA-style note over the implemented controls; if it is not produced, present the controls as controls and do not claim compliance | E / A | Open | A reviewer asks how the data-protection requirement was analysed |

**Exposure summary.** Twelve risks sit at exposure 6, so each has a named
contingency on top of its mitigation: R-01, R-02, R-04, R-05, R-07, R-09,
R-10, R-13, R-14, R-15, R-19 and R-20. Of those, R-04, R-05, R-07, R-09, R-10,
R-13 and **R-14 (contributions integrated after the sprint rather than through
it)** are open quality, tooling or configuration-management risks carried into
submission. Everything else is either mitigated in the artefact or accepted as a
documented limitation.

---

## 2. Contingency plan for the demonstration

The demonstration is the risky moment: a live engine, a Java process, a large
model and a browser all have to cooperate in one timebox. The plan names what to
do when a component fails, in the order a presenter would hit it.

| Failure at the demonstration | Immediate action | Fallback evidence to show instead | Owner |
|---|---|---|---|
| The laptop or c8run will not start | Start the bundled c8run; if it fails within 5 minutes, stop trying | Retained `screenshots/run-happy-path.log` and `run-exception-path.log`, plus the Operate screenshots | E |
| `GET /v2/topology` does not return 200 | Restart c8run and re-check once | As above; do not spend the slot debugging infrastructure | E |
| Deployment rejected | Re-run `tools/deploy.sh` once and read the error; check resource size (R-01) | Show the last accepted deployment evidence (`docs/03-test-record.md` §C1, §H2a) | C |
| Workers fail to start or subscribe | Re-run `java -jar workers/target/hospital-external-workers-1.0.0.jar`; check the gateway address | Show the retained subscription log and explain the 37 subscriptions | C |
| The path stalls at a user task | Do not skip the task manually; check the incident search first | Switch to the exception path, which is shorter, or present the retained log | E |
| An incident appears live | Capture it, name it honestly, then cancel the instance in Operate | Use the incident as the demonstration of the exception design rather than pretending it did not happen | E |
| Tasklist will not draw a form | Do not debug authentication live (R-07) | Show `screenshots/camunda-forms-rendered.png` and the form-js census | D |
| The diagram is too large to navigate | Open `diagram/hospital-patient-pathway-v16-sections.pdf`, one captioned stage per page | Show one stage at a time | B |
| Time runs out | Stop adding material; close with the limitations | The limitations list in `docs/04-modelling-decisions.md` §7 is the closing script | A |

**Presenting rule.** A recorded result is labelled as recorded, and a simulated
service is called simulated. A branch that was not driven is never implied to have
run. The test plan applies the same rule in
`docs/08-test-plan.md` §7.

---

## 3. Rollback plan

Camunda 8 keeps every deployed version and does not delete one, so rollback is a
re-deploy of the previous resource plus cancellation of the instances the faulty
version created. The mechanism is stated here so that it cannot be discovered for
the first time during a demonstration.

| Component | Roll forward normally | Roll back to the previous release |
|---|---|---|
| Model and forms | `python3 tools/build_v3.py` then `bash tools/deploy.sh` | Check out the previous tagged commit (`git checkout v14.0-final -- bpm/model bpm/tools`) and re-run `tools/deploy.sh`; the engine records a further version rather than replacing one |
| Running instances | Let the path complete | Cancel the affected instances in Operate; they are not deleted and remain visible as cancelled |
| Workers | `mvn -gs maven-settings.xml -s maven-settings.xml -o package` and restart | Stop the JVM and restart the previous jar; the H2 store is a file, so a rollback of the jar also rolls back the schema only if the file is restored with it |
| Demo state | Optionally pin `demo.clock.today` and the failure switches in `application.yaml` | Set the switches back to their defaults (`simulated-failure.enabled: false`, `payment.status: APPROVED`, `force-no-slots: false`, `unavailable-resources: []`) |
| Diagram and sections | `python3 tools/render_v16.py` and `python3 tools/render_sections_v16.py` | Re-run both against the restored model; they are generated artefacts and hold no state |
| Release as a whole | Deploy the current tag | Check out the previous tag (`v14.0-final`) and deploy it; the engine keeps both versions and an instance names the one it ran on |

**Decision rule.** Roll back if a Must item fails at Sprint Review 2 and cannot
be fixed within the review slot. State the rollback and the reason; do not
present an unverified release as if the rollback had not happened.

---

## 4. Configuration-management plan

### 4.1 Repository layout

The configuration is held in a Git repository (`origin` is
`github.com/Cczy1203/Advanced-information-systems-development`). A release is a
commit and each review snapshot is a tag, so the **history** is what identifies a
version; the deterministic build and the executable gates below are what keep the
*contents* consistent. See Assumption A1.

| Path | Contents | Under configuration control? |
|---|---|---|
| `model/UFCEP6-0-3_Hospital_Patient_Pathway_v16.bpmn` | The single deployable collaboration | Yes; generated from `tools/spec_v3.py`, then committed |
| `model/forms/*.form` | 37 Camunda Forms | Yes; generated, hardened, then committed |
| `workers/` | Java sources, `pom.xml`, `run-workers.sh`, `maven-settings.xml`, `README.md`, `DEPLOYMENT.md`, `src/main/resources/` | Yes; hand-written |
| `tools/` | Model: `spec_v3.py`, `bpmn_builder_v2.py`, `bpmn_builder_v3.py`, `build_v3.py`, `layout_engine.py`, `forms_spec.py`. Gates: `analyse_bpmn.py`, `analyse_layout.py`, `forms_inventory.py`, `harden_forms.py`, `fix_form_group_paths.py`, `audit_accessibility.py`, `validate_model.js`. Drivers and export: `deploy.sh`, `run_v16.py`, `verify.ps1`, `render_v16.py`, `render_sections_v16.py`, `export_pdf.py` | Yes; hand-written |
| `docs/NN-topic.md` | The working notes, this plan and the reviews | Yes, hand-written |
| `README.md`, `.bpmnlintrc` | Entry point and lint configuration | Yes |
| `screenshots/` | Run logs and UI evidence | Yes for the logs; the PNGs are capture output |
| `diagram/` | SVG, PNG and the two PDFs (full drawing, sectioned) | Generated, regenerable, treated as release evidence |

### 4.2 Revision and release scheme

A release is a commit; a review snapshot or a named release is a tag. The tags that
exist, what each points at, and when each was created:

| Tag | Points at | Tag created | What it is |
|---|---|---|---|
| `sr1-snapshot` | `8cf1625`, committed 2026-09-29 | 2026-10-16 | Sprint Review 1 snapshot |
| `v14.0-final` | `60298f8`, committed 2026-09-29 | 2026-09-29 | The release that was reviewed |
| `sr2-snapshot` | the submitted commit | 2026-10-16, moved to the submitted commit | Sprint Review 2 / submission snapshot |

**Read the tag dates honestly.** Both review tags were created after the sprint they
record, and the submission was 2026-09-28, so the tags do not freeze an increment at
the moment of its review — they point at the state that was submitted. The history
is dated and the dates are not favourable; risk R-14 states the consequence.

| Release | Model file | Design document | `zeebe:versionTag` in the file |
|---|---|---|---|
| v1.0 | an earlier folder, not in this tree | — | — |
| v2.0 (Initial Release, R1) | `model/UFCEP6-0-3_Hospital_Patient_Pathway_v2.bpmn` (superseded) | `docs/01`–`docs/04` | `2.0.0` on all 9 processes |
| v2.1 (second release, R2) | same path, regenerated (superseded) | `docs/05-v2.1-changes.md` | `2.0.0` (not bumped) |
| **v16.0 (shipped)** | **`model/UFCEP6-0-3_Hospital_Patient_Pathway_v16.bpmn`** | **`docs/17-single-pool-operational-model.md`** | **`16.0.0` on the single process** |

Only the v16.0 file is in the tree; the v2.0/v2.1 files are in git history. The
`versionTag` shortcoming recorded for R2 is closed by v16.0, which carries a tag that
matches its release name.

### 4.3 Naming and identifier conventions

| Thing | Convention | Examples |
|---|---|---|
| Participants | `P_<name>` | `P_Hospital`, `P_Referrer`, `P_Payment` |
| Executable process | the hospital process, kebab-case | `hospital-patient-pathway` |
| Lanes | named after the responsibility, nested per team | `outpatient-bookings`, `consultants` |
| Elements by kind | `<TEAM>_<kind>_<Name>` | `SEC_Task_CheckPack`, `TRT_Auto_ConfirmAppointments`, `CON_Bnd_LetterOverdue`, `OUT_GW_SlotsFound`, `SEC_Catch_InfoReceived`, `TRT_Comp_ReleaseSeries` |
| Camunda Forms | kebab-case, action-first | `check-referral-pack`, `determine-funding-route`, `choose-appointment-slot` |
| Job types | `<domain>.<verb-noun>` | `referral.check-supporting-documents`, `payment.process-transaction`, `treatment.release-series` |
| BPMN errors | `Error_<CODE>` with `errorCode="<CODE>"` | `Error_REFERRAL_PACK_UNREADABLE` / `REFERRAL_PACK_UNREADABLE` |
| Messages | `Message_<event>` | `Message_referral_info_received`, `Message_letter_escalation_higher_management` |
| Documents | `NN-topic.md`, two-digit prefix | `07-product-backlog.md` |
| Backlog items | `Mj-nn` in the delivered workbook; `PB-nn` in `docs/07` (historical) | `Mj15`, `Mj45`; the crosswalk is `docs/07` §11 |
| Other IDs | `TC-<AREA>-nn`, `DEF-nn`, `R-nn`, `HO-nn`, `FB-nn` | `TC-BPMN-12`, `DEF-15`, `R-13`, `HO-09`, `FB-16` |

The conventions are enforced where they can be: `tools/validate_model.js` fails a
user task without a form or candidate group and a service task without a job type;
`tools/build_v3.py` fails a model whose gateway conditions disagree with the bound
forms, and refuses a form that is bound but not defined or defined but not bound;
`tools/audit_convergences.py` fails a convergence that is neither a loop-back nor a
single exclusive fork.

### 4.4 What is generated and what is authored

| Generated artefact | Authored source | Command |
|---|---|---|
| `model/UFCEP6-0-3_Hospital_Patient_Pathway_v16.bpmn` | `tools/spec_v3.py`, `tools/bpmn_builder_v3.py`, `tools/layout_engine.py` | `python3 tools/build_v3.py` |
| `model/forms/*.form` (37) | `tools/forms_spec.py`, hardened by `tools/harden_forms.py` | `python3 tools/build_v3.py` |
| `diagram/hospital-patient-pathway-v16.svg` and `.png` | the model | `python3 tools/render_v16.py` |
| `diagram/hospital-patient-pathway-v16-sections.pdf` | the full-page PNG | `python3 tools/render_sections_v16.py` |
| `docs/pdf/*.pdf` | `docs/*.md` | `python3 tools/export_pdf.py --docs` |

Everything else (workers, tools that are not the generator, documents) is
authored. The authoring rule is that a generated file is never hand-edited: a
change is made in the source and the artefact is regenerated. `docs/05-v2.1-changes.md`
§5 records that the generator is deterministic and produces byte-identical output
for the same inputs, so an unexplained diff is a real change to be reviewed; the
v16.0 generator retains that property.

### 4.5 Keeping the deployable model and its forms in step

Camunda 8 stores the whole BPMN resource inside each process definition record, so
the model and its forms must go up in the same deployment. Three controls hold
this together:

1. **One batch, one command.** `tools/deploy.sh` collects every `model/forms/*.form`
   and the single BPMN file into one multipart deployment, so a form can never
   lag its model on the cluster by being uploaded separately.
2. **Build-time binding check.** `tools/build_v3.py` cross-checks every form bound
   by a `zeebe:formDefinition` against the form definitions and refuses to emit
   when either side is missing; the parser gate independently confirms 38/38 user
   tasks have a form and a candidate group, and that the 37 form files have neither
   an orphan nor a missing member.
3. **Regeneration regenerates both.** The same command writes the BPMN and all 37
   forms from the same sources, so the model and the forms cannot be regenerated
   from different revisions without the diff showing it.

### 4.6 Change review and integration

A change is integrated only when all of the following hold. These are the same
gates as the Definition of Done in `docs/07-product-backlog.md` §6.

| Gate | Command | Failure action |
|---|---|---|
| Generator accepts the change | `python3 tools/build_v3.py` | Fix `tools/spec_v3.py`; never edit the generated file |
| Layout rules hold | `python3 tools/analyse_layout.py model/UFCEP6-0-3_Hospital_Patient_Pathway_v16.bpmn` | Re-run the layout pass; overlaps must be 0 |
| Convergences are safe | `python3 tools/audit_convergences.py model/UFCEP6-0-3_Hospital_Patient_Pathway_v16.bpmn` | Add the missing merging gateway, or record why the convergence is a loop-back |
| The Modeler's parser is clean | `node tools/validate_model.js model/UFCEP6-0-3_Hospital_Patient_Pathway_v16.bpmn` | Fix the model; 0 warnings and 0 unresolved references |
| The release still deploys, and RBAC persists | `pwsh -File tools/verify.ps1 -Check engine` | Fix or roll back (§3) |
| State survives a cold restart | `pwsh -File tools/verify.ps1 -Check persistence` | Fix the schema or the store before anything else is accepted |
| The behaviour still runs | `pwsh -File tools/verify.ps1 -Check e2e` | Re-run after the fix; a pass recorded against an undeployed model is discarded |
| A second owner has read it | hand-over log, `docs/07-product-backlog.md` §7 | The item is not Done |

### 4.7 Reproducing the whole release from source

Every command below runs against the artefacts in this folder. The generator for
the shipped file is `spec_v3.py` / `build_v3.py`; the v1/v2 generators that earlier
revisions of this section named have been removed (see
`docs/18-cited-files-no-longer-present.md`).

```bash
# 1. regenerate the model and the 37 forms
python3 tools/build_v3.py

# 2. measure the drawing: 0 overlaps, 0 diagonals, 0 lines through a shape
python3 tools/analyse_layout.py model/UFCEP6-0-3_Hospital_Patient_Pathway_v16.bpmn

# 3. prove every convergence is a loop-back or a single exclusive fork
python3 tools/audit_convergences.py model/UFCEP6-0-3_Hospital_Patient_Pathway_v16.bpmn

# 4. parse it the way the Modeler does
node tools/validate_model.js model/UFCEP6-0-3_Hospital_Patient_Pathway_v16.bpmn

# 5. audit the forms: labels, descriptions, groups, validation
python3 tools/audit_accessibility.py

# 6. build the workers, then deploy and run the scenarios
cd workers && mvn -gs maven-settings.xml -s maven-settings.xml -o package && cd ..
pwsh -File tools/verify.ps1 -Check engine          # deploy model + forms
java -jar workers/target/hospital-external-workers-1.0.0.jar &
pwsh -File tools/verify.ps1 -Check e2e             # 8 scenarios, real workers

# 7. regenerate the release evidence
python3 tools/render_v16.py model/UFCEP6-0-3_Hospital_Patient_Pathway_v16.bpmn \
        diagram/hospital-patient-pathway-v16
python3 tools/render_sections_v16.py diagram/hospital-patient-pathway-v16.png \
        diagram/hospital-patient-pathway-v16-sections.pdf
python3 tools/export_pdf.py
```

**Where this plan and the history disagree.** The gates above were run, but the
commits do not show them being run *as the work progressed*: the delivered tree
entered version control in three bulk commits, two of them dated after the
submission date. That is risk R-14, and it is stated here rather than presented as
continuous integration. The tag dates and what each tag points at are in §4.2.

---

## 5. Assumptions

1. **A1. Version control exists, and it is the record.** This plan was first written when it did not: the text above used to say "There is no `.git` directory in it (checked)". That was true of the v2.0 workspace and is not true now. The workspace is a Git repository (`origin` is `github.com/Cczy1203/Advanced-information-systems-development`) and every release is committed. The scheme in §4.2 describes the *effective* model (a deterministic generator, the gates, and a two-owner review); Git supplies the version identity that the folder alone could not. Feedback FB-12 ("initialise a repository") is therefore closed. **What the history does not show is integration throughout the sprint:** the delivered tree arrived in three bulk commits, two dated after the submission date. That gap is risk R-14, not an assumption.
2. **A2. Branching.** The repository carries one long-lived branch, `main`, and a branch per member during the sprints (`Damon`, `Lorrey`, `Tommy`, `Young`), with work merged into `main`. The review snapshots are tags, not branches: `v14.0-final` is the release that was reviewed, and `sr1-snapshot` and `sr2-snapshot` are the two sprint-review snapshots. No release branch is kept — a release is a tag on `main`.
3. **A3. Version tag.** The `zeebe:versionTag` in the shipped file is `16.0.0` on the single executable process, which matches the release name v16.0. *Corrected:* this assumption previously read that the tag was `2.0.0` on all nine processes — true of the v2.1-era file, false of the file that ships.
4. **A4. Release identity.** "Initial Release" is R1 (v2.0) and the "second release" is R2 (v2.1); the shipped file is the later v16.0 rebuild. See `docs/07-product-backlog.md` §2, §11 and `docs/17-single-pool-operational-model.md`.
5. **A5. Risk owners.** Risk owners are recorded as the role letters used in the planning documents; the four members and the roles they held are named in `../../docs/Contribution-Matrix.md`, and `docs/07-product-backlog.md` §4 maps the letters onto them. *Corrected:* this assumption previously read "no individual is named in any artefact", which the contribution matrix disproves.
6. **A6. Exposure scores.** Likelihood and impact are the authors' judgement against the evidence in this folder. They are not derived from incident data, because no incident history is retained beyond what `docs/03-test-record.md` records.
7. **A7. Documentation drift.** One cited screenshot does not match the shipped artefacts (defect DEF-17 in `docs/08-test-plan.md` §9). DEF-14, DEF-15 and DEF-16 were closed in R3 by completing the `workers/README.md` catalogue and replacing the drifted diagram document with `docs/06-diagram-engineering.md`. This plan records the remainder as risk R-13 and feedback items in `docs/10-sprint-reviews-and-feedback.md` §4.
