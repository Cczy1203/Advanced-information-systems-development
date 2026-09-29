# Submission index — UFCEP6-0-3 Initial Release

**Version submitted: v14.0** — tag `v14.0-final`, commit recorded below.

Everything the assessment asks for, and where it lives in this repository.

## Runnable model

| Required | File |
|---|---|
| Editable BPMN | [bpm/model/UFCEP6-0-3_Hospital_Patient_Pathway_v14.bpmn](bpm/model/UFCEP6-0-3_Hospital_Patient_Pathway_v14.bpmn) |
| Deployment configuration | [bpm/tools/deploy.sh](bpm/tools/deploy.sh), [bpm/workers/src/main/resources/application.yaml](bpm/workers/src/main/resources/application.yaml) |
| Readable PDF export | [bpm/diagram/UFCEP6-0-3_Hospital_Patient_Pathway_v14.pdf](bpm/diagram/UFCEP6-0-3_Hospital_Patient_Pathway_v14.pdf) |
| PDF, one pool per page | [bpm/diagram/UFCEP6-0-3_Hospital_Patient_Pathway_v14_sections.pdf](bpm/diagram/UFCEP6-0-3_Hospital_Patient_Pathway_v14_sections.pdf) |
| Vector and raster export | [bpm/diagram/](bpm/diagram/) (`.svg`, `.png`, `sections/`) |

## External workers

| Required | File |
|---|---|
| Source code | [bpm/workers/src/main/java/](bpm/workers/src/main/java/) |
| Dependencies | [bpm/workers/pom.xml](bpm/workers/pom.xml) |
| Configuration template | [bpm/workers/src/main/resources/application.yaml](bpm/workers/src/main/resources/application.yaml) |
| Build and deployment notes | [bpm/workers/README.md](bpm/workers/README.md), [bpm/workers/DEPLOYMENT.md](bpm/workers/DEPLOYMENT.md) |

## Camunda Forms

| Required | File |
|---|---|
| Editable form files | [bpm/model/forms/](bpm/model/forms/) (36 `.form` files) |
| Task bindings | `zeebe:formDefinition` on each user task in the `.bpmn` file |

## Project and test plan

| Required | File |
|---|---|
| Product backlog | [docs/GroupMj Product-Backlog.xlsx](docs/GroupMj%20Product-Backlog.xlsx), [bpm/docs/07-product-backlog.md](bpm/docs/07-product-backlog.md) |
| Sprint backlogs | [docs/GroupMj Sprint-1-Backlog.xlsx](docs/GroupMj%20Sprint-1-Backlog.xlsx), [docs/GroupMj Sprint-2-Backlog.xlsx](docs/GroupMj%20Sprint-2-Backlog.xlsx) |
| Test plan and execution record | [bpm/docs/08-test-plan.md](bpm/docs/08-test-plan.md) |
| Risk, contingency and configuration management | [bpm/docs/09-risk-contingency-and-config-management.md](bpm/docs/09-risk-contingency-and-config-management.md) |
| Sprint reviews, retrospectives, feedback log | [bpm/docs/10-sprint-reviews-and-feedback.md](bpm/docs/10-sprint-reviews-and-feedback.md) |
| Readable PDF copies of the above | [bpm/docs/pdf/](bpm/docs/pdf/) |

## Justification of decisions

| Required | File |
|---|---|
| Process structure, pools, gateways, exceptions, assumptions | [bpm/docs/04-modelling-decisions.md](bpm/docs/04-modelling-decisions.md) |
| External participants and system boundary | [bpm/docs/11-white-box-external-participants.md](bpm/docs/11-white-box-external-participants.md) |

## Demonstration

| Required | File |
|---|---|
| Run evidence, happy path and exception path | [bpm/screenshots/run-happy-path-v14.log](bpm/screenshots/run-happy-path-v14.log), [run-exception-path-v14.log](bpm/screenshots/run-exception-path-v14.log) |
| Run evidence, failure branches | [bpm/screenshots/](bpm/screenshots/) (`run-declined-payment`, `run-confirmation-lost`, `run-overdue-escalation`, `run-escalation-manager`, `run-compensation`) |
| Engine and Tasklist captures | [bpm/screenshots/](bpm/screenshots/) (`operate-*.png`, `tasklist-*.png`, `camunda-*.png`) |
| Demo driver | [bpm/tools/demo_scenario.py](bpm/tools/demo_scenario.py) |
| Bring-up runbook | [bpm/RUNBOOK.md](bpm/RUNBOOK.md) |

## Regenerating the PDFs

```bash
cd bpm
python3 tools/export_pdf.py             # diagram PDFs and document PDFs
python3 tools/export_pdf.py --diagram   # diagram only
python3 tools/export_pdf.py --docs      # documents only
```

Requires Google Chrome for headless rendering. The diagram PDF is vector, so it
can be zoomed without softening.
