// ==============================================================
// CortexPrime — k6 Stress Test
// ==============================================================
// Ramps up to high load to identify breaking points.
// Run: k6 run tests/load/k6-stress.js
// ==============================================================

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

const errorRate = new Rate('errors');
const healthLatency = new Trend('health_latency');

export const options = {
  stages: [
    { duration: '2m', target: 50 },   // Ramp up to 50 users
    { duration: '5m', target: 50 },   // Stay at 50 users
    { duration: '2m', target: 100 },  // Ramp up to 100 users
    { duration: '5m', target: 100 },  // Stay at 100 users
    { duration: '2m', target: 200 },  // Ramp up to 200 users
    { duration: '5m', target: 200 },  // Stay at 200 users
    { duration: '2m', target: 0 },    // Ramp down
  ],
  thresholds: {
    errors: ['rate<0.05'],             // < 5% error rate
    health_latency: ['p(95)<5000'],    // p95 latency < 5s
    http_req_duration: ['p(95)<10000'], // p95 all requests < 10s
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const AUTH_TOKEN = __ENV.AUTH_TOKEN || '';

const params = {
  headers: {
    'Content-Type': 'application/json',
  },
};

if (AUTH_TOKEN) {
  params.headers['Authorization'] = `Bearer ${AUTH_TOKEN}`;
}

export default function () {
  // Health check (readiness)
  const tStart = Date.now();
  const healthResp = http.get(`${BASE_URL}/health`, params);
  healthLatency.add(Date.now() - tStart);

  check(healthResp, {
    'health is OK': (r) => r.status === 200,
  }) || errorRate.add(1);

  sleep(0.5);

  // System health
  const sysResp = http.get(`${BASE_URL}/health/system`, params);
  check(sysResp, {
    'system health is OK': (r) => r.status === 200,
  }) || errorRate.add(1);

  sleep(0.5);

  // Metrics
  const metricsResp = http.get(`${BASE_URL}/metrics`, params);
  check(metricsResp, {
    'metrics are accessible': (r) => r.status === 200,
  }) || errorRate.add(1);

  sleep(1);
}
