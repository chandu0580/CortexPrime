import { describe, it, expect, beforeAll } from "vitest"
import { getAllScenarioIds, getScenarioDefinition } from "@/lib/validation/scenarios"
import { simulateMission, runScenarioCheckpoints, buildScenarioResult } from "@/lib/validation/mission-simulator"
import {
  calculateScenarioScore, calculateOverallScore, generateReportSummary,
  generateCoverage, generatePerformance, generateFailures,
  generateMissionSuccess, generateKnownGaps, generateRiskAssessment,
  generateRecommendations, determineReadinessLevel,
  buildProductionReadinessReport,
} from "@/lib/validation/score-calculator"
import { formatReportAsText, formatReportAsJSON } from "@/lib/validation/report-generator"
import type { ScenarioResult, ScenarioService, ProductionReadinessReport } from "@/lib/validation/types"

describe("Enterprise Mission Validation Suite", () => {
  let results: ScenarioResult[] = []
  let report: ProductionReadinessReport | null = null

  beforeAll(() => {
    const ids = getAllScenarioIds()
    expect(ids.length).toBe(5)

    results = ids.map((id) => {
      const def = getScenarioDefinition(id)
      if (!def) throw new Error(`Definition not found for ${id}`)

      const sim = simulateMission()
      const services: ScenarioService[] = def.services.map((s) => ({
        ...s,
        durationMs: Math.floor(Math.random() * 800) + 100,
        status: "pass",
      }))
      const checkpoints = runScenarioCheckpoints(id, sim)
      return buildScenarioResult(id, checkpoints, services)
    })

    report = buildProductionReadinessReport(results)
  })

  it("runs all 5 enterprise scenarios", () => {
    expect(results.length).toBe(5)
  })

  it("all scenarios pass overall", () => {
    for (const result of results) {
      expect(result.overallStatus).toBe("pass")
    }
  })

  it("each scenario scores 100%", () => {
    for (const result of results) {
      expect(result.score).toBe(100)
    }
  })

  it("each scenario has checkpoint results", () => {
    for (const result of results) {
      expect(result.checkpoints.length).toBeGreaterThan(0)
      expect(result.passCount + result.failCount + result.skipCount).toBe(result.checkpoints.length)
    }
  })

  it("calculates overall score correctly", () => {
    const overallScore = calculateOverallScore(results)
    expect(overallScore).toBe(100)
  })

  it("generates report summary", () => {
    const summary = generateReportSummary(results)
    expect(summary.totalScenarios).toBe(5)
    expect(summary.passed).toBe(5)
    expect(summary.failed).toBe(0)
    expect(summary.totalCheckpoints).toBeGreaterThan(0)
    expect(summary.passedCheckpoints).toBe(summary.totalCheckpoints - summary.skippedCheckpoints)
    expect(summary.overallScore).toBe(100)
    expect(summary.totalDurationMs).toBeGreaterThan(0)
  })

  it("generates coverage by dimension", () => {
    const coverage = generateCoverage(results)
    expect(coverage.length).toBe(12) // All 12 dimensions

    for (const cov of coverage) {
      expect(cov.tested).toBeGreaterThanOrEqual(0)
      expect(cov.passed).toBeGreaterThanOrEqual(0)
      expect(cov.coveragePercent).toBeGreaterThanOrEqual(0)
    }

    const withTests = coverage.filter((c) => c.tested > 0)
    const allPassed = withTests.every((c) => c.coveragePercent === 100)
    expect(allPassed).toBe(true)
  })

  it("generates performance metrics", () => {
    const perf = generatePerformance(results)
    expect(perf.length).toBe(5)

    for (const p of perf) {
      expect(p.scenarioId).toBeTruthy()
      expect(p.checkpointsTotal).toBeGreaterThan(0)
      expect(p.score).toBe(100)
    }
  })

  it("generates failure report with no failures", () => {
    const failures = generateFailures(results)
    // All scenarios pass, so there should be no failures
    expect(failures.length).toBe(0)
  })

  it("generates mission success report", () => {
    const success = generateMissionSuccess(results)
    expect(success.length).toBe(5)

    for (const ms of success) {
      expect(ms.score).toBe(100)
      expect(ms.status).toBe("pass")
      expect(ms.servicesUsed).toBeGreaterThan(0)
    }
  })

  it("identifies known gaps", () => {
    const gaps = generateKnownGaps(results)
    // With all passing, known gaps should only cover structural items
    expect(gaps.length).toBeGreaterThanOrEqual(0)
  })

  it("performs risk assessment", () => {
    const risks = generateRiskAssessment(results)
    expect(risks.length).toBeGreaterThan(0)

    const highRisks = risks.filter((r) => r.level === "high")
    // All scenarios pass, so there should be no high risks
    expect(highRisks.length).toBe(0)
  })

  it("generates recommendations", () => {
    const recs = generateRecommendations(results)
    expect(recs.length).toBeGreaterThanOrEqual(0)
  })

  it("determines readiness level correctly", () => {
    expect(determineReadinessLevel(95)).toBe("production_ready")
    expect(determineReadinessLevel(80)).toBe("high")
    expect(determineReadinessLevel(65)).toBe("medium")
    expect(determineReadinessLevel(45)).toBe("low")
    expect(determineReadinessLevel(20)).toBe("critical")
  })

  it("builds complete production readiness report", () => {
    expect(report).not.toBeNull()
    if (!report) return

    expect(report.overallScore).toBe(100)
    expect(report.readinessLevel).toBe("production_ready")
    expect(report.summary.totalScenarios).toBe(5)
    expect(report.coverage.length).toBe(12)
    expect(report.performance.length).toBe(5)
    expect(report.missionSuccess.length).toBe(5)
    expect(report.riskAssessment.length).toBeGreaterThan(0)
    expect(report.recommendations.length).toBeGreaterThanOrEqual(0)
  })

  it("formats report as printable text", () => {
    if (!report) return
    const text = formatReportAsText(report)
    expect(text.length).toBeGreaterThan(100)
    expect(text).toContain("CORTEXPRIME")
    expect(text).toContain("MISSION VALIDATION REPORT")
    expect(text).toContain("Readiness Level")
    expect(text).toContain("Overall Score")
    expect(text).toContain("COVERAGE BY DIMENSION")
    expect(text).toContain("PERFORMANCE METRICS")
    expect(text).toContain("MISSION SUCCESS")
    expect(text).toContain("RISK ASSESSMENT")
    expect(text).toContain("RECOMMENDATIONS")
  })

  it("formats report as JSON", () => {
    if (!report) return
    const json = formatReportAsJSON(report)
    expect(json.length).toBeGreaterThan(100)
    const parsed = JSON.parse(json)
    expect(parsed.overallScore).toBe(100)
    expect(parsed.readinessLevel).toBe("production_ready")
  })
})
