import { ConnectorCompliance, type ConnectorTestResult, type ConnectorValidationReport, type ConnectorTestSuite, type ConnectorTestCase, type ConnectorHarnessMetrics, type ConnectorHarnessHealth, type TestStatus, type ConnectorCompliance as ConnectorComplianceType } from "./types"
import { ConnectorContractValidator } from "./ConnectorContractValidator"
import { ConnectorLifecycleValidator } from "./ConnectorLifecycleValidator"
import { ConnectorCapabilityValidator } from "./ConnectorCapabilityValidator"
import { ConnectorPermissionValidator } from "./ConnectorPermissionValidator"
import { ConnectorHealthValidator } from "./ConnectorHealthValidator"
import { ConnectorMetricsValidator } from "./ConnectorMetricsValidator"
import { ConnectorEventValidator } from "./ConnectorEventValidator"
import { ConnectorReportBuilder } from "./ConnectorReportBuilder"
import { generateId } from "./shared"

interface ConnectorInfo {
  name: string
  connector: Record<string, unknown>
  exports: string[]
  capabilities: { name: string; id: string; version: string; enabled: boolean }[]
  permissionEvaluators: string[]
  metrics: { name: string; value: number }[]
  events: string[]
  health: { status?: string; lastHeartbeat?: string }
  definition: { state: string }
  transitions: Record<string, string[]>
}

const validationResults = new Map<string, ConnectorValidationReport>()

export const ConnectorTestHarness = {
  async validateConnector(info: ConnectorInfo): Promise<ConnectorValidationReport> {
    const expectedMethods = ["initialize", "shutdown", "health", "metrics", "validate", "snapshot"]
    const contract = await ConnectorContractValidator.validate(
      info.connector, info.exports,
      info.capabilities, expectedMethods,
      [info.name], info.capabilities.map((c) => c.name),
    )

    const lifecycle = await ConnectorLifecycleValidator.validate(info.definition, info.transitions)

    const stages = info.capabilities.map((c) => c.name.split(".")[0])
    const capability = await ConnectorCapabilityValidator.validate(
      info.capabilities, info.capabilities.length, [...new Set(stages)],
    )

    const permission = await ConnectorPermissionValidator.validate(info.permissionEvaluators, 3)

    const health = await ConnectorHealthValidator.validate(info.connector, info.health)

    const metrics = await ConnectorMetricsValidator.validate(info.metrics, 2)

    const validCategories = [...new Set(stages)]
    const event = await ConnectorEventValidator.validate(info.events, validCategories)

    const report = await ConnectorReportBuilder.buildValidationReport(
      info.name, contract, lifecycle, capability, permission, health, metrics, event,
    )
    validationResults.set(info.name, report)
    return report
  },

  async validateAll(connectors: ConnectorInfo[]): Promise<ConnectorValidationReport[]> {
    return Promise.all(connectors.map((c) => this.validateConnector(c)))
  },

  async buildReport(connectorName: string): Promise<ConnectorValidationReport | null> {
    return validationResults.get(connectorName) ?? null
  },

  async metrics(): Promise<ConnectorHarnessMetrics> {
    const reports = Array.from(validationResults.values())
    const totalConnectorsValidated = reports.length
    const totalTestsRun = reports.reduce((sum, r) => sum + r.summary.totalTests, 0)
    const totalPassed = reports.reduce((sum, r) => sum + r.summary.passed, 0)
    const totalFailed = reports.reduce((sum, r) => sum + r.summary.failed, 0)
    const totalWarnings = reports.reduce((sum, r) => sum + r.summary.warnings, 0)
    const scores = reports.map((r) => r.complianceScore)
    const averageComplianceScore = scores.length > 0 ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length) : 0
    const fullyCompliant = reports.filter((r) => r.compliance === ConnectorCompliance.FULLY_COMPLIANT).length
    const partiallyCompliant = reports.filter((r) => r.compliance === ConnectorCompliance.PARTIALLY_COMPLIANT).length
    const nonCompliant = reports.filter((r) => r.compliance === ConnectorCompliance.NON_COMPLIANT).length

    return {
      totalConnectorsValidated,
      totalTestsRun,
      totalPassed,
      totalFailed,
      totalWarnings,
      averageComplianceScore,
      fullyCompliant,
      partiallyCompliant,
      nonCompliant,
      lastRunAt: reports.length > 0 ? reports[reports.length - 1].generatedAt : null,
    }
  },

  async health(): Promise<ConnectorHarnessHealth> {
    const reports = Array.from(validationResults.values())
    const validationErrors = reports.filter((r) => r.compliance !== ConnectorCompliance.FULLY_COMPLIANT).length
    let status: "healthy" | "degraded" | "unhealthy" | "unknown" = "healthy"
    if (validationErrors > 0) status = "degraded"
    if (reports.length === 0) status = "unknown"

    return {
      status,
      lastValidationAt: reports.length > 0 ? reports[reports.length - 1].generatedAt : null,
      totalConnectors: reports.length,
      validationErrors,
      details: { totalReports: reports.length },
    }
  },
}