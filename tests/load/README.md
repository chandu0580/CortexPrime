# CortexPrime — Load Testing

Uses [k6](https://k6.io) for performance and stress testing.

## Prerequisites

```bash
# Install k6
# macOS: brew install k6
# Linux: https://k6.io/docs/getting-started/installation/
# Windows: choco install k6
```

## Smoke Test

Quick verification that endpoints respond correctly:

```bash
k6 run tests/load/k6-smoke.js -e BASE_URL=http://localhost:8000
```

## Stress Test

Ramp up to find breaking points:

```bash
k6 run tests/load/k6-stress.js \
  -e BASE_URL=http://localhost:8000 \
  --out json=results/stress-test.json \
  --out dashboard
```

## Performance Baseline

```bash
k6 run tests/load/k6-stress.js \
  -e BASE_URL=https://staging.cortexprime.ai \
  --out csv=results/baseline-$(date +%Y%m%d).csv
```

## Thresholds

| Metric       | Warning | Critical |
|-------------|---------|----------|
| Error rate   | >1%     | >5%      |
| p95 latency  | >2s     | >5s      |
| p99 latency  | >5s     | >10s     |
