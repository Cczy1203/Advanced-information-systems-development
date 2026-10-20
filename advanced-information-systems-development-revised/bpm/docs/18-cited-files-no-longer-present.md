# 18 - Files the documents cite that are no longer in the tree

An audit of the submission found that the documents cite files that are not in the
repository: **39 paths, across 19 documents**. This is the list, what happened to
each, and what replaced it. Every one of them is still in git history — `git show
v14.0-final:<path>` returns the file — so nothing has been lost, but a reader
following a citation should not have to find that out by trying it.

The four groups below account for all 39.


## The fourteen-pool model and its drawing

**Replaced by:** model/UFCEP6-0-3_Hospital_Patient_Pathway_v16.bpmn, diagram/hospital-patient-pathway-v16.{svg,png,pdf,-overview.png,-sections.pdf}

| Path | Why it went |
|---|---|
| `bpm/diagram/UFCEP6-0-3_Hospital_Patient_Pathway_v14.pdf` | the v14.0 model and its exports were replaced by v16.0 |
| `bpm/diagram/hospital-patient-pathway-v14.png` | the v14.0 model and its exports were replaced by v16.0 |
| `bpm/diagram/hospital-patient-pathway-v14.svg` | the v14.0 model and its exports were replaced by v16.0 |
| `bpm/diagram/sections/01_Medical_Secretaries.png` | the per-pool crops were for a fourteen-pool drawing; v16 sections the single pool by stage instead |
| `bpm/diagram/sections/02_External_Correspondence_Service.png` | the per-pool crops were for a fourteen-pool drawing; v16 sections the single pool by stage instead |
| `bpm/diagram/sections/03_External_Payment_Service_Provider.png` | the per-pool crops were for a fourteen-pool drawing; v16 sections the single pool by stage instead |
| `bpm/diagram/sections/04_Finance_Team.png` | the per-pool crops were for a fourteen-pool drawing; v16 sections the single pool by stage instead |
| `bpm/diagram/sections/05_External_Treatment_Laboratory_and_Imaging_Services.png` | the per-pool crops were for a fourteen-pool drawing; v16 sections the single pool by stage instead |
| `bpm/diagram/sections/06_Treatment_and_Chemotherapy_Bookings_Team.png` | the per-pool crops were for a fourteen-pool drawing; v16 sections the single pool by stage instead |
| `bpm/diagram/sections/07_Consultants.png` | the per-pool crops were for a fourteen-pool drawing; v16 sections the single pool by stage instead |
| `bpm/diagram/sections/08_Outpatient_Bookings_Team.png` | the per-pool crops were for a fourteen-pool drawing; v16 sections the single pool by stage instead |
| `bpm/diagram/sections/09_External_Scheduling_Service.png` | the per-pool crops were for a fourteen-pool drawing; v16 sections the single pool by stage instead |
| `bpm/diagram/sections/10_Patient_or_authorised_representative.png` | the per-pool crops were for a fourteen-pool drawing; v16 sections the single pool by stage instead |
| `bpm/diagram/sections/11_Clinical_Nurse_Specialist_Team.png` | the per-pool crops were for a fourteen-pool drawing; v16 sections the single pool by stage instead |
| `bpm/diagram/sections/12_Call_Handling_Team.png` | the per-pool crops were for a fourteen-pool drawing; v16 sections the single pool by stage instead |
| `bpm/diagram/sections/13_Patient_Pathway_Coordinators.png` | the per-pool crops were for a fourteen-pool drawing; v16 sections the single pool by stage instead |
| `bpm/diagram/sections/14_Administrative_Management_Team.png` | the per-pool crops were for a fourteen-pool drawing; v16 sections the single pool by stage instead |
| `bpm/diagram/sections/INDEX.md` | the per-pool crops were for a fourteen-pool drawing; v16 sections the single pool by stage instead |
| `bpm/model/UFCEP6-0-3_Hospital_Patient_Pathway_v14.bpmn` | the v14.0 model and its exports were replaced by v16.0 |
| `bpm/screenshots/static-checks-v7.0.txt` | captured against v7.0, three releases ago |

## The v1/v2 model generators

**Replaced by:** tools/spec_v3.py and tools/build_v3.py, which carry the same build checks the v2 generator only promised

| Path | Why it went |
|---|---|
| `bpm/tools/build_external_participants.py` | it built the five white-box outside participants; v16 draws them as black boxes |
| `bpm/tools/build_v2.py` | the v2.0 generator; its promised build check (refuse a model that mixes boolean and string comparisons) was never implemented in it, and is now implemented in tools/spec_v3.py |
| `bpm/tools/check_external_participants.py` | it built the five white-box outside participants; v16 draws them as black boxes |
| `bpm/tools/r0.json` | a scratch analysis output |
| `bpm/tools/spec_v2.py` | the v2.0 generator; its promised build check (refuse a model that mixes boolean and string comparisons) was never implemented in it, and is now implemented in tools/spec_v3.py |
| `bpm/tools/v1/bpmn_builder.py` | the v1.0 model definition the v2.0 generator read; the v2.0 generator has gone too |
| `bpm/tools/v1/spec_hospital.py` | the v1.0 model definition the v2.0 generator read; the v2.0 generator has gone too |
| `bpm/tools/verify_preservation.py` | it checked the model against a v2.0 baseline that no longer exists. It was cited 19 times as the only evidence for the '62/62 and 67/67 preservation checks' results, which is the clearest example in the submission of a conclusion resting on a file that is not there |

## The fourteen-pool drawing scripts

**Replaced by:** tools/render_v16.py and tools/render_sections_v16.py

| Path | Why it went |
|---|---|
| `bpm/tools/export_sections.py` | it rendered and cropped the fourteen-pool collaboration |
| `bpm/tools/render_diagram.sh` | it rendered and cropped the fourteen-pool collaboration |

## The legacy Node scaffold

**Replaced by:** nothing; it was Sprint 0 scaffolding and the workers are Java

| Path | Why it went |
|---|---|
| `bpm/diagram/UFCEP6-0-3_Hospital_Patient_Pathway_v14_sections.pdf` | the v14.0 model and its exports were replaced by v16.0 |
| `bpm/diagram/hospital-patient-pathway-v14-overview.png` | the v14.0 model and its exports were replaced by v16.0 |
| `package-lock.json` | Sprint 0 Node.js scaffolding, never part of the delivered system |
| `package.json` | Sprint 0 Node.js scaffolding, never part of the delivered system |
| `src/config.js` | Sprint 0 Node.js scaffolding, never part of the delivered system |
| `src/index.js` | Sprint 0 Node.js scaffolding, never part of the delivered system |
| `src/services/patientService.js` | Sprint 0 Node.js scaffolding, never part of the delivered system |
| `src/utils/logger.js` | Sprint 0 Node.js scaffolding, never part of the delivered system |
| `src/workers/referralWorker.js` | Sprint 0 Node.js scaffolding, never part of the delivered system |

## What this means for a marker

If a document sends you to one of these paths, the thing it describes has been
replaced rather than removed. The current equivalents are in the **Replaced by**
line at the top of each group. Where a result is cited as evidence, prefer the
result rather than the citation: the v16.0 results, with the files that carry them,
are in `docs/17-single-pool-operational-model.md`.

Nothing here was deleted to hide a number. The two results that the audit found to
be contradicted by their own evidence — the empty RBAC read-back and the
compensation log with no compensation in it — are both still in the tree, annotated
where they stand.
