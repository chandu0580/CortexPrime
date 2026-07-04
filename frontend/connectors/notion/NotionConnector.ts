import { ConnectorDefinition, ConnectorHealth, ConnectorMetric, ConnectorValidation, ConnectorSnapshot, ConnectorCapability } from "../../connector-framework/types"
import { NotionWorkspace, NotionPage, NotionDatabase, NotionBlock, NotionTemplate, NotionComment, SearchResult, WorkspacePermission, NotionHealth, NotionMetrics } from "./types"
import { AbstractConnector } from "../../connector-framework/AbstractConnector"
import { ConnectorLifecycleManager } from "../../connector-framework/ConnectorLifecycle"
import { ConnectorHealthManager } from "../../connector-framework/ConnectorHealthManager"
import { ConnectorMetricsCollector } from "../../connector-framework/ConnectorMetricsCollector"
import { ConnectorValidator } from "../../connector-framework/ConnectorValidator"
import { cortexEventBus } from "@/event-bus/cortexEventBus"
import { generateId } from "../../connector-framework/shared"
import { NotionAuth } from "./NotionAuth"
import { NotionClient } from "./NotionClient"
import { NotionTelemetry } from "./NotionTelemetry"
import { WorkspaceManager } from "./WorkspaceManager"
import { PageManager } from "./PageManager"
import { DatabaseManager } from "./DatabaseManager"
import { BlockManager } from "./BlockManager"
import { TemplateManager } from "./TemplateManager"
import { CommentManager } from "./CommentManager"
import { SearchManager } from "./SearchManager"
import { PermissionManager } from "./PermissionManager"
import { NotionCapabilityDefinitions } from "./NotionCapability"

export class NotionConnector extends AbstractConnector {
  private startTime: number = Date.now()
  private operationCount = 0
  private errorCount = 0

  constructor(definition: ConnectorDefinition) { super(definition) }

  async initialize(): Promise<ConnectorDefinition> {
    const lifecycle = await ConnectorLifecycleManager.initialize(this.definition.state)
    if (!lifecycle) return this.definition
    const config = await this.loadAuthConfig()
    if (config) await NotionAuth.configure(config)
    const capabilities: ConnectorCapability[] = NotionCapabilityDefinitions.map((d) => ({ id: d.id, name: d.name, description: d.description, version: d.version, supported: d.enabled, config: {} }))
    const updated: ConnectorDefinition = { ...this.definition, capabilities, state: "initialized", status: "unknown", updatedAt: new Date().toISOString() }
    await cortexEventBus.publish("notion", "connector", "notion.initialized", "NotionConnector", { connectorId: updated.id, name: updated.name })
    return updated
  }

  private async loadAuthConfig(): Promise<{ type: "internal_integration" | "oauth"; token: string } | null> {
    try {
      const { DependencyContainer } = await import("@/application/DependencyContainer")
      const configLoader = await DependencyContainer.resolve<{ getSetting: (key: string) => Promise<unknown> }>("ConfigurationLoader")
      if (configLoader) {
        const token = await configLoader.getSetting("notion_token") as string
        if (token) return { type: "internal_integration", token }
      }
    } catch { return null }
    return null
  }

  async shutdown(): Promise<ConnectorDefinition> {
    const lifecycle = await ConnectorLifecycleManager.shutdown(this.definition.id, this.definition.state)
    if (!lifecycle) return this.definition
    const updated: ConnectorDefinition = { ...this.definition, state: "deactivated", status: "unknown", updatedAt: new Date().toISOString() }
    await cortexEventBus.publish("notion", "connector", "notion.shutdown", "NotionConnector", { connectorId: updated.id })
    return updated
  }

  async health(): Promise<ConnectorHealth> {
    const uptime = Date.now() - this.startTime
    const isAuth = await NotionAuth.isAuthenticated()
    const telemetry = await NotionTelemetry.getMetrics()
    const details: Record<string, unknown> = { operationCount: this.operationCount, errorCount: this.errorCount, authenticated: isAuth, authType: await NotionAuth.getAuthType(), apiCalls: telemetry.totalCalls, apiFailures: telemetry.totalFailures, successRate: telemetry.successRate, averageLatencyMs: telemetry.averageLatencyMs }
    const lastError = this.errorCount > 0 ? `${this.errorCount} errors recorded` : telemetry.totalFailures > 0 ? `${telemetry.totalFailures} API failures` : null
    return ConnectorHealthManager.check(this.definition.id, this.definition.state, uptime, lastError, details)
  }

  async metrics(): Promise<ConnectorMetric[]> {
    const c = await ConnectorMetricsCollector.collectConnectorMetric(this.definition.id, "notion_operations", this.operationCount, "count", { state: this.definition.state })
    const e = await ConnectorMetricsCollector.collectConnectorMetric(this.definition.id, "notion_errors", this.errorCount, "count", {})
    const t = await NotionTelemetry.getMetrics()
    const l = await ConnectorMetricsCollector.collectConnectorMetric(this.definition.id, "notion_api_latency_ms", t.averageLatencyMs, "ms", {})
    const a = await ConnectorMetricsCollector.collectConnectorMetric(this.definition.id, "notion_api_calls", t.totalCalls, "count", {})
    return [c, e, l, a]
  }

  async validate(): Promise<ConnectorValidation> { return ConnectorValidator.validateMetadata(this.definition) }

  async snapshot(): Promise<ConnectorSnapshot> {
    return { id: generateId("snap"), connectorId: this.definition.id, state: this.definition.state, status: "healthy", capabilityCount: this.definition.capabilities.length, endpointCount: this.definition.endpoints?.length ?? 0, timestamp: new Date().toISOString() }
  }

  workspaces(): typeof WorkspaceManager { return WorkspaceManager }
  pages(): typeof PageManager { return PageManager }
  databases(): typeof DatabaseManager { return DatabaseManager }
  blocks(): typeof BlockManager { return BlockManager }
  templates(): typeof TemplateManager { return TemplateManager }
  comments(): typeof CommentManager { return CommentManager }
  search(): typeof SearchManager { return SearchManager }
  permissions(): typeof PermissionManager { return PermissionManager }

  private async publish(event: string, data: Record<string, unknown>): Promise<void> {
    this.operationCount++
    await cortexEventBus.publish("notion", "connector", `notion.${event}`, "NotionConnector", data)
  }
}