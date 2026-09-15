# Test plan

## Testing objectives
This project will test the process logic, service worker behaviour and data handling as the system evolves from its initial scaffold to the integrated workflow.

## Test categories
### Unit-level tests
- Referral validation logic
- Treatment plan creation
- Enquiry classification
- Process variable defaults and validation

### Integration-level tests
- Workflow variables flowing from BPMN to service task results
- Worker responses to valid and invalid inputs
- Exception handling for external service outages or communication issues

### End-to-end tests
- Referral accepted and booking generated
- Referral rejected or redirected
- Payment required and payment declined
- Emergency treatment pathway with documented rationale

## Planned scenarios
1. Valid referral with all required information
2. Referral missing supporting documentation
3. Consultant rejects a referral
4. Appointment schedule unavailable
5. External booking service returns a failure response
6. Payment request succeeds
7. Payment is declined and a new attempt is required
8. Payment is taken but confirmation is not returned
9. Urgent treatment proceeds with recorded justification
10. Delayed clinic letter triggers escalation reminders

## Evidence collection
- Test scripts stored with project artefacts
- Results recorded in a shared log or issue tracker
- Failures classified as functional, integration, or external-service related
- Retrospective improvements captured if a scenario exposes a design gap

## Current status
Initial testing framework has been defined. The team should expand the test matrix as BPMN, workers and forms become active in the sprint increments.
