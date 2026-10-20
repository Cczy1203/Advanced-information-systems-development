# UFCEP6-0-3 Hospital Patient Referral, Treatment and Administration System

**Group Mj, Advanced Information Systems Development.**
**Current release: v16.0**, the operational model rebuilt as one pool, carrying the
v15.0 feedback response (RBAC, form validation, H2 persistence) forward unchanged.

---

## 1. What this is

A case-study hospital patient pathway modelled as a single Camunda 8 BPMN process,
one hospital pool, responsibilities as lanes, the outside participants as black-box
pools — implemented with external job workers, Camunda Forms and an embedded H2
database. The model was rebuilt from the v14.0 fourteen-pool collaboration; why, and
the evidence, is in `bpm/docs/17-single-pool-operational-model.md`.

The system covers the patient journey from referral and booking through treatment
planning, funding checks, correspondence, follow-up scheduling and audit reporting,
keeping the clinical, administrative and financial responsibilities apart.

**Scale of the delivered artefact**

| | |
|---|---|
| BPMN process | **one**, the hospital, with 3 responsibility lanes holding 9 team lanes |
| Participants | 7: the hospital pool plus 6 black-box outside participants |
| Flow nodes | 166 (150 flow nodes + 16 boundary events) |
| Sequence / message flows | 180 / 15 |
| User tasks | 38, every one with a Camunda Form **and** a candidate group |
| Service tasks | 48, every one with a job type a worker subscribes to |
| Camunda Forms | 37 files, 237 fields, all 37 bound in the model |
| External workers | 36 Java classes subscribing to 36 job types — no orphan on either side |
| Database | H2, 15 tables, idempotent schema and seed |
| Roles | 10 declared, matching the model's 9 candidate groups plus an auditor |

---

## 2. What v15.0 changed, and why

The release answers the three items written against this group in the external
`Group Feedback` sheet. Nothing else in the model was changed, so the release can be
judged on the feedback it answers.

| Feedback item | What was done | Where the evidence is |
|---|---|---|
| 1. Implement role-based access control in Camunda | 11 users, 10 roles matching the BPMN's candidate groups, 20 least-privilege authorisation blocks; enforcement demonstrated by refusal | `bpm/camunda/application.yaml`, `bpm/tools/verify.ps1 -Check rbac`, `bpm/screenshots/v15/rbac-enforcement.txt` |
| 2. Improve form validation, particularly date selections | All 37 forms hardened; one shared date-rule table drives both the forms and a worker-side validator | `bpm/tools/harden_forms.py`, `bpm/workers/src/main/resources/date-rules.json`, `bpm/workers/.../support/DateRuleValidator.java` |
| 3. Implement database integration for data persistence | Embedded H2 behind the unchanged store API, with reference data used for business validation | `bpm/workers/src/main/resources/db/`, `bpm/workers/.../db/`, `bpm/tools/verify.ps1 -Check persistence` |

Measured before and after (both releases measured by the same script, the v14.0
baseline extracted from git so the comparison is like-for-like):

| Metric | v14.0 | v15.0 |
|---|---|---|
| Form `pattern` rules | 0 | **63** |
| Required fields | 142 | **147** |
| Form-validation findings | 6 | **0** |
| Roles declared to the cluster | 0 | **10** |
| Authorisations persisted | 0 | **213** |
| State that survives a restart | none | **all of it** |

The full account, decision, action, evidence, result and limitations for each item,
is in `bpm/docs/14-feedback-response.md`. The planning comparison is in
`bpm/docs/15-project-plan-assessment.md`. The same three actions appear as
FB-15 to FB-17 in `bpm/docs/10-sprint-reviews-and-feedback.md` §5.1.

---

## 3. Read these in order

1. `bpm/docs/14-feedback-response.md`. What the feedback asked, what was decided, what was changed, what is proved, what is not solved
2. `bpm/docs/15-project-plan-assessment.md` — original plan vs revised plan vs what actually happened
3. `bpm/docs/17-single-pool-operational-model.md`. Why the model is one pool, what it contains, and the measured evidence
4. `SUBMISSION.md`, index mapping each assessment requirement to a file
5. `bpm/README.md`. The model, the drawing and the headline numbers
6. `bpm/RUNBOOK.md` — how to reproduce a release end to end
7. `bpm/docs/20-accessibility-and-the-forms.md`. The accessibility work, and what it does not claim
8. `bpm/docs/18-cited-files-no-longer-present.md`. The 39 paths the documents cite that are no longer in the tree, and what replaced each
9. `bpm/docs/02-status.md`. What is known not to work

---

## 4. Repository structure

| Path | What is in it |
|---|---|
| `bpm/model/` | The deployable BPMN collaboration and the 37 `.form` files |
| `bpm/diagram/` | The rendered diagram (PNG, SVG, PDF) and 14 section images |
| `bpm/workers/` | The Java external workers: `pom.xml`, `src/main/java`, `src/test/java`, `src/main/resources` |
| `bpm/camunda/` | The orchestration-cluster configuration and the start/stop scripts |
| `bpm/tools/` | Model, form and verification tooling (analysis, hardening, deployment, end-to-end driver) |
| `bpm/docs/` | Modelling decisions, test plan and record, risk register, backlog, feedback log |
| `bpm/screenshots/` | Run logs and captured evidence, including `v15/` for this release |
| `docs/` | Group-level planning artefacts: backlogs, sprint plans, contribution matrix |

---

## 5. Running it

### 5.1 Prerequisites

| | |
|---|---|
| JDK | 21 (`java -version` must report 21) |
| Maven | 3.9.x, **offline build** — needs `bpm/workers/maven-settings.xml` |
| Camunda | A local Camunda 8.10 orchestration cluster (c8run distribution works) |
| Python | 3.x, for the model and form tooling only |

### 5.2 Build the workers

```bash
cd bpm/workers
mvn -gs maven-settings.xml -s maven-settings.xml -o package
```

Expected: `BUILD SUCCESS`, **52 tests, 0 failures**. The shaded jar lands in
`bpm/workers/target/hospital-external-workers-1.0.0.jar`.

> `-gs` and `-s` are both required, and the settings file must declare no mirrors.
> The reason is written into `bpm/workers/maven-settings.xml`: cached artefacts record
> the repository id `central`, and declaring a mirror under a different id makes the
> offline build fail provenance verification.

### 5.3 Start the engine

```bash
pwsh -File bpm/camunda/start-engine.ps1 -Detached
```

There are two configuration profiles, selected by switches on this script. They differ
by one marked line each in `bpm/camunda/application.yaml`; the script edits only the
runtime copy, so the delivered configuration never changes.

| Profile | Switch | Use it for |
|---|---|---|
| RBAC (default) | *(none)* | Demonstrating role-based access control |
| Workers | `-WorkersProfile` | Running the external workers end to end |
| Workers + protected API | `-WorkersProfile -ProtectedApi` | Running workers with the REST API requiring credentials |

Why the profiles exist: with `authorizations.enabled: true`, the unauthenticated gRPC
job workers receive no jobs at all, jobs stay in state `CREATED` and the worker log
shows `COMPLETED 0`. This is measured, not assumed, and is documented as limitation L-1 in
`bpm/docs/14-feedback-response.md`. See §6 below.

### 5.4 Deploy and run

```bash
# deploy the model and all 37 forms in one batch
pwsh -File bpm/tools/verify.ps1 -Check engine

# prove persistence survives a cold restart
pwsh -File bpm/tools/verify.ps1 -Check persistence

# full end-to-end regression: engine + real workers + all 8 scenarios
pwsh -File bpm/tools/verify.ps1 -Check e2e

# role-based access control: allowed and refused, in both directions
pwsh -File bpm/tools/verify.ps1 -Check rbac -ProtectedApi
```

`verify.ps1 -Check e2e` must start, verify and stop the engine **inside one invocation**:
on a machine where the shell reaps its process tree at the end of a command, an engine
left running in the background does not survive.

### 5.5 Worker configuration

Every setting has an environment-variable override; the mapping is listed in the header
of `bpm/workers/src/main/resources/application.yaml`. The two groups added in v15.0:

```yaml
database:
  enabled: true
  url: jdbc:h2:file:./data/hospital
  seed: true
  validation:
    strict-patient: false
    require-accepting-gp: true
security:
  enabled: true
  enforce: true
```

---

## 6. Known limitations

These are stated rather than omitted. The full list with evidence is in
`bpm/docs/14-feedback-response.md` §6.

- **L-1, RBAC enforcement and the unauthenticated gRPC worker are mutually exclusive
  in this environment.** This build supports only BASIC and OIDC authentication
  (`AuthenticationMethod` has no `NONE`), and `zeebe-client-java:8.9.0` cannot perform
  BASIC. With no OIDC provider available offline, the worker cannot present an identity,
  and the gRPC job-activation path will not accept one that is absent. This is why the
  two profiles above exist. Moving the workers to OAuth client credentials is the correct
  next step.
- L-2, Form-level date bounds are calendar constraints, not enforcement.
  `disallowPassedDates` is a flatpickr `minDate`; it never runs in the renderer's
  validation function. The worker-side `DateRuleValidator` is therefore the enforcement
  layer, not a duplicate of the form.
- L-3 — Five persistence tests self-skip under a restricted file sandbox, where
  `java.nio.file.Files.isWritable()` reports `false` for every path while actual writes
  succeed. H2 uses that check to decide a database is read-only. Outside the sandbox they
  run and pass; the end-to-end persistence proof does not depend on them.
- **L-4. The model still has 14 activities where several sequence flows converge without
  a merging gateway. This was not** changed: merging gateways are asked of other
  groups in the feedback sheet, not of this one, and re-drawing a verified model to fix a
  point nobody raised for us would risk the deployment for no assessed gain. The analysis
  is retained in `bpm/tools/analyse_bpmn.py` so the decision can be revisited.
- The five outside participants are documented pools, not deployed process
  definitions; they reuse the hospital-side job types.

---

## 7. Notes for the team

- Process evidence counts for as much as the code. Every claim in the v15.0 documents
  names a file that exists or a command that reproduces it.
- A backlog row marked `Done` without a gate result is not done. That rule is what the
  v15.0 release was audited against, and it is why `bpm/docs/10-sprint-reviews-and-feedback.md`
  §5 carries unfinished rows with reasons instead of a clean sheet.
- The `_runtime/` directory holds engine state (RocksDB, H2, logs). It is regenerable and
  is not part of the submission.
