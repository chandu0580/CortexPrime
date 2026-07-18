// ==============================================================
// CortexPrime — k6 Smoke Test
// ==============================================================
// Quick smoke test to verify API endpoints under minimal load.
// Run: k6 run tests/load/k6-smoke.js
// ==============================================================

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';

const errorRate = new Rate('errors');

export const options = {
  vus: 2,
  duration: '30s',
  thresholds: {
    errors: ['rate<0.1'],
    http_req_duration: ['p(95)<2000'],
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';

export default function () {
  // Health check
  const healthResp = http.get(`${BASE_URL}/health`);
  const healthOk = check(healthResp, {
    'health endpoint returns 200': (r) => r.status === 200,
    'health response is healthy': (r) => r.json('status') === 'healthy',
  });
  if (!healthOk) errorRate.add(1);
  sleep(1);

  // System health
  const sysHealthResp = http.get(`${BASE_URL}/health/system`);
  const sysHealthOk = check(sysHealthResp, {
    'system health returns 200': (r) => r.status === 200,
  });
  if (!sysHealthOk) errorRate.add(1);
  sleep(1);

  // Metrics
  const metricsResp = http.get(`${BASE_URL}/metrics`);
  const metricsOk = check(metricsResp, {
    'metrics returns 200': (r) => r.status === 200,
    'metrics contain cortex_ prefix': (r) => r.body.includes('cortex_'),
  });
  if (!metricsOk) errorRate.add(1);
  sleep(1);

  // 404 handling
  const notFoundResp = http.get(`${BASE_URL}/api/nonexistent`);
  const notFoundOk = check(notFoundResp, {
    '404 returns error envelope': (r) => r.status === 404 && r.body.includes('error'),
  });
  if (!notFoundOk) errorRate.add(1);
  sleep(1);
}
