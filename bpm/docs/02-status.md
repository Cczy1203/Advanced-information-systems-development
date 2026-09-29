# Status — v2.0 and v2.1 (historical)

> **This document describes v2.0 and v2.1.** It is kept because it records how the
> drawing and the exception branches were rebuilt, and because the gaps it lists
> were real. It is **not** the state of the current release.
>
> Current state: the model is `model/UFCEP6-0-3_Hospital_Patient_Pathway_v14.bpmn`
> — one collaboration, 14 participants, 9 executable hospital processes, 5
> documented outside participants, 36 forms, 432 KB. What v14 changed is in
> `docs/11-white-box-external-participants.md`; the checks are in
> `docs/03-test-record.md`; the counts in `README.md` were re-measured against the
> v14 file.
>
> **Open item carried from this document's era:** `tools/verify_preservation.py`
> still expects the referring-organisation pool that v14 removed, so five of its
> checks fail on the current file. The failures name that pool and nothing else —
> the remaining 65 checks pass. Either the pool returns or the five checks are
> re-pointed at the current baseline; it is not a defect in the model.

Honest state of play for those two releases. Read this before treating anything in
this folder as finished.

v2.1 is v2.0 with a thinner drawing: message flows 66 → 31, end events 60 → 32,
lanes 20 → 14, dashed line 421,424 px → 174,820 px. No scored element was
removed, verified by 62 parsed checks in `tools/verify_preservation.py`. The
changes, the before/after table and the shortfalls are in
`docs/05-v2.1-changes.md`; the re-run evidence is in `docs/03-test-record.md`
section H. Everything below describes the model both releases share.

## Done and verified

**Gap audit** — `docs/01-gap-audit.md`. Complete, measured, and the thing to read
first. v1.0's drawing defects were quantified with `tools/analyse_layout.py`
rather than guessed at.

**A new layout engine** — `tools/layout_engine.py`. It replaces the v1.0 router
that caused the trouble, and treats the drawing as a channel routing problem:

- elements on a column/row grid, columns separated by vertical channels, rows by
  horizontal corridors;
- every flow leaves the right edge and enters the left edge at a port offset
  unique to that flow;
- vertical legs run on tracks inside a channel; two segments share a track only
  when their y ranges clear each other by a safety gap;
- horizontal legs allocated the same way;
- backward flows go to a loop corridor below the pool;
- message flows get their own half of every channel, so a dashed message line
  never sits on a solid pool line.

**Structural and behavioural work** — `tools/spec_v2.py`

- 20 lanes across 8 pools.
- 3 collapsed subprocesses: clinic letter dispatch, outbound telephone contact,
  weekly overdue correspondence list.
- Compensation: 2 boundary compensation events with handlers that release a
  provisional appointment series and a provisional cycle booking, plus 2
  compensation throw events.
- A counted re-attempt capped at 3 for external capacity, which then releases the
  series and hands the case to the pathway team, instead of retrying until the
  incident queue fills.
- The unreadable-referral-pack boundary no longer ends in a bare end event; it
  joins the missing-information loop, which has an owner and a 14 day exit.
- A funding delay now has an owner (Pathway Coordinators) rather than ending
  quietly.

**It deploys.** v14: 9 process definitions and 36 Camunda Forms from the main
file, plus the six outside participants from their own 30 KB file, on local c8run
8.10.0-alpha5 (deployment key `2251799813952610`).

**It renders.** `diagram/hospital-patient-pathway-v14.svg` and `.png`,
5,741 × 15,476, produced by `tools/render_diagram.sh` through bpmn-js in headless
Chrome — the same rendering engine Camunda Modeler uses.

**v14 note.** The current file is
`model/UFCEP6-0-3_Hospital_Patient_Pathway_v14.bpmn`: the six outside
participants are no longer black boxes, so the model now declares 15 processes
and 22 drawn message flows where v7.0 had 9 and 15, and it has been **deployed and
run** on c8run 8.10.0-alpha5 — both hospital paths, all five exception branches
(declined payment, confirmation lost, both escalation rungs, compensation) and all
six outside participants started, driven and completed with `incidents: none`. Fifteen
executable processes do **not** fit the 4 MB append batch (measured: nine records
fit, the tenth is refused), so the shipped configuration deploys nine from the
main file and the six outside participants from a second, generated file. Where
the rest of this document says "9 processes" or "15 message flows", it is
describing v7.0; the current numbers are in `README.md` and
`docs/11-white-box-external-participants.md`.

## Measured result

| Measurement | v1.0 | v2.0 | Target |
|---|---|---|---|
| Sequence-flow overlapping segments | 142 pairs / 18,951 px | **0** | 0 |
| Message-flow overlapping segments | 448 pairs / 507,620 px | **0** | 0 |
| Sequence vs message overlaps | — | **0** | 0 |
| Diagonal segments | 0 px | **0 px** | 0 |
| Line through an unrelated shape | 730 pairs | **4 pairs** | 0 |
| Crossings | 42 | 148 | as low as possible |
| Lanes / collapsed subprocesses | 0 / 0 | **20 / 3** | used |
| Bends per sequence flow | mean 0.7, max 4 | mean 0.8, max 4 | ≤ 4 |

Every overlap target is met. The remaining 4 line-through-shape violations are
flows clipping a boundary event sitting beside the one they belong to — a few
pixels at the edge of a 36 px circle.

One thing is worse than v1.0 and it is a real trade-off:

- **Crossings rose (42 → 148).** Spreading routes across corridors instead of
  funnelling them all down one removes the overlaps but makes more lines cross.
  Zero overlaps and zero crossings pull against each other; this model chose zero
  overlaps, because the brief names overlap and parallel-adjacency as the fault
  and crossing only as something to minimise.

## Done since the last round

- **Zero overlaps reached** — none for sequence flows, none for message flows,
  none between the two, no diagonals.
- **Workers completed and running** — the v1.0 set plus the three new job types
  (`treatment.release-series`, `treatment.release-cycle-booking`,
  `treatment.record-capacity-retry`). 37 subscriptions, builds green.
- **Both paths run** — `screenshots/run-happy-path.log` (11 steps, three
  `incidents: none`) and `screenshots/run-exception-path.log`.
- **Operate and Tasklist captured** — `screenshots/`. Operate reports
  **"Your processes are healthy — There are no incidents on any instances."**
- **`docs/03-test-record.md`** — every layout, deployment, worker and path check,
  with the eleven defects found by running it.
- **`docs/04-modelling-decisions.md`** — gateway-by-gateway reasoning, exception
  branch justifications, assumptions and limitations, written to be read out.

## Dashed-line thinning

The message flows were thinned after a review question about how many dashed
lines the diagram carries. Three changes, none of which touch the model's
meaning:

| Change | Why |
|---|---|
| Eleven flows from a service task to an external supplier removed | The task type (`correspondence.*`, `payment.*`, `scheduling.*`, `external-resources.*`) already names the supplier. The dashed line only documented a call the task represents — 62,589 px of line for no information |
| Pools re-ordered so frequent correspondents sit near each other | Pool order is presentation only, but it sets how far each message travels. Chosen by a fixed-seed search over the stacking order |
| Row pitch 160 → 142, pool gap 128 → 104 | The canvas was 16,018 px tall, which is what made every cross-pool line enormous |

| | before | after |
|---|---|---|
| Message flows | 77 | **66** |
| Total dashed length | 541,992 px | **421,424 px** (−22%) |
| Vertical riser length | 340,361 px | **250,013 px** (−27%) |
| Flows longer than 8,000 px | 31 | **19** |
| Canvas | 8,698 × 16,018 | 8,698 × **14,060** |
| Sequence / message overlaps | 0 / 0 | **0 / 0** |

The remaining 66 cannot be merged. Merging two message flows onto one line would
make them indistinguishable, which breaks the brief's requirement that every line
be independently traceable at 100%.

## Found late and fixed

**Every form with a date on it was broken.** 17 fields used `"type": "date"`.
Camunda Forms has no such type — a date field is a `datetime` with
`subtype: "date"` — so the renderer refused the whole form. All 36 forms now
render: `TOTAL=36 FAILED=0` against form-js, the same renderer Tasklist uses.
`screenshots/camunda-forms-rendered.png` shows them drawn as real widgets.

This would have cost the entire Camunda Forms mark had it gone unnoticed. The
full story is in `docs/03-test-record.md` section F4.

## Done in the final round

- **Opened in Camunda Modeler** — `Camunda 8.10 (alpha)`, `Local C8Run`,
  **0 errors**, 30 warnings (`screenshots/camunda-modeler-v2-status-bar.png`).
  The 30 are 28 elements inside collapsed subprocesses that have no diagram
  interchange of their own, plus the 2 compensation handlers that carry no
  sequence flows because Zeebe requires them not to. Both are legitimate
  constructs, not mistakes.
- **Both paths re-run on the fresh engine** — happy path 11 steps, three
  `incidents: none`; exception path held at `SEC_EGW_InfoRequest`, no incident.
- **Operate captured** — dashboard reports *"Your processes are healthy — There
  are no incidents on any instances"*, with the held Medical Secretaries instance
  visible.
- **`tools/deploy.sh`** added to the v2.0 folder; `tools/forms_spec.py` is now a
  local copy rather than borrowed from v1.0, so the folder is self-contained.

## Not done

- **Tasklist cannot draw the forms** even though they are valid: it gets `401`
  from `/v2/authentication/me` in this c8run setup. Environmental, not a model
  defect. The forms themselves are proven to render (F4).
- **Three branches not demonstrated** end to end: declined payment,
  payment-confirmation-lost, and the three-month letter escalation. Modelled and
  the workers support them; not run.
- **Compensation not triggered in a live run.**

## Where to pick up

1. Sort the c8run webapp authentication so Tasklist can draw the forms, then
   re-capture the task view.
2. Run the three undemonstrated branches.
3. Add a crossing-reduction pass if the crossing count matters more than it did
   here.

The v1.0 folder is untouched and still works — it deploys, runs both paths, and
has its own evidence. If v2.0 cannot be finished in time, v1.0 is the safer
submission.
