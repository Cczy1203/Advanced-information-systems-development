# Submission index — UFCEP6-0-3

**Submitted repository version: tag `sr2-snapshot`** — that tag is the state this
index describes, and it is the state the run logs were produced against. (The
tag is moved to the submitted commit with `git tag -f sr2-snapshot`; the previous
release that was reviewed is tag `v14.0-final`.)

**Version submitted: v16.0** — the operational model rebuilt as **one hospital pool**,
carrying the v15.0 feedback response forward unchanged. The rebuild and its measured
evidence are in
[bpm/docs/17-single-pool-operational-model.md](bpm/docs/17-single-pool-operational-model.md).

This file lists everything the assessment asks for and where it sits in the
repository.

---

## Feedback response (the v15.0 change set)

The three items written against this group in the external `Group Feedback` sheet,
and where the answer to each one lives.

| # | Feedback item | Answer | Evidence |
|---|---|---|---|
| 1 | Implement role-based access control in Camunda | [bpm/camunda/application.yaml](bpm/camunda/application.yaml): 11 users, 10 roles matching the BPMN's candidate groups, 20 least-privilege authorisation blocks | [bpm/tools/verify.ps1](bpm/tools/verify.ps1), [bpm/tools/verify.ps1](bpm/tools/verify.ps1), [bpm/screenshots/v15/](bpm/screenshots/v15/) |
| 2 | Improve form validation, particularly date selections | [bpm/model/forms/](bpm/model/forms/) (37 hardened forms), [bpm/tools/harden_forms.py](bpm/tools/harden_forms.py), [bpm/workers/src/main/resources/date-rules.json](bpm/workers/src/main/resources/date-rules.json), [DateRuleValidator.java](bpm/workers/src/main/java/uk/ac/uwe/ufcep603/hospital/support/DateRuleValidator.java) | [bpm/tools/forms-inventory-v14.json](bpm/tools/forms-inventory-v14.json) vs [forms-inventory-v15.json](bpm/tools/forms-inventory-v15.json) |
| 3 | Implement database integration to support data persistence | [db/schema.sql](bpm/workers/src/main/resources/db/schema.sql) (15 tables), [db/seed.sql](bpm/workers/src/main/resources/db/seed.sql), [db/](bpm/workers/src/main/java/uk/ac/uwe/ufcep603/hospital/db/), rewritten [HospitalStore.java](bpm/workers/src/main/java/uk/ac/uwe/ufcep603/hospital/support/HospitalStore.java) | [bpm/tools/verify.ps1](bpm/tools/verify.ps1), [bpm/screenshots/v15/h2-persistence.txt](bpm/screenshots/v15/h2-persistence.txt) |

| Required | File |
|---|---|
| Feedback response — decision, action, evidence, result, limitations | [bpm/docs/14-feedback-response.md](bpm/docs/14-feedback-response.md) |
| Project plan assessment: original vs revised plan vs actual progress | [bpm/docs/15-project-plan-assessment.md](bpm/docs/15-project-plan-assessment.md) |
| Bilingual review document (Chinese and English) | [docs/GroupMj-v15-Feedback-Response-and-Plan-Assessment-CN.docx](docs/GroupMj-v15-Feedback-Response-and-Plan-Assessment-CN.docx), [EN](docs/GroupMj-v15-Feedback-Response-and-Plan-Assessment-EN.docx) |
| Feedback action log, rows FB-15 to FB-17 | [bpm/docs/10-sprint-reviews-and-feedback.md](bpm/docs/10-sprint-reviews-and-feedback.md) §5.1 |
| Acceptance criteria assessment: initial vs revised, measured, with failures | [bpm/docs/16-acceptance-criteria.md](bpm/docs/16-acceptance-criteria.md) |
| Why the BPMN merging-gateway candidate is not the shipped model (A/B evidence) | [bpm/screenshots/v15/merging-gateway-deployment-ab.txt](bpm/screenshots/v15/merging-gateway-deployment-ab.txt), [bpm/tools/add_merging_gateways.py](bpm/tools/add_merging_gateways.py) |
| Updated run instructions | [README.md](README.md): build, the two configuration profiles, the four verification scripts, known limitations |
| Known limitation L-1 (RBAC vs the gRPC job worker) | [bpm/docs/14-feedback-response.md](bpm/docs/14-feedback-response.md) §6 |

**Verification commands.** Every claim above is reproducible:

```bash
cd bpm/workers && mvn -gs maven-settings.xml -s maven-settings.xml -o package   # 52 tests
pwsh -File bpm/tools/verify.ps1 -Check engine                                          # deploy + RBAC persisted
pwsh -File bpm/tools/verify.ps1 -Check rbac -ProtectedApi                              # enforcement, by refusal
pwsh -File bpm/tools/verify.ps1 -Check persistence                                  # survives a cold restart
pwsh -File bpm/tools/verify.ps1 -Check e2e                                      # 37/37 forms, real workers
```

---

## Runnable model

| Required | File |
|---|---|
| Editable BPMN | [bpm/model/UFCEP6-0-3_Hospital_Patient_Pathway_v16.bpmn](bpm/model/UFCEP6-0-3_Hospital_Patient_Pathway_v16.bpmn): one hospital pool, 3 responsibility lanes, 9 team lanes, 6 black-box outside participants |
| Deployment configuration | [bpm/tools/deploy.sh](bpm/tools/deploy.sh), [bpm/workers/src/main/resources/application.yaml](bpm/workers/src/main/resources/application.yaml) |
| Readable PDF export | [bpm/diagram/hospital-patient-pathway-v16.pdf](bpm/diagram/hospital-patient-pathway-v16.pdf): full drawing on one page, vector |
| PDF, one stage of the pathway per page | [bpm/diagram/hospital-patient-pathway-v16-sections.pdf](bpm/diagram/hospital-patient-pathway-v16-sections.pdf): seven captioned stages, readable at 100% |
| Vector and raster export | [bpm/diagram/](bpm/diagram/) (`.svg`, `.png`, `-overview.png`) |
| Why the model is one pool, and the measured evidence | [bpm/docs/17-single-pool-operational-model.md](bpm/docs/17-single-pool-operational-model.md) |
| Files the documents cite that are no longer in the tree | [bpm/docs/18-cited-files-no-longer-present.md](bpm/docs/18-cited-files-no-longer-present.md) |
| Stand-up records, both sprints | [bpm/docs/19-standups.md](bpm/docs/19-standups.md) |
| Date rules: what the form can block, what the worker blocks, and the repair loop | [bpm/docs/21-date-rules-and-the-form-layer.md](bpm/docs/21-date-rules-and-the-form-layer.md) |
| Accessibility audit and rationale for the 37 forms | [bpm/docs/20-accessibility-and-the-forms.md](bpm/docs/20-accessibility-and-the-forms.md), [report](bpm/screenshots/v16/accessibility-report.json) |

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
| Editable form files | [bpm/model/forms/](bpm/model/forms/) (37 `.form` files) |
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
| Run evidence for the shipped model, eight scenarios, all completed, **from the forms alone** (`--form-fields-only`: nothing seeded) | [happy path](bpm/screenshots/run-v16-happy-path.log), [declined treatment](bpm/screenshots/run-v16-declined-treatment.log), [incomplete pack](bpm/screenshots/run-v16-incomplete-pack.log), [no capacity](bpm/screenshots/run-v16-no-capacity.log), [refund](bpm/screenshots/run-v16-refund.log), [no refund](bpm/screenshots/run-v16-no-refund.log), [compensation](bpm/screenshots/run-v16-compensation.log), [enquiry](bpm/screenshots/run-v16-enquiry.log) |
| Engine-side record: deployment, instance states, defects found by running | [bpm/screenshots/v16/engine-record.txt](bpm/screenshots/v16/engine-record.txt) |
| Run driver for the shipped model | [bpm/tools/run_v16.py](bpm/tools/run_v16.py) |
| Build checks that refuse a broken form-to-model contract | [bpm/tools/spec_v3.py](bpm/tools/spec_v3.py): condition type, unset variable, upstream source, option value |
| Accessibility audit | [bpm/tools/audit_accessibility.py](bpm/tools/audit_accessibility.py) |
| v14.0 run evidence (the release that was reviewed) | [bpm/screenshots/run-happy-path-v14.log](bpm/screenshots/run-happy-path-v14.log), [run-exception-path-v14.log](bpm/screenshots/run-exception-path-v14.log) |
| Run evidence, failure branches | [bpm/screenshots/](bpm/screenshots/) (`run-declined-payment`, `run-confirmation-lost`, `run-overdue-escalation`, `run-escalation-manager`, `run-compensation`) |
| Engine and Tasklist captures | [bpm/screenshots/](bpm/screenshots/) (`operate-*.png`, `tasklist-*.png`, `camunda-*.png`) |
| Bring-up runbook | [bpm/RUNBOOK.md](bpm/RUNBOOK.md) |

## Regenerating the PDFs

```bash
cd bpm
python3 tools/export_pdf.py             # everything
python3 tools/export_pdf.py --diagram   # the diagram PDFs (delegates to the two scripts below)
python3 tools/export_pdf.py --docs      # documents only

# or the diagram scripts directly
python3 tools/build_v3.py
python3 tools/render_v16.py model/UFCEP6-0-3_Hospital_Patient_Pathway_v16.bpmn \
        diagram/hospital-patient-pathway-v16
python3 tools/render_sections_v16.py diagram/hospital-patient-pathway-v16.png \
        diagram/hospital-patient-pathway-v16-sections.pdf
```

Needs Google Chrome for headless rendering. The diagram PDF is vector, so it can
be zoomed without softening.
