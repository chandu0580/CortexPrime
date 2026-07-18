import type { ProductionReadinessReport, ScenarioResult, CoverageItem, FailureItem, PerfMetric, MissionSuccessItem } from "./types"

export function formatReportAsText(report: ProductionReadinessReport): string {
  const lines: string[] = []
  lines.push("=".repeat(78))
  lines.push("  CORTEXPRIME — ENTERPRISE MISSION VALIDATION REPORT")
  lines.push("=".repeat(78))
  lines.push(`  Generated: ${report.generatedAt}`)
  lines.push(`  Readiness Level: ${report.readinessLevel.toUpperCase()}`)
  lines.push(`  Overall Score: ${report.overallScore}%`)
  lines.push("")

  lines.push("─".repeat(78))
  lines.push("  SUMMARY")
  lines.push("─".repeat(78))
  lines.push(`  Scenarios:  ${report.summary.totalScenarios} total, ${report.summary.passed} passed, ${report.summary.failed} failed`)
  lines.push(`  Checkpoints: ${report.summary.totalCheckpoints} total, ${report.summary.passedCheckpoints} passed, ${report.summary.failedCheckpoints} failed, ${report.summary.skippedCheckpoints} skipped`)
  lines.push(`  Duration:    ${(report.summary.totalDurationMs / 1000).toFixed(1)}s`)
  lines.push("")

  lines.push("─".concat("=".repeat(77)))
  lines.push("  COVERAGE BY DIMENSION")
  lines.push("─".concat("=".repeat(77)))
  lines.push(`  ${pad("Dimension", 24)} ${pad("Tested", 8)} ${pad("Passed", 8)} ${pad("Failed", 8)} ${pad("Coverage", 10)}`)
  lines.push("  ".concat("─".repeat(58)))
  for (const cov of report.coverage) {
    const bar = renderBar(cov.coveragePercent, 10)
    lines.push(`  ${pad(cov.dimension, 24)} ${pad(cov.tested.toString(), 8)} ${pad(cov.passed.toString(), 8)} ${pad(cov.failed.toString(), 8)} ${pad(`${cov.coveragePercent}%`, 6)} ${bar}`)
  }
  lines.push("")

  lines.push("─".repeat(78))
  lines.push("  PERFORMANCE METRICS")
  lines.push("─".repeat(78))
  lines.push(`  ${pad("Scenario", 24)} ${pad("Checkpoints", 12)} ${pad("Passed", 8)} ${pad("Duration", 10)} ${pad("Score", 8)}`)
  lines.push("  ".concat("─".repeat(58)))
  for (const perf of report.performance) {
    lines.push(`  ${pad(perf.scenarioId, 24)} ${pad(perf.checkpointsTotal.toString(), 12)} ${pad(perf.checkpointsPassed.toString(), 8)} ${pad(`${(perf.durationMs / 1000).toFixed(1)}s`, 10)} ${pad(`${perf.score}%`, 8)}`)
  }
  lines.push("")

  if (report.failures.length > 0) {
    lines.push("─".repeat(78))
    lines.push("  FAILURES")
    lines.push("─".repeat(78))
    for (const f of report.failures) {
      lines.push(`  [${f.severity.toUpperCase()}] ${f.scenarioTitle} / ${f.description}`)
      lines.push(`         ${f.detail}`)
    }
    lines.push("")
  }

  lines.push("─".repeat(78))
  lines.push("  MISSION SUCCESS")
  lines.push("─".repeat(78))
  lines.push(`  ${pad("Scenario", 24)} ${pad("Score", 8)} ${pad("Status", 12)} ${pad("Services", 10)}`)
  lines.push("  ".concat("─".repeat(50)))
  for (const ms of report.missionSuccess) {
    lines.push(`  ${pad(ms.title, 24)} ${pad(`${ms.score}%`, 8)} ${pad(ms.status, 12)} ${pad(`${ms.servicesPassed}/${ms.servicesUsed}`, 10)}`)
  }
  lines.push("")

  if (report.knownGaps.length > 0) {
    lines.push("─".repeat(78))
    lines.push("  KNOWN GAPS")
    lines.push("─".repeat(78))
    for (const gap of report.knownGaps) {
      lines.push(`  • ${gap}`)
    }
    lines.push("")
  }

  lines.push("─".repeat(78))
  lines.push("  RISK ASSESSMENT")
  lines.push("─".repeat(78))
  for (const risk of report.riskAssessment) {
    const icon = risk.level === "high" ? "●" : risk.level === "medium" ? "◉" : "○"
    lines.push(`  ${icon} [${risk.level.toUpperCase()}] ${risk.category}: ${risk.description}`)
  }
  lines.push("")

  lines.push("─".repeat(78))
  lines.push("  RECOMMENDATIONS")
  lines.push("─".repeat(78))
  for (let i = 0; i < report.recommendations.length; i++) {
    lines.push(`  ${i + 1}. ${report.recommendations[i]}`)
  }
  lines.push("")
  lines.push("=".repeat(78))
  lines.push(`  READINESS: ${report.readinessLevel.toUpperCase()} (Score: ${report.overallScore}%)`)
  lines.push("=".repeat(78))

  return lines.join("\n")
}

export function formatReportAsJSON(report: ProductionReadinessReport): string {
  return JSON.stringify(report, null, 2)
}

function pad(s: string, len: number): string {
  return s.padEnd(len)
}

function renderBar(percent: number, width: number): string {
  const filled = Math.round((percent / 100) * width)
  const empty = width - filled
  return "█".repeat(filled) + "░".repeat(empty)
}
