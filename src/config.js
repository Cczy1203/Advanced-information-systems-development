require('dotenv').config();

const config = {
  appName: 'Hospital Patient Administration System',
  nodeEnv: process.env.NODE_ENV || 'development',
  port: Number(process.env.PORT || 3000),
  camunda: {
    baseUrl: process.env.CAMUNDA_URL || '',
    username: process.env.CAMUNDA_USERNAME || 'demo',
    password: process.env.CAMUNDA_PASSWORD || 'demo'
  },
  serviceDefaults: {
    referralTimeoutMs: 5000,
    bookingTimeoutMs: 8000,
    paymentTimeoutMs: 9000
  }
};

module.exports = config;
