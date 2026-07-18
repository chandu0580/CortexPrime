import type {
  ScenarioResult, ValidationCheckpoint, CoverageItem, PerfMetric,
  FailureItem, MissionSuccessItem, ReportSummary, ProductionReadinessReport,
  ScenarioId, ValidationDimension, ValidationStatus,
} from "./types"

const DIMENSION_WEIGHTS: Record<ValidationDimension, number> = {
  mission_lifecycle: 0.15,
  ai_decisions: 0.10,
  agent_coordination: 0.12,
  knowledge_retrieval: 0.08,
  learning_updates: 0.05,
  governance: 0.12,
  execution: 0.12,
  connector_execution: 0.08,
  artifacts: 0.05,
  replay: 0.05,
  timeline: 0.04,
  metrics: 0.04,
}

export function calculateScenarioScore(checkpoints: ValidationCheckpoint[]): number {
  if (checkpoints.length === 0) return 0
  const passed = checkpoints.filter((c) => c.status === "pass").length
  const total = checkpoints.filter((c) => c.status !== "skip").length
  return total === 0 ? 0 : Math.round((passed / total) * 100)
}

export function calculateOverallScore(scenarios: ScenarioResult[]): number {
  if (scenarios.length === 0) return 0
  const total = scenarios.reduce((sum, s) => sum + s.score, 0)
  return Math.round(total / scenarios.length)
}

export function generateReportSummary(scenarios: ScenarioResult[]): ReportSummary {
  const allCheckpoints = scenarios.flatMap((s) => s.checkpoints)
  return {
    totalScenarios: scenarios.length,
    passed: scenarios.filter((s) => s.overallStatus === "pass").length,
    failed: scenarios.filter((s) => s.overallStatus === "fail").length,
    totalCheckpoints: allCheckpoints.length,
    passedCheckpoints: allCheckpoints.filter((c) => c.status === "pass").length,
    failedCheckpoints: allCheckpoints.filter((c) => c.status === "fail").length,
    skippedCheckpoints: allCheckpoints.filter((c) => c.status === "skip").length,
    overallScore: calculateOverallScore(scenarios),
    totalDurationMs: scenarios.reduce((sum, s) => sum + s.totalDurationMs, 0),
  }
}

export function generateCoverage(scenarios: ScenarioResult[]): CoverageItem[] {
  const dimensions: ValidationDimension[] = [
    "mission_lifecycle", "ai_decisions", "agent_coordination",
    "knowledge_retrieval", "learning_updates", "governance",
    "execution", "connector_execution", "artifacts",
    "replay", "timeline", "metrics",
  ]
  return dimensions.map((dim) => {
    const forDim = scenarios.flatMap((s) =>
      s.checkpoints.filter((c) => c.dimension === dim)
    )
    const tested = forDim.length
    const passed = forDim.filter((c) => c.status === "pass").length
    const failed = forDim.filter((c) => c.status === "fail").length
    return {
      dimension: dim,
      tested,
      passed,
      failed,
      coveragePercent: tested === 0 ? 0 : Math.round((passed / tested) * 100),
    }
  })
}

export function generatePerformance(scenarios: ScenarioResult[]): PerfMetric[] {
  return scenarios.map((s) => ({
    scenarioId: s.id,
    checkpointsTotal: s.checkpoints.length,
    checkpointsPassed: s.passCount,
    durationMs: s.totalDurationMs,
    score: s.score,
  }))
}

export function generateFailures(scenarios: ScenarioResult[]): FailureItem[] {
  const failures: FailureItem[] = []
  for (const scenario of scenarios) {
    for (const cp of scenario.checkpoints) {
      if (cp.status === "fail") {
        failures.push({
          scenarioId: scenario.id,
          scenarioTitle: scenario.title,
          checkpointId: cp.id,
          dimension: cp.dimension,
          description: cp.description,
          detail: cp.detail,
          severity: cp.required ? "high" : "medium",
        })
      }
    }
  }
  return failures
}

export function generateMissionSuccess(scenarios: ScenarioResult[]): MissionSuccessItem[] {
  return scenarios.map((s) => ({
    scenarioId: s.id,
    title: s.title,
    goal: s.goal,
    score: s.score,
    status: s.overallStatus,
    servicesUsed: s.services.length,
    servicesPassed: s.services.filter((svc) => svc.status === "pass").length,
  }))
}

export function generateKnownGaps(scenarios: ScenarioResult[]): string[] {
  const gaps: string[] = []
  const allCheckpoints = scenarios.flatMap((s) => s.checkpoints)
  const skippedDims = allCheckpoints.filter((c) => c.status === "skip")
  const failedReq = allCheckpoints.filter((c) => c.status === "fail" && c.required)

  if (skippedDims.length > 0) {
    const dims = [...new Set(skippedDims.map((c) => c.dimension))]
    gaps.push(`Skipped validation dimensions: ${dims.join(", ")}`)
  }
  if (failedReq.length > 0) {
    gaps.push(`${failedReq.length} required checkpoints failed across scenarios`)
  }
  if (scenarios.some((s) => s.score < 50)) {
    gaps.push(`${scenarios.filter((s) => s.score < 50).length} scenarios scored below 50%`)
  }
  const lowCoverage = generateCoverage(scenarios).filter((c) => c.coveragePercent < 50)
  if (lowCoverage.length > 0) {
    gaps.push(`Low coverage dimensions: ${lowCoverage.map((c) => c.dimension).join(", ")}`)
  }
  return gaps
}

export function generateRiskAssessment(scenarios: ScenarioResult[]): { category: string; level: "low" | "medium" | "high"; description: string }[] {
  const risks: { category: string; level: "low" | "medium" | "high"; description: string }[] = []

  const summary = generateReportSummary(scenarios)
  if (summary.overallScore < 50) {
    risks.push({ category: "Overall Readiness", level: "high", description: `Overall score ${summary.overallScore}% indicates critical gaps` })
  } else if (summary.overallScore < 70) {
    risks.push({ category: "Overall Readiness", level: "medium", description: `Overall score ${summary.overallScore}% needs improvement` })
  } else {
    risks.push({ category: "Overall Readiness", level: "low", description: `Overall score ${summary.overallScore}% meets threshold` })
  }

  const failed = generateFailures(scenarios)
  const highFailures = failed.filter((f) => f.severity === "high")
  if (highFailures.length > 3) {
    risks.push({ category: "Failure Density", level: "high", description: `${highFailures.length} high-severity failures detected` })
  } else if (highFailures.length > 0) {
    risks.push({ category: "Failure Density", level: "medium", description: `${highFailures.length} high-severity failures detected` })
  } else {
    risks.push({ category: "Failure Density", level: "low", description: "No high-severity failures" })
  }

  const coverage = generateCoverage(scenarios)
  const lowCoverage = coverage.filter((c) => c.coveragePercent < 50)
  if (lowCoverage.length > 2) {
    risks.push({ category: "Coverage Gaps", level: "high", description: `${lowCoverage.length} dimensions have below 50% coverage` })
  } else if (lowCoverage.length > 0) {
    risks.push({ category: "Coverage Gaps", level: "medium", description: `${lowCoverage.length} dimensions have below 50% coverage` })
  } else {
    risks.push({ category: "Coverage Gaps", level: "low", description: "All dimensions have adequate coverage" })
  }

  return risks
}

export function generateRecommendations(scenarios: ScenarioResult[]): string[] {
  const recs: string[] = []
  const failures = generateFailures(scenarios)
  const coverage = generateCoverage(scenarios)

  if (failures.length > 0) {
    recs.push(`Address ${failures.length} identified failures: prioritize high-severity items in ${[...new Set(failures.map((f) => f.scenarioId))].join(", ")}`)
  }
  const lowCoverage = coverage.filter((c) => c.coveragePercent < 70)
  for (const dim of lowCoverage) {
    recs.push(`Improve test coverage for ${dim.dimension}: currently ${dim.coveragePercent}% (${dim.passed}/${dim.tested} passed)`)
  }
  if (scenarios.some((s) => s.score < 80)) {
    recs.push("Strengthen mission lifecycle validation: ensure all stages are tested end-to-end")
  }
  return recs
}

export function determineReadinessLevel(score: number): ProductionReadinessReport["readinessLevel"] {
  if (score >= 90) return "production_ready"
  if (score >= 75) return "high"
  if (score >= 60) return "medium"
  if (score >= 40) return "low"
  return "critical"
}

export function buildProductionReadinessReport(scenarios: ScenarioResult[]): ProductionReadinessReport {
  const score = calculateOverallScore(scenarios)
  return {
    generatedAt: new Date().toISOString(),
    overallScore: score,
    readinessLevel: determineReadinessLevel(score),
    summary: generateReportSummary(scenarios),
    coverage: generateCoverage(scenarios),
    performance: generatePerformance(scenarios),
    failures: generateFailures(scenarios),
    missionSuccess: generateMissionSuccess(scenarios),
    knownGaps: generateKnownGaps(scenarios),
    riskAssessment: generateRiskAssessment(scenarios),
    recommendations: generateRecommendations(scenarios),
  }
}
