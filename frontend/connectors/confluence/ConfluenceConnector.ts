import { ConnectorDefinition, ConnectorHealth, ConnectorMetric, ConnectorValidation, ConnectorSnapshot, ConnectorCapability } from "../../connector-framework/types"
import { ConfluenceSpace, ConfluencePage, ConfluenceBlogPost, ConfluenceAttachment, ConfluenceComment, ConfluenceTemplate, SearchResult, SpacePermission, ConfluenceHealth, ConfluenceMetrics } from "./types"
import { AbstractConnector } from "../../connector-framework/AbstractConnector"
import { ConnectorLifecycleManager } from "../../connector-framework/ConnectorLifecycle"
import { ConnectorHealthManager } from "../../connector-framework/ConnectorHealthManager"
import { ConnectorMetricsCollector } from "../../connector-framework/ConnectorMetricsCollector"
import { ConnectorValidator } from "../../connector-framework/ConnectorValidator"
import { cortexEventBus } from "@/event-bus/cortexEventBus"
import { generateId } from "../../connector-framework/shared"
import { ConfluenceAuth } from "./ConfluenceAuth"
import { ConfluenceClient } from "./ConfluenceClient"
import { ConfluenceTelemetry } from "./ConfluenceTelemetry"
import { ConfluenceSpaceManager } from "./ConfluenceSpaceManager"
import { ConfluencePageManager } from "./ConfluencePageManager"
import { ConfluenceBlogManager } from "./ConfluenceBlogManager"
import { ConfluenceAttachmentManager } from "./ConfluenceAttachmentManager"
import { ConfluenceCommentManager } from "./ConfluenceCommentManager"
import { ConfluenceTemplateManager } from "./ConfluenceTemplateManager"
import { ConfluenceSearchManager } from "./ConfluenceSearchManager"
import { ConfluencePermissionManager } from "./ConfluencePermissionManager"
import { ConfluenceCapabilityDefinitions } from "./ConfluenceCapability"

export class ConfluenceConnector extends AbstractConnector {
  private startTime: number = Date.now()
  private operationCount = 0
  private errorCount = 0

  constructor(definition: ConnectorDefinition) { super(definition) }

  async initialize(): Promise<ConnectorDefinition> {
    const lifecycle = await ConnectorLifecycleManager.initialize(this.definition.state)
    if (!lifecycle) return this.definition
    const config = await this.loadAuthConfig()
    if (config) await ConfluenceAuth.configure(config)
    const capabilities: ConnectorCapability[] = ConfluenceCapabilityDefinitions.map((d) => ({
      id: d.id, name: d.name, description: d.description, version: d.version, supported: d.enabled, config: {},
    }))
    const updated: ConnectorDefinition = { ...this.definition, capabilities, state: "initialized", status: "unknown", updatedAt: new Date().toISOString() }
    await cortexEventBus.publish("confluence", "connector", "confluence.initialized", "ConfluenceConnector", { connectorId: updated.id, name: updated.name })
    return updated
  }

  private async loadAuthConfig(): Promise<{ type: "api_token" | "pat" | "oauth"; site: string; email?: string; apiToken?: string; token?: string } | null> {
    try {
      const { DependencyContainer } = await import("@/application/DependencyContainer")
      const configLoader = await DependencyContainer.resolve<{ getSetting: (key: string) => Promise<unknown> }>("ConfigurationLoader")
      if (configLoader) {
        const site = await configLoader.getSetting("confluence_site") as string
        if (site) {
          const email = await configLoader.getSetting("confluence_email") as string
          const apiToken = await configLoader.getSetting("confluence_api_token") as string
          if (email && apiToken) return { type: "api_token", site, email, apiToken }
          const token = await configLoader.getSetting("confluence_token") as string
          if (token) return { type: "pat", site, token }
        }
      }
    } catch { return null }
    return null
  }

  async shutdown(): Promise<ConnectorDefinition> {
    const lifecycle = await ConnectorLifecycleManager.shutdown(this.definition.id, this.definition.state)
    if (!lifecycle) return this.definition
    const updated: ConnectorDefinition = { ...this.definition, state: "deactivated", status: "unknown", updatedAt: new Date().toISOString() }
    await cortexEventBus.publish("confluence", "connector", "confluence.shutdown", "ConfluenceConnector", { connectorId: updated.id })
    return updated
  }

  async health(): Promise<ConnectorHealth> {
    const uptime = Date.now() - this.startTime
    const isAuth = await ConfluenceAuth.isAuthenticated()
    const telemetry = await ConfluenceTelemetry.getMetrics()
    const details: Record<string, unknown> = { operationCount: this.operationCount, errorCount: this.errorCount, authenticated: isAuth, authType: await ConfluenceAuth.getAuthType(), site: await ConfluenceAuth.getSite(), apiCalls: telemetry.totalCalls, apiFailures: telemetry.totalFailures, successRate: telemetry.successRate, averageLatencyMs: telemetry.averageLatencyMs }
    const lastError = this.errorCount > 0 ? `${this.errorCount} errors recorded` : telemetry.totalFailures > 0 ? `${telemetry.totalFailures} API failures` : null
    return ConnectorHealthManager.check(this.definition.id, this.definition.state, uptime, lastError, details)
  }

  async metrics(): Promise<ConnectorMetric[]> {
    const c = await ConnectorMetricsCollector.collectConnectorMetric(this.definition.id, "confluence_operations", this.operationCount, "count", { state: this.definition.state })
    const e = await ConnectorMetricsCollector.collectConnectorMetric(this.definition.id, "confluence_errors", this.errorCount, "count", {})
    const t = await ConfluenceTelemetry.getMetrics()
    const l = await ConnectorMetricsCollector.collectConnectorMetric(this.definition.id, "confluence_api_latency_ms", t.averageLatencyMs, "ms", {})
    const a = await ConnectorMetricsCollector.collectConnectorMetric(this.definition.id, "confluence_api_calls", t.totalCalls, "count", {})
    return [c, e, l, a]
  }

  async validate(): Promise<ConnectorValidation> { return ConnectorValidator.validateMetadata(this.definition) }

  async snapshot(): Promise<ConnectorSnapshot> {
    return { id: generateId("snap"), connectorId: this.definition.id, state: this.definition.state, status: "healthy", capabilityCount: this.definition.capabilities.length, endpointCount: this.definition.endpoints?.length ?? 0, timestamp: new Date().toISOString() }
  }

  spaces(): typeof ConfluenceSpaceManager { return ConfluenceSpaceManager }
  pages(): typeof ConfluencePageManager { return ConfluencePageManager }
  blogs(): typeof ConfluenceBlogManager { return ConfluenceBlogManager }
  attachments(): typeof ConfluenceAttachmentManager { return ConfluenceAttachmentManager }
  comments(): typeof ConfluenceCommentManager { return ConfluenceCommentManager }
  templates(): typeof ConfluenceTemplateManager { return ConfluenceTemplateManager }
  search(): typeof ConfluenceSearchManager { return ConfluenceSearchManager }
  permissions(): typeof ConfluencePermissionManager { return ConfluencePermissionManager }

  private async publish(event: string, data: Record<string, unknown>): Promise<void> {
    this.operationCount++
    await cortexEventBus.publish("confluence", "connector", `confluence.${event}`, "ConfluenceConnector", data)
  }
}