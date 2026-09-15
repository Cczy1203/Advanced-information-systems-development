const { logger } = require('../utils/logger');

function validateReferral(referral) {
  const requiredFields = ['patientId', 'specialty', 'referrerName', 'sourceOrganisation'];
  const missingFields = requiredFields.filter((field) => !referral[field]);

  if (missingFields.length > 0) {
    return {
      isValid: false,
      reason: 'Missing required referral data',
      missingFields
    };
  }

  logger.info('Referral data validated', { patientId: referral.patientId, specialty: referral.specialty });

  return {
    isValid: true,
    reason: 'Referral meets intake requirements',
    missingFields: []
  };
}

function createTreatmentPlan(request) {
  const defaultPlan = {
    treatmentCode: request.treatmentCode || 'TREAT-UNKNOWN',
    cycles: request.cycles || 1,
    startDate: request.startDate || new Date().toISOString().slice(0, 10),
    needsFundingCheck: true,
    authorised: Boolean(request.authorised)
  };

  logger.info('Treatment plan created', { treatmentCode: defaultPlan.treatmentCode });

  return defaultPlan;
}

function classifyEnquiry(enquiry) {
  const type = enquiry.type || 'administrative';
  const classification = {
    administrative: 'ADMIN',
    financial: 'FINANCE',
    clinical: 'CLINICAL'
  };

  return {
    type,
    team: classification[type] || 'ADMIN',
    priority: enquiry.priority || 'normal'
  };
}

module.exports = {
  validateReferral,
  createTreatmentPlan,
  classifyEnquiry
};
