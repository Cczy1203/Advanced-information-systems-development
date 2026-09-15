const { logger } = require('../utils/logger');
const { validateReferral } = require('../services/patientService');

class ReferralWorker {
  constructor(taskClient) {
    this.taskClient = taskClient;
  }

  async handleReferralTask(task) {
    const referral = {
      patientId: task.variables.patientId,
      specialty: task.variables.specialty,
      referrerName: task.variables.referrerName,
      sourceOrganisation: task.variables.sourceOrganisation
    };

    const result = validateReferral(referral);

    logger.info('Referral worker evaluated task', {
      taskId: task.id,
      patientId: referral.patientId,
      result
    });

    return {
      referralValid: result.isValid,
      reason: result.reason,
      missingFields: result.missingFields
    };
  }

  async register(taskClient) {
    if (!taskClient) {
      logger.warn('Referral worker registration skipped: no task client configured');
      return;
    }

    logger.info('Referral worker registered for external task processing');
  }
}

module.exports = { ReferralWorker };
