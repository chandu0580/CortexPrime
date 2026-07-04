import { ConnectorDefinition, ConnectorHealth, ConnectorMetric, ConnectorValidation, ConnectorSnapshot, ConnectorCapability } from "../../connector-framework/types"
import { AzureOrganization, AzureProject, AzureBoard, AzurePipeline, AzureRepository, AzureFeed, AzureTestPlan, AzurePermission, AzureHealth, AzureMetrics } from "./types"
import { AbstractConnector } from "../../connector-framework/AbstractConnector"
import { ConnectorLifecycleManager } from "../../connector-framework/ConnectorLifecycle"
import { ConnectorHealthManager } from "../../connector-framework/ConnectorHealthManager"
import { ConnectorMetricsCollector } from "../../connector-framework/ConnectorMetricsCollector"
import { ConnectorValidator } from "../../connector-framework/ConnectorValidator"
import { cortexEventBus } from "@/event-bus/cortexEventBus"
import { generateId } from "../../connector-framework/shared"
import { AzureDevOpsAuth } from "./AzureDevOpsAuth"
import { AzureDevOpsClient } from "./AzureDevOpsClient"
import { AzureDevOpsTelemetry } from "./AzureDevOpsTelemetry"
import { AzureOrganizationManager } from "./AzureOrganizationManager"
import { AzureProjectManager } from "./AzureProjectManager"
import { AzureBoardManager } from "./AzureBoardManager"
import { AzurePipelineManager } from "./AzurePipelineManager"
import { AzureRepositoryManager } from "./AzureRepositoryManager"
import { AzureArtifactManager } from "./AzureArtifactManager"
import { AzureTestManager } from "./AzureTestManager"
import { AzurePermissionManager } from "./AzurePermissionManager"
import { AzureCapabilityDefinitions } from "./AzureCapability"

export class AzureDevOpsConnector extends AbstractConnector {
  private startTime: number = Date.now()
  private operationCount = 0
  private errorCount = 0

  constructor(definition: ConnectorDefinition) { super(definition) }

  async initialize(): Promise<ConnectorDefinition> {
    const lifecycle = await ConnectorLifecycleManager.initialize(this.definition.state)
    if (!lifecycle) return this.definition
    const config = await this.loadAuthConfig()
    if (config) await AzureDevOpsAuth.configure(config)
    const capabilities: ConnectorCapability[] = AzureCapabilityDefinitions.map((d) => ({ id: d.id, name: d.name, description: d.description, version: d.version, supported: d.enabled, config: {} }))
    const updated: ConnectorDefinition = { ...this.definition, capabilities, state: "initialized", status: "unknown", updatedAt: new Date().toISOString() }
    await cortexEventBus.publish("azure", "connector", "azure.initialized", "AzureDevOpsConnector", { connectorId: updated.id, name: updated.name })
    return updated
  }

  private async loadAuthConfig(): Promise<{ type: "pat" | "oauth" | "managed_identity"; organization: string; pat?: string } | null> {
    try {
      const { DependencyContainer } = await import("@/application/DependencyContainer")
      const configLoader = await DependencyContainer.resolve<{ getSetting: (key: string) => Promise<unknown> }>("ConfigurationLoader")
      if (configLoader) {
        const org = await configLoader.getSetting("azure_organization") as string
        if (org) {
          const pat = await configLoader.getSetting("azure_pat") as string
          if (pat) return { type: "pat", organization: org, pat }
        }
      }
    } catch { return null }
    return null
  }

  async shutdown(): Promise<ConnectorDefinition> {
    const lifecycle = await ConnectorLifecycleManager.shutdown(this.definition.id, this.definition.state)
    if (!lifecycle) return this.definition
    const updated: ConnectorDefinition = { ...this.definition, state: "deactivated", status: "unknown", updatedAt: new Date().toISOString() }
    await cortexEventBus.publish("azure", "connector", "azure.shutdown", "AzureDevOpsConnector", { connectorId: updated.id })
    return updated
  }

  async health(): Promise<ConnectorHealth> {
    const uptime = Date.now() - this.startTime
    const isAuth = await AzureDevOpsAuth.isAuthenticated()
    const telemetry = await AzureDevOpsTelemetry.getMetrics()
    const details: Record<string, unknown> = { operationCount: this.operationCount, errorCount: this.errorCount, authenticated: isAuth, org: await AzureDevOpsAuth.getOrganization(), apiCalls: telemetry.totalCalls, apiFailures: telemetry.totalFailures, successRate: telemetry.successRate, averageLatencyMs: telemetry.averageLatencyMs }
    const lastError = this.errorCount > 0 ? `${this.errorCount} errors recorded` : telemetry.totalFailures > 0 ? `${telemetry.totalFailures} API failures` : null
    return ConnectorHealthManager.check(this.definition.id, this.definition.state, uptime, lastError, details)
  }

  async metrics(): Promise<ConnectorMetric[]> {
    const c = await ConnectorMetricsCollector.collectConnectorMetric(this.definition.id, "azure_operations", this.operationCount, "count", { state: this.definition.state })
    const e = await ConnectorMetricsCollector.collectConnectorMetric(this.definition.id, "azure_errors", this.errorCount, "count", {})
    const t = await AzureDevOpsTelemetry.getMetrics()
    const l = await ConnectorMetricsCollector.collectConnectorMetric(this.definition.id, "azure_api_latency_ms", t.averageLatencyMs, "ms", {})
    const a = await ConnectorMetricsCollector.collectConnectorMetric(this.definition.id, "azure_api_calls", t.totalCalls, "count", {})
    return [c, e, l, a]
  }

  async validate(): Promise<ConnectorValidation> { return ConnectorValidator.validateMetadata(this.definition) }

  async snapshot(): Promise<ConnectorSnapshot> {
    return { id: generateId("snap"), connectorId: this.definition.id, state: this.definition.state, status: "healthy", capabilityCount: this.definition.capabilities.length, endpointCount: this.definition.endpoints?.length ?? 0, timestamp: new Date().toISOString() }
  }

  organizations(): typeof AzureOrganizationManager { return AzureOrganizationManager }
  projects(): typeof AzureProjectManager { return AzureProjectManager }
  boards(): typeof AzureBoardManager { return AzureBoardManager }
  pipelines(): typeof AzurePipelineManager { return AzurePipelineManager }
  repositories(): typeof AzureRepositoryManager { return AzureRepositoryManager }
  artifacts(): typeof AzureArtifactManager { return AzureArtifactManager }
  tests(): typeof AzureTestManager { return AzureTestManager }
  permissions(): typeof AzurePermissionManager { return AzurePermissionManager }

  private async publish(event: string, data: Record<string, unknown>): Promise<void> {
    this.operationCount++
    await cortexEventBus.publish("azure", "connector", `azure.${event}`, "AzureDevOpsConnector", data)
  }
}