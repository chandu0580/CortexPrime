# ==============================================================
# CortexPrime — Deployment Smoke Test (PowerShell)
# ==============================================================
param(
    [string]$Domain = "http://localhost:8000"
)

$pass = 0
$fail = 0

function Check {
    param($Desc, $Expected, $Actual)
    if ($Actual -eq $Expected) {
        Write-Host "✓ $Desc" -ForegroundColor Green
        $script:pass++
    } else {
        Write-Host "✗ $Desc (expected: $Expected, got: $Actual)" -ForegroundColor Red
        $script:fail++
    }
}

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host " CortexPrime Deployment Smoke Test" -ForegroundColor Cyan
Write-Host " Target: $Domain" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# 1. Health
try {
    $status = (Invoke-WebRequest -Uri "$Domain/health" -Method GET -UseBasicParsing -TimeoutSec 10).StatusCode
} catch { $status = 000 }
Check "Health endpoint returns 200" 200 $status

# 2. System health
try {
    $status = (Invoke-WebRequest -Uri "$Domain/health/system" -Method GET -UseBasicParsing -TimeoutSec 10).StatusCode
} catch { $status = 000 }
Check "System health endpoint returns 200" 200 $status

# 3. Metrics
try {
    $status = (Invoke-WebRequest -Uri "$Domain/metrics" -Method GET -UseBasicParsing -TimeoutSec 10).StatusCode
} catch { $status = 000 }
Check "Metrics endpoint returns 200" 200 $status

# 4. Security headers
try {
    $response = Invoke-WebRequest -Uri "$Domain/health" -Method GET -UseBasicParsing -TimeoutSec 10
    $headers = $response.Headers
    if ($headers.ContainsKey("Strict-Transport-Security")) {
        Write-Host "✓ Strict-Transport-Security present" -ForegroundColor Green; $pass++
    } else {
        Write-Host "✗ Strict-Transport-Security missing" -ForegroundColor Red; $fail++
    }
    if ($headers.ContainsKey("X-Request-ID")) {
        Write-Host "✓ X-Request-ID present" -ForegroundColor Green; $pass++
    } else {
        Write-Host "✗ X-Request-ID missing" -ForegroundColor Red; $fail++
    }
} catch {
    Write-Host "✗ Could not fetch headers" -ForegroundColor Red; $fail += 2
}

# 5. CORS preflight
try {
    $corsStatus = (Invoke-WebRequest -Uri "$Domain/health" -Method OPTIONS -UseBasicParsing -TimeoutSec 10 `
        -Headers @{ Origin = "https://app.cortexprime.ai"; "Access-Control-Request-Method" = "GET" }).StatusCode
    Check "CORS preflight returns 200" 200 $corsStatus
} catch { Write-Host "✗ CORS preflight failed" -ForegroundColor Red; $fail++ }

# 6. Metrics content
try {
    $metrics = Invoke-WebRequest -Uri "$Domain/metrics" -UseBasicParsing -TimeoutSec 10
    if ($metrics.Content -match "^cortex_") {
        Write-Host "✓ Metrics contain cortex_ prefix" -ForegroundColor Green; $pass++
    } else {
        Write-Host "✗ Metrics missing cortex_ prefix" -ForegroundColor Red; $fail++
    }
} catch { Write-Host "✗ Could not fetch metrics" -ForegroundColor Red; $fail++ }

# 7. 404 envelope
try {
    $notFound = Invoke-WebRequest -Uri "$Domain/api/nonexistent" -UseBasicParsing -TimeoutSec 10
    if ($notFound.Content -match "error") {
        Write-Host "✓ 404 returns JSON error envelope" -ForegroundColor Green; $pass++
    } else {
        Write-Host "✗ 404 does not return JSON error envelope" -ForegroundColor Red; $fail++
    }
} catch {
    if ($_.Exception.Response.StatusCode -eq 404) {
        Write-Host "✓ 404 returns JSON error envelope" -ForegroundColor Green; $pass++
    } else {
        Write-Host "✗ 404 check failed" -ForegroundColor Red; $fail++
    }
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host " Results: $pass passed, $fail failed" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

if ($fail -gt 0) { exit 1 } else { exit 0 }
