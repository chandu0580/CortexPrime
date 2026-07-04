import { ConnectorDefinition, ConnectorHealth, ConnectorMetric, ConnectorValidation, ConnectorSnapshot, ConnectorCapability } from "../../connector-framework/types"
import { JiraProject, JiraIssue, JiraEpic, JiraSprint, JiraBoard, JiraWorkflow, JiraComment, JiraRelease, JiraPermission, JiraHealth, JiraMetrics } from "./types"
import { AbstractConnector } from "../../connector-framework/AbstractConnector"
import { ConnectorLifecycleManager } from "../../connector-framework/ConnectorLifecycle"
import { ConnectorHealthManager } from "../../connector-framework/ConnectorHealthManager"
import { ConnectorMetricsCollector } from "../../connector-framework/ConnectorMetricsCollector"
import { ConnectorValidator } from "../../connector-framework/ConnectorValidator"
import { cortexEventBus } from "@/event-bus/cortexEventBus"
import { generateId } from "../../connector-framework/shared"
import { JiraAuth } from "./JiraAuth"
import { JiraClient } from "./JiraClient"
import { JiraTelemetry } from "./JiraTelemetry"
import { JiraProjectManager } from "./JiraProjectManager"
import { JiraIssueManager } from "./JiraIssueManager"
import { JiraEpicManager } from "./JiraEpicManager"
import { JiraSprintManager } from "./JiraSprintManager"
import { JiraBoardManager } from "./JiraBoardManager"
import { JiraWorkflowManager } from "./JiraWorkflowManager"
import { JiraCommentManager } from "./JiraCommentManager"
import { JiraReleaseManager } from "./JiraReleaseManager"
import { JiraPermissionManager } from "./JiraPermissionManager"
import { JiraCapabilityDefinitions } from "./JiraCapability"

export class JiraConnector extends AbstractConnector {
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
    if (config) await JiraAuth.configure(config)

    const capabilities: ConnectorCapability[] = JiraCapabilityDefinitions.map((d) => ({
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
    await cortexEventBus.publish("jira", "connector", "jira.initialized", "JiraConnector", {
      connectorId: updated.id,
      name: updated.name,
    })
    return updated
  }

  private async loadAuthConfig(): Promise<{ type: "api_token" | "pat" | "oauth"; site: string; email?: string; apiToken?: string; token?: string } | null> {
    try {
      const { DependencyContainer } = await import("@/application/DependencyContainer")
      const configLoader = await DependencyContainer.resolve<{ getSetting: (key: string) => Promise<unknown> }>("ConfigurationLoader")
      if (configLoader) {
        const site = await configLoader.getSetting("jira_site") as string
        const type = await configLoader.getSetting("jira_auth_type") as string ?? "api_token"
        if (type === "api_token") {
          const email = await configLoader.getSetting("jira_email") as string
          const apiToken = await configLoader.getSetting("jira_api_token") as string
          if (site && email && apiToken) return { type: "api_token", site, email, apiToken }
        } else {
          const token = await configLoader.getSetting("jira_token") as string
          if (site && token) return { type: type as "pat", site, token }
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
    await cortexEventBus.publish("jira", "connector", "jira.shutdown", "JiraConnector", {
      connectorId: updated.id,
    })
    return updated
  }

  async health(): Promise<ConnectorHealth> {
    const uptime = Date.now() - this.startTime
    const isAuth = await JiraAuth.isAuthenticated()
    const telemetry = await JiraTelemetry.getMetrics()
    const details: Record<string, unknown> = {
      operationCount: this.operationCount,
      errorCount: this.errorCount,
      authenticated: isAuth,
      authType: await JiraAuth.getAuthType(),
      jiraSite: await JiraAuth.getSite(),
      apiCalls: telemetry.totalCalls,
      apiFailures: telemetry.totalFailures,
      successRate: telemetry.successRate,
      averageLatencyMs: telemetry.averageLatencyMs,
    }
    const lastError = this.errorCount > 0 ? `${this.errorCount} errors recorded` : telemetry.totalFailures > 0 ? `${telemetry.totalFailures} API failures` : null
    const health = await ConnectorHealthManager.check(
      this.definition.id,
      this.definition.state,
      uptime,
      lastError,
      details,
    )
    return health
  }

  async metrics(): Promise<ConnectorMetric[]> {
    const connectorMetric = await ConnectorMetricsCollector.collectConnectorMetric(
      this.definition.id,
      "jira_operations",
      this.operationCount,
      "count",
      { state: this.definition.state },
    )
    const errorMetric = await ConnectorMetricsCollector.collectConnectorMetric(
      this.definition.id,
      "jira_errors",
      this.errorCount,
      "count",
      {},
    )
    const telemetry = await JiraTelemetry.getMetrics()
    const latencyMetric = await ConnectorMetricsCollector.collectConnectorMetric(
      this.definition.id,
      "jira_api_latency_ms",
      telemetry.averageLatencyMs,
      "ms",
      {},
    )
    const apiCallsMetric = await ConnectorMetricsCollector.collectConnectorMetric(
      this.definition.id,
      "jira_api_calls",
      telemetry.totalCalls,
      "count",
      {},
    )
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

  projects(): typeof JiraProjectManager {
    return JiraProjectManager
  }

  issues(): typeof JiraIssueManager {
    return JiraIssueManager
  }

  epics(): typeof JiraEpicManager {
    return JiraEpicManager
  }

  sprints(): typeof JiraSprintManager {
    return JiraSprintManager
  }

  boards(): typeof JiraBoardManager {
    return JiraBoardManager
  }

  workflows(): typeof JiraWorkflowManager {
    return JiraWorkflowManager
  }

  comments(): typeof JiraCommentManager {
    return JiraCommentManager
  }

  releases(): typeof JiraReleaseManager {
    return JiraReleaseManager
  }

  permissions(): typeof JiraPermissionManager {
    return JiraPermissionManager
  }

  private async publish(event: string, data: Record<string, unknown>): Promise<void> {
    this.operationCount++
    await cortexEventBus.publish("jira", "connector", `jira.${event}`, "JiraConnector", data)
  }
}
