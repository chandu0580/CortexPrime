import { ConnectorDefinition, ConnectorHealth, ConnectorMetric, ConnectorValidation, ConnectorSnapshot, ConnectorCapability } from "../../connector-framework/types"
import { SlackWorkspace, SlackChannel, SlackMessage, SlackThread, SlackUser, SlackNotification, SlackReaction, SlackWorkflow, SlackPermission, SlackHealth, SlackMetrics } from "./types"
import { AbstractConnector } from "../../connector-framework/AbstractConnector"
import { ConnectorLifecycleManager } from "../../connector-framework/ConnectorLifecycle"
import { ConnectorHealthManager } from "../../connector-framework/ConnectorHealthManager"
import { ConnectorMetricsCollector } from "../../connector-framework/ConnectorMetricsCollector"
import { ConnectorValidator } from "../../connector-framework/ConnectorValidator"
import { cortexEventBus } from "@/event-bus/cortexEventBus"
import { generateId } from "../../connector-framework/shared"
import { SlackAuth } from "./SlackAuth"
import { SlackClient } from "./SlackClient"
import { SlackTelemetry } from "./SlackTelemetry"
import { SlackWorkspaceManager } from "./SlackWorkspaceManager"
import { SlackChannelManager } from "./SlackChannelManager"
import { SlackMessageManager } from "./SlackMessageManager"
import { SlackThreadManager } from "./SlackThreadManager"
import { SlackUserManager } from "./SlackUserManager"
import { SlackNotificationManager } from "./SlackNotificationManager"
import { SlackReactionManager } from "./SlackReactionManager"
import { SlackWorkflowManager } from "./SlackWorkflowManager"
import { SlackPermissionManager } from "./SlackPermissionManager"
import { SlackCapabilityDefinitions } from "./SlackCapability"

export class SlackConnector extends AbstractConnector {
  private startTime: number = Date.now()
  private operationCount = 0
  private errorCount = 0

  constructor(definition: ConnectorDefinition) {
    super(definition)
  }

  async initialize(): Promise<ConnectorDefinition> {
    const lifecycle = await ConnectorLifecycleManager.initialize(this.definition.state)
    if (!lifecycle) return this.definition

    const config = await this.loadAuthConfig()
    if (config) await SlackAuth.configure(config)

    const capabilities: ConnectorCapability[] = SlackCapabilityDefinitions.map((d) => ({
      id: d.id,
      name: d.name,
      description: d.description,
      version: d.version,
      supported: d.enabled,
      config: {},
    }))
    const updated: ConnectorDefinition = {
      ...this.definition,
      capabilities,
      state: "initialized",
      status: "unknown",
      updatedAt: new Date().toISOString(),
    }
    await cortexEventBus.publish("slack", "connector", "slack.initialized", "SlackConnector", {
      connectorId: updated.id,
      name: updated.name,
    })
    return updated
  }

  private async loadAuthConfig(): Promise<{ type: "bot" | "user" | "oauth"; botToken?: string; userToken?: string } | null> {
    try {
      const { DependencyContainer } = await import("@/application/DependencyContainer")
      const configLoader = await DependencyContainer.resolve<{ getSetting: (key: string) => Promise<unknown> }>("ConfigurationLoader")
      if (configLoader) {
        const botToken = await configLoader.getSetting("slack_bot_token") as string
        if (botToken) return { type: "bot", botToken }
        const userToken = await configLoader.getSetting("slack_user_token") as string
        if (userToken) return { type: "user", userToken }
      }
    } catch {
      return null
    }
    return null
  }

  async shutdown(): Promise<ConnectorDefinition> {
    const lifecycle = await ConnectorLifecycleManager.shutdown(this.definition.id, this.definition.state)
    if (!lifecycle) return this.definition
    const updated: ConnectorDefinition = {
      ...this.definition,
      state: "deactivated",
      status: "unknown",
      updatedAt: new Date().toISOString(),
    }
    await cortexEventBus.publish("slack", "connector", "slack.shutdown", "SlackConnector", {
      connectorId: updated.id,
    })
    return updated
  }

  async health(): Promise<ConnectorHealth> {
    const uptime = Date.now() - this.startTime
    const isAuth = await SlackAuth.isAuthenticated()
    const telemetry = await SlackTelemetry.getMetrics()
    const details: Record<string, unknown> = {
      operationCount: this.operationCount,
      errorCount: this.errorCount,
      authenticated: isAuth,
      authType: await SlackAuth.getAuthType(),
      apiCalls: telemetry.totalCalls,
      apiFailures: telemetry.totalFailures,
      successRate: telemetry.successRate,
      averageLatencyMs: telemetry.averageLatencyMs,
    }
    const lastError = this.errorCount > 0 ? `${this.errorCount} errors recorded` : telemetry.totalFailures > 0 ? `${telemetry.totalFailures} API failures` : null
    const health = await ConnectorHealthManager.check(this.definition.id, this.definition.state, uptime, lastError, details)
    return health
  }

  async metrics(): Promise<ConnectorMetric[]> {
    const connectorMetric = await ConnectorMetricsCollector.collectConnectorMetric(this.definition.id, "slack_operations", this.operationCount, "count", { state: this.definition.state })
    const errorMetric = await ConnectorMetricsCollector.collectConnectorMetric(this.definition.id, "slack_errors", this.errorCount, "count", {})
    const telemetry = await SlackTelemetry.getMetrics()
    const latencyMetric = await ConnectorMetricsCollector.collectConnectorMetric(this.definition.id, "slack_api_latency_ms", telemetry.averageLatencyMs, "ms", {})
    const apiCallsMetric = await ConnectorMetricsCollector.collectConnectorMetric(this.definition.id, "slack_api_calls", telemetry.totalCalls, "count", {})
    return [connectorMetric, errorMetric, latencyMetric, apiCallsMetric]
  }

  async validate(): Promise<ConnectorValidation> {
    return ConnectorValidator.validateMetadata(this.definition)
  }

  async snapshot(): Promise<ConnectorSnapshot> {
    const capabilities = this.definition.capabilities
    return {
      id: generateId("snap"),
      connectorId: this.definition.id,
      state: this.definition.state,
      status: "healthy",
      capabilityCount: capabilities.length,
      endpointCount: this.definition.endpoints?.length ?? 0,
      timestamp: new Date().toISOString(),
    }
  }

  workspaces(): typeof SlackWorkspaceManager {
    return SlackWorkspaceManager
  }

  channels(): typeof SlackChannelManager {
    return SlackChannelManager
  }

  messages(): typeof SlackMessageManager {
    return SlackMessageManager
  }

  threads(): typeof SlackThreadManager {
    return SlackThreadManager
  }

  users(): typeof SlackUserManager {
    return SlackUserManager
  }

  notifications(): typeof SlackNotificationManager {
    return SlackNotificationManager
  }

  reactions(): typeof SlackReactionManager {
    return SlackReactionManager
  }

  workflows(): typeof SlackWorkflowManager {
    return SlackWorkflowManager
  }

  permissions(): typeof SlackPermissionManager {
    return SlackPermissionManager
  }

  private async publish(event: string, data: Record<string, unknown>): Promise<void> {
    this.operationCount++
    await cortexEventBus.publish("slack", "connector", `slack.${event}`, "SlackConnector", data)
  }
}