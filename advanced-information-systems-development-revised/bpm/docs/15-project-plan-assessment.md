# Project plan assessment


> **Citations to files that are not in this tree.** An audit found 39 paths cited across 19 documents that no longer exist. The fourteen-pool model, the v1/v2 generators and the drawing scripts that went with them, and the Sprint 0 Node scaffold. Nothing was lost: all of it is in git history, and every citation is listed with what replaced it in [18-cited-files-no-longer-present.md](18-cited-files-no-longer-present.md).

**UFCEP6-0-3 Advanced Information Systems Development, Group Mj, release v15.0**

A critical comparison of what was planned, what was revised, and what actually
happened: scope, priority, estimates, allocation, dependencies, risk, integration
and sprint outcomes. It is written against the artefacts in this repository, and
every figure below was read out of those artefacts rather than recalled.

---

## 1. First finding: there are two plans, and they contradict each other

Before anything can be compared, the record has to be established — and the
record is not single.

| | Plan A. The workbooks | Plan B, `docs/07-product-backlog.md` |
|---|---|---|
| File | `docs/GroupMj Product-Backlog.xlsx` plus the two sprint workbooks | `bpm/docs/07-product-backlog.md` |
| Items | 58, numbered `Mj01`–`Mj58` | 35, numbered `PB-01`–`PB-35` |
| Priority scheme | `P0` / `P1` / `P2` | MoSCoW (Must / Should / Could / Won't) with ranks |
| People | Four named members | "team members A–E" |
| Dates | Sprint 1 `2026-09-15`–`2026-09-21`; Sprint 2 `2026-09-22`–`2026-09-28` | none |
| Estimates | 397 story points | story points per item, no total |

The two are not two views of one plan. They make **claims about each other that
are false**, and both claims are in the delivered package:

> Plan B, assumption A2: "No estimate exists in any artefact in the workspace."

The workbook's `Workload` sheet records an estimate for every one of its 58 items
, 397 story points in total, split 151 in Sprint 1 and 246 in Sprint 2.

> Plan B, assumption A1: "No real names appear in any artefact in the
> workspace, or in this document."

`docs/Contribution-Matrix.md` names all four members and gives each a percentage.

A third record disagrees with both: the `Contribution-Matrix` shares (Tommy
26.8%, Damon 24.4%, Lorrey 24.4%, Young 24.4%) are not the workbook's story-point
shares (Tommy 24.2%, Damon 24.9%, Young 26.5%, Lorrey 24.4%), and the matrix says
so itself.

Assessment. This is the weakest part of the v14.0 planning record, and it is
not a modelling problem — it is a configuration-management problem of the kind
already logged as risk R-13 ("documentation drift"). Three artefacts each believe
they are the plan. For v15.0 a single rule was adopted instead of a fourth
document: **the repository is the record; where two documents disagree, the one
that names a file that exists wins.** The contradiction is recorded here rather
than quietly repaired, because repairing it silently would hide exactly the
defect the review is asking about.

---

## 2. Scope: planned, revised, actual

**Planned (Plan B, §1).** In scope: 15 case-study participants, the whole pathway
from referral receipt to follow-up, 9 executable hospital processes, 6 outside
participants, 9 named exception conditions, Camunda Forms with validation,
external workers automating 35 job types, and evidence that it runs.

Explicitly out of scope in the same section:

> "production identity, RBAC and persistence; a production database"

**That sentence is the plan defect this release exists to correct. But the defect
is not the one it first appears to be.** Read the scope statement on its own and it
looks as though the feedback asked for work nobody had planned. The backlog says
otherwise, and the two artefacts contradict each other:

| Feedback item | Was it in the workbook? |
|---|---|
| Role-based access control | **Yes, `Mj46`**, epic Security, **P0**, **8 SP**, first owner L, Sprint 2, status **`Done`**. Its acceptance criterion reads: "A role matrix exists, and a test shows a role being refused an action outside its remit." |
| Audit log | **Yes, `Mj47`**, P0, 8 SP, Sprint 2, **`Done`** |
| Form validation | **Yes — `Mj45`**, epic Forms, P0, 8 SP, Sprint 2, **`Done`**. "Every form has labels, an error message for invalid input, keyboard access and sufficient contrast." |
| Database / persistence | **No item at all.** Searching all 58 items for "database", "persist" or "H2" returns nothing. |

So the accurate statement is narrower than the scope statement suggests, and more
useful: **the database was genuinely never planned; role-based access control and
form validation were planned, estimated, allocated. And marked `Done`.** They were
`Done` while no role existed in the cluster, no authorisation was persisted, and all
36 forms still carried zero `pattern` rules. The scope statement in
`docs/07-product-backlog.md` then disowned work that the workbook still claimed to
have finished. That is not a plan with a gap in it. It is a plan that disagrees with
itself, and the `Done` column is what let the disagreement go unnoticed.

Revised for v15.0. The out-of-scope line is withdrawn. RBAC, form-validation
hardening and database persistence move into scope, and the three become the only
in-scope items for the release. Everything else. The model's structure, the
drawing, the other exception branches, is frozen, so that the release can be
judged on the feedback it answers.

Actual. The revision held. No BPMN structural change was made in v15.0, and
the model still deploys unchanged (9 process definitions + 36 forms, deployment
key `2251799813685383`). The only model artefact touched was the 36 forms.

---

## 3. Priority: what the scheme was, and what it should have caught

Plan A uses `P0` / `P1` / `P2`. Of its 58 items: P0 50, P1 7, P2 1.

That distribution is the tell. When 86% of a backlog is top priority, the scheme
carries no information — it cannot be used to decide what to drop, which is the
only thing a priority scheme is for. Plan B's MoSCoW is better in principle, and
its own definition of *Must* is the right test: *"Without it the release is not
accepted."*

**Assessment.** By Plan B's own definition, RBAC and database persistence were
*Must* items that the scope statement had excluded, which is how a backlog can be
100% complete and still fail a review. The v15.0 revision uses the same test in
reverse: the three feedback items are the only *Must* items, the frozen model is
*Won't (this release)* with a stated reason, and nothing else was added.

---

## 4. Estimates: 397 points planned, and what that bought

**Plan A, `Workload` sheet, verbatim totals:**

| Member | Items | SP | Share | Sprint 1 SP | Sprint 2 SP | Items (2nd owner) | SP (2nd) |
|---|---|---|---|---|---|---|---|
| Tommy | 18 | 96 | 24.2% | 39 | 57 | 19 | 127 |
| Damon | 13 | 99 | 24.9% | 39 | 60 | 11 | 87 |
| Young | 13 | 105 | 26.5% | 37 | 68 | 21 | 115 |
| Lorrey | 14 | 97 | 24.4% | 36 | 61 | 7 | 68 |
| **TOTAL** | **58** | **397** | **100%** | **151** | **246** | **58** | **397** |

Plan B carries points per item but publishes no total, and states that its
points are "planning values authored for this document".

**Assessment. Two observations.**

1. The estimate is complete and internally consistent. 151 + 246 = 397, the
   per-member shares sum to 100%, and the four shares are within 2.3 points of
   each other. As a *levelling* exercise this is sound: no one is carrying a
   disproportionate share.
2. **The estimate is complete, and three of its lines were reported finished
   without being finished.** No line in the 397 points covers a database: that work
   genuinely did not exist and had to be estimated from nothing. But `Mj45`, `Mj46`
   and `Mj47` do cover form validation, role-based access control and the audit log,
   at 8 SP each, and all three read `Done`. The v15.0 estimate in §5 is therefore
   not the cost of unplanned work; it is the cost of finally doing three items that
   had already been marked complete.

The second owner column is also worth noting: 58 items carry 58 second-owner
assignments totalling another 397 points. Coverage is complete on paper. What it
did not cover is work that no item described.

---

## 5. The v15.0 revision: what was added, and how it was sized

Three items, one per feedback item, each with a first owner, a second owner and a
written acceptance test. Sizes are given in the same unit as the existing plan so
the two can be read together.

| ID | Item | Feedback | SP | 1st | 2nd | Acceptance test (measurable) |
|---|---|---|---|---|---|---|
| V15-01 | Role-based access control in Camunda | R7-1 | 13 | C | E | Every one of the 9 candidate groups in the BPMN exists as a cluster role; every user task grants those permissions; the grants are read back from the engine's `AUTHORIZATIONS` table, not from our file |
| V15-02 | Form validation hardening | R7-2 | 8 | D | C | Inventory findings 6 → 0; no `min`/`max` on any `datetime`; every `pattern` anchored; measurement on both releases taken by the same script |
| V15-03 | Shared date-rule layer and worker-side enforcement | R7-2 | 8 | C | D | One rule table read by both the Python tool and the Java validator; a breach raises `ValidationException`; unit tests cover both date classes and the cross-field rule |
| V15-04 | H2 database integration and persistence | R7-3 | 21 | C | B | 15-table schema, idempotent seed, `HospitalStore` public API unchanged; data written by one cold run is read by the next |
| V15-05 | Database-driven business validation | R7-3 | 8 | C | Y | NHS number validated by modulus 11 then looked up; a referral to a practice with `accepting_referrals = FALSE` is refused |
| V15-06 | Verification and evidence capture |, | 8 | Y | C | Engine start/deploy/RBAC capture, cold-restart persistence proof, end-to-end run, all under `bpm/screenshots/v15/` |
| V15-07 | Feedback-response and plan-assessment documents | — | 5 | T | Y | `docs/14`, `docs/15`, the FB-15…FB-17 rows, and the bilingual review document |
| | **Total** | | **71** | | | |

Against 397 points over two one-week sprints, 71 points is roughly a third of a
sprint. The estimate was wrong, and it is worth saying by how much. Measured
by artefacts produced, V15-04 alone (the database) took the largest share of the
release: a 15-table schema, a rewritten store, three new support classes, a
configuration surface, five persistence tests and a two-cold-run proof. Its 21
points were reasonable in isolation and are the single largest line, but the
*integration* cost, finding that the cluster already runs on H2, that the file
sandbox makes `Files.isWritable()` lie, and that the seed must be idempotent or
every restart corrupts the reminder state, was not in the estimate at all,
because none of it was knowable before starting.

Lesson. For work of this kind the estimate should include an explicit
*discovery* line. Three separate findings (the renderer's real validation
capability, the engine's authorisation initialisation quirks, the sandbox's
effect on H2) each cost more than a day and none appeared in the plan.

---

## 6. Allocation, and whether the matrix is the plan

Three different allocation records exist: 397 story points by four names
(workbook), 100% of "contribution" by the same four names with different
percentages (`docs/Contribution-Matrix.md`), and five abstract members A–E
(`docs/07-product-backlog.md`).

**Assessment.** The story-point shares and the contribution shares measure
different things, and the Contribution-Matrix says so in a note, story points
record *first-owner effort on backlog items only*, and do not count coordination,
review and integration. That distinction is legitimate. What is not legitimate is
Plan B claiming no names appear anywhere while two other artefacts use them.

For v15.0, allocation followed the Contribution-Matrix, because it is the only
record that names the work each person actually did: the three feedback items map
onto it cleanly — RBAC and the workers onto Lorrey (workers, security, role-based
access control and the audit log), the forms onto Damon (all 36 Camunda Forms
including their validation), and the verification and reporting onto Young.

One allocation weakness is visible in the v15.0 work. The database item
(V15-04) has a first owner but no second owner with database experience; the
review of it was therefore a review of *behaviour* (does the data survive a
restart?) rather than of *design* (is the schema right?). That is the weakest
review in the release and is recorded as such.

---

## 7. Dependencies: the ones that were planned, and the one that was not

Plan A carries a `Dependency` column and Plan B a `Depends on` column; the model
depends on the forms, the workers depend on the model's job types, the tests
depend on the deployment. Those held.

The dependency the v15.0 work exposed is a different kind: **a feedback item can
depend on a technology decision nobody has made.** The form-validation item
looked like a forms task and turned out to depend on finding out how the renderer
validates; the persistence item looked like a store rewrite and turned out to
depend on which database the platform already embeds. Both dependencies were
discovered by reading the vendor's own source and configuration rather than its
documentation, and both changed the shape of the answer.

Lesson. Plan the dependency on the *unknown*, not just on the artefact. A
line reading "confirm the renderer's validation model before hardening the forms"
would have been a more honest plan than "harden 36 forms".

---

## 8. Risk: was the register useful?

`docs/09-risk-contingency-and-config-management.md` holds R-01…R-21 with a
likelihood/impact/exposure score and a named contingency for the high-exposure
rows. It is a real register, not decoration: several rows describe things that
then actually happened.

**Assessment. The register was useful for the risks it named and silent on the
ones that mattered for v15.0.** Its entries are about the model, the drawing, the
deployment and the schedule. It holds nothing about:

- whether the roles the model declares are enforced by anything (R7-1);
- whether the date rules the forms show can be bypassed (R7-2);
- whether state that the model promises to keep is actually kept (R7-3).

Those three gaps are the same gap as §2: work that was out of scope was also out
of the risk register, so no mitigation, contingency or trigger existed for it. A
risk register can only see inside the scope it is given.

**What v15.0 adds, as risks in the same scheme:**

| ID | Risk | L | I | Exp | Mitigation | Contingency |
|---|---|---|---|---|---|---|
| R-22 | The gateway API must stay unauthenticated, so role-based control is demonstrated on the web/REST surface only and not on gRPC | H | M | 6 | State it as limitation L-1 in `docs/14` §6; demonstrate refusal on the authenticated surface | Move the workers to OAuth client credentials; out of scope this release |
| R-23 | Form-level date rules are calendar constraints and can be bypassed by a direct API call | H | H | 9 | Enforce the same rules server-side in `DateRuleValidator`, reading one shared rule table | None needed; the server-side check is the mitigation and it is tested |
| R-24 | An H2 file database can be opened read-only by the environment, silently losing writes | M | H | 6 | Detect on open, log an error, fall back to in-memory; run the persistence proof outside the sandbox | Re-run `verify.ps1 -Check persistence` in an unrestricted shell |

---

## 9. Integration: the part that carried the most risk and got the least plan

The feedback items were three separate asks. They were treated as three separate
pieces of work and integrated at one point only: `AbstractHospitalWorker.handle()`.

That single method is where a job is checked against the date rules, audited
against the role matrix, executed, and have database-resolved patient details
merged into its output. Putting all three integrations in one place was the right
call, 36 worker classes needed no change, and there is exactly one place to read
to know what every worker does before and after its own logic.

Assessment. Integration risk was under-planned. The plan treated the three
items as independent, and they were not: the role matrix lives in the database,
so RBAC depends on the database work, so two of the three feedback items are one
workstream, not two. Sequencing the database first and RBAC second would have
been the correct order; the actual order happened to work, but by luck rather than
by plan. This is recorded as a planning defect, not a delivery defect.

---

## 10. Sprint outcomes: what the record says, and what it does not

Plan A marks **all 58 items `Done`**, 100% complete, 397 of 397 points.

Plan B reports, in its own words, "Completed at Sprint Review 1 (22 of 24)"
and "Completed at Sprint Review 2 (5 of 5 committed)", and then lists items it did
*not* complete: accessibility grouping, live compensation, three unrun branches,
Tasklist rendering, and real provider APIs.

In the internal feedback log (`docs/10` §5), of FB-01…FB-14: 3 Complete, 1
Complete-with-qualifier, 2 Done-in-R3, 2 Partly complete, 3 Not carried out, 4
Open.

Assessment. The workbooks say the plan was finished; the log says a third of
its actions were not. Both cannot be true, and the log is the more credible of the
two, because it names a reason and an outstanding impact for each unfinished item
while the workbook names none. A backlog where every row says `Done` is a backlog
that stopped being updated.

The concrete example is `Mj46`. "Role-based access control", P0, 8 story points,
first owner L, Sprint 2, `Done` — with an acceptance criterion that explicitly
demands *"a test shows a role being refused an action outside its remit"*. At
v14.0 there was no role in the cluster to refuse anything, no authorisation in the
database, and no such test. The row was marked complete against a criterion it had
not met, and nothing in the process caught it. The same is true of `Mj45` for form
validation. This is the single most useful thing the v15.0 work establishes: the
gap the feedback identified was not a gap in the plan's *coverage*, it was a gap
between what the plan *claimed* and what the repository could *show*.

The honest sprint-level statement for v14.0 is therefore: **scope delivered, plan
not closed.** The model, the forms, the workers and the deployment were delivered
and verified; six logged actions, two partly-complete ones and three named
limitations were carried out of the sprint, and the backlog did not record it.

For v15.0 the closing rule was applied instead: an item is `Done` only when the
gate named in its acceptance test has been run, and unfinished work keeps its row.
That is why `docs/14` §6 lists limitations L-1 to L-4 and the deliberately-not-done
items, rather than reporting a clean sheet.

---

## 11. Overall assessment

**What the planning got right.** The pathway decomposition was sound, the
levelling was fair, the risk register was real and its high-exposure rows were the
ones that materialised, and the second-owner coverage was complete. The
verification habit, a command per claim, an evidence file per gate, is the
reason the v15.0 changes could be proved rather than asserted.

**What it got wrong, in order of consequence.**

1. Scope excluded two of the three things the review then asked for. RBAC and
   persistence were written out of scope in advance, so they were never estimated,
   allocated, risk-assessed or tested. This is the root cause of the feedback.
2. Three artefacts each claimed to be the plan, and two of them contained
   statements the others disprove.
3. Priority carried no information, 50 of 58 items at P0.
4. Estimates contained no discovery line, which is where the v15.0 overrun
   came from.
5. **Integration was treated as a phase, not as a dependency** — the database
   underlies the RBAC work, which the plan did not express.
6. **A backlog that reports 100% `Done` while the log reports a third of actions
   unfinished** has stopped being a plan and become a claim.

The single change that would have prevented most of this: treating
"a production database / RBAC / persistence" as *deferred with a stated reason and
a revisit trigger*, rather than as *out of scope*. The v14.0 scope statement had
the right structure, MoSCoW with "Won't (this release): explicitly deferred, with
the reason recorded". And then used the out-of-scope list to avoid writing the
reason down. That is the difference between a plan that can be assessed and one
that has to be reconstructed afterwards.
