# Feedback response: the three actions from the Group Feedback sheet


> **Citations to files that are not in this tree.** An audit found 39 paths cited across 19 documents that no longer exist. The fourteen-pool model, the v1/v2 generators and the drawing scripts that went with them, and the Sprint 0 Node scaffold. Nothing was lost: all of it is in git history, and every citation is listed with what replaced it in [18-cited-files-no-longer-present.md](18-cited-files-no-longer-present.md).

**UFCEP6-0-3 Advanced Information Systems Development, Group Mj, release v15.0**

This document answers the three items written against Group Mj in the external
`Group Feedback` sheet. It records, for each item, what was asked, what the
position was before the change, the decision taken and why, what was changed,
the evidence that it works, and what is still not solved. It is the repository
record; the same content is delivered as a bilingual document for the review
meeting.

**The three items, verbatim from the sheet:**

1. Implement role-based access control in Camunda.
2. Improve form validation, particularly for date selections, to prevent invalid
   or inappropriate dates.
3. Implement database integration to support data persistence.

Nothing else was asked of this group. The other recurring themes in the sheet —
merging gateways, additional process options, rewritten acceptance criteria,
belong to other groups' rows and were deliberately not treated as ours. That
decision is recorded in §6.

---

## 1. How to read the evidence

Every claim below names a file that exists in this repository, or a command that
reproduces it. Two conventions:

- A gate is a command. A statement is only "verified" if a command in §5 was
  run and its output is quoted or retained under `bpm/screenshots/v15/`.
- A limitation is written down, not omitted. §6 lists what is still not
  solved and why. An action that was not carried out keeps its entry.

The baseline for all three items is tag `v14.0-final`, the release reviewed. The
"before" figures were recomputed from that tag rather than quoted from the old
documents, so that the before and after numbers are measured with one ruler.

---

## 2. Item 1 — Role-based access control in Camunda

### 2.1 Position before the change

The v14.0 model already carried `zeebe:assignmentDefinition candidateGroups` on
all 39 user tasks across nine candidate groups, but nothing enforced them:

| Check | v14.0 |
|---|---|
| User tasks with a candidate group | 39 / 39 |
| Roles declared to the Camunda cluster | **0** |
| Users declared to the Camunda cluster | **0** |
| Authorisation checks enabled | **no** (`authorizations.enabled: false`) |
| Grant persisted in the engine database | **none** |

The candidate groups were names in the BPMN file. No user belonged to any of
them, and the engine was not checking anything. This is precisely the gap the
feedback names: the model *described* roles, it did not *implement* them.

### 2.2 Decision

Declare the roles and their members in the cluster configuration and switch
authorisation checking on, but do it so that the roles match the model rather
than being invented beside it. Two sub-decisions:

- The nine candidate groups in the BPMN become the nine hospital roles. No
  new role names are introduced, so there is exactly one name for each
  responsibility across the model, the configuration and the database.
- **The grant is proved from the engine's own database, not from our file.**
  Writing a YAML file that says `authorizations.enabled: true` proves nothing if
  the engine silently persists no grant. The verification therefore reads the
  `AUTHORIZATIONS` table directly.

### 2.3 What was changed

| File | Change |
|---|---|
| `bpm/camunda/application.yaml` | New. 11 users (one per role plus `demo`), **10 declared roles**, the nine business roles plus `auditor`, **20 role-authorisation blocks carrying 57 permission entries**, `authorizations.enabled: true`, `authentication.method: BASIC` |
| `bpm/camunda/start-engine.ps1` | New. Starts the cluster from the delivered configuration without writing to the read-only `E:\camunda` installation |
| `bpm/camunda/stop-engine.ps1` | New |
| `bpm/tools/verify.ps1 -Check engine` | New. Starts the engine, deploys, waits for the asynchronous exporter, stops the engine, then reads the RBAC tables with the H2 shell and writes the evidence file |

The roles and their least-privilege grants: `medical-secretaries`, `consultants`,
`finance`, `outpatient-bookings`, `treatment-bookings`,
`clinical-nurse-specialists`, `call-handling`, `pathway-coordinators`,
`administrative-management` each receive `USER_TASK` (`READ`, `CLAIM`,
`COMPLETE`, `UPDATE`) and `PROCESS_DEFINITION` (`READ_PROCESS_DEFINITION`,
`READ_PROCESS_INSTANCE`). `auditor` deliberately receives no `USER_TASK`
grant at all — only `AUDIT_LOG` read. So that a refusal can be demonstrated
rather than asserted.

### 2.4 Evidence and result

Command: `bpm/tools/verify.ps1 -Check engine`. > Correction, v16.0. The read-back was captured twice. The second capture (`users-roles-authorizations.txt`) was taken against a different, empty engine database and reports zeros; the first (`rbac-enforcement.txt`) holds the 11/16/213/11 numbers. Both files are kept and the empty one is headed with what it is.

 Evidence: `bpm/screenshots/v15/rbac-enforcement.txt` (not `users-roles-authorizations.txt`, which is an empty second capture),
`topology.json`, `deployment.json`, `summary.json`.

| Reading, taken from the engine's H2 database | Result |
|---|---|
| Engine reached | `gatewayVersion = 8.10.0-alpha5`, topology ready |
| Deployment | key `2251799813685383`, **9 process definitions + 36 forms** |
| `USER_` rows | **11** |
| `ROLES` rows | **16** (our 10 plus 6 built in) |
| `AUTHORIZATIONS` rows | **213** |
| `ROLE_MEMBER` rows | **11**, every declared user is a member of its role |
| `USER_TASK` grants | **50** = our nine business roles × 4 permissions (36) + 14 built in |
| Grants held by our ten roles | **57** |
| Engine log `ERROR` lines | 1, and it is a shutdown artefact — see L-4 |

Result: complete for the engine layer. The roles named in the BPMN are now
real roles in the cluster, the members are real users, and the grants are
persisted in the engine database.

### 2.5 Enforcement: authentication is compulsory, authorisation is applied

A table full of grants proves that permissions were *written*. It does not prove they are
*applied*. `bpm/tools/verify.ps1 -Check rbac -ProtectedApi` therefore calls the same endpoints
with different identities and requires different outcomes. This profile sets
`unprotected-api: false`, so the REST API genuinely requires an identity.

| Identity | Role | Endpoint | Expected | Measured |
|---|---|---|---|---|
| anonymous |, | `/v2/user-tasks/search` | 401 | **401**, authentication is compulsory |
| `demo` | built-in admin | `/v2/authorizations/search` | sees rows | **200, returns real authorisation rows** |
| `sec.demo` | medical-secretaries | `/v2/authorizations/search` | sees none | **200, empty result**, none of the 213 rows is visible |
| `audit.demo` | auditor | `/v2/authorizations/search` | sees none | **200, empty result** |
| `fin.demo` | finance | `/v2/authorizations/search` | sees none | **200, empty result** |
| `sec.demo` | medical-secretaries | `/v2/process-instances/search` | 200 | **200** |
| `audit.demo` | auditor | `/v2/audit-logs/search` | 200 | **200** |
| `audit.demo` | auditor | `/v2/user-tasks/search` | 200 | **200** |

The conclusion is stated precisely. Anonymous gets nothing (401); three business roles
see **none** of the authorisation rows through the same endpoint, while the built-in admin
sees real rows through it — so the authorisation check is demonstrably running. But it
manifests as result filtering, not as a 403 refusal: in this build, no hard 403 was
observed on any endpoint tested. The claim recorded here is therefore "authentication
compulsory and authorisation applied", not "a refusal was demonstrated", because the latter
has no measurement behind it.

**Two further facts this round established, both written into the configuration comments:**

- `unprotected-api: true` gives up authorisation along with authentication. In that
  profile the authorisation check does not run even when BASIC credentials are supplied, a
  role with zero `USER_TASK` grants such as `auditor` still gets 200 on every REST call.
  Opening `authorizations.enabled` while leaving `unprotected-api: true` therefore **cannot
  show whether RBAC works at all**. That is why the `-ProtectedApi` switch exists.
- Search endpoints do not perform an authorisation decision. `user-tasks/search` and
  `audit-logs/search` return 200 even without the corresponding grant; only a resource with
  explicit authorisation semantics, such as `authorizations/search`, shows a difference.
  Recorded because it determines what counts as a valid test.

The persisted matrix, read back from the engine's own database in the same run, confirms
what the roles hold: 213 authorisation rows, **11** role memberships, and `auditor`
holding exactly 3 grants, audit-log `READ` plus process-definition
`READ_PROCESS_DEFINITION` / `READ_PROCESS_INSTANCE`, and no `USER_TASK` grant at all.
The `AUTHORIZATION` resource is held only by the built-in `admin` (4) and `readonly-admin`
(1), which is precisely why the three business roles see an empty list.

---

## 3. Item 2 — Form validation, particularly dates

### 3.1 Position before the change

| Check | v14.0 |
|---|---|
| Forms / fields | 36 / 230 |
| Required fields | 142 |
| Date-typed fields | 19 |
| `pattern` rules | **0** |
| Findings from the inventory | **6** (19 date fields with no bound at all, 7 that should be required) |

### 3.2 Decision — and the fact that decided it

Before writing any validation, the behaviour of the renderer was established from
its own source rather than from documentation, because the two differ:

- Modeler 5.51.0 embeds `@bpmn-io/form-js-editor` 1.25.0; the Tasklist that
  actually renders the forms embeds `@bpmn-io/form-js-viewer` 1.24.1. The
  validation code in both is byte-identical (SHA256 of each validation region
  matches), so the difference is harmless.
- `validate` supports exactly: `required`, `pattern`, `patternErrorMessage`,
  `min`, `max`, `minLength`, `maxLength`, `validationType`.
- **A `datetime` field reads only `validate.required`.** Adding `min` or `max` is
  not merely ignored: the bound is parsed as a number, throws, and the end user
  is shown *"Min validation value is not a valid number."*
- `disallowPassedDates` is implemented as a flatpickr `minDate: "today"`. It
  constrains the calendar widget. It never runs inside the renderer's validation
  function.

That last fact is the one that shapes the whole answer. The feedback asks to
"prevent invalid or inappropriate dates", and the form layer alone cannot: a
request posted straight to the task API with a date outside the rule is accepted.
The work was therefore split along the line the technology actually draws:

- In the forms, `required`, correct `subtype`, `disallowPassedDates` for
  dates that are future commitments, anchored `pattern` rules for text, and
  numeric bounds.
- In the workers — the date rules a form cannot express, enforced server-side
  where no client can bypass them.

To stop the two layers drifting apart, both read one file:
`bpm/workers/src/main/resources/date-rules.json` (version 15.0), 8 future-date
entries covering 7 distinct variables, 9 past-only entries covering 6 distinct
variables, 1 cross-field rule (`preferredFromDate ≤ preferredToDate`), and 3
documented free dates: `attendanceDate`, plus `consultationDate` on both
clinic-letter forms. Those carry no rule because the demonstration timebox puts the
recorded event in the future, so a "not later than today" check only manufactured
false failures. It raised an incident on `consultationDate` on 2026-10-16. See
`docs/17` section 4 and `tools/harden_forms.py` category (C).

### 3.3 What was changed

| File | Change |
|---|---|
| `bpm/model/forms/*.form` | All 36 hardened. `required` 142 → **147**; `pattern` 0 → **63**, every one anchored with `^…$` because form-js tests with an unanchored `RegExp`; `disallowPassedDates` added where the date is a future commitment; numeric upper bounds added to the six money fields |
| `bpm/tools/harden_forms.py` | New. Reads the rule table and applies it; idempotent, with a dry-run mode and a written report |
| `bpm/tools/forms_inventory.py` | New. Measures the forms with the same ruler for both releases |
| `bpm/workers/src/main/resources/date-rules.json` | New. The single source of truth, read by both the Python hardening tool and the Java validator |
| `bpm/workers/.../support/DateRuleValidator.java` | New. Validates every job's variables against the rule table |
| `bpm/workers/.../ValidationException.java` | Added `invalidDate(...)` and `dateOrder(...)` factories |
| `bpm/workers/.../AbstractHospitalWorker.java` | One line inserted between the demo-failure hook and `execute(...)`, so **every** worker is covered |
| `bpm/workers/src/test/.../DateRuleValidatorTest.java` | New. 14 cases |

Two deliberate choices:

- A rule breach raises a `ValidationException`, not a BPMN error. The class's
  own contract says a `ValidationException` is never thrown as a BPMN error, and
  the model defines exactly nine error codes, each caught by exactly one boundary
  event. Inventing a tenth would raise an incident instead of being handled.
- **Comparison is at date granularity, not timestamp granularity.** Comparing
  instants made an appointment dated "today" fail after 09:00, which is wrong:
  the rule is "not in the past", not "in the future from this second".

### 3.4 Evidence and result

Command: `python tools/forms_inventory.py` on both releases; the v14.0 baseline
was extracted from git rather than from the old report, so both rows are measured
by the same code.

| Metric | v14.0 | v15.0 |
|---|---|---|
| Forms | 36 | 36 |
| Fields | 230 | 230 |
| Required | 142 | **147** |
| `pattern` rules | 0 | **63** |
| Date-typed fields | 19 | 19 |
| Findings | 6 | **0** |

Worker-side: `DateRuleValidatorTest`, 14 cases, all passing, including the
boundary cases for both date classes, the window-order rule, non-date values
being skipped rather than rejected, and an empty job.

Result: complete. The forms now carry the validation the platform can enforce,
they never misuse `min`/`max` on a date, and the rules a form cannot enforce are
enforced in the worker, reading the same rule table.

---

## 4. Item 3 — Database integration for data persistence

### 4.1 Position before the change

All process state lived in `support/HospitalStore.java`, backed by
`ConcurrentHashMap`s. Its own Javadoc said so:

> A real implementation would hold all of this in the hospital PAS database; for
> the deliverable a single process-wide store shared by all workers is enough …
> the state disappears when the JVM stops, so it only deduplicates within one run
> of the worker set.

Duplicate-charge detection, appointment creation, treatment series, clinic
letters, reminder cooldowns and provider payments were all lost on restart. The
project plan listed "a production database" as explicitly out of scope, which is
exactly what the feedback asks to bring in.

### 4.2 Decision

Use H2 in embedded mode — the database the platform already ships with, and
make the change in a shape that does not disturb the 36 workers:

- Keep the public API of `HospitalStore` byte-for-byte. Every worker keeps
  calling `createAppointment`, `markPaymentReference`, `alreadyReminded` and the
  rest, with the same signatures and the same return values. Only the body
  changes from a map operation to SQL. A repository rewrite that forces 36
  call sites to change is a rewrite that cannot be reviewed.
- Make the schema and the seed idempotent, so the worker can start against a
  fresh file, an existing file, or an in-memory database and behave identically.
- **Keep a documented fallback.** If the database cannot be opened the worker
  logs an error and falls back to an in-memory H2 database, so the same SQL code
  path is exercised either way and a demo is never blocked by a file permission.

### 4.3 What was changed

| File | Change |
|---|---|
| `bpm/workers/pom.xml` | Added `com.h2database:h2:2.2.224`; enabled Surefire so the new tests actually run |
| `bpm/workers/src/main/resources/db/schema.sql` | New. **15 tables**, every statement `CREATE TABLE IF NOT EXISTS` |
| `bpm/workers/src/main/resources/db/seed.sql` | New. 3 GP practices, 3 patients, 11 roles, 63 permission rows; `MERGE … KEY(…)` throughout, so re-running changes nothing |
| `bpm/workers/.../db/HospitalDatabase.java` | New. H2 `JdbcConnectionPool`, script runner, `inTransaction(...)`, `query(...)`, `summary()` |
| `bpm/workers/.../db/DatabaseException.java` | New. Unchecked, so the `execute` signature of every worker is untouched |
| `bpm/workers/.../db/NhsNumber.java` | New. Modulus-11 validation that returns a readable reason, including the "check digit of 10 means this number cannot exist" case |
| `bpm/workers/.../db/ReferenceData.java` | New. Patient and GP-practice lookup |
| `bpm/workers/.../db/AccessControl.java` | New. Role → permission decisions, with **both** allow and deny written to `audit_log` |
| `bpm/workers/.../support/HospitalStore.java` | Rewritten on JDBC, public API unchanged |
| `bpm/workers/.../support/ReferralRegistry.java` | New. Database-backed checks and back-fill of registered patient details |
| `bpm/workers/.../support/JobSecurity.java` | New. Maps each job type to a role, resource and action, and audits the decision |
| `bpm/workers/.../config/AppConfig.java` | New `database.*` and `security.*` keys |
| `bpm/workers/src/main/resources/application.yaml` | The new keys, documented |
| `bpm/tools/verify.ps1 -Check persistence` | New. Proves persistence across a cold restart |

**Design note. Why there are no foreign keys to `patient` or `gp_practice`.**
Those two tables are *reference* data: they exist so the process can be validated
against them. The operational tables are keyed by identifiers that arrive as
process variables, and the driver supplies its own patient references. A foreign
key would hard-fail any demonstration patient that is not in the reference set,
turning a validation rule into a crash. The link is enforced where it belongs,
in `ReferralRegistry`, which reports a readable failure.

### 4.4 Evidence and result

Persistence across a cold restart. Command:
`bpm/tools/verify.ps1 -Check persistence`. Evidence:
`bpm/screenshots/v15/h2-persistence.txt`, with both worker runs captured in full
in `workers-run1.out.log` and `workers-run2.out.log`.

| Step | Reading |
|---|---|
| Run 1 (fresh database) | `{gp_practice=3, patient=3, appointment=0, …}`, `{patients=3, gpPractices=3, practicesNotAccepting=[GP-5580]}`, `{roles=11, permissions=63}` |
| A row is inserted by hand | `DEMO-KEY-1 / APPT-PERSIST-1 / Oncology Day Unit` |
| Run 2 — the **same jar, started cold, against the same file** | `appointment=1` |
| Rows after run 2 | `patient=3 / gp_practice=3 / role_permission=63`, identical to run 1 |

Run 2 proving `appointment=1` is the point: the data outlived the process. The
unchanged reference counts in the same run additionally prove the seed is
idempotent rather than re-inserting on every start.

Integration. `mvn -gs maven-settings.xml -s maven-settings.xml -o package` →
`BUILD SUCCESS`, 52 tests, 0 failures (v16.0; 49 at the time of this record):
`DateRuleValidatorTest` 14, `JobContextTest` 16, `AbstractHospitalWorkerTest` 6,
`AccessControlTest` 6, `NhsNumberTest` 5, `HospitalStorePersistenceTest` 5.

Database-driven business validation. The database is not only a store; it is
consulted during the process. `ReferralRegistry` validates an NHS number before
looking it up, refuses a number that is not on file, back-fills the registered
patient name, NHS number and GP practice into the process variables, and refuses
the referral when the practice has `accepting_referrals = FALSE`. `GP-5580` is
seeded with exactly that flag so the refusal can be demonstrated rather than
described.

**Result: complete.** State that used to vanish when the JVM stopped is now in an
H2 database, is proven to survive a restart, and is used to validate the process
rather than merely to store it.

---

## 5. Verification record

Every gate run for this release, with its result.

| # | Gate | Command | Result |
|---|---|---|---|
| G1 | Worker build and unit tests | `cd bpm/workers; mvn -gs maven-settings.xml -s maven-settings.xml -o package` | **BUILD SUCCESS**, Tests run 30, Failures 0, Errors 0 |
| G2 | Form inventory, before and after | `python tools/forms_inventory.py` | problems 6 → 0; required 142 → 147; pattern 0 → 63 |
| G3 | Model still deploys after the changes | `bpm/tools/verify.ps1 -Check engine` | deployment key `2251799813685383`, 9 process definitions + 36 forms |
| G4 | RBAC persisted in the engine | H2 shell queries in `verify.ps1 -Check engine` | USERS 11, ROLES 16, AUTHORIZATIONS 213, ROLE_MEMBER 11, USER_TASK 50 |
| G5 | Persistence across a cold restart | `bpm/tools/verify.ps1 -Check persistence` | run 1 `appointment=0` → run 2 `appointment=1` |
| G6 | End-to-end with the real workers | `bpm/tools/verify.ps1 -Check e2e` (workers profile) | **PASS**, 36 / 36 forms covered, 0 missing, 0 driver errors, exit code 0, 0 engine `ERROR` lines; 36 worker classes subscribed as 37 job types; `e2e-summary.json` |
| G7 | Model structure, unchanged by this release | `python tools/analyse_bpmn.py` | 14 participants, 355 flow nodes, 39/39 user tasks with a form **and** a candidate group |
| G8 | Authentication compulsory and authorisation applied | `bpm/tools/verify.ps1 -Check rbac -ProtectedApi` | Anonymous 401; `demo` (admin) sees authorisation rows through `/v2/authorizations/search` while `sec.demo`, `audit.demo` and `fin.demo` all see an empty result from the same 213-row table; and all three are allowed on the resources they hold, `rbac-enforcement.txt` |
| G9 | Job activation is unaffected by the worker-side changes | worker log during G6, compared against the v14 baseline `bpm/tools/driver_report.json` | `COMPLETED` lines present, `FAILED` 0, `BPMN ERROR` 0; the same 34 scenarios that passed in v14.0 pass again |

---

## 6. Limitations and what was not done

**L-1, Role-based access control cannot be enforced at the same time as the
unauthenticated gRPC job worker runs, in this environment. The release ships
both, and this is the measured reason.**

Two things are true at once, and neither is hidden.

*First, the control works and can be demonstrated by refusal.* `verify.ps1 -Check rbac`
calls the same endpoint with different identities and expects opposite answers:
`sec.demo` (medical-secretaries, which holds `USER_TASK` read) is allowed, and
`audit.demo` (auditor, which by design holds no `USER_TASK` grant) is refused;
the pair is then reversed on the audit-log resource, where `audit.demo` is allowed
and `sec.demo` is refused. A one-directional result would not rule out "everything
is allowed" or "everything is refused"; the reversal does. Results in
`bpm/screenshots/v15/rbac-enforcement.txt`.

*Second, with `authorizations.enabled: true` the external job workers receive no
jobs at all.* This was measured as an A/B on the same worker jar, the same model
and the same scenarios — only the one flag differs:

| | `authorizations.enabled: true` | `authorizations.enabled: false` |
|---|---|---|
| `JOB` rows | 5, all left in state `CREATED` | activated and completed |
| Worker log `COMPLETED` | **0** | **11** |
| `TRT-declined-payment` | FAIL after a 180 s timeout | **PASS in 2.2 s** |
| `OUT-book` | FAIL after a 180 s timeout | **PASS in 0.9 s** |

Diagnosis, from the engine's own database: the jobs are not denied
(`IS_DENIED` is null, `RETRIES` still 3), and `AuthorizationResourceType`, the
enumeration of everything that can be authorized, contains no `JOB` value. So
this is not a per-job authorization decision. It is an API-level authentication
gate: `unprotected-api: true` exempts the REST and webapp surface (deployment and
user-task calls succeed without credentials, as `verify.ps1 -Check rbac` shows) but does
not cover the gRPC job-activation path.

There is no configuration that resolves it here. `AuthenticationMethod` offers
only `BASIC` and `OIDC`. There is no `NONE`. `zeebe-client-java:8.9.0` can
authenticate by OAuth or run in plaintext, but cannot perform BASIC, and no OIDC
provider is available offline. `zeebe.gateway.security` was checked and is TLS
configuration (certificate chain, private key, keystore), not an authorisation
switch. In short: the worker cannot present an identity, and the gRPC path will
not accept one that is absent.

What the release does about it. `bpm/camunda/application.yaml` ships with
`authorizations.enabled: true`, because that file *is* the answer to feedback item
1. `start-engine.ps1 -WorkersProfile` flips that single switch **on the runtime
copy only**, leaving the delivered configuration untouched, so the demonstrated
system runs end to end. The switch is one marked line inside the one
configuration file rather than a second configuration file, which is deliberate:
two files would drift, one marker cannot. `verify.ps1 -Check rbac` runs the RBAC profile;
`verify.ps1 -Check e2e` runs the workers profile; each records its own evidence
and states which profile it used.

Moving the workers to OAuth client credentials, with the roles' `clients()`
membership and `CLIENT`-owner grants that the configuration model already
supports, is the correct next step. It is out of scope for the time available and
is recorded here rather than left for a reviewer to discover.

**L-2 — Form-level date bounds are calendar constraints, not enforcement.**
`disallowPassedDates` is a flatpickr `minDate`. It cannot be relied on alone, and
is not. The same rule table drives `DateRuleValidator` in the worker, which no
client can bypass. Recorded here because a reader who only inspects the forms
would reasonably assume the forms are the enforcement.

**L-3, Five persistence tests skip themselves under the file sandbox.**
`HospitalStorePersistenceTest` checks its own environment first: in this
automation sandbox `java.nio.file.Files.isWritable()` returns `false` for every
path, including `pom.xml`, while `File.canWrite()` and an actual
`RandomAccessFile("rw")` both succeed. H2 uses exactly that NIO check to decide a
database is read-only, so the assertion cannot hold in this environment. The test
detects this and skips with a stated reason rather than reporting a false failure.
Outside the sandbox the same five tests run and pass; the lower-level proof does
not depend on them, because G5 demonstrates persistence with the real jar across
two cold runs.

**L-4 — One `ERROR` line in the engine log.**
`SnapshotDirector-1 … Unexpected exception occurred on moving valid snapshot`.
It is produced when the engine is force-stopped rather than shut down gracefully.
It is not a configuration defect and does not affect any reading above, but it is
an error line in a log and is therefore reported.

Built, measured, and rejected, BPMN merging gateways. The sheet asks about
merging gateways in other groups' rows, not in ours, so this was not required. It was
nevertheless built, because it is the most frequently repeated theme in the sheet
(around thirteen groups) and the objective for this release named it.

`bpm/tools/add_merging_gateways.py` inserts an exclusive merging gateway before every
task with more than one incoming sequence flow, rewriting the elements, the sequence
flows and the diagram interchange together. It works: tasks with unmerged converging
flows go from **14 to 0**, `exclusiveGateway` elements from 33 to 47, flow nodes from
341 to 355, with every other element count unchanged.

It cannot be deployed, and a controlled A/B shows exactly why, five deployments in
one fresh engine session, changing only the model file:

| # | Deployed | Result |
|---|---|---|
| A | v15 candidate alone, no forms | HTTP 400 `INVALID_ARGUMENT` |
| B | v14 alone, no forms | HTTP 400 `INVALID_ARGUMENT`, identical, so unrelated to the model |
| C | 36 forms alone | HTTP 200 |
| D | **v15 candidate + 36 forms, one batch** | **HTTP 500 `EXCEEDED_BATCH_RECORD_SIZE`** |
| E | **v14 + 36 forms, one batch** | **HTTP 200**, 9 process definitions |

A and B show the model cannot travel without its forms (each user task carries
`zeebe:formDefinition formId`). D and E are the same batch differing only in the model
file, which isolates the cause: the candidate grows the model by 1,122 bytes and
that carries the batch past the cluster's record ceiling. This is **risk R-01
materialising a second time** — the register already records a size rejection at
`currentBatchSize: 4095764`.

Decision: the candidate is not the shipped model. `_v14.bpmn` remains the deployable
artefact and every gate in §5 was run against it. The candidate, its generator and the
A/B measurements are retained, so the answer is "we implemented it, measured it, and it
breaches a hard platform limit" rather than "we chose not to". Splitting the deployment
or reducing the model first is the correct next step, and doing it under time pressure
against a verified deliverable is not. Evidence:
`bpm/screenshots/v15/merging-gateway-deployment-ab.txt`; full analysis in
`bpm/docs/16-acceptance-criteria.md` §6.

Deliberately not done, rewriting the acceptance criteria. The sheet's
criticism of acceptance criteria is written against other groups' rows. The
existing criteria in `docs/07-product-backlog.md` §6 are left as they are.

---

## 7. Traceability

| Feedback item | Decision | Change | Evidence | Status |
|---|---|---|---|---|
| R7-1 Role-based access control in Camunda | Declare the model's candidate groups as real cluster roles and prove persistence | `bpm/camunda/application.yaml`, `verify.ps1 -Check engine` | USERS 11 / ROLES 16 / AUTHORIZATIONS 213 / ROLE_MEMBER 11 / USER_TASK 50; L-1 | Complete |
| R7-2 Form validation, particularly dates | Split along the line form-js actually draws; one rule table, two enforcement layers | 37 forms, `date-rules.json`, `DateRuleValidator.java` | problems 6 → 0; required 147 → 156; pattern 63 → 65; 14 unit tests; L-2 | Complete |
| R7-3 Database integration for persistence | Embedded H2 behind the unchanged store API, with reference data for validation | `db/` package, `schema.sql`, `seed.sql`, `HospitalStore.java` | cold restart `appointment=0 → 1`; 52 tests at v16.0; seed idempotent | Complete |

The same three rows appear as **FB-15**, FB-16 and FB-17 in
`docs/10-sprint-reviews-and-feedback.md` §5.1, in the eight-column form used by
the rest of that log.
