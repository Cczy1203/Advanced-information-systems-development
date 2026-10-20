# 19 — Stand-up records (SU1 and SU2)

The assessment asks for stand-ups to be marked individually and for "a brief record
of blockers, next actions and handovers" to be retained. No such record was kept while
the sprints ran, and the two rows that claimed one, `Mj05` and `Mj09`, both marked
Done against a "filled standup sheet", pointed at a sheet that is not in the tree.
Those two rows are now recorded as reconstructed rather than Done.

These are the records, written from the artefacts each update points at. Each row
names a file or a command, so an update can be checked rather than believed.

Two things to be straight about. First, the **dates and the exact wording are
reconstructed** from the commit log and the artefacts, not taken from
contemporaneous notes, because none were kept. Second, the **individual attribution
is what the work log supports**; where the repository can only show that a thing was
done and not who did it, the row says so rather than inventing a name.

---

## Stand-up 1 — during Sprint 1

**Sprint goal:** an executable BPMN increment covering the referral, treatment and
administration pathway, with a project plan behind it.

| Member | Done since the last stand-up | Evidence | Next | Blocker | Dependency / handover |
|---|---|---|---|---|---|
| **Tommy** (leader) | Modelled the nine hospital processes as separate pools with their lanes; wired the twenty message flows; validated the collaboration against the Camunda 8 deployer | `bpm/model/UFCEP6-0-3_Hospital_Patient_Pathway_v14.bpmn`, `bpm/tools/validate_model.js` | Start on the gateway conditions and the exception boundaries | The deployer rejected the first batch: nine process definitions fit, a tenth is refused at 4,095,764 bytes | **Handover to Damon:** the five outside participants must go in a second deployment file. Recorded as R-01 in `docs/09` |
| **Damon** | Wrote the routing engine that lays the flows out on a column grid, because the first drawing had 142 overlapping segments | `bpm/tools/layout_engine.py`, `bpm/docs/06-diagram-engineering.md` | Reduce the crossings; measure before and after | Two message flows still ran through shapes they were not connected to | **Blocker escalated** to Tommy: needs a position for the outside participants before the crossing count can come down |
| **Lorrey** | Wrote the 36 Camunda Forms and bound each to its user task; checked every binding resolves | `bpm/model/forms/`, `zeebe:formDefinition` on 37 user tasks | Form validation: find out what form-js can and cannot enforce | None | **Handover to Young:** the field list, so the workers read the same names the forms write |
| **Young** | Read the form-js source to establish what the renderer actually validates | `bpm/docs/14-feedback-response.md` §3 | Split validation between the form and a worker-side rule table | `datetime` reads only `required`; adding `min`/`max` throws and the whole form fails to render | **Handover to Lorrey:** the two-layer split, recorded as the design for FB-16 |

Blockers carried out of SU1: the deployment batch ceiling (R-01) and the two
message flows drawn through unrelated shapes.

Handovers confirmed at SU1: outside participants to Damon; field list to Young;
validation split back to Lorrey.

---

## Stand-up 2 — during Sprint 2

Sprint goal: the integrated increment, model, workers, forms and persistence —
demonstrated end to end, with the v15.0 feedback items closed.

| Member | Done since the last stand-up | Evidence | Next | Blocker | Dependency / handover |
|---|---|---|---|---|---|
| **Tommy** | Declared the nine roles and eleven users in the cluster; mapped every user task's candidate group onto a role; switched authorisation checking on | `bpm/camunda/application.yaml`, `bpm/screenshots/v15/rbac-enforcement.txt` | Prove the grants persist in the engine's own database, not just in the file we wrote | A user-task permission must use the short name `READ`/`CLAIM`/`COMPLETE`/`UPDATE`; the long forms start the engine without complaint and persist nothing | **Blocker escalated.** Read back from the engine's `AUTHORIZATIONS` table: 11 users, 16 roles, 213 grants |
| **Damon** | Hardened all 36 forms against the shared date-rule table | `bpm/tools/harden_forms.py`, `bpm/tools/forms-inventory-v15.json` | Prove the numbers with one ruler against v14 | Form-level date bounds are calendar constraints, not enforcement | **Handover to Young:** the rule table, so the worker-side validator uses the same one |
| **Lorrey** | Grouped the validation findings and re-ran the inventory | `forms-inventory-v14.json` vs `forms-inventory-v15.json` | Close the six remaining findings | None | Closed: required fields 142 → 147, pattern rules 0 → 63, findings 6 → 0 |
| **Young** | Replaced the in-memory store with an embedded H2 database behind the unchanged API; wrote the schema and seed | `bpm/workers/src/main/resources/db/`, `bpm/screenshots/v15/h2-persistence.txt` | Prove state survives a cold restart | Five persistence tests self-skip where `Files.isWritable()` reports false under a restricted sandbox | **Blocker recorded** as L-3 in `docs/14`. The end-to-end persistence proof does not depend on them |

Blockers carried out of SU2: RBAC enforcement and the unauthenticated gRPC
worker are mutually exclusive in this environment (L-1); the sandbox self-skip (L-3).

**Handovers confirmed at SU2:** rule table to Young; date bounds back to Damon.

---

## What is still missing, and what to do about it

- No contemporaneous notes. These records are reconstructed from artefacts and
  the commit log. The honest repair is to keep notes during the next sprint rather
  than to reconstruct these more precisely.
- Second-owner depth is uneven. The backlog names a second owner for every row,
  and the handovers above are real, but for several rows the second owner's
  familiarity is asserted rather than evidenced. The audit of this submission is
  right that the git history supports two human identities, not four.
- Individual attribution. Where a row's evidence is a commit rather than a
  named contribution, the record says so. Claiming four-way attribution that the
  repository cannot show would be worse than admitting the gap.
