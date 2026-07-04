import { ConnectorDefinition, ConnectorHealth, ConnectorMetric, ConnectorValidation, ConnectorSnapshot, ConnectorCapability } from "../../connector-framework/types"
import { TeamsOrganization, Team, TeamChannel, TeamMessage, TeamMeeting, TeamsNotification, Presence, Workflow, TeamsPermission, TeamsHealth, TeamsMetrics } from "./types"
import { AbstractConnector } from "../../connector-framework/AbstractConnector"
import { ConnectorLifecycleManager } from "../../connector-framework/ConnectorLifecycle"
import { ConnectorHealthManager } from "../../connector-framework/ConnectorHealthManager"
import { ConnectorMetricsCollector } from "../../connector-framework/ConnectorMetricsCollector"
import { ConnectorValidator } from "../../connector-framework/ConnectorValidator"
import { cortexEventBus } from "@/event-bus/cortexEventBus"
import { generateId } from "../../connector-framework/shared"
import { TeamsAuth } from "./TeamsAuth"
import { TeamsClient } from "./TeamsClient"
import { TeamsTelemetry } from "./TeamsTelemetry"
import { TeamsOrganizationManager } from "./TeamsOrganizationManager"
import { TeamsTeamManager } from "./TeamsTeamManager"
import { TeamsChannelManager } from "./TeamsChannelManager"
import { TeamsMessageManager } from "./TeamsMessageManager"
import { TeamsMeetingManager } from "./TeamsMeetingManager"
import { TeamsNotificationManager } from "./TeamsNotificationManager"
import { TeamsPresenceManager } from "./TeamsPresenceManager"
import { TeamsWorkflowManager } from "./TeamsWorkflowManager"
import { TeamsPermissionManager } from "./TeamsPermissionManager"
import { TeamsCapabilityDefinitions } from "./TeamsCapability"

export class TeamsConnector extends AbstractConnector {
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
    if (config) await TeamsAuth.configure(config)

    const capabilities: ConnectorCapability[] = TeamsCapabilityDefinitions.map((d) => ({
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
    await cortexEventBus.publish("teams", "connector", "teams.initialized", "TeamsConnector", {
      connectorId: updated.id,
      name: updated.name,
    })
    return updated
  }

  private async loadAuthConfig(): Promise<{ type: "client_credentials" | "auth_code" | "managed_identity"; tenantId: string; clientId?: string; clientSecret?: string; token?: string } | null> {
    try {
      const { DependencyContainer } = await import("@/application/DependencyContainer")
      const configLoader = await DependencyContainer.resolve<{ getSetting: (key: string) => Promise<unknown> }>("ConfigurationLoader")
      if (configLoader) {
        const tenantId = await configLoader.getSetting("teams_tenant_id") as string
        if (tenantId) {
          const clientId = await configLoader.getSetting("teams_client_id") as string
          const clientSecret = await configLoader.getSetting("teams_client_secret") as string
          if (clientId && clientSecret) return { type: "client_credentials", tenantId, clientId, clientSecret }
          const token = await configLoader.getSetting("teams_token") as string
          if (token) return { type: "client_credentials", tenantId, token }
        }
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
    await cortexEventBus.publish("teams", "connector", "teams.shutdown", "TeamsConnector", {
      connectorId: updated.id,
    })
    return updated
  }

  async health(): Promise<ConnectorHealth> {
    const uptime = Date.now() - this.startTime
    const isAuth = await TeamsAuth.isAuthenticated()
    const telemetry = await TeamsTelemetry.getMetrics()
    const details: Record<string, unknown> = {
      operationCount: this.operationCount,
      errorCount: this.errorCount,
      authenticated: isAuth,
      authType: await TeamsAuth.getAuthType(),
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
    const connectorMetric = await ConnectorMetricsCollector.collectConnectorMetric(this.definition.id, "teams_operations", this.operationCount, "count", { state: this.definition.state })
    const errorMetric = await ConnectorMetricsCollector.collectConnectorMetric(this.definition.id, "teams_errors", this.errorCount, "count", {})
    const telemetry = await TeamsTelemetry.getMetrics()
    const latencyMetric = await ConnectorMetricsCollector.collectConnectorMetric(this.definition.id, "teams_api_latency_ms", telemetry.averageLatencyMs, "ms", {})
    const apiCallsMetric = await ConnectorMetricsCollector.collectConnectorMetric(this.definition.id, "teams_api_calls", telemetry.totalCalls, "count", {})
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

  organizations(): typeof TeamsOrganizationManager {
    return TeamsOrganizationManager
  }

  teams(): typeof TeamsTeamManager {
    return TeamsTeamManager
  }

  channels(): typeof TeamsChannelManager {
    return TeamsChannelManager
  }

  messages(): typeof TeamsMessageManager {
    return TeamsMessageManager
  }

  meetings(): typeof TeamsMeetingManager {
    return TeamsMeetingManager
  }

  notifications(): typeof TeamsNotificationManager {
    return TeamsNotificationManager
  }

  presence(): typeof TeamsPresenceManager {
    return TeamsPresenceManager
  }

  workflows(): typeof TeamsWorkflowManager {
    return TeamsWorkflowManager
  }

  permissions(): typeof TeamsPermissionManager {
    return TeamsPermissionManager
  }

  private async publish(event: string, data: Record<string, unknown>): Promise<void> {
    this.operationCount++
    await cortexEventBus.publish("teams", "connector", `teams.${event}`, "TeamsConnector", data)
  }
}