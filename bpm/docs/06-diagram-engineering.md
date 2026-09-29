# The drawing: how the collaboration is routed, and what v7.0 changed

This document replaces the earlier `06-visual-compaction.md`. That file described
a third, much smaller compaction pass (9 lanes, 12 collapsed sub-processes, 15
message flows, canvas 2,398 × 6,858) whose output was never shipped. The shipped
model is the one described here. The earlier pass is written up in §5 as a
rejected experiment, with the numbers that rejected it, and those numbers explain
why the drawing looks the way it does now.

Everything below is measured, never remembered:

```bash
python3 tools/analyse_layout.py model/UFCEP6-0-3_Hospital_Patient_Pathway_v2.bpmn
```

---

## 1. What the drawing is

One BPMN collaboration, one diagram, fifteen participants and fourteen lanes:

| | |
|---|---:|
| participants (pools) | 15 |
| lanes | 14 |
| drawn shapes on the plane | 357 |
| sequence flows | 298 |
| drawn message flows | 15 |
| end events | 65: one per terminating path, none merged |
| collapsed sub-processes | 3 |
| canvas | 5,332 × 14,176 px |

The full diagram is a wall map; that is what a fifteen-participant collaboration
is. It is meant to be read three ways, and all three are in `diagram/`:

| artefact | what it is for |
|---|---|
| `hospital-patient-pathway-v2.svg` | the vector original: open it and zoom, the lines stay sharp |
| `hospital-patient-pathway-v2.png` | 7,484 × 14,468 raster of the same drawing |
| `hospital-patient-pathway-v2-overview.png` | scaled to 2,400 px on the long edge, to see the whole shape at once |
| `sections/NN_<pool>.png` | one image per pool: this is how a reader actually follows one team's work, at full size and with nothing else on the page |

## 2. How the routing works

`tools/layout_engine.py` treats the drawing as a channel-routing problem rather
than drawing each line on its own:

1. **Grid.** Every element sits on a column/row cell fixed by `tools/spec_v2.py`.
   Columns are separated by vertical channels, rows by horizontal corridors.
2. **Ports.** Every flow leaves the right edge of its source and enters the left
   edge of its target at an offset unique to that flow, so no two flows start
   from the same point.
3. **Tracks.** The vertical leg of a route runs on a track inside a channel; two
   segments share a track only when their y ranges clear each other. Horizontal
   legs are allocated the same way. This is what makes overlapping segments
   impossible by construction rather than by luck.
4. **Corridors.** A flow that has to change row crosses on a corridor chosen for
   it, and backward flow goes to a loop corridor below its pool.
5. **Message flows** get their own risers and their own track across the gap
   between pools, fed through the same allocator, so a dashed line cannot land
   on a sequence flow.

## 3. What v7.0 changed

Three changes, all inside the router. No element, task, form, message or path
was added or removed to make the drawing better.

### 3.1 Corridors are now chosen by measured crossings, not by guessing

The v2.1 router picked the least-loaded corridor nearest the middle of a jump.
That spreads the ink out, but a jump of eight rows still cut whatever was in
between. v7.0 keeps that as the first pass and then measures: for every
dogleg it tries the corridors its own rows allow, counts how many other segments
the resulting polyline would cut, keeps the best, and redraws. It repeats until a
round changes nothing.

The geometry phases were split out of `place()` into `_geometry()` so the
optimiser can re-measure the whole drawing after each round without touching the
row, corridor or port plan. The build stays deterministic. The same input gives
the same file, byte for byte (verified: two consecutive runs produce the same
SHA-256).

### 3.2 Boundary events no longer sit under the corridor tracks

A boundary event straddles the bottom edge of its host, so it reaches into the
corridor underneath, exactly where that corridor's horizontal runs want to go.
Two fixes:

* **Sibling spacing.** Two boundary events on one host were drawn 34 px apart on
  36 px circles, so the circles overlapped and a line leaving the left one ran
  straight across the right one. The pitch is now `EVT + 6` = 42 px.
* **Row height.** A row that hosts boundary events is grown by `BND_DEPTH` = 40 px,
  so the corridor below it has room for its tracks without touching a circle.

### 3.3 A verified pass removes any line still drawn across a shape

`_unclip()` walks every horizontal run, samples it against every box, and if it
finds a run inside a shape it is not connected to, it shifts that run up or down
by 18–36 px and closes the gap with a short vertical stub, so the line still
leaves the shape edge it started from. Every candidate move is checked against
the boxes **and** against every other segment before it is kept. The pass can
therefore only remove a defect, never add one.

### 3.4 Measured effect

| metric | shipped v2.1 | **v7.0** | change |
|---|---:|---:|---|
| Sequence-flow overlapping segment pairs | 0 | **0** | — |
| Message-flow overlapping segment pairs | 0 | **0** | — |
| Diagonal segments | 0 px | **0 px** | — |
| Sequence-flow crossings | 197 | **95** | **−102 (−52%)** |
| Lines drawn through an unrelated shape | 4 | **0** | **−4** |
| Dashed message flows drawn | 31 | **15** | **−16 (−52%)** |
| End events | 32, several merged | **65, none merged** | see §3.6 |
| Bends per sequence flow (mean / max) | 1.1 / 4 | **0.9 / 5** | fewer bends on average |
| Sequence-flow ink | 197,576 px | **120,704 px** | −76,872 (−39%) |
| Message-flow ink | 179,059 px | **61,613 px** | −117,446 (−66%) |
| Total ink | 378,475 px | **182,317 px** | **−196,158 (−52%)** |
| Canvas | 7,496 × 13,736 | **5,332 × 14,176** | 2,164 px narrower |
| Distinct node left-edges | 54 | **54** | — |

The canvas is 440 px taller because of the boundary-event row height in §3.2,
and 2,164 px narrower because the routing channels no longer have to carry the
runs that the merged end events and the surplus message flows created. The
drawing is now less than half the ink it was, at the cost of 3.1% more paper.

### 3.5 One end event per terminating path

v2.1 merged routine end events that sat within three rows of each other, which
took them from 60 to 32. The drawing got quieter and less true: several sequence
flows converged on one circle, so a reader could not tell which branch had
finished, and the flows that were merged away had to travel to a shared circle
instead of ending where they finish.

Merging is switched off (`_merge_end_events` is kept in the generator but is no
longer called), and the five joins inherited from v1.0 were split as well, so no
end event has more than one incoming flow. End events went 32 → 65.

This is the change that paid for itself twice. Because each path now ends where
it finishes, fewer flows need a long run to a distant circle: crossings fell from
123 to 94 on their own, the busiest routing channel narrowed from 228 px to
111 px, and the canvas lost 2,164 px of width. `tools/verify_preservation.py`
now checks the invariant directly: no end event with more than one incoming
flow, and no end event with none.

One end event was deleted rather than kept: `SEC_End_PackIncomplete`. v2.0
replaced that dead end with a loop that asks the referring organisation for what
is missing, which left the circle unreachable. It is residue, not a scored
terminal, and it showed up as a disconnected element once the merges were undone.

### 3.6 Fifteen dashed lines instead of thirty-one

A message flow is a picture of a hand-off. In Camunda 8 the throw event's
`publish-message` job performs the hand-off, so the dashed line is documentation;
31 of them running the height of the drawing cost far more attention than they
returned.

What is drawn now:

* **every exception and outcome hand-off**: a rejected referral, a request for
  more information, a funding delay, a payment left unresolved, a refund the
  provider has not returned, an escalation to the manager or to higher
  management, an urgent clinical concern. These carry marks and are never
  thinned; and
* **the four hand-offs that cross the system boundary** (the referral arriving
  from the referring organisation, the clinic letter going out through the
  correspondence service, the patient attending the new patient appointment, and
  the patient contacting the hospital).

Everything else stays in the model as a throw/catch pair and still runs; it is
simply not drawn. Dashed-line ink fell from 179,059 px to 61,613 px, a 66%
reduction, and the message-flow track demand that drives the channel width
collapsed with it.

The retention guarantee is checked, not asserted: `tools/verify_preservation.py`
fails if a system-boundary hand-off is missing, if anything other than an
exception or boundary hand-off is drawn, or if the number of drawn exception
hand-offs drops below the eleven the previous release drew.

### 3.7 The two lint errors, closed

`bpmnlint:recommended` reported two `no-implicit-start` errors: an element that
nothing can reach. Both were real, not linter pedantry.

**`TRT_Throw_BookingPending`** was the head of the counted capacity retry. The
v2.0 pass added a second timer branch and pointed the external-capacity boundary
event straight at the release step, which left the whole record→cap→retry chain
unreachable. The "capped retry" the modelling document describes was doing
nothing at runtime. The boundary now enters the chain it was built for: three
attempts, then the provisional series is released and the pathway team is told.
Behaviour on the driven paths is unchanged; they never reach that branch, because
external capacity is available on both.

**`SUB_Secretaries_Dispatch_Chase`** is the retry step inside the collapsed
dispatch sub-process. The boundary event that used to reach it cannot be
expressed inside a collapsed sub-process, so the step was unreachable code. The
inner flow now runs Prepare → Send → *Did the service accept the letter?* → End
on `dispatchStatus = "SENT"`, defaulting to the retry step when the service did
not accept it. That reads the status the dispatch worker already returns, so the
run behaves exactly as before.

Both fixes are in `tools/spec_v2.py` and both are checked: the audit fails if any
element inside the collaboration is an implicit start.

### 3.8 Diagram interchange inside the collapsed boxes

The first v2.1 pass removed the diagram interchange for the steps inside the
three collapsed sub-processes, on the reasoning that a collapsed box never draws
them. The effect was the opposite of the intent: `no-bpmndi` fires when DI is
missing, so that change created 30 lint errors, and the boxes could not be
opened in the Modeler either.

In v7.0 every inner element carries DI again, and the inner start and end events
carry names. bpmn-js hides the children of a collapsed sub-process, so the main
plane is byte-for-byte the same drawing; what changes is that opening a box shows
a laid-out flow instead of an empty frame.

| | v2.1 | **v7.0** |
|---|---:|---:|
| `bpmnlint:recommended` errors | 39 | **2** |
| of which `no-bpmndi` | 30 | **0** |
| of which `label-required` | 7 | **0** |
| of which `no-implicit-start` | 2 | 2 (DEF-18) |
| elements without diagram interchange | 30 | **0** |

`tools/analyse_layout.py` was updated at the same time: it now excludes hidden
children from every count, because two lines inside a box that is never drawn
open cannot overlap on the page. That is a measurement fix, not a model change.

## 4. Nothing scored was touched

The router writes diagram interchange only. The semantic content of the file is
unchanged from the release the preservation audit was run against:
`tools/verify_preservation.py` still answers 67 parsed checks, and every one of
them reads the BPMN XML, not the drawing.

## 5. The rejected compaction, and why it is in this document

An earlier attempt at this release tried to fight the wall-map problem directly:
fold each pool's main line into one collapsed sub-process, merge routine end
events, and thin the drawn message flows. It produced a 2,398 × 6,858 canvas
that looks calm at a glance.

Measured against the shipped model, that version is worse everywhere it matters:

| metric | compacted attempt | **shipped v7.0** |
|---|---:|---:|
| Sequence-flow overlapping segment pairs | 2,702 (155,054 px) | **0** |
| Message-flow overlapping segment pairs | 12 (4,772 px) | **0** |
| Diagonal segments | 250 px | **0 px** |
| Sequence-flow crossings | 397 | **94** |
| Lines through an unrelated shape | 751 | **0** |
| Drawn message flows | 15 | **15** |
| Canvas | 1,456 × 6,724 | 5,332 × 14,176 |

Three of those numbers are the whole argument. Compressing the drawing did not
simplify the connections; it put them on top of one another and dragged them
through the boxes. The shipped drawing reaches a *smaller* width than the
compacted attempt without any of that, because it removed lines that carried
nothing and gave every path its own ending instead of shrinking the paper. A
smaller canvas is not a more readable one. The earlier pass is also the reason
this document exists: while it was in the tree, the prose and the model disagreed,
which is the configuration-management failure `docs/09-...` §1 raises as R-13.

The readability problem it was trying to solve is real, and it is answered
instead by the per-pool section images in §1: one pool per page, at full size.

## 6. Reproducing the drawing

```bash
cd tools
python3 build_v2.py                     # rewrite the .bpmn and the 36 .form files
python3 ../tools/analyse_layout.py ../model/UFCEP6-0-3_Hospital_Patient_Pathway_v2.bpmn
bash    render_diagram.sh               # SVG + PNG + overview
python3 export_sections.py              # one PNG per pool
```

`build_v2.py` takes about twelve seconds: six of those are the crossing
optimiser measuring candidate corridors, which is the price of the 38% reduction
in §3.4.
