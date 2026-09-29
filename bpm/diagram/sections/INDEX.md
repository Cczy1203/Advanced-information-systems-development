# Section images — reading order

One PNG per pool, at full size, with nothing else on the page. This is how the
collaboration is meant to be read: the full drawing is a fourteen-participant wall
map, and no single team's work is legible on it.

**The file numbering matches the model's own top-to-bottom pool order**, so
`01_Medical_Secretaries.png` is the top band in
`../hospital-patient-pathway-v14.svg`. That order is chosen by the routing
optimiser to keep the message hand-offs short and local, which is why it is not
the order below. v14 re-optimised it, so the external services now sit beside the
hospital teams that call them.

**This is the order a reader should follow them in** — the path a patient takes
through the service:

| # | Read this | Why |
|---|---|---|
| 10 | `10_Patient_or_authorised_representative.png` | The patient, who attends and contacts the hospital |
| 01 | `01_Medical_Secretaries.png` | Referral pack checked, clinic letters processed and dispatched |
| 07 | `07_Consultants.png` | Accept, reject, redirect or ask for more; the clinical decisions and authorisations |
| 08 | `08_Outpatient_Bookings_Team.png` | The new patient appointment, contact rule and cancellations |
| 06 | `06_Treatment_and_Chemotherapy_Bookings_Team.png` | Treatment booking, cycle scheduling, capacity, payment and compensation |
| 04 | `04_Finance_Team.png` | Funding route, charges, payment outcomes and refunds |
| 11 | `11_Clinical_Nurse_Specialist_Team.png` | Clinical advice and enquiries |
| 12 | `12_Call_Handling_Team.png` | Enquiries classified and routed |
| 13 | `13_Patient_Pathway_Coordinators.png` | Overdue letters, reminders, escalations and delayed bookings |
| 14 | `14_Administrative_Management_Team.png` | The top of the escalation ladder |

The services outside the hospital, read when the pool that calls them is being
read:

| # | Read this | Why |
|---|---|---|
| 02 | `02_External_Correspondence_Service.png` | Letters received, printed and dispatched |
| 09 | `09_External_Scheduling_Service.png` | Appointment slots searched and returned |
| 05 | `05_External_Treatment_Laboratory_and_Imaging_Services.png` | Treatment and diagnostic capacity checked and returned |
| 03 | `03_External_Payment_Service_Provider.png` | The card transaction processed, status and reference returned |

## What each one contains

Every pool image shows that participant's full run: its start event, its user
tasks (with the Camunda Form bound to each), its service tasks (with the job type
each publishes), its gateways with their conditions, its boundary events and its
end events. The images for the external participants are the same rule applied
outside the hospital: a message that arrives, the step that does the work, and the
answer that goes back.

**v14 note.** Until v14 the outside suppliers were black boxes, and three of them —
payments, treatment and diagnostics, scheduling — had no drawn connection at all.
Each now carries a process of its own and a hand-off in each direction, so no pool
on the drawing is a box that nothing points at. What they deliberately do *not*
carry is invented hospital detail: an outside participant has no user task and no
form, because nobody at the hospital performs its work. The patient pool carries a
single start event for the same reason.

The three collapsed sub-processes are drawn closed on the main plane. Their steps
carry diagram interchange, so a section image that contains one shows the box,
and opening it in Camunda Modeler shows the laid-out flow inside.
