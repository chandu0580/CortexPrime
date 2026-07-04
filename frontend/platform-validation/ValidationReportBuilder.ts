import type { ValidationReport, ValidationSummary, ValidationIssue, ValidationWarning, SmokeTestResult, DependencyValidation, LifecycleValidation, RuntimeValidationData, HealthValidation, MetricsValidation, ValidationSeverity } from "./types"
import { generateId } from "./shared"

export const ValidationReportBuilder = {
  async build(
    smokeTests: SmokeTestResult,
    dependency: DependencyValidation,
    lifecycle: LifecycleValidation,
    runtime: RuntimeValidationData,
    health: HealthValidation,
    metrics: MetricsValidation,
  ): Promise<ValidationReport> {
    const allResults = [smokeTests, dependency, lifecycle, runtime, health, metrics]
    const totalTests = allResults.length
    const passed = allResults.filter((r) => {
      if ("valid" in r) return (r as { valid: boolean }).valid
      return false
    }).length
    const warnings = dependency.errors.length + lifecycle.errors.length
    const issues: ValidationIssue[] = []

    if (!dependency.valid) {
      issues.push({
        id: generateId("issue"),
        resultId: "dependency",
        severity: "critical" as ValidationSeverity,
        message: `Dependency validation failed: ${dependency.errors.join("; ")}`,
        recommendation: "Resolve missing or circular dependencies",
      })
    }
    if (!lifecycle.valid) {
      issues.push({
        id: generateId("issue"),
        resultId: "lifecycle",
        severity: "high" as ValidationSeverity,
        message: `Lifecycle validation failed: ${lifecycle.errors.join("; ")}`,
        recommendation: "Fix invalid state transitions",
      })
    }
    if (!runtime.valid) {
      issues.push({
        id: generateId("issue"),
        resultId: "runtime",
        severity: "critical" as ValidationSeverity,
        message: `Runtime validation failed: ${runtime.errors.join("; ")}`,
        recommendation: "Ensure runtime is properly composed and started",
      })
    }
    if (!health.valid) {
      issues.push({
        id: generateId("issue"),
        resultId: "health",
        severity: "high" as ValidationSeverity,
        message: `Health validation failed: ${health.errors.join("; ")}`,
        recommendation: "Resolve health check failures",
      })
    }
    if (!metrics.valid) {
      issues.push({
        id: generateId("issue"),
        resultId: "metrics",
        severity: "medium" as ValidationSeverity,
        message: `Metrics validation failed: ${metrics.errors.join("; ")}`,
        recommendation: "Verify metrics collection and coverage",
      })
    }

    const warningsArray: ValidationWarning[] = []
    if (warnings > 0) {
      warningsArray.push({
        id: generateId("warn"),
        resultId: "validation",
        message: `${warnings} validation warnings present`,
      })
    }

    const recommendations: string[] = []
    if (!dependency.valid) recommendations.push("Resolve all dependency issues before startup")
    if (!lifecycle.valid) recommendations.push("Ensure all modules follow valid state transitions")
    if (!runtime.valid) recommendations.push("Complete runtime composition and verify startup sequence")
    if (passed === totalTests) recommendations.push("Platform is fully validated and ready for production")

    const overallScore = totalTests > 0 ? Math.round((passed / totalTests) * 100) : 0
    const platformReady = overallScore >= 80 && dependency.valid && runtime.valid

    const summary: ValidationSummary = {
      total: totalTests,
      passed,
      failed: totalTests - passed,
      skipped: 0,
      warnings,
      durationMs: 0,
    }

    return {
      id: generateId("report"),
      sessionId: generateId("session"),
      summary,
      smokeTests,
      dependency,
      lifecycle,
      runtime,
      health,
      metrics,
      issues,
      warnings: warningsArray,
      recommendations,
      overallScore,
      platformReady,
      generatedAt: new Date().toISOString(),
    }
  },
}