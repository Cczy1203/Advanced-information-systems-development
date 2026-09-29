# Gap audit — v1.0 against the 70%+ band

Written before any modelling was redone, as asked. The point of this document is
to be honest about what v1.0 actually achieves, so that v2.0 is a list of jobs
rather than a redraw.

**v1.0 reviewed:** `/Users/cczy/Desktop/UFCEP6-0-3_BPMN_Hospital_Referral`
**Rubric:** UFCEP6-0-3 Portfolio Assessment Specification V2, section 4
**Environment checked:** c8run 8.10.0-alpha5 (`GET /v2/topology` → 200),
Camunda Modeler 5.51.0, JDK 25, Maven 3.9.9

## How the v1.0 numbers were obtained

"The lines look tangled" is not actionable, so v1.0 was measured with
`tools/analyse_layout.py`, which walks the BPMN DI section and looks for the
things the brief complains about. v1.0, as delivered:

| Measurement | v1.0 | What good looks like |
|---|---|---|
| Sequence-flow segments overlapping or parallel within 6 px | **142 pairs, 18,951 px of shared length** | 0 |
| Message-flow segments overlapping or parallel within 6 px | **448 pairs, 507,620 px** | 0 |
| Sequence-flow segment crossings | **42** | as close to 0 as the process allows |
| Lines running through a shape they are not connected to | **730 (flow, shape) pairs** | 0 |
| Distinct left-edge x positions across 312 nodes | **48** | a small fixed set of columns |
| Clear gap between pools | 60 px, no routing channel | enough for the message-flow channel |
| Lanes | **0** | where a pool covers more than one sub-role |
| Collapsed subprocesses / call activities | **0** | repetitive admin contained |
| Diagonal segments | 0 px | 0 (this one was already right) |
| Bends per sequence flow | mean 0.7, max 4 | ≤ 4 (also already right) |

The last two rows matter: v1.0 was already orthogonal and did not use long
diagonals. The problem is not the shape of individual lines, it is that lines
share the same corridors. The router sent every flow between the same pair of
columns down the same mid-x, and every message flow between the same pair of
pools down the same mid-y. That is where the 142 and 448 overlaps come from, and
it is why the picture reads as a smear even though each line is individually
straight.

---

## A. Runnable BPMN (15%, LO2, LO4)

70%+ descriptor: *a full, consistent and reliable runnable model that deals with
the relevant business complexity and exceptions; behaviour backed by clear
evidence and an understanding of the limits; configuration management used well.*

| # | What the descriptor wants | v1.0 | Evidence | v2.0 fix |
|---|---|---|---|---|
| A1 | Relevant business complexity | Largely there. 15 pools, 312 nodes, 56 messages, whole pathway from referral to follow-up | model statistics | Keep the coverage. Restructure how it is drawn, not what it says |
| A2 | Exceptions handled, not just detected | **Half done.** 9 error codes and 17 boundary events exist, but most exception branches end in a bare end event — "Referral held", "Booking pending", "Payment unresolved". Once there, nothing else happens. There is no recovery, no second attempt, no escalation timer on the failed service | see the end events named "held", "pending", "unresolved" | Give every exception branch an owner and an exit: re-attempt, escalate on a timer, or hand to a named team. A dead end is not exception handling |
| A3 | Consistency | **Not met visually.** 142 overlapping sequence-flow segment pairs | analyse_layout | Recompute every coordinate. New orthogonal channel router with one dedicated track per flow between a column pair |
| A4 | Reliability | **Partly.** Three defects only surfaced when the model was actually run: missing `correlationKey` on throw events, Yes/No radios compared as booleans, and a service task ordered before the form that feeds it | README §7 of v1.0 | Keep the build-time guards, and add more (unreachable end events, exception branches with no outgoing flow, dead-end detection) |
| A5 | Readable as one diagram | **Not met.** 730 line-through-shape violations, 42 crossings, 48 distinct node columns | analyse_layout | Column grid per pool, uniform spacing, a routing channel between every row band and between every pool |
| A6 | Main line readable, repetitive admin contained | **Not met.** 0 lanes, 0 subprocesses, 0 call activities. Call handling, letter dispatch and pathway reporting are all laid out flat, so 312 nodes compete for attention | analyse_layout | Lanes in the pools that cover more than one sub-role. Call activity for the enquiry handling cycle. Collapsed subprocesses for correspondence dispatch and weekly reporting |
| A7 | Clear evidence of behaviour | **Partly.** Deployment log, two scripted paths, console output | `screenshots/demo-*.log` | Add Operate and Tasklist screenshots per path, plus a written test record with expected vs actual |
| A8 | Understanding the limits | Met. Nine numbered limitations | v1.0 README §10 | Carry them forward and extend; split into its own document so it can be used as a presentation script |
| A9 | Configuration management | **Partly.** Generated from specs, `versionTag`, build-time checks | `tools/` | Add a v2.0 version tag, a change list against v1.0, and keep the generator so the diff stays reviewable |

## B. External workers (15%, LO2, LO4, LO5)

70%+ descriptor: *maintainable workers that complete the required activities and
deal with the relevant failures consistently; integration and data handling
convincingly demonstrated; configuration management used well.*

| # | What the descriptor wants | v1.0 | Evidence | v2.0 fix |
|---|---|---|---|---|
| B1 | A worker per automated activity | Met. 33 worker classes, 34 subscriptions, one per job type | `workers/README.md` | Keep |
| B2 | Invalid input and service failure | Met. Validation, 9 BPMN error codes, `retries="3"`, `SimulatedFailureRegistry` | `workers/DEPLOYMENT.md` | Keep, and show it in the run evidence |
| B3 | **Compensation** | **Absent.** `compensateEventDefinition` appears nowhere. When a confirmed appointment is cancelled or a treatment changes, the money and the booking are not unwound by the model — the case just goes to a task | grep of the v1.0 BPMN | Add compensation: a compensation boundary event on the treatment confirmation activity with a compensating handler that releases the booking and triggers the refund path. This is the clearest single gap on the worker side |
| B4 | Retry behaviour beyond the retry count | **Partly.** `retries="3"` is set, but when retries run out Zeebe raises an incident and the model has nothing to say about it. There is also no explicit timer-based re-attempt for an external service that is down rather than erroring | v1.0 model | Add a timer-based re-attempt loop for the external capacity check, with a cap and an escalation, so "still unavailable after three days" has an owner |
| B5 | Internal systems distinguished from external services | **Partly.** External suppliers are black-box pools and service tasks carry `external-*` job types, but nothing groups them visually and the naming drifts (`scheduling.` in one place, `external-resources.` in another) | v1.0 BPMN | Group the external pools, standardise the job-type prefixes, and say in the decisions document which boundary each one crosses |
| B6 | Integration convincingly demonstrated | Met on the happy path, thin on the exception path | `screenshots/demo-exception-run.log` | Run and screenshot the exception path end to end |

## C. Camunda Forms (15%, LO1, LO2, LO5)

70%+ descriptor: *well-reasoned, user-centred forms that are consistent,
accessible and effective; validation and data integration reliably support the
relevant user journeys; configuration management used well.*

| # | What the descriptor wants | v1.0 | Evidence | v2.0 fix |
|---|---|---|---|---|
| C1 | A form on every user task | Met. 38 tasks, 36 forms, one shared on purpose | `model/forms/` | Keep |
| C2 | Validation | Met. Required, length, and numeric range rules | form JSON | Keep |
| C3 | Accessibility | **Partly.** One field per row and a description on most fields, but nothing groups related fields, long forms have no headings, and there is no written accessibility rationale | form JSON | Add group headings to the long forms, add descriptions where they are missing, and write the accessibility reasoning into the decisions document |
| C4 | Consistency | **Partly, and it bit us.** Yes/No radios submit the text `"true"`, while ten gateway conditions compared against a boolean. That produced a FEEL null and a live incident before it was found | v1.0 README §7 | Pick one convention, apply it everywhere, and keep the build check that refuses to emit a model mixing the two |
| C5 | Fits the target user | **Partly.** Some forms mix clinical wording into clerical tasks (a secretary's checklist asks about "clinical documentation") and some labels are longer than they need to be | form JSON | Reword per role: secretaries and bookings staff get administrative language, clinical forms stay clinical |

## D. Requirements in the v2.0 brief that v1.0 does not attempt at all

1. Orthogonal routing with one track per flow, no shared corridors.
2. Message flows on their own channel, separated from in-pool lines.
3. Gateway branches fanned out with the condition label next to its own line.
4. Text annotations that do not sit on top of any line.
5. Loops routed below or above the pool, never back through the middle.
6. Collapsed subprocesses or call activities for repetitive administration.
7. Lanes inside pools where one pool covers more than one desk.
8. Operate and Tasklist screenshots as run evidence.
9. A written test record: what was tested, expected, actual, what was fixed.
10. A separate modelling decisions document usable as a presentation script.

---

## What v2.0 will actually change

**Drawing.** A new layout engine (`tools/layout.py`) replaces the v1.0 router.
It assigns each pool a band, each band a set of lanes, each lane a row, and each
element a column on a fixed grid. Every flow gets:

- a named exit port and entry port, so no two flows leave a gateway from the
  same point;
- its own vertical track in the inter-column corridor, offset from its
  neighbours by a fixed pitch, so two flows between the same columns never run
  side by side;
- its own horizontal track in the inter-row corridor when it has to travel
  across rows;
- a dedicated channel between pools for message flows, and a separate channel
  below the pool for loops.

Coordinates are computed, not reused from v1.0. After generating, the layout is
measured again with `analyse_layout.py` and the model is not accepted until the
overlap, crossing and through-shape counts are at or near zero.

**Structure.** Enquiry handling becomes a call activity (one process, called from
the call handling pool). Correspondence dispatch and weekly pathway reporting
become collapsed subprocesses. That takes the main line down from 312 visible
nodes to a figure a person can follow in one pass, without losing any of the
behaviour — the detail is still in the same file and still runs.

**Behaviour.** Compensation on the treatment confirmation activity, a capped
re-attempt loop for external capacity, and an owner plus an exit for every
exception branch that currently dead-ends.

**Evidence.** Two paths run on the live engine and captured in Operate and
Tasklist, plus a test record and the decisions document.

**What will not change.** The pool list, the message names, the 36 forms and the
33 workers are sound. Reusing them keeps the v1.0 to v2.0 diff reviewable, which
is itself part of the configuration-management mark.
