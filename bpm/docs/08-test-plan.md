# Test plan and execution record

Test counterpart to the delivered portfolio. The test strategy and the plan are in
§1–§6; the execution record is in §7–§9. Every actual result and status in §7 is
taken from `docs/03-test-record.md` or from the evidence file named in the row.
Nothing is asserted as a pass without an artefact behind it. Where evidence is
absent, the row says so.

Read with: `docs/03-test-record.md` (the working execution record this plan
formalises), `docs/07-product-backlog.md` (the items being tested), `docs/02-status.md`
(what is known not to work), `workers/README.md` and `workers/DEPLOYMENT.md`
(worker behaviour and configuration).

---

## 1. Test strategy

### 1.1 Levels

Effort is layered for a reason. A defect is caught at the cheapest level that can
catch it, and the expensive live runs are kept for integration work, not syntax.

| Level | ID prefix | What it proves | Tooling | When it runs |
|---|---|---|---|---|
| Static model lint and layout analysis | `TC-BPMN` | The BPMN parses, the DI is complete, the drawer's rules hold, and scored elements survive a regeneration | `tools/validate_model.js`, `tools/analyse_layout.py`, `tools/verify_preservation.py`, Camunda Modeler 5.51.0 | After every model regeneration |
| Worker unit and contract | `TC-WRK` | Each worker handles success, invalid input and the BPMN error conditions in its contract | `mvn` build plus throwaway models run against the live engine | After every worker change |
| Form render and validation | `TC-FRM` | Every form imports into the renderer that Tasklist uses, and the field types used are supported | `@bpmn-io/form-js` in headless Chrome | After every form regeneration |
| Deployment and configuration | `TC-DEP` | The model and its forms deploy together, within the batch ceiling, and re-deploy cleanly | `tools/deploy.sh` | At every release |
| End-to-end process | `TC-E2E` | The collaboration runs across pools with real messages, user tasks and worker jobs, with no incidents | `tools/demo_scenario.py`, Operate, Tasklist | At every release and after every behavioural change |
| Non-functional | `TC-NFR` | Data protection, role separation, audit behaviour, availability handling and accessibility intent | Static inspection of model, forms and worker sources; no dedicated NFR harness exists | At release, by inspection |

### 1.2 Test types

Functional (process behaviour, exception routing, gateway outcomes), integration
(message correlation, worker-to-engine, form-to-task binding), regression
(preservation audit, re-run of both paths after a drawing-only change), static
(parser, lint, DI completeness, job-type and error-code coverage), configuration
(deployment, subscription, environment overrides), data-protection (card-data
exclusion, minimum test data), usability/accessibility (form structure and
descriptions). Negative testing forces a service failure, feeds invalid input and
publishes an uncorrelated message.

There is no automated performance, load or penetration testing in this portfolio.
That is a scope decision, not an omission, and it is stated again in §10.

### 1.3 Risk-based rationale: what is tested hardest

| Rank | Area | Why it is tested hardest | Depth |
|---|---|---|---|
| 1 | Message correlation between pools | A missing or wrong correlation key produces a live incident (`JOB_NO_RETRIES`), and the whole collaboration depends on the hand-off working. It was the first real defect found by running the model (`docs/03-test-record.md` §B1) | Every throw event statically; both live paths end to end |
| 2 | Form field types and form-to-task binding | One unsupported field type made 17 fields and every form containing them unrenderable, and 39 user tasks depend on the forms. This was the single most valuable defect found (`docs/03-test-record.md` §F4) | All 36 forms rendered in the real renderer; binding checked for 39/39 tasks |
| 3 | Exception branches with an owner | The assessment rewards handling, not detection. A branch that reaches a bare end event is a failure of the modelled business process | All 9 error codes and 18 boundary events checked statically; the referral branch driven live |
| 4 | Layout quality | The rubric names overlap and parallel-adjacency as faults and asks for a diagram a person can read. It is a measured, automatable gate | Every rebuild measured; first two rows must be zero before the build is accepted |
| 5 | Preservation across a regeneration | R3 changes the drawing and two modelling rules; a silent loss of a form, candidate group, job type or exception hand-off would cost marks already earned | 67 parsed checks against the previous file, run before R3 was accepted |
| 6 | Payment and financial handling | Money is involved; a duplicate charge or a lost confirmation must not be silently retried | Worker contract tests for every payment outcome; live happy path |
| 7 | Deployment size and versioning | Camunda 8 stores the whole BPMN resource per process definition, and **v14's fifteen processes mean fifteen copies**; the 4 MB append batch is a hard ceiling that already forced a design decision, and v14 has taken that risk on to connect the outside participants | Measured at every deployment; recorded in §7; the v14 exposure and its three mitigations are in `docs/11-white-box-external-participants.md` §5 |

Everything else (formatting, label wording, cosmetic clipping) is tested for
existence and recorded, but is not allowed to hold a release.

---

## 2. Scope

**In scope.** The BPMN collaboration and its diagram interchange; the 36 Camunda
Forms; the 36 Java worker classes and their 37 job-type subscriptions; the build
and deployment scripts in `tools/`; the two scripted run paths; the Operate and
Tasklist evidence; and the configuration files that make the above reproducible.

**Out of scope.** Any external service; any production system; production
identity and RBAC; persistent storage; the web applications themselves (Operate
and Tasklist are used as supplied, not tested); and any cluster other than the
local c8run instance.

### 2.1 Test items

| Item | Version / identity | Location |
|---|---|---|
| BPMN collaboration | `UFCEP6-0-3_Hospital_Patient_Pathway_v2.bpmn`, 15 participants, 9 executable processes, `versionTag` 2.0.0 | `model/` |
| Camunda Forms | 36 files, form-js `schemaVersion` 19, `executionPlatformVersion` 8.10.0 | `model/forms/` |
| External workers | `hospital-external-workers-1.0.0.jar`, 36 task classes, 37 subscriptions | `workers/` |
| Generator and gates | `build_v2.py`, `spec_v2.py`, `bpmn_builder_v2.py`, `layout_engine.py`, `forms_spec.py` | `tools/` |
| Deployment and demo | `deploy.sh`, `demo_scenario.py`, `render_diagram.sh`, `export_sections.py` | `tools/` |
| Verifiers | `verify_preservation.py`, `analyse_layout.py`, `validate_model.js` | `tools/` |
| Evidence | run logs and UI screenshots | `screenshots/`, `diagram/` |

### 2.2 Features to be tested

Message hand-off and correlation; the nine hospital processes and their user
tasks; gateway behaviour (34 exclusive, 3 inclusive, 2 parallel, 2 event-based);
the nine exception conditions; compensation definitions; the clinic-letter timer
ladder; form rendering, binding and validation; worker success, validation
failure and BPMN-error paths; deployment and re-deployment; both end-to-end paths;
and the data-protection rule on card data.

### 2.3 Features NOT to be tested

Real provider integration; performance and load; concurrent multi-instance
contention; security penetration of the c8run webapps; the Tasklist rendering
path (blocked by an environmental `401`, see `TC-FRM-07`); WCAG conformance with
assistive technology (`TC-NFR-06`); and any browser other than Chrome
(`TC-NFR-07`).

The three branches that were never driven (`TC-E2E-03` to `TC-E2E-05`) and the
live compensation trigger (`TC-E2E-06`) are no longer gaps: all four were
driven on v14 (`docs/03-test-record.md` §J11–J15). What remains outstanding is
Operate, Tasklist and Modeler screenshots of v14, and the two pre-existing
documentation defects DEF-14 and DEF-16.

---

## 3. Entry, exit, suspension and resumption criteria

**Entry criteria (before any test run).**

| # | Criterion | Check |
|---|---|---|
| E1 | The engine answers: `GET /v2/topology` returns 200 | c8run 8.10.0-alpha5 running on `localhost:8080` / `localhost:26500` |
| E2 | The generator exits 0 and the two layout gates are zero | `python3 tools/build_v2.py`; `python3 tools/analyse_layout.py model/…bpmn` |
| E3 | The model parses clean in the Modeler's parser | `node tools/validate_model.js model/…bpmn` |
| E4 | The deployment is accepted | `bash tools/deploy.sh` reports 9 process definitions and 36 forms |
| E5 | The workers are running and subscribed | Start-up log shows the job-type subscriptions on `localhost:26500` |
| E6 | The test data is seeded as intended | `application.yaml` demo switches set for the branch under test |

**Exit criteria (before a release is signed off).**

| # | Criterion |
|---|---|
| X1 | Layout gates: sequence-flow overlaps 0 pairs and message-flow overlaps 0 pairs (`docs/03-test-record.md` §A1–A2) |
| X2 | Preservation gate: 67/67 parsed checks pass for any release after R1 |
| X3 | Static parser gate: 0 warnings, 0 unresolved references, 0 dangling flows, 0 user tasks without a form or candidate group, 0 service tasks without a job type |
| X4 | Both scripted paths complete with `incidents: none` |
| X5 | Non-functional design checks (`TC-NFR-01` to `TC-NFR-04`) hold, or their failure is recorded as an accepted residual risk |
| X6 | Every test row has an actual result and an evidence reference, or is honestly marked `NOT RUN` / `NOT EVIDENCED` |

**Suspension criteria.** Suspend the run if the engine dies or the deployment is
rejected; if a change makes either scripted path hang or raise an incident the
defect is not attributed to the test; or if an expected evidence file cannot be
written.

**Resumption criteria.** Resume only after the generator accepts the change
(E2), the model parses clean (E3) and the change has been re-deployed (E4). A run
made against an undeployed model is discarded, not recorded.

---

## 4. Test environment and configurations

| Component | Configuration used | Where it is recorded |
|---|---|---|
| Engine | Camunda c8run **8.10.0-alpha5**, gRPC `localhost:26500`, REST `http://localhost:8080`; `GET /v2/topology` → 200 | `docs/01-gap-audit.md` header; `docs/03-test-record.md` header |
| Modeler | Camunda Modeler **5.51.0**; model target platform `Camunda 8.10 (alpha)`, target **Local C8Run** | `screenshots/camunda-modeler-v2.1-status-bar.png`; `docs/03-test-record.md` §H5a |
| Model platform metadata | `modeler:executionPlatform="Camunda Cloud"`, `modeler:executionPlatformVersion="8.10.0"`, exporter 5.51.0 | parsed from the model file |
| Model version tag | `zeebe:versionTag value="2.0.0"` on all processes (9 at v7.0, 15 at v14) | parsed from the model file |
| Workers runtime | Plain Java (no Spring Boot): `maven.compiler.release` **21**, `zeebe-client-java` **8.9.0**, Jackson 2.21.2, slf4j 2.0.17, logback 1.5.32 | `workers/pom.xml` |
| Build toolchain | Maven 3.9.9; built under JDK 25 while targeting release 21 | `docs/01-gap-audit.md` header; `workers/pom.xml` comment |
| Form renderer | `@bpmn-io/form-js`, the renderer Tasklist uses, driven in headless Chrome | `docs/03-test-record.md` §F4 |
| Diagram renderer | `bpmn-js` 17.11.1 in headless Chrome, the same engine the Modeler canvas uses | `tools/render_diagram.sh` |
| Browser | Google Chrome (macOS, `darwin-aarch64` bundle) | `tools/render_diagram.sh`; screenshot set |
| Scripting | Python 3 (`deploy.sh`, `demo_scenario.py`, the analysers); Node (the lint and export) | `tools/` |

**Configuration under test.** The demo switches in
`workers/src/main/resources/application.yaml` are part of the test configuration:
`demo.simulated-failure` (`always` / `once`), `demo.payment.status`
(`APPROVED` / `DECLINED` / `DUPLICATE` / `NO_CONFIRMATION`),
`demo.payment.confirmation-lost-mode` (`bpmn-error` / `retry`),
`demo.scheduling.force-no-slots`, `demo.external.unavailable-resources`,
`demo.pathway.scenario` (`SEVEN_DAYS` / `ONE_MONTH` / `THREE_MONTHS`), and
`demo.clock.today` / `offset-days`. Every key is overridable by an environment
variable; the mapping is documented in the file itself and in
`workers/DEPLOYMENT.md` §4.

---

## 5. Test data strategy

| Data | How it is produced | Reproducibility |
|---|---|---|
| Patient reference | `demo_scenario.py` generates a per-run reference, e.g. `PAT-DEMO-18020` (normal path) and `PAT-DEMO-18106` (exception path) | Unique per run, so instances do not collide on correlation keys |
| Form variables | Filled by `demo_scenario.py` over the REST API exactly as a person would fill them in Tasklist: the same form fields, submitted with the same completion call | Deterministic per run |
| Dates and day counts | `DemoClock` is freezable and shiftable (`demo.clock.today`, `demo.clock.offset-days`) so that day counts and escalation bands are reproducible | Deterministic when the clock is pinned |
| Escalation bands | The in-memory store seeds an overdue clinic letter according to `demo.pathway.scenario` (`SEVEN_DAYS` → worst case 9 days; `ONE_MONTH` → 45 days; `THREE_MONTHS` → 120 days, the default) | Deterministic per scenario |
| External-service results | Simulated: `correspondence.dispatch-letter`, `scheduling.find-appointment-slots`, `external-resources.check-availability`, `payment.process-transaction`, `payment.process-refund` are deterministic stubs driven by the demo switches | Deterministic, but simulated |
| Failure/invalid input | `SimulatedFailureRegistry` can force `always` or `once` failure per job type; a canonical BPMN error code can be pinned as `job-type:ERROR_CODE` | Deterministic |
| Personal data | None. Test identifiers are synthetic (`PAT-DEMO-…`); no real patient data is used or required | By design (see `TC-NFR-08`) |
| Idempotency state | In-memory `HospitalStore`, reset when the worker JVM restarts | A repeat across a restart is not the same test as a repeat inside one JVM (a limitation, see §10) |

**Simulated external services and their limitations.** The five simulated job
types never call a network service. The four suppliers were black-box pools in
v7.0, and from v14 they are white-box pools of their own. They genuinely exercise
the success and failure branches, and they produce plausible references, but they
cannot confirm delivery, settlement or capacity, nor reproduce the timing and
partial-failure behaviour of a real provider. Swapping one for a real API means
replacing one worker class (`workers/README.md`, "Simplifications and known
gaps"). No test result in §7 should be read as evidence of real integration.

---

## 6. Defect management

**How defects are logged.** Every defect is found by running something, not by
reading. It is entered against the test case that found it, with the symptom as
observed, the cause, the fix, and the severity. The working record is §B and §F4
of `docs/03-test-record.md`; the table in §9 below formalises it with IDs and
severities.
**Severity scale.**

| Severity | Meaning | Release effect |
|---|---|---|
| S1 Blocker | The release cannot be accepted: the model will not deploy or run, a scored deliverable would be lost, or a financial rule is broken | Must be fixed before the release |
| S2 Major | A scored behaviour is wrong or unreliable but a workaround exists | Must be fixed before the release unless explicitly accepted |
| S3 Minor | A visible quality defect that does not change behaviour | Fixed if time allows; recorded otherwise |
| S4 Cosmetic | Appearance only | Recorded; normally deferred |

**Triage rule.** An S1 or S2 defect found during a run suspends the run under §3
until it is fixed and the run is repeated. S3 and S4 defects are recorded and
carried; they do not suspend a run.

---

## 7. Test cases and execution record

Status legend: **PASS** (expected met, evidence present); **FAIL** (expected not
met); **PARTIAL** (met in part, or met with an accepted deviation);
**NOT RUN** (never executed); **NOT EVIDENCED** (claimed or implied somewhere but
no evidence file exists in the workspace).

### 7.1 Static model, layout and structure: `TC-BPMN`

| ID | Objective | Preconditions | Steps | Expected | Actual | Status | PB | Evidence |
|---|---|---|---|---|---|---|---|---|
| TC-BPMN-01 | No sequence-flow overlaps or parallel adjacency | Model regenerated | `python3 tools/analyse_layout.py model/…bpmn` | 0 pairs / 0 px | 0 pairs / 0 px (v2.1; v1.0 was 142 pairs / 18,951 px) | PASS | PB-05 | `docs/03-test-record.md` §A1 |
| TC-BPMN-02 | No message-flow overlaps | as above | as above | 0 pairs / 0 px | 0 pairs / 0 px (v1.0 was 448 pairs / 507,620 px) | PASS | PB-05, PB-26 | §A2 |
| TC-BPMN-03 | No diagonal segments | as above | as above | 0 px | 0 px | PASS | PB-05 | §A3 |
| TC-BPMN-04 | No line passes through an unrelated shape | as above | as above | 0 pairs | **0 pairs** in R3 (v7.0). v2.0 and v2.1 had 4: sibling boundary events sat 34 px apart on 36 px circles, and a line leaving the left one crossed the right one | **PASS** | PB-05, PB-34 | §A4; `docs/06-diagram-engineering.md` §3.2–3.3 |
| TC-BPMN-05 | Bends per sequence flow ≤ 4 | as above | as above | ≤ 4 | mean 1.1, max 4 | PASS | PB-05 | §A5 |
| TC-BPMN-06 | A routing channel separates pools | as above | as above | present | 104 px | PASS | PB-05, PB-26 | §A6 |
| TC-BPMN-07 | Lanes exist where a pool covers several desks | as above | as above | lanes present | 14 lanes across 6 pools at v7.0; **20 lanes at v14**, one for each of the six outside participants | PASS (re-measured) | PB-04 | §A7; `docs/11` §4 |
| TC-BPMN-08 | Repetitive administration is contained | as above | as above | collapsed sub-processes used | 3 collapsed sub-processes | PASS | PB-06 | §A8 |
| TC-BPMN-09 | Crossings minimised | as above | as above | as low as possible | **94** in R3 (v7.0), down from 197 in v2.1, 147 in v2.0 and 42 in v1.0. Two causes: the router measures the crossings a candidate corridor would create instead of picking the nearest one, and giving every path its own end event removed the long runs to shared circles | **PASS**: 52% reduction, with 0 overlaps and 0 clipped lines held | PB-27, PB-34 | `docs/06-diagram-engineering.md` §3.1, §3.4, §3.5 |
| TC-BPMN-10 | Model opens in Camunda Modeler with no errors | Modeler 5.51.0 installed | Open the model; read the status bar | 0 errors | **0 errors** in v2.1 (`screenshots/camunda-modeler-v2.1-status-bar.png`). In R3 the underlying linter was re-run on the shipped file under the project's own `bpmnlint:recommended` config: **0 errors / 32 warnings**, against 39 errors in v2.1. DEF-18 is closed | **PASS** on both the Modeler and the stricter config | PB-29, PB-34 | `screenshots/static-checks-v7.0.txt` §4; `docs/03-test-record.md` §I2b |
| TC-BPMN-11 | Model parses clean in the Modeler's own parser | Node with `bpmn-moddle` and `zeebe-bpmn-moddle` | `NODE_MODULES_DIR=… node tools/validate_model.js model/…bpmn` | 0 warnings, 0 unresolved refs, 0 dangling flows, 0 user tasks without a form or candidate group, 0 service tasks without a job type | exactly that | PASS | PB-24, PB-25 | §H5d |
| TC-BPMN-12 | Regeneration loses nothing scored | The v2.0 baseline is vendored at `tools/baseline/…bpmn` | `python3 tools/verify_preservation.py` | all checks pass | **67 checks, 67 passed, 0 failed** in R3 (62 in the v2.1 round, §H1) | PASS | PB-25 | `screenshots/static-checks-v7.0.txt` §2 |
| TC-BPMN-13 | Sub-process steps remain in the file and executable | as above | Count inner elements and check reachability | 28 inner elements present | 28/28 | PASS | PB-06, PB-25 | §H1; `docs/05-v2.1-changes.md` §3 |
| TC-BPMN-14 | No Camunda 7 attributes | as above | Scan for the 6 forbidden attribute names | none present | none present | PASS | PB-25 | §H1 |
| TC-BPMN-15 | Structural census matches the intended design | Model present | Parse participants, processes, lanes, tasks, forms, flows | 15 pools, 9 executable processes, 14 lanes, 39 user tasks, 47 service tasks, 36 forms, 15 drawn message flows, 311 sequence flows, 65 end events (v7.0) | exactly those counts at v7.0; **v14: 15 pools, 15 executable processes, 20 lanes, 39 user tasks, 51 service tasks, 36 forms, 22 drawn message flows, 329 sequence flows, 72 end events** | PASS at v7.0; v14 counts re-parsed and listed in `docs/11` §4 | PB-02, PB-04, PB-09, PB-13 | parsed from `model/…bpmn`; `README.md` headline numbers |
| TC-BPMN-24 | No end event merges more than one terminating path | Model present | Count incoming sequence flows per end event | every end event has exactly one incoming flow | **65/65 have exactly one incoming; none is unreachable** | PASS | PB-35 | `docs/06-diagram-engineering.md` §3.5 |
| TC-BPMN-25 | The drawn message flows are only the ones that inform | Model present | Compare the drawn set with the retention rule | every exception hand-off drawn, four system-boundary hand-offs drawn, nothing else | **15 drawn = 11 exception + 4 boundary; 100%** | PASS | PB-35 | `docs/06-diagram-engineering.md` §3.6 |
| TC-BPMN-16 | All nine exception conditions exist and are reachable | Model present | Enumerate `bpmn:error` and boundary events | 9 error codes, 18 boundary events, all attached to a host activity | 9 and 18, matching names in `docs/05-v2.1-changes.md` §3 | PASS | PB-07, PB-08 | §H1; parsed from the model |
| TC-BPMN-17 | The generator is deterministic | Dependencies installed | Run `python3 tools/build_v2.py` twice and compare | byte-identical output | byte-identical | PASS | PB-25 | `docs/05-v2.1-changes.md` §5 |
| TC-BPMN-18 | Build-time guards refuse a dangerous model | Generator present | Inspect and exercise the guards | Refuses unbound/undefined forms, two elements in one grid cell, and a model mixing boolean `true` with text `"true"` comparisons | Guards present in `build_v2.py` (`check_cells`, form binding) and the builder (boolean/text); the last two were added after defects `DEF-02` and `DEF-09` | PASS | PB-05, PB-15, PB-25 | `tools/build_v2.py`; `docs/03-test-record.md` §B2, §B9 |
| TC-BPMN-19 | Every user task has a form and a candidate group | Model present | Parse `zeebe:formDefinition` and `zeebe:assignmentDefinition` on each user task | 39/39 with both | 39/39, candidate groups matching the pool roles | PASS | PB-09, PB-10 | §H1, §H5d |
| TC-BPMN-20 | Thinning the drawn message flows changed no behaviour | v2.1 deployed | Re-run both paths and compare incidents | both paths clean | both paths clean, `incidents: none` (hand-off is the throw event's job, not the drawn line) | PASS | PB-26 | §H3 |
| TC-BPMN-21 | Message start events reduced to ≤ 2 per pool | — | Count start events | ≤ 2 per pool | **43 start events**: target missed, because a Camunda 8 message start subscribes to one message name, so collapsing them needs a protocol change | FAIL (deferred to PB-33) | PB-33 | §H6a; `docs/05-v2.1-changes.md` §4 |
| TC-BPMN-22 | Four clipped lines fixed | — | Re-run TC-BPMN-04 | 0 pairs | **0 pairs** in R3 (v7.0): sibling boundary-event pitch widened to `EVT + 6`, boundary-host rows grown by `BND_DEPTH`, and a verified `_unclip` pass that can only remove a defect | **PASS** | PB-34 | `docs/06-diagram-engineering.md` §3.2–3.3 |
| TC-BPMN-23 | Sub-process boxes drawn open | — | Set `V2Builder.EXPAND_SUBPROCESSES = True` and measure | open boxes with no new faults | tried and reverted: 21 lines through a shape against 4, and 3 new overlaps | NOT RUN (deliberately reverted) | PB-06 | §H6d; `docs/05-v2.1-changes.md` §4 |

### 7.2 Worker contract and integration (`TC-WRK`)

| ID | Objective | Preconditions | Steps | Expected | Actual | Status | PB | Evidence |
|---|---|---|---|---|---|---|---|---|
| TC-WRK-01 | Workers build | Maven 3.9.9, offline repository populated | `mvn -q -o clean package` | BUILD SUCCESS | success, 29 MB fat jar | PASS | PB-13 | §E1 |
| TC-WRK-02 | One subscription per job type at start-up | Engine up | Start the jar; read the log | subscription per job type | **37 job-type subscriptions** on `localhost:26500` | PASS | PB-13 | §E2, §H2b |
| TC-WRK-03 | The three v2.0 job types resolve | as above | Check the log for the new types | all three registered | `treatment.release-series`, `treatment.release-cycle-booking`, `treatment.record-capacity-retry` all registered | PASS | PB-18, PB-19 | §E3 |
| TC-WRK-04 | Jobs complete with no incidents during the paths | Both paths run | Run `demo_scenario.py` and `--exception`; search incidents | no incidents | no incidents in either run | PASS | PB-13 | §E4 |
| TC-WRK-05 | Referral worker success and both error branches | Throwaway model in `/tmp` | Activate and exercise the worker | success, `REFERRAL_PACK_INCOMPLETE`, `REFERRAL_PACK_UNREADABLE` branches behave | all three exercised against the live cluster | PASS | PB-07, PB-13 | `workers/README.md` ("Verified against the running engine") |
| TC-WRK-06 | A blank correlation key fails safely | Throwaway model | Publish a message with a blank key | job fails three times, then an incident naming the variable; no BPMN error | exactly that | PASS | PB-03, PB-13 | `workers/README.md` |
| TC-WRK-07 | All domain job types run in one process | Throwaway 34-task model | Run it | completes with no incidents, including idempotency repeats | completed with no incidents | PASS | PB-13, PB-15 | `workers/README.md` |
| TC-WRK-08 | Failure injection works in both modes | Demo switches set | Force `always` and `once`, and the canonical simulated codes | BPMN error on the boundary in `always`; engine retry then success in `once` | both modes verified, plus empty-recipient dispatch and a malformed-variable job failure | PASS | PB-14 | `workers/README.md`; `application.yaml` |
| TC-WRK-09 | Idempotency | Live store | Repeat a booking/charge operation | same reference returned; no duplicate created | repeats return the same appointment; duplicate charges detected | PASS | PB-15 | `workers/README.md`; §E1–E4 |
| TC-WRK-10 | An over-large refund does not throw an unroutable error | Throwaway model | Force a refund larger than the amount paid | failed job (incident), not a BPMN error | failed job, as designed: the model attaches no boundary error event to that step | PASS | PB-07 | `workers/README.md` ("Simplifications and known gaps") |
| TC-WRK-11 | Payment confirmation-lost handling is configurable | Demo switches | Run with `bpmn-error` and with `retry` | `bpmn-error` throws `PAYMENT_CONFIRMATION_LOST`; `retry` fails the job | both behaviours verified | PASS | PB-07, PB-14 | `workers/README.md`; `application.yaml` |
| TC-WRK-12 | Workers verified against the *full* collaboration | — | Run the workers against the generated collaboration | full integration verified at worker-test level | Not done at worker-build time: verification used equivalent throwaway models because the collaboration was still being regenerated; integration was later demonstrated by the two scripted paths (TC-E2E-01/02) | PARTIAL | PB-13 | `workers/README.md` ("Not verified") |
| TC-WRK-13 | The job-type table documents every model job type | Sources and README present | Compare model job types with the README table | every type documented | **Model has 35 distinct service-task job types; the README table documents 32.** The three v2.0 types are missing from it, and its summary line still reads "33 job workers = 1 + 32" although 36 task classes exist | FAIL (documentation defect `DEF-14`) | PB-13 | `workers/README.md`; `workers/src/.../tasks/` (36 classes); §E3 |

### 7.3 Forms: `TC-FRM`

| ID | Objective | Preconditions | Steps | Expected | Actual | Status | PB | Evidence |
|---|---|---|---|---|---|---|---|---|
| TC-FRM-01 | Every form imports and renders in the Tasklist renderer | `@bpmn-io/form-js` available; headless Chrome | Render all 36 forms | no failures | **`TOTAL=36 FAILED=0`** | PASS | PB-23 | `screenshots/camunda-forms-rendered.png`; §F4 |
| TC-FRM-02 | No unsupported field types | as above | Census the field types actually emitted | only supported types | census: `textfield 69, radio 35, textarea 47, select 25, number 17, datetime 19, checkbox 12, checklist 6`, with no `date`; the earlier `"type": "date"` defect is fixed | PASS | PB-23 | §F4 |
| TC-FRM-03 | Long forms are grouped by heading for accessibility | Forms present | Count `group` components | at least the long forms grouped | **0 `group` components in any of the 36 forms**: the grouping half of PB-12 was not implemented | FAIL | PB-12 | form JSON census; `docs/01-gap-audit.md` §C3 |
| TC-FRM-04 | Fields carry an accessible description | Forms present | Count descriptions against fields | every field described | 71 `description` values across 230 components, so coverage is partial | PARTIAL | PB-12 | form JSON census |
| TC-FRM-05 | Validation rules are present | Forms present | Count `validate` blocks and inspect rules | required/length/range where needed | 172 `validate` blocks across the 36 forms | PASS | PB-11 | form JSON census; `docs/01-gap-audit.md` §C2 |
| TC-FRM-06 | Every user task is bound to a defined form and vice versa | Model and forms present | Cross-check bindings and definitions | every bound form defined and every defined form bound | 39/39 user tasks bound; 36 unique forms, two shared on purpose (`resolve-dispatch-problem`, `answer-administrative-enquiry`); build check asserts both directions | PASS | PB-09 | `tools/build_v2.py` (`user_tasks`, binding checks); §H1 |
| TC-FRM-07 | Forms render inside Tasklist | c8run webapps running | Open a claimed task; watch the Task tab | the form renders | **NOT EVIDENCED**: the Task tab stayed empty; Tasklist gets `401` from `/v2/authentication/me` (with and without basic credentials), so it cannot fetch the schema. The forms themselves are proven to render by TC-FRM-01 | NOT EVIDENCED (environmental, deferred to PB-32) | PB-32 | §F5; `docs/02-status.md` ("Not done") |
| TC-FRM-08 | Labels use role-appropriate language | Forms present | Read the labels against the task's role | clerical tasks use administrative wording, clinical tasks clinical wording | not systematically checked; the gap audit records the concern (`docs/01-gap-audit.md` §C5) and no re-check exists | NOT EVIDENCED | PB-12 | `docs/01-gap-audit.md` §C5 |

### 7.4 Deployment and configuration (`TC-DEP`)

| ID | Objective | Preconditions | Steps | Expected | Actual | Status | PB | Evidence |
|---|---|---|---|---|---|---|---|---|
| TC-DEP-01 | Model and all forms deploy in one batch | Engine up | `bash tools/deploy.sh` | accepted, no error | **9 process definitions + 36 forms** | PASS | PB-20 | §C1 |
| TC-DEP-02 | Re-deployment after a change is accepted and versioned | as above | Re-run the deployment | accepted | accepted; the v2.1 rebuild deployed as **process definitions at v17 and forms at v18** (engine-assigned versions) | PASS | PB-20, PB-29 | §C2, §H2a |
| TC-DEP-03 | The resource stays inside the 4 MB append batch | as above | Measure the resource against the ceiling | inside the limit | v7.0: 397 KB × 9 processes, inside the limit. **v14 with all fifteen executable is rejected: "Can't append entry ... with size: 405002 this would exceed the maximum batch size ... currentBatchSize: 4095764". Nine fit, the tenth does not.** Shipped configuration: 9 executable in the main file (deploys clean, key 2251799813952610) + the 6 outside participants from a 30 KB second file (deploys clean) | **PASS as shipped; the 15-in-one-batch variant is a documented failure** | PB-20 | §C3; `docs/04-modelling-decisions.md` §7.6; `docs/11` §5; `screenshots/static-checks-v14.txt` §8 |
| TC-DEP-04 | Workers build and subscribe on the stated runtime | JDK and Maven installed | Build and start | subscriptions on `localhost:26500` | 37 subscriptions; the jar targets Java 21 bytecode and was built under JDK 25 | PASS | PB-13 | §H2b; `workers/pom.xml` |

### 7.5 End-to-end paths and UI evidence: `TC-E2E`

| ID | Objective | Preconditions | Steps | Expected | Actual | Status | PB | Evidence |
|---|---|---|---|---|---|---|---|---|
| TC-E2E-01 | Normal path across pools | Deployment and workers in place | `python3 tools/demo_scenario.py` | every step reached, no incidents | **all eleven steps reached**, `incidents: none` at each stage end; `medical-secretaries`, `consultants`, `outpatient-bookings`, `call-handling`, `treatment-bookings` and `finance-team` exchanged messages | PASS | PB-21 | `screenshots/run-happy-path.log`; §D1, §H3a |
| TC-E2E-02 | Unreadable-referral exception path | as above | `python3 tools/demo_scenario.py --exception` | `REFERRAL_PACK_UNREADABLE` thrown, caught by the boundary event, case leaves the main line and joins the missing-information loop, no incident | exactly that, `incidents: none`; the branch reaches `SEC_EGW_InfoRequest` | PASS | PB-22 | `screenshots/run-exception-path.log`; §D2, §H3b |
| TC-E2E-03 | Declined-payment branch | Demo payment status set to `DECLINED` | Drive the path to payment | branch runs, no duplicate booking or charge | never executed | NOT RUN (deferred to PB-30) | PB-30 | §D3, §G, §H6e; `docs/02-status.md` |
| TC-E2E-04 | Payment-confirmation-lost branch | `DEMO_PAYMENT_STATUS=NO_CONFIRMATION`, `--investigate` | Drive the path to payment | investigation raised and a clinician asked to authorise urgent treatment | **executed on v14**: `FIN_Task_InvestigatePayment` and `CON_Task_AuthoriseUrgentTreatment` both driven, `incidents: none` | **PASS** (was NOT RUN) | PB-30 | `screenshots/run-confirmation-lost-v14.log`; `docs/03` §J12 |
| TC-E2E-05 | Three-month letter escalation | `DEMO_LETTER_OVERDUE_DAYS=120`, `--overdue`, short-timer variant deployed | Drive the overdue-letter path | escalation to the Administrative Management Team | **executed on v14**: `SUB_Pathway_Report_Review` and `ADM_Task_ReferHigher` driven; with `DEMO_LETTER_OVERDUE_DAYS=45` the manager rung (`ADM_Task_ContactConsultant`) is driven instead | **PASS** (was NOT RUN) | PB-30 | `screenshots/run-overdue-escalation-v14.log`, `run-escalation-manager-v14.log`; `docs/03` §J13–J14 |
| TC-E2E-06 | Compensation triggered live | Engine and workers running, capacity forced unavailable, short-timer variant deployed | Force the giving-up path and observe the handler | compensation handler completes in a real instance | **executed on v14**: `TRT_Throw_CompSeries`, `TRT_Bnd_CompSeries` and `TRT_Comp_ReleaseSeries` all COMPLETED on instance 2251799813979308, no incident | **PASS** (was NOT RUN) | PB-31 | `screenshots/run-compensation-v14.log`; `docs/03` §J15 |
| TC-E2E-07 | A v2.0 task can be claimed and completed in Tasklist | c8run webapps | Open Tasklist, claim a task, complete it | task opens with its candidate group and form | **NOT EVIDENCED**: `docs/03-test-record.md` §F2 cites `screenshots/tasklist-camunda-form.png` for this, but no such file exists in `screenshots/`. What does exist is `screenshots/tasklist-open-tasks.png`, which shows the open task list and the pool names | NOT EVIDENCED | PB-32 | `screenshots/tasklist-open-tasks.png`; §F1, §F2, §H4d |
| TC-E2E-08 | The engine reports no incidents and a completed instance shows its real path | Operate reachable | Read the dashboard and a completed instance | no incidents; executed steps and variables visible | **21 running instances, 0 with an incident**, "Your processes are healthy"; a completed Medical Secretaries instance shows its Instance History and the real variables `adminChecksCarriedOut`, `approvingClinician`, `authorizingClinician`, `chargeAmount`, `appointmentDate` | PASS | PB-21, PB-24 | `screenshots/operate-dashboard.png`, `operate-instance-completed.png`, `operate-processes.png`; §H4 |

### 7.6 Non-functional (`TC-NFR`)

| ID | Objective | Preconditions | Steps | Expected | Actual | Status | PB | Evidence |
|---|---|---|---|---|---|---|---|---|
| TC-NFR-01 | No complete card data is stored or emitted | Payment worker sources | Inspect the variables the payment workers read and write | only a payment reference, status, date and amount | payment workers "never emit card data"; only `paymentReference`, `paymentStatus`, `paymentRef`, `paymentDate`, `paidAmount` are returned | PASS (design inspection) | PB-16 | `workers/README.md` job types 13 and 24 |
| TC-NFR-02 | Clinical and financial responsibilities stay separate | Model and candidate groups | Check that clinical decisions sit in clinical groups and financial decisions in Finance, and that no user task mixes them | separation holds | gateway conditions route funding to `finance`, clinical decisions to `consultants`/`clinical-nurse-specialists`; 39/39 candidate groups match the pool | PASS (static); behavioural proof of refusal NOT EVIDENCED | PB-10, PB-17 | model `assignmentDefinition`; `docs/04-modelling-decisions.md` §3; §H5d |
| TC-NFR-03 | Audit records are not overwritten by clinical edits | Audit worker sources | Inspect the two audit workers | audit ref and timestamp written; clinical variables not written back; blank `patientRef` fails the job | exactly that | PASS (worker contract; engine-level immutability NOT TESTED) | PB-17 | `workers/README.md` job types 2 and 3 |
| TC-NFR-04 | Behaviour during an external-service failure is defined | Demo switches | Force each simulated service to fail | the modelled boundary error fires with a defined owner; retries are bounded by `retries="3"`; no unbounded retry loop | each simulated code is reachable and its boundary event exists; retry cap 3 verified at worker level on throwaway models | PASS at worker level; full-path NOT RUN for the three undriven branches | PB-07, PB-14, PB-19 | `workers/README.md`; §H1; §D3 |
| TC-NFR-05 | Performance and load | — | Measure throughput, latency or concurrency | no target exists | never measured; no NFR harness exists. One instance at a time is driven | NOT RUN | — | — |
| TC-NFR-06 | Accessibility conformance | — | Run a WCAG conformance assessment with assistive technology | conformance level met | never run; only the structural checks TC-FRM-03/04 (both incomplete) were attempted | NOT RUN | PB-12 | — |
| TC-NFR-07 | Cross-browser and cross-platform behaviour | — | Repeat the form and UI checks in another browser | renders in more than Chrome | only Chrome was used | NOT RUN | — | §F4 (headless Chrome) |
| TC-NFR-08 | No personal data in test artefacts | Repo present | Inspect test data and screenshots | synthetic identifiers only | `PAT-DEMO-…` references, illustrative financial figures, demo clock; no real patient data. A data-protection impact assessment was not produced | PASS for test data; DPIA NOT EVIDENCED | PB-16 | `docs/04-modelling-decisions.md` §6 items 4–5; run logs |

---

## 8. Requirement → test traceability matrix

Backlog item → the tests that exercise it. An item with no test beside it has not
been tested.

| Backlog item | Tests | Coverage note |
|---|---|---|
| PB-01 Gap audit | — | Analysis item; its own evidence is the measurement, not a test |
| PB-02 Participants and processes | TC-BPMN-15, TC-DEP-01 | Counted and deployed |
| PB-03 Correlated hand-offs | TC-WRK-06, TC-E2E-01, TC-E2E-02 | Static + live |
| PB-04 Lanes | TC-BPMN-07, TC-BPMN-15 | Counted |
| PB-05 Layout engine | TC-BPMN-01, -02, -03, -05, -06, -18 | Measured |
| PB-06 Collapsed sub-processes | TC-BPMN-08, -13, -23 | Counted; open-box variant deferred |
| PB-07 Exception branches with owners | TC-BPMN-16, TC-WRK-05, TC-WRK-10, TC-E2E-02, TC-NFR-04 | One branch live; others static |
| PB-08 Letter timers and escalation | TC-BPMN-16, TC-E2E-05 | **Driven on v14**, both rungs (short-timer variant; `docs/03` §J13–J14) |
| PB-09 Forms per user task | TC-BPMN-19, TC-FRM-01, TC-FRM-06 | Complete |
| PB-10 Candidate groups | TC-BPMN-10, TC-BPMN-19, TC-NFR-02 | Static |
| PB-11 Form validation | TC-FRM-05 | Structural |
| PB-12 Accessibility and descriptions | TC-FRM-03, TC-FRM-04, TC-FRM-08, TC-NFR-06 | **Failing / not evidenced** |
| PB-13 Workers per job type | TC-WRK-01 – TC-WRK-04, TC-WRK-07, TC-WRK-12, TC-WRK-13, TC-DEP-04 | Integration level partial |
| PB-14 Simulated services and failure switches | TC-WRK-08, TC-WRK-11, TC-NFR-04 | Complete at worker level |
| PB-15 Duplicate suppression | TC-WRK-07, TC-WRK-09, TC-E2E-01 | Verified |
| PB-16 No card data | TC-NFR-01, TC-NFR-08 | Inspection |
| PB-17 Audit workers | TC-NFR-02, TC-NFR-03 | Inspection |
| PB-18 Compensation | TC-BPMN-16, TC-E2E-06 | Modelled and **live trigger driven on v14** (`docs/03` §J15) |
| PB-19 Capped external-capacity retry | TC-WRK-08, TC-NFR-04 | Worker level |
| PB-20 Deployment | TC-DEP-01, -02, -03 | Complete |
| PB-21 Normal path evidence | TC-E2E-01, TC-E2E-08 | Complete |
| PB-22 Exception path evidence | TC-E2E-02 | Complete |
| PB-23 Form rendering | TC-FRM-01, TC-FRM-02 | Complete |
| PB-24 Test record and decisions | TC-BPMN-11, TC-E2E-08 | The record is evidence, not a subject |
| PB-25 Preservation audit | TC-BPMN-12, -13, -14, -17, -18 | Complete |
| PB-26 Message-flow thinning | TC-BPMN-02, -20, TC-E2E-01, TC-E2E-02 | Complete |
| PB-27 End-event merge | TC-BPMN-09 | Trade-off measured |
| PB-28 Lane consolidation | TC-BPMN-07, TC-BPMN-15 | Counted |
| PB-29 Modeler validation and export | TC-BPMN-10, -11 | Complete |
| PB-30 Undriven branches | TC-E2E-03, -04, -05 | **NOT RUN** |
| PB-31 Live compensation | TC-E2E-06 | **Driven on v14**: handler completed in a real instance, `incidents: none` |
| PB-32 Tasklist form display | TC-FRM-07, TC-E2E-07 | **NOT EVIDENCED** |
| PB-33 Start-event reduction | TC-BPMN-21 | **FAIL (deferred)** |
| PB-34 Crossing reduction | TC-BPMN-04, -09, -22 | **PASS in R3**: 197 → 94 crossings, clipped lines 4 → 0 |
| PB-35 Readable terminals and hand-offs | TC-BPMN-24, -25 | **PASS in R3**: 65 end events, none merged; 15 drawn message flows, with no exception hand-off lost |
| PB-35 Real provider integration | — | Explicitly out of scope |

---

## 9. Defect log

### 9.1 Defects recorded in `docs/03-test-record.md`

All thirteen were found by running the model or the forms, not by reading it.

| ID | Test | Severity | Symptom as observed | Cause | Fix / status |
|---|---|---|---|---|---|
| DEF-01 | TC-WRK-06 | S1 | `JOB_NO_RETRIES` incident on the first message throw | A worker publishes the message and needs the correlation key as a process variable | Builder now writes a `correlationKey` input mapping onto every throw event. **Fixed** |
| DEF-02 | TC-E2E-01 | S1 | Incident at `CON_GW_ConsentGiven`: *Can't compare `"true"` with `true`* | Yes/No radios submit the text `"true"`; ten conditions compared against a boolean, giving a FEEL null | All ten conditions compare against `"true"`; the build refuses a model that mixes the two. **Fixed** |
| DEF-03 | TC-WRK-04 | S1 | `booking.record-appointment-outcome` failed | It ran before the form that captures the outcome | Task order swapped; **Fixed** |
| DEF-04 | TC-E2E-01 | S2 | `SUB_CallHandling_Contact` forked: two tasks active at once | A node inside the collapsed sub-process had two unconditional outgoing flows | Exclusive gateway added inside the sub-process with a condition and a default. **Fixed** |
| DEF-05 | TC-BPMN-03 | S4 | Lines drawn as long diagonals | Same-row links used port offsets, tilting a 300 px run by 7 px | Straight runs take a single level. **Fixed** |
| DEF-06 | TC-BPMN-04 | S3 | Every flow out of a boundary event routed to the far-left channel | Boundary events inherited `col = 0`; the host's grid cell was applied after routing was planned | Boundary events inherit their host's cell during the row phase. **Fixed** |
| DEF-07 | TC-BPMN-02 | S3 | Message risers landing on top of each other | All pools share a column grid, so channel 5 in one pool sat at the same x as channel 5 in another | Message flows get their own half of every channel, allocated globally per column. **Fixed** |
| DEF-08 | TC-BPMN-02 | S3 | Riser lookup collapsing | One message has two risers that can share a column, so keying by message index merged them | The lookup key identifies the segment, not the message. **Fixed** |
| DEF-09 | TC-BPMN-18 | S2 | Two new elements drawn on top of existing ones | Compensation handlers and the retry chain were given grid cells already in use | Cells remapped; `build_v2.py` refuses a model where two elements share a cell. **Fixed** |
| DEF-10 | TC-BPMN-04 | S4 | Message lines running behind the note boxes | Notes sat at the foot of each pool, in the path of the risers | Notes moved into one panel below the collaboration. **Fixed** |
| DEF-11 | TC-E2E-06 | S1 | Compensating for a booking that was never made | Compensation handlers were attached before the confirm step in one place | Handlers attached to the activities that actually commit the booking. **Fixed** |
| DEF-12 | TC-FRM-01 | S1 | `render error: form field of type <date> not supported`; the Tasklist Task pane stayed blank | 17 fields across the forms used `"type": "date"`; Camunda Forms has no `date` type, so a date-only field is `datetime` with `subtype: "date"` | `tools/forms_spec.py` now emits `datetime` with a subtype; all 36 forms render. **Fixed** |
| DEF-13 | TC-FRM-01 | S1 | The DEF-12 fix silently did not reach the generated files | `build_v2.py` imported `spec_v2` before `forms_spec`, and `spec_v2` put the v1.0 tools directory on `sys.path`, so the v1.0 `forms_spec.py` was loaded | Import order corrected; **Fixed** |

### 9.2 Documentation and planning defects found while writing this plan

These are not model defects. They are recorded because they affect a marker's
reading of the portfolio and are the kind of thing configuration management is
supposed to catch.

| ID | Severity | Finding | Evidence | Status |
|---|---|---|---|---|
| DEF-14 | S3 | `workers/README.md` documented 32 of the 35 domain job types the model uses and its summary line was stale | compare `workers/README.md` table with the model job types and `workers/src/.../tasks/` (36 classes) | **Closed in R3.** The catalogue now lists 36 rows (0–35), names the three missing types (`treatment.record-capacity-retry`, `treatment.release-series`, `treatment.release-cycle-booking`), and its summary lines read 36 workers = 1 dispatcher + 35 service tasks. See FB-09. |
| DEF-15 | S2 | `docs/06-visual-compaction.md` described a compaction (9 lanes, 12 sub-processes, 15 message flows, canvas 2,398 × 6,858) that was not present in the shipped model | parse the model file; compare with `README.md`, `docs/02-status.md`, `docs/03-test-record.md` §H, `docs/05-v2.1-changes.md` §2 | **Closed in R3**: the drifted document was deleted and replaced by `docs/06-diagram-engineering.md`, which describes the shipped drawing and records the abandoned pass with its measurements. See FB-11. |
| DEF-16 | S3 | The subscription count was stated as 34 in `workers/README.md` and 37 in `docs/03-test-record.md` §E2 | 36 task classes; 35 distinct model job types; one alias; `publish-message` → 37 subscriptions | **Closed in R3.** `workers/README.md` now states 37 subscriptions and shows the arithmetic. This plan documents the same figure in `docs/07-product-backlog.md` A5. |
| DEF-17 | S3 | `docs/03-test-record.md` §F2 cited `screenshots/tasklist-camunda-form.png`, which did not exist | directory listing of `screenshots/` | **Closed in R3.** The Tasklist login answered on a clean engine, a user task was left pending, and the form was captured open in Tasklist (`screenshots/tasklist-camunda-form.png`, landed on `/tasklist/2251799813689594`). See `TC-E2E-07` |
| DEF-18 | S4 | Under the project's own `bpmnlint:recommended` config, two elements were implicit starts: `TRT_Throw_BookingPending` (the head of the counted capacity retry, left unreachable when the v2.0 pass pointed the capacity boundary event straight at the release step) and `SUB_Secretaries_Dispatch_Chase` (the retry step inside the collapsed dispatch sub-process) | `bpmnlint model/*.bpmn`; walk the sequence flows into each element | **Closed in R3**: the capacity boundary now enters the retry chain it was built for, and the dispatch sub-process gained an inner gateway that reaches the retry step on the status the worker already returns. `bpmnlint` reports 0 errors; both paths re-run with `incidents: none` |
| DEF-19 | S3 | Outpatient Bookings parked at `OUT_Catch_PhoneContact` for ever and Call Handling always had a contact task pending | polled for 90 s; re-ran with the message published by hand | **Closed in R3: two causes, neither of them the model's message wiring.** (1) **Test harness:** `wait_for_task` filtered user tasks by process definition *id*, so on a shared engine it regularly completed a matching task belonging to an abandoned instance from an earlier session. The run's own instance then waited for ever, and the branch looked broken. The lookup is now scoped to the instances this run creates, and the branch completes. (2) **Model:** the Call Handling process ended by looping straight back into its own sub-process (`SUB_CallHandling_Contact → CALL_Throw_ContactFinished → SUB_CallHandling_Contact`), so it never finished and always had a pending contact task. It now ends after the hand-off is published. Proven correct in the strongest available way: publishing `appointment.phone-contact-finished` by hand with the right key moved a stuck instance immediately, so correlation was never the problem |
| DEF-22 | S3 | The capacity retry could never finish: `TRT_Auto_RecordRetry` mapped `=externalResourceAttempts + 1`, and the counter starts unset, so `null + 1` is null. `TRT_GW_CapacityCap` then evaluated `externalResourceAttempts < 3` to NULL rather than BOOLEAN and raised an incident, so the loop neither retried nor released and the compensation handlers were unreachable | ran the short-timer variant with `external-resources.check-availability` forced to fail; two treatment instances parked at `TRT_GW_CapacityCap` with incident *"Expected result of the expression 'externalResourceAttempts < 3' to be 'BOOLEAN', but was 'NULL'"* | **Closed in R3**: the mapping is now `=if externalResourceAttempts = null then 1 else externalResourceAttempts + 1`. Re-run: the retry loop counts 1, 2, 3, takes the cap, and **the compensation handlers execute** (`TRT_Comp_ReleaseSeries` completed 4 times). That is the first live execution of compensation this portfolio has had |
| DEF-23 | S4 | After the higher-management rung was worked, `ADM_Throw_HigherRecorded` parked: the "record the escalation" throw did not complete | active element instances for administrative-management | **Closed in R3.** Same family as DEF-21: Administrative Management is *started by* the escalation, so it inherits the batch context and has no `patientRef`, but its two "record the escalation" throws still keyed on the patient. Both now use `="letter-escalation"`. Confirmed on a clean engine: the ladder runs to both rungs and the Administrative Management instance reaches `COMPLETED` (`ADM_Throw_HigherRecorded` published `letter.escalation-recorded`, no active elements left) |
| DEF-21 | S3 | The clinic-letter escalation ladder cannot complete. `PCW_Start_WeeklyReview` is a **timer** start event, so the instance has no `patientRef`, yet `PCW_Throw_EscalateManager` and `PCW_Throw_EscalateHigher` key their messages on `=patientRef + "-letter-escalation"`. The key evaluates to null, so the worker refuses the job: *"Process variable 'correlationKey' is missing or blank for message 'letter.escalation-higher-management'"*. The instance parks. Found by demonstrating the branch, which is what the demonstration was for | ran the short-timer variant (`model/demo/`), drove the weekly review task (`SUB_Pathway_Report_Review` completed), then read the worker log: three failed `publish-message` jobs on `PCW_Throw_EscalateHigher`, remainingRetries 2/1/0 | **Closed in R3.** Both escalation messages and their `bpmn:message` subscriptions now correlate on `="letter-escalation"`, the review run rather than a patient the timer-started instance does not have. Re-run: `PUBLISHED ... letter.escalation-higher-management correlationKey=letter-escalation`, and `ADM_Task_ReferHigher` was driven to completion. The compromise is that all escalations from a review run share one key, so only one Administrative Management instance exists at a time; a production design would key on the letter, and that is written down rather than hidden |
| DEF-20 | S4 | The clinic-letter escalation ladder and the compensation handlers cannot be driven in a run of demonstration length: the weekly review is a `R/PT168H` timer start event and the capacity retry waits on `P3D` timers | traced the pathway process: `PCW_Start_WeeklyReview` is a timer start event, not a message start; `TRT_Catch_RetryTimer` is `P3D` | **Closed in R3.** A short-timer variant (`model/demo/`, three timers set to `PT15S`, identical process ids) is built by `build_v2.py` and deployed with `BPMN=model/demo/... ./tools/deploy.sh`. The shipped model keeps the real durations. Both were then driven live: the ladder runs to both rungs and completes, and the compensation handler executes. Note the side effect recorded in `model/demo/README.md`: the variant's repeating timer cannot be withdrawn through the 8.10.0-alpha5 API and needs an engine restart |

---

## 10. What is not covered, and the residual risk

| Not covered | Why | Residual risk | Where it is tracked |
|---|---|---|---|
| Declined payment, confirmation lost, three-month escalation | Not driven before the release was signed off | A branch that is modelled but never run can still contain a routing or data defect; the payment branches carry financial consequence | PB-30; `docs/03-test-record.md` §D3, §H6e; risk R-05 |
| Live compensation | No run gave up a committed resource | The model-side compensation wiring is asserted statically but its runtime behaviour is unproven | PB-31; risk R-06 |
| Tasklist rendering | c8run authentication returns `401` for this setup | The forms are proven to render, but the delivered user journey through Tasklist is not demonstrated | PB-32; `docs/03-test-record.md` §F5; risk R-07 |
| Real external services | Five simulated job types | Delivery, settlement and capacity behaviour of real providers is unknown, including partial failure | risk R-04; `workers/README.md` |
| Performance, load and concurrent instances | No NFR harness and no target was set | Single-instance timing proves nothing about the audit trail under concurrent pathway load | TC-NFR-05; risk R-08 |
| Accessibility conformance | Only structural field checks were attempted, and the grouping half of PB-12 was not delivered | The forms may not meet the accessibility expectation in the rubric despite rendering correctly | TC-FRM-03, TC-FRM-06, TC-NFR-06; risk R-09 |
| Security of the webapps and the cluster | Out of scope; local c8run only | Not a deliverable, but any real deployment would need it | `docs/09-risk-contingency-and-config-management.md` §1 |
| Cross-instance compensation | Camunda 8 compensation does not cross process instances; a refund is an explicit hand-off instead | The design limitation is deliberate and documented; it is not tested as a compensation | `docs/04-modelling-decisions.md` §5 |
| Message start events ≤ 2 per pool | Deferred with the arithmetic recorded | The start-event target in the brief remains unmet; it needs a message-protocol change | TC-BPMN-21; PB-33; risk R-10 |
| Crossing reduction and clipped lines | **Delivered in R3** | 197 → 94 crossings, 4 → 0 clipped lines, 0 overlaps held | TC-BPMN-04, -09, -22; PB-34 |
| One end event per path and far fewer dashed lines | **Delivered in R3** | 32 → 66 end events, none merged; 31 → 15 drawn message flows with nothing meaningful dropped. **v14 trades four of those lines back (15 → 22) for six connected outside participants**, the deliberate exception, recorded in `docs/11` | TC-BPMN-24, -25; PB-35 |
| Idempotency across a worker restart | State is in memory in one JVM | A restart could allow a repeat that a persistent store would prevent | `docs/04-modelling-decisions.md` §7 item 5; risk R-11 |

---

## 11. Assumptions

1. **A1: Worker runtime.** The brief supplied to the author of this document describes the workers as "Java 17 Spring Boot". The artefact does not match: `workers/pom.xml` sets `maven.compiler.release` to **21**, depends on `io.camunda:zeebe-client-java` 8.9.0, and contains no Spring Boot dependency; configuration is plain YAML read by `AppConfig`. This plan tests the worker as it is built.
2. **A2: Test dates and runner.** No test-run dates, machine names or operator identities are recorded beyond the environment header in `docs/03-test-record.md`. Test runs are attributed to first/second owners in `docs/07-product-backlog.md`, which is a planning value, not a recorder's log.
3. **A3: "37 job types".** The model defines 47 service tasks across 35 distinct job types; the workers produce 37 job-type subscriptions (35 model types + one alias + `publish-message`). Where a document says "37 job types" or "34 subscriptions", the reconciliation is in `docs/07-product-backlog.md` Assumption A5 and defect DEF-16.
4. **A4: Diagram document.** This plan takes the shipped model file as the source of truth (14 lanes, 3 sub-processes, 15 drawn message flows, 65 end events, canvas 5,332 × 14,176). The earlier compaction document that disagreed with it was removed in R3; DEF-15 is closed.
5. **A5: Missing screenshot.** `screenshots/tasklist-camunda-form.png`, cited by `docs/03-test-record.md` §F2, does not exist in the workspace. `TC-E2E-07` is therefore recorded as `NOT EVIDENCED` rather than as a pass.
6. **A6: Accessibility.** No accessibility rationale document exists in `docs/`, although `docs/01-gap-audit.md` §C3 asked for one. `TC-FRM-03`, `TC-FRM-04`, `TC-FRM-08` and `TC-NFR-06` reflect that absence honestly.
7. **A7: Defect identifiers.** Defects DEF-01 to DEF-13 are re-identified here from §B and §F4 of `docs/03-test-record.md`; that record uses B1–B11 and prose headings rather than ID prefixes. The cross-reference is one-to-one and stated in the table.
