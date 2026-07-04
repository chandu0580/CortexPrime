import { ConnectorCompliance, CoverageLevel, ValidationSeverity, type ConnectorValidationReport, type ConnectorSummary, type ConnectorCoverage, type ConnectorIssue, type ConnectorRecommendation, type ConnectorContractResult, type ConnectorLifecycleResult, type ConnectorCapabilityResult, type ConnectorPermissionResult, type ConnectorHealthResult, type ConnectorMetricResult, type ConnectorEventResult, type ReportFormat } from "./types"
import { generateId } from "./shared"

export const ConnectorReportBuilder = {
  async buildValidationReport(
    connectorName: string,
    contract: ConnectorContractResult,
    lifecycle: ConnectorLifecycleResult,
    capability: ConnectorCapabilityResult,
    permission: ConnectorPermissionResult,
    health: ConnectorHealthResult,
    metrics: ConnectorMetricResult,
    event: ConnectorEventResult,
  ): Promise<ConnectorValidationReport> {
    const allResults = [contract, lifecycle, capability, permission, health, metrics, event]
    const totalTests = allResults.length
    const passed = allResults.filter((r) => r.status === "passed").length
    const failed = allResults.filter((r) => r.status === "failed").length
    const totalErrors = allResults.reduce((sum, r) => sum + r.errors.length, 0)
    const warnings = totalErrors

    const totalScore = allResults.reduce((sum, r) => sum + (r.status === "passed" ? 100 : 50), 0)
    const complianceScore = Math.round(totalScore / totalTests)

    let compliance: ConnectorCompliance
    if (complianceScore >= 90) compliance = ConnectorCompliance.FULLY_COMPLIANT
    else if (complianceScore >= 60) compliance = ConnectorCompliance.PARTIALLY_COMPLIANT
    else compliance = ConnectorCompliance.NON_COMPLIANT

    const summary: ConnectorSummary = { totalTests, passed, failed, skipped: 0, warnings, durationMs: 0 }

    const coverage: ConnectorCoverage = {
      overall: failed === 0 ? CoverageLevel.FULL : passed > failed ? CoverageLevel.PARTIAL : CoverageLevel.MINIMAL,
      contract: contract.status === "passed" ? CoverageLevel.FULL : CoverageLevel.MINIMAL,
      lifecycle: lifecycle.status === "passed" ? CoverageLevel.FULL : CoverageLevel.MINIMAL,
      capability: capability.status === "passed" ? CoverageLevel.FULL : CoverageLevel.MINIMAL,
      permission: permission.status === "passed" ? CoverageLevel.FULL : CoverageLevel.MINIMAL,
      health: health.status === "passed" ? CoverageLevel.FULL : CoverageLevel.MINIMAL,
      metrics: metrics.status === "passed" ? CoverageLevel.FULL : CoverageLevel.MINIMAL,
      event: event.status === "passed" ? CoverageLevel.FULL : CoverageLevel.MINIMAL,
    }

    const issues: ConnectorIssue[] = allResults
      .filter((r) => r.errors.length > 0)
      .flatMap((r) => r.errors.map((err) => ({
        id: generateId("issue"),
        category: "validation",
        severity: ValidationSeverity.HIGH,
        message: err,
        recommendation: `Fix the reported issue in ${connectorName}`,
      })))

    const recommendations: ConnectorRecommendation[] = []
    if (complianceScore < 100) {
      recommendations.push({
        id: generateId("rec"),
        category: "compliance",
        priority: "high",
        message: `Improve compliance score from ${complianceScore}% to 100%`,
      })
    }

    return {
      id: generateId("report"),
      connectorName,
      contract, lifecycle, capability, permission, health, metrics, event,
      summary, coverage, issues, recommendations,
      compliance, complianceScore,
      generatedAt: new Date().toISOString(),
    }
  },

  async generateSummary(report: ConnectorValidationReport): Promise<string> {
    return [
      `Connector: ${report.connectorName}`,
      `Compliance: ${report.compliance} (${report.complianceScore}%)`,
      `Tests: ${report.summary.passed}/${report.summary.totalTests} passed, ${report.summary.failed} failed`,
      `Issues: ${report.issues.length}`,
      `Coverage: ${report.coverage.overall}`,
    ].join("\n")
  },
}