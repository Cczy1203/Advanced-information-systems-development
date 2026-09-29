# Advanced Information Systems Development

## Project overview
This repository is the initial scaffold for the Hospital Patient Administration System case study used in UFCEP6-0-3. It is set up for an agile development process, with an implementation model built on BPMN, external workers and Camunda forms.

The system covers the patient journey from referral and booking through treatment planning, funding checks, communication, follow-up scheduling and audit reporting, while keeping the clinical, administrative and financial responsibilities apart.

## Project status
- Stage: Sprint 0 / project foundation
- Current milestone: repository, backlog, process baseline and worker/service skeleton prepared
- Goal: establish the shared structure needed before the first executable BPMN and form implementation work starts

## Repository structure
- `bpm/` – BPMN process starter files and process notes
- `docs/` – project plan, backlog, standups, testing plan and retrospective templates
- `src/` – application bootstrap, service logic and worker skeleton code
- `package.json` – Node.js project bootstrap and script entry points

## Agile evidence log
### 2026-09-15 – Kickoff and baseline creation
- Reviewed the assessment specification and hospital case study.
- Confirmed the project direction: BPMN, external workers, forms and process/test evidence.
- Created the repository scaffold and initial documentation.
- Identified the first backlog items and defined the project structure for the coming sprint.

### 2026-09-15 – Framework established
- Added a Node.js starter application that runs in demo mode when Camunda is not configured.
- Created a referral validation service and a worker template for external-task processing.
- Drafted a starter BPMN file for the patient administration workflow.
- Added project management documentation to cover standups, reviews and retrospective records.

## Local setup
```bash
npm install
npm run start
```

With no Camunda connection configured the app starts in demo mode. That is deliberate: workflow design and team documentation come first, and the live service is connected later.

## Current tasks to complete next
1. Confirm team roles and second owners.
2. Agree sprint goals and backlog priority ordering.
3. Expand the BPMN model to include the main referral, consultation and booking branches.
4. Implement the first external worker workflows for referral validation and scheduling logic.
5. Prepare initial Camunda forms and task bindings.
6. Keep the backlog, standup log and review evidence in the `docs/` folder up to date.

## Notes for the team
- This is a project foundation, not the final implementation.
- Process evidence counts for as much as the code in this assessment.
- Backlog updates, standup notes and sprint reviews should be maintained throughout the project.
- The repository must stay discoverable, versioned and suitable for tutor review.
