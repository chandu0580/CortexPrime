#!/bin/bash
# ==============================================================
# CortexPrime — Deployment Smoke Test
# ==============================================================
# Run this script after deploying to verify the system is
# operational. Can be run against Docker Compose or K8s.
#
# Usage:
#   export DOMAIN="https://yourdomain.com"
#   bash tests/deployment/smoke-test.sh
# ==============================================================
set -euo pipefail

DOMAIN="${DOMAIN:-http://localhost:8000}"
PASS=0
FAIL=0

green() { echo -e "\033[32m✓ $1\033[0m"; }
red()   { echo -e "\033[31m✗ $1\033[0m"; }

check() {
    local desc="$1" expected="$2" actual="$3"
    if [ "$actual" = "$expected" ]; then
        green "$desc"
        PASS=$((PASS + 1))
    else
        red "$desc (expected: $expected, got: $actual)"
        FAIL=$((FAIL + 1))
    fi
}

echo "=========================================="
echo " CortexPrime Deployment Smoke Test"
echo " Target: $DOMAIN"
echo "=========================================="
echo ""

# 1. Health endpoint
STATUS=$(curl -sf -o /dev/null -w "%{http_code}" "${DOMAIN}/health" 2>/dev/null || echo "000")
check "Health endpoint returns 200" "200" "$STATUS"

# 2. System health endpoint
STATUS=$(curl -sf -o /dev/null -w "%{http_code}" "${DOMAIN}/health/system" 2>/dev/null || echo "000")
check "System health endpoint returns 200" "200" "$STATUS"

# 3. Metrics endpoint
STATUS=$(curl -sf -o /dev/null -w "%{http_code}" "${DOMAIN}/metrics" 2>/dev/null || echo "000")
check "Metrics endpoint returns 200" "200" "$STATUS"

# 4. API docs endpoint (should return 404 in production)
STATUS=$(curl -sf -o /dev/null -w "%{http_code}" "${DOMAIN}/docs" 2>/dev/null || echo "000")
# In production, /docs should be disabled (404). In dev, it may be 200.
# Accept either.
if [ "$STATUS" = "404" ] || [ "$STATUS" = "200" ]; then
    green "/docs returns $STATUS (acceptable)"
    PASS=$((PASS + 1))
else
    red "/docs returned unexpected status: $STATUS"
    FAIL=$((FAIL + 1))
fi

# 5. CORS headers
CORS=$(curl -s -D - -o /dev/null \
    -H "Origin: https://app.cortexprime.ai" \
    -H "Access-Control-Request-Method: GET" \
    -X OPTIONS "${DOMAIN}/health" 2>/dev/null \
    | grep -i "access-control-allow-origin" \
    | tr -d '\r' || echo "MISSING")
if echo "$CORS" | grep -qi "access-control-allow-origin"; then
    green "CORS headers present: $CORS"
    PASS=$((PASS + 1))
else
    red "CORS headers missing"
    FAIL=$((FAIL + 1))
fi

# 6. X-Request-ID header
REQ_ID=$(curl -s -D - -o /dev/null "${DOMAIN}/health" 2>/dev/null \
    | grep -i "x-request-id" \
    | tr -d '\r' || echo "MISSING")
if echo "$REQ_ID" | grep -qi "x-request-id"; then
    green "X-Request-ID header present"
    PASS=$((PASS + 1))
else
    red "X-Request-ID header missing"
    FAIL=$((FAIL + 1))
fi

# 7. Security headers
for header in "strict-transport-security" "x-frame-options" "x-content-type-options"; do
    VALUE=$(curl -s -D - -o /dev/null "${DOMAIN}/health" 2>/dev/null \
        | grep -i "$header" \
        | tr -d '\r' || echo "MISSING")
    if [ "$VALUE" != "MISSING" ]; then
        green "Security header present: $header"
        PASS=$((PASS + 1))
    else
        red "Security header missing: $header"
        FAIL=$((FAIL + 1))
    fi
done

# 8. Metrics contain cortex_ prefix
if METRICS=$(curl -sf "${DOMAIN}/metrics" 2>/dev/null); then
    if echo "$METRICS" | grep -q "^cortex_"; then
        green "Metrics contain cortex_ prefix"
        PASS=$((PASS + 1))
    else
        red "Metrics missing cortex_ prefix"
        FAIL=$((FAIL + 1))
    fi
else
    red "Could not fetch metrics"
    FAIL=$((FAIL + 1))
fi

# 9. 404 returns JSON envelope
NOT_FOUND=$(curl -sf "${DOMAIN}/api/nonexistent" 2>/dev/null || true)
if echo "$NOT_FOUND" | grep -q "error"; then
    green "404 returns JSON error envelope"
    PASS=$((PASS + 1))
else
    red "404 does not return JSON error envelope"
    FAIL=$((FAIL + 1))
fi

echo ""
echo "=========================================="
echo " Results: $PASS passed, $FAIL failed"
echo "=========================================="

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
exit 0
