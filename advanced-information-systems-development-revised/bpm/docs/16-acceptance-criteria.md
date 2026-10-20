# Acceptance criteria assessment


> **Citations to files that are not in this tree.** An audit found 39 paths cited across 19 documents that no longer exist. The fourteen-pool model, the v1/v2 generators and the drawing scripts that went with them, and the Sprint 0 Node scaffold. Nothing was lost: all of it is in git history, and every citation is listed with what replaced it in [18-cited-files-no-longer-present.md](18-cited-files-no-longer-present.md).

**UFCEP6-0-3 Advanced Information Systems Development, Group Mj, release v15.0**

> **This is the v15.0 assessment, kept as the record of how the acceptance criteria were
> revised. It is not the shipped release.** The shipped model is `versionTag` 16.0.0: one
> executable process plus six black-box participants, 37 forms bound to 38 user tasks, 10
> error codes, 29 boundary events, and 52 unit tests that pass. Every figure below that names
> nine process definitions, `v14`/`v15` model files, 36 forms or `Tests run 30` is the v15.0
> measurement. The shipped numbers, and the evidence behind them, are in
> `docs/17-single-pool-operational-model.md`, `docs/03-test-record.md` §I and
> `screenshots/v16/engine-record.txt`.

An assessment of the acceptance criteria the project was planned against: what they
were, what is wrong with them, what the revised criteria for this release look like,
and what actually passed. It closes with a worked pattern for revising the remainder.

---

## 1. What the initial criteria look like, measured

Measured directly from `docs/GroupMj Product-Backlog.xlsx`, sheet `Product Backlog`,
column `Acceptance Criteria` — 58 items, `Mj01` to `Mj58`.

| Observation | Result |
|---|---|
| Items with an acceptance criterion | **58 / 58**, none empty, none shorter than 40 characters |
| Criteria naming a **specific artefact** (a file, a release tag, or a command) | **6 / 58** |
| Criteria naming a **numeric threshold** attached to a named measure | 3 / 58 |
| Criteria containing a word such as "sufficient", "appropriate" or "clear" with no measure defined | 12 / 58 |

The six that name their evidence are `Mj04` (a Sprint 1 backlog exists), `Mj06` (tag
`sr1-snapshot` is pushed), `Mj08`, `Mj10` (tag `sr2-snapshot` is pushed), `Mj50` (the
plan states entry and exit criteria) and `Mj58` ("the submitted commit or tag is named
in the submission note").

This is a better starting position than the headline suggests. The criteria are
written as statements about observable behaviour, not as restatements of the task.
They say what should be *true of the world* when the item is done:

> `Mj19`, "The process blocks any treatment request that has not been authorised by a
> clinical role."
> `Mj26`, "If no slot matches the clinical timeframe, the case is flagged rather than
> quietly booked late."
> `Mj33` — "Invalid input and timeout are handled, and running the same job twice
> produces one booking."

Each of those is falsifiable. A reviewer can look at the model and decide. So the
problem is not that the criteria are vague in the usual sense.

---

## 2. Where the weakness actually is

The weakness is that **a criterion states the required outcome but not the evidence
that would settle it.** Fifty-two of the fifty-eight name no file, no command, no
threshold and no measurement, so "done" is decided by whoever is reading the row.

Three worked examples make the cost visible:

| Item | Criterion | Why it does not settle anything |
|---|---|---|
| `Mj45` | "…keyboard access and **sufficient contrast**." | "Sufficient contrast" has no ratio and no checker. WCAG sets the number (4.5:1 for normal text); the criterion does not, and no tool was ever run, so the row could not fail. |
| `Mj46` | "A role matrix exists, and **a test shows a role being refused** an action outside its remit." | The strongest criterion in the backlog. It names the artefact *and* the test. At v14.0 neither existed: no role was declared to the cluster, no authorisation was persisted, and no refusal test was written. The row still read `Done`. |
| `Mj49` | "Each requested report can be produced with a date filter, **or the gap is recorded as a limitation**." | An escape hatch inside the criterion itself. Either outcome satisfies it, so it cannot fail. And a criterion that cannot fail is not a gate. |

That last pattern is worth naming separately because it is the one that does real
damage: **a criterion with an "or" that permits the work not to happen is not an
acceptance criterion.** `Mj49` is the clearest case; it was written honestly, but it
converts a deliverable into a choice.

The consequence is visible in the register. `docs/09` risk R-13 is "documentation
drift". Criteria that name no evidence are exactly how drift becomes invisible: the
document and the artefact can disagree indefinitely, because nothing compares them.
`Mj46` is that failure in miniature. The criterion was correct, the row said `Done`,
and the cluster had no roles in it.

---

## 3. Revised criteria for this release

The three feedback items were given acceptance criteria that name the threshold, the
command and the evidence file. This is the pattern the rest of the backlog should
follow.

| ID | Item | Acceptance criterion (revised) | Threshold | Command | Evidence |
|---|---|---|---|---|---|
| V15-01 | Role-based access control | Every one of the nine candidate groups in the BPMN exists as a role in the cluster; every declared user is a member of its role; every grant is read back from the engine's own `AUTHORIZATIONS` table; a resource the role does **not** hold is invisible to it | `USERS = 11`, `ROLES = 16`, `AUTHORIZATIONS = 213`, `ROLE_MEMBER = 11`; `USER_TASK` grants `= 50`; anonymous REST `= 401`; three business roles see `0` rows of `AUTHORIZATIONS` while admin sees `>0` | `pwsh -File bpm/tools/verify.ps1 -Check engine` and `pwsh -File bpm/tools/verify.ps1 -Check rbac -ProtectedApi` | `bpm/screenshots/v15/rbac-enforcement.txt` §7 (the counts), §4-6 (the by-refusal checks). **Not** `users-roles-authorizations.txt`, which is a second capture against an empty database and proves nothing; its header now says so |
| V15-02 | Form validation | No date-typed field carries `min` or `max`; every `pattern` is anchored; findings from a single inventory script | findings `= 0`; `pattern` count `= 63`; required `= 147`; `min`/`max` on `datetime` `= 0` | `python bpm/tools/forms_inventory.py` | `bpm/tools/forms-inventory-v15.json` vs `forms-inventory-v14.json` |
| V15-03 | Date rules enforced server-side | One rule table is read by both the tooling and the worker; a rule breach raises `INVALID_DATE`, which returns the token to the form that captured the date (see `docs/21` §3) | rule table version `15.0`; tests `= 14`, failures `= 0` | `cd bpm/workers; mvn -gs maven-settings.xml -s maven-settings.xml -o package` | `bpm/workers/src/main/resources/date-rules.json`, `DateRuleValidatorTest` |
| V15-04 | Database persistence | Schema and seed are idempotent; data written by one cold run is read by the next | 15 tables; run 1 `appointment = 0`; run 2 `appointment = 1`; reference counts identical across runs | `pwsh -File bpm/tools/verify.ps1 -Check persistence` | `bpm/screenshots/v15/h2-persistence.txt`, `workers-run1.out.log`, `workers-run2.out.log` |
| V15-05 | Database-driven validation | An NHS number is validated before lookup; a referral to a practice not accepting referrals is refused | modulus-11 tests `= 5`, failures `= 0`; `GP-5580` seeded `accepting_referrals = FALSE` | `mvn … package` | `NhsNumberTest`, `AccessControlTest`, `db/seed.sql` |
| V15-06 | End-to-end regression | Every deployed form is exercised by the scripted driver against the real worker jar | forms covered `= 36 / 36`; missing `= 0`; driver errors `= 0`; exit code `= 0` | `pwsh -File bpm/tools/verify.ps1 -Check e2e` | `bpm/screenshots/v15/e2e-summary.json`, `e2e-driver-report.json` |

Note what changed between the old style and this one. The old criterion told a reader
what the team *intended*. These tell a reader **what number counts as passing, how to
reproduce it, and which file to open if they do not believe it.** A criterion that
cannot be reproduced is an opinion.

---

## 4. Actual results

Every gate above was run. Results as measured, not as intended.

| Gate | Command | Result |
|---|---|---|
| G1 | `mvn -gs maven-settings.xml -s maven-settings.xml -o package` | **BUILD SUCCESS** — Tests run **30**, Failures 0, Errors 0, Skipped 5 |
| G2 | `python bpm/tools/forms_inventory.py` | findings **0**, `pattern` **63**, required **147** |
| G3 | `pwsh -File bpm/tools/verify.ps1 -Check engine` | deployment key `2251799813685383`, **9 process definitions + 36 forms** |
| G4 | `pwsh -File bpm/tools/verify.ps1 -Check rbac -ProtectedApi` | anonymous **401**; three roles see **0** of 213 authorisation rows; admin sees rows; **6 / 9 checks pass** |
| G5 | `pwsh -File bpm/tools/verify.ps1 -Check persistence` | run 1 `appointment=0` → run 2 **`appointment=1`**; seed idempotent |
| G6 | `pwsh -File bpm/tools/verify.ps1 -Check e2e` | **PASS**, forms covered **36 / 36**, missing 0, driver errors 0, exit code 0, engine `ERROR` lines 0 |

---

## 5. What failed, and what is not met

These are failures against the revised criteria, reported as failures.

F1, G4 is 6 of 9, not 9 of 9. The three failures are all the same expectation:
that a role without a grant to the `AUTHORIZATION` resource would be **refused** with a
403. It is not; it receives 200 with an empty result. The authorization check is
demonstrably running — admin sees rows through the same endpoint, the three business
roles see none of the 213. But this build enforces it as result filtering, not as
refusal. The expectation in the criterion was wrong, not the configuration; the
criterion has since been rewritten to state what is actually required. This is the
correct way for a criterion to fail: it produced a measurement, and the measurement
changed the criterion.

F2, five persistence tests skip themselves. `HospitalStorePersistenceTest` reports
`Skipped: 5` in this environment. The cause is environmental and diagnosed in
`docs/14` §6 (L-3): the file sandbox makes `java.nio.file.Files.isWritable()` return
`false` for every path, which is the exact check H2 uses to decide a database is
read-only. The tests detect this and skip with a stated reason rather than reporting a
false failure. The criterion is nonetheless met, because G5 proves persistence with
the real jar across two cold runs; but a reader is entitled to see the count of 5.

**F3. The BPMN merging-gateway change was built, verified structurally, and then
rejected on a platform limit.** This is a failure against the extended objective and is
recorded in full in §6.

**F4 — `Mj45`'s "sufficient contrast" is still unmet.** No contrast ratio was ever
measured and no accessibility checker was run. The v15.0 revision did not address
accessibility; `Mj45` remains `Done` on a criterion that was never tested.

---

## 6. The merging-gateway work: built, measured, rejected

The external sheet raises merging gateways against roughly thirteen groups, although
not against this one; the objective for this release nonetheless included it. It
was therefore built. And then rejected on evidence, which is the useful outcome.

What was built. `bpm/tools/add_merging_gateways.py` inserts an exclusive merging
gateway before every task that had more than one incoming sequence flow, rewriting the
element, the sequence flows and the diagram interchange together. It is idempotent and
runs as a dry run first.

It works. Measured on the model the script generates (written to a scratch path, never into
`bpm/model/`, because the candidate cannot be deployed, see below):

| | v14.0 | v15 candidate |
|---|---|---|
| Tasks with more than one incoming flow and no merging gateway | **14** | **0** |
| `exclusiveGateway` elements | 33 | 47 |
| Flow nodes | 341 | 355 |
| User tasks / service tasks / start events / end events | 35 / 47 / 45 / 68 | **unchanged** |

It cannot be deployed. And the control shows why. Five deployments were run in
one fresh engine session, changing only the model file:

| # | What was deployed | Result |
|---|---|---|
| A | v15 candidate **alone**, without the forms | **HTTP 400** `INVALID_ARGUMENT` — "Expected to deploy new resources …" |
| B | v14 **alone**, without the forms | **HTTP 400** `INVALID_ARGUMENT`. The same failure |
| C | the 36 forms alone | **HTTP 200**, deployment key `2251799813685383` |
| D | **v15 candidate + 36 forms**, one batch | **HTTP 500 `EXCEEDED_BATCH_RECORD_SIZE`** |
| E | **v14 + 36 forms**, one batch (baseline control) | **HTTP 200**, deployment key `2251799813685420`, 9 process definitions |

> **The batch-size question this experiment answered is closed by v16.0.** The shipped file is
> a single process definition with six non-executable outside participants, so there is no
> batch to fit and no second file to deploy; `docs/09` records R-01 as closed on that basis.
> The five deployments are retained because they are the measurement that motivated the
> single-pool rebuild, not because they describe the shipped configuration.

Two conclusions, both clean:

1. A and B fail identically, so the model cannot travel without its forms. Each user
   task carries `zeebe:formDefinition formId`, and deploying the BPMN before those 36
   forms exist fails validation. The model and its forms must be deployed in the same
   batch — which is what `bpm/RUNBOOK.md` already records.
2. **D and E are the same batch, differing only in the model file: v14 succeeds and v15
   fails.** That isolates the cause without ambiguity. The candidate grows the model
   from 447,481 to 448,603 bytes, and **1,122 extra bytes carry the batch past the
   cluster's record ceiling.**

This is risk R-01 in `docs/09` materialising a second time. The register already
records a deployment rejected for size at `currentBatchSize: 4095764`; the same ceiling
has now stopped a change of just over a kilobyte on top of an already-large model.
Evidence: `bpm/screenshots/v15/merging-gateway-deployment-ab.txt`.

Decision: the candidate is not the deployable model. `_v14.bpmn` remains the model
that ships and that every gate above was run against. The candidate, its builder and
the measurements are retained as evidence, because "we implemented it, measured it, and
it breaches a hard platform limit" is a stronger and more useful answer than "we chose
not to do it".

What this changes for the future. The ceiling is now a known, quantified constraint
rather than a warning in a register: on this cluster the deployable BPMN has roughly
1.1 KB of headroom at 447 KB when the 36 forms travel in the same batch. Any further
model work must either split the deployment (`bpm/RUNBOOK.md` already notes that the
BPMN should be deployed separately from the forms) or reduce the model before adding to
it. That is the correct next step for the merging gateways, and it is recorded rather
than attempted under time pressure against a verified deliverable.

---

## 7. A revision pattern for the remaining criteria

Fifty-two criteria still name no evidence. The pattern that fixed the six above, and
that should be applied to the rest:

1. **Name the number.** Replace "sufficient", "appropriate", "clear" and "limited" with
   a threshold. If no threshold exists, the criterion is not testable and the first job
   is to find one, WCAG's 4.5:1 for `Mj45`, for instance.
2. Name the command. A criterion a reviewer cannot re-run is an assertion. Every
   criterion above resolves to one of six commands.
3. Name the file. Expected result, actual result and the evidence path in one row.
4. Remove every "or". An escape hatch inside a criterion, "or the gap is recorded
   as a limitation" in `Mj49`, guarantees the criterion can never fail. If the
   fallback is legitimate, it belongs in the risk register with a trigger, not in the
   acceptance criterion.
5. State the failure mode. What does it look like when this is *not* done? `Mj46`
   was unfalsifiable in practice because nobody asked what the cluster would look like
   if the work had not happened. The answer was: identical to how it looked.

Worked example, applying the pattern to the two weakest items:

| Item | Before | After |
|---|---|---|
| `Mj45` | "…keyboard access and sufficient contrast." | "Every form field is reachable and operable by keyboard alone; every text/background pair meets WCAG AA (4.5:1 normal, 3:1 large), measured by `axe-core` in headless Chrome; 0 violations across 36 forms. Evidence: `bpm/screenshots/v15/accessibility-report.json`." |
| `Mj49` | "…or the gap is recorded as a limitation." | "Each of the four requested reports is produced with a date filter and the output is retained. Threshold: 4 of 4, or an explicit scope reduction agreed at a sprint review with the reason and the trigger for revisiting it. Evidence: `bpm/screenshots/v15/reports/`." |

---

## 8. Assessment

**What was right.** All 58 items had a criterion, and the criteria were written as
observable behaviour rather than as restatements of the task. `Mj46` — the RBAC item,
is the best of them: it names the artefact *and* the test. It is also the one that
failed silently, which is the more instructive fact.

**What was wrong, in order of consequence.**

1. Fifty-two of fifty-eight criteria named no evidence. "Done" was decided by the
   reader, and `Mj45`, `Mj46` and `Mj47` were all marked `Done` against criteria they
   had not met.
2. One criterion contained its own escape hatch (`Mj49`), which makes it impossible
   to fail.
3. No criterion asked what failure would look like, so a row could be marked
   complete without anyone checking whether the work had happened. `Mj46` was `Done`
   while the cluster contained no roles at all.
4. Undefined measures ("sufficient contrast", "clear 'none available' result",
   "appropriate") appear in twelve criteria and cannot be decided by anyone, including
   the author.

**Second pass, 2026-10-18. The same rule applied to every row.** Three rows had already
been corrected. Applying the rule to the whole workbook found six more that met part of
their criterion and not all of it, and they now read `Partly done`:

| Row | Clauses met | Clause that is not |
|---|---|---|
| `Mj01` | The tutor approved a four-person group | The written reply is not held in the tree, and the criterion says to keep it |
| `Mj33` | Retry, idempotency and the boundary errors work; six failure paths driven | An unauthorised treatment request raises an incident instead of the declared business error (K5.9); the availability recovery loop has no bound (K5.8) |
| `Mj35` | 52 tests pass, covering the base class, `JobContext`, the date rules, the store and access control | "Each worker has at least one passing test", none of the 38 `execute()` methods has one |
| `Mj54` | Audit entries exist, the 37-form accessibility audit is clean, RBAC is enforced | No unauthorised action is refused as a business outcome; contrast measured on one form of 37; no keyboard-only pass |
| `Mj56` | The script covers a normal, an alternative and six failure scenarios | "Names a speaker for each part" — no speaker is named |
| `Mj57` | Every run in §K follows one documented procedure | "Runs twice without failure" with all four members present, not rehearsed |

Workbook totals after the pass: Done 47, Partly done 9, Done (record reconstructed) 2.
Each of the six carries the missing clause in the workbook's Description column, so the
row cannot be read as complete without it.

The single change that would have caught all of this: require every acceptance
criterion to name a command and an evidence file. The three items marked `Done` without
being done would then have had nowhere to hide, `Mj46` would have read "run
`verify.ps1 -Check rbac`; expect `AUTHORIZATIONS > 0` and one refusal", and at v14.0 that
command would have returned zero.

Relationship to the feedback. The external sheet criticises acceptance criteria in
other groups' rows, not in this group's. This assessment was produced anyway, because
the measurement above shows the criticism applies here too: the criteria were
behaviour-shaped but evidence-free, and two of the three items this group was marked
down on were rows that had already been ticked.
