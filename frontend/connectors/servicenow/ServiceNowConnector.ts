import { ConnectorDefinition, ConnectorHealth, ConnectorMetric, ConnectorValidation, ConnectorSnapshot, ConnectorCapability } from "../../connector-framework/types"
import { ServiceNowInstance, Incident, ChangeRequest, Problem, ConfigurationItem, KnowledgeArticle, Catalog, ServiceNowPermission, ServiceNowHealth, ServiceNowMetrics } from "./types"
import { AbstractConnector } from "../../connector-framework/AbstractConnector"
import { ConnectorLifecycleManager } from "../../connector-framework/ConnectorLifecycle"
import { ConnectorHealthManager } from "../../connector-framework/ConnectorHealthManager"
import { ConnectorMetricsCollector } from "../../connector-framework/ConnectorMetricsCollector"
import { ConnectorValidator } from "../../connector-framework/ConnectorValidator"
import { cortexEventBus } from "@/event-bus/cortexEventBus"
import { generateId } from "../../connector-framework/shared"
import { ServiceNowAuth } from "./ServiceNowAuth"
import { ServiceNowClient } from "./ServiceNowClient"
import { ServiceNowTelemetry } from "./ServiceNowTelemetry"
import { ServiceNowInstanceManager } from "./ServiceNowInstanceManager"
import { IncidentManager } from "./IncidentManager"
import { ChangeRequestManager } from "./ChangeRequestManager"
import { ProblemManager } from "./ProblemManager"
import { CMDBManager } from "./CMDBManager"
import { KnowledgeManager } from "./KnowledgeManager"
import { CatalogManager } from "./CatalogManager"
import { ServiceNowPermissionManager } from "./ServiceNowPermissionManager"
import { ServiceNowCapabilityDefinitions } from "./ServiceNowCapability"

export class ServiceNowConnector extends AbstractConnector {
  private startTime: number = Date.now()
  private operationCount = 0
  private errorCount = 0

  constructor(definition: ConnectorDefinition) { super(definition) }

  async initialize(): Promise<ConnectorDefinition> {
    const lifecycle = await ConnectorLifecycleManager.initialize(this.definition.state)
    if (!lifecycle) return this.definition
    const config = await this.loadAuthConfig()
    if (config) await ServiceNowAuth.configure(config)
    const capabilities: ConnectorCapability[] = ServiceNowCapabilityDefinitions.map((d) => ({ id: d.id, name: d.name, description: d.description, version: d.version, supported: d.enabled, config: {} }))
    const updated: ConnectorDefinition = { ...this.definition, capabilities, state: "initialized", status: "unknown", updatedAt: new Date().toISOString() }
    await cortexEventBus.publish("servicenow", "connector", "servicenow.initialized", "ServiceNowConnector", { connectorId: updated.id, name: updated.name })
    return updated
  }

  private async loadAuthConfig(): Promise<{ type: "basic" | "oauth" | "pat"; instance: string; username?: string; password?: string; token?: string } | null> {
    try {
      const { DependencyContainer } = await import("@/application/DependencyContainer")
      const configLoader = await DependencyContainer.resolve<{ getSetting: (key: string) => Promise<unknown> }>("ConfigurationLoader")
      if (configLoader) {
        const inst = await configLoader.getSetting("servicenow_instance") as string
        if (inst) {
          const username = await configLoader.getSetting("servicenow_username") as string
          const password = await configLoader.getSetting("servicenow_password") as string
          if (username && password) return { type: "basic", instance: inst, username, password }
          const token = await configLoader.getSetting("servicenow_token") as string
          if (token) return { type: "pat", instance: inst, token }
        }
      }
    } catch { return null }
    return null
  }

  async shutdown(): Promise<ConnectorDefinition> {
    const lifecycle = await ConnectorLifecycleManager.shutdown(this.definition.id, this.definition.state)
    if (!lifecycle) return this.definition
    const updated: ConnectorDefinition = { ...this.definition, state: "deactivated", status: "unknown", updatedAt: new Date().toISOString() }
    await cortexEventBus.publish("servicenow", "connector", "servicenow.shutdown", "ServiceNowConnector", { connectorId: updated.id })
    return updated
  }

  async health(): Promise<ConnectorHealth> {
    const uptime = Date.now() - this.startTime
    const isAuth = await ServiceNowAuth.isAuthenticated()
    const telemetry = await ServiceNowTelemetry.getMetrics()
    const details: Record<string, unknown> = { operationCount: this.operationCount, errorCount: this.errorCount, authenticated: isAuth, instance: await ServiceNowAuth.getInstance(), apiCalls: telemetry.totalCalls, apiFailures: telemetry.totalFailures, successRate: telemetry.successRate, averageLatencyMs: telemetry.averageLatencyMs }
    const lastError = this.errorCount > 0 ? `${this.errorCount} errors recorded` : telemetry.totalFailures > 0 ? `${telemetry.totalFailures} API failures` : null
    return ConnectorHealthManager.check(this.definition.id, this.definition.state, uptime, lastError, details)
  }

  async metrics(): Promise<ConnectorMetric[]> {
    const c = await ConnectorMetricsCollector.collectConnectorMetric(this.definition.id, "servicenow_operations", this.operationCount, "count", { state: this.definition.state })
    const e = await ConnectorMetricsCollector.collectConnectorMetric(this.definition.id, "servicenow_errors", this.errorCount, "count", {})
    const t = await ServiceNowTelemetry.getMetrics()
    const l = await ConnectorMetricsCollector.collectConnectorMetric(this.definition.id, "servicenow_api_latency_ms", t.averageLatencyMs, "ms", {})
    const a = await ConnectorMetricsCollector.collectConnectorMetric(this.definition.id, "servicenow_api_calls", t.totalCalls, "count", {})
    return [c, e, l, a]
  }

  async validate(): Promise<ConnectorValidation> { return ConnectorValidator.validateMetadata(this.definition) }

  async snapshot(): Promise<ConnectorSnapshot> {
    return { id: generateId("snap"), connectorId: this.definition.id, state: this.definition.state, status: "healthy", capabilityCount: this.definition.capabilities.length, endpointCount: this.definition.endpoints?.length ?? 0, timestamp: new Date().toISOString() }
  }

  instances(): typeof ServiceNowInstanceManager { return ServiceNowInstanceManager }
  incidents(): typeof IncidentManager { return IncidentManager }
  changes(): typeof ChangeRequestManager { return ChangeRequestManager }
  problems(): typeof ProblemManager { return ProblemManager }
  cmdb(): typeof CMDBManager { return CMDBManager }
  knowledge(): typeof KnowledgeManager { return KnowledgeManager }
  catalog(): typeof CatalogManager { return CatalogManager }
  permissions(): typeof ServiceNowPermissionManager { return ServiceNowPermissionManager }

  private async publish(event: string, data: Record<string, unknown>): Promise<void> {
    this.operationCount++
    await cortexEventBus.publish("servicenow", "connector", `servicenow.${event}`, "ServiceNowConnector", data)
  }
}