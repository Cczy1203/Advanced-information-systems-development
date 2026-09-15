const config = require('./config');
const { logger } = require('./utils/logger');
const { validateReferral, createTreatmentPlan, classifyEnquiry } = require('./services/patientService');
const { ReferralWorker } = require('./workers/referralWorker');

function bootstrap() {
  logger.info('Initialising Hospital Patient Administration System bootstrap', {
    appName: config.appName,
    nodeEnv: config.nodeEnv,
    camundaConfigured: Boolean(config.camunda.baseUrl)
  });

  const sampleReferral = {
    patientId: 'P-1001',
    specialty: 'Oncology',
    referrerName: 'Dr. Smith',
    sourceOrganisation: 'Northside GP Practice'
  };

  const referralResult = validateReferral(sampleReferral);
  const treatmentPlan = createTreatmentPlan({
    treatmentCode: 'CHEMO-001',
    cycles: 6,
    startDate: '2026-09-30',
    authorised: true
  });
  const enquiryOutcome = classifyEnquiry({ type: 'clinical', priority: 'urgent' });

  const worker = new ReferralWorker();
  worker.register(null);

  logger.info('Bootstrap complete', {
    referralResult,
    treatmentPlan,
    enquiryOutcome,
    mode: config.camunda.baseUrl ? 'camunda-connected' : 'demo-mode'
  });
}

bootstrap();
