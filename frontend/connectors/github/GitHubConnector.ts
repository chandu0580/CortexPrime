import { ConnectorDefinition, ConnectorHealth, ConnectorMetric, ConnectorValidation, ConnectorSnapshot, ConnectorCapability } from "../../connector-framework/types"
import { GitHubRepository, GitHubIssue, GitHubPullRequest, GitHubBranch, GitHubCommit, GitHubWorkflow, GitHubActionRun, GitHubRelease, GitHubDiscussion, GitHubProject, GitHubHealth, GitHubMetrics, GitHubPermission } from "./types"
import { AbstractConnector } from "../../connector-framework/AbstractConnector"
import { ConnectorLifecycleManager } from "../../connector-framework/ConnectorLifecycle"
import { ConnectorHealthManager } from "../../connector-framework/ConnectorHealthManager"
import { ConnectorMetricsCollector } from "../../connector-framework/ConnectorMetricsCollector"
import { ConnectorValidator } from "../../connector-framework/ConnectorValidator"
import { cortexEventBus } from "@/event-bus/cortexEventBus"
import { generateId } from "../../connector-framework/shared"
import { GitHubAuth } from "./GitHubAuth"
import { GitHubClient } from "./GitHubClient"
import { GitHubTelemetry } from "./GitHubTelemetry"
import { GitHubRepositoryManager } from "./GitHubRepositoryManager"
import { GitHubIssueManager } from "./GitHubIssueManager"
import { GitHubPullRequestManager } from "./GitHubPullRequestManager"
import { GitHubBranchManager } from "./GitHubBranchManager"
import { GitHubCommitManager } from "./GitHubCommitManager"
import { GitHubActionManager } from "./GitHubActionManager"
import { GitHubReleaseManager } from "./GitHubReleaseManager"
import { GitHubDiscussionManager } from "./GitHubDiscussionManager"
import { GitHubProjectManager } from "./GitHubProjectManager"
import { GitHubSecurityManager } from "./GitHubSecurityManager"
import { GitHubCapabilityDefinitions } from "./GitHubCapability"

export class GitHubConnector extends AbstractConnector {
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
    if (config) await GitHubAuth.configure(config)

    const capabilities: ConnectorCapability[] = GitHubCapabilityDefinitions.map((d) => ({
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
    await cortexEventBus.publish("github", "connector", "github.initialized", "GitHubConnector", {
      connectorId: updated.id,
      name: updated.name,
    })
    return updated
  }

  private async loadAuthConfig(): Promise<{ type: "pat" | "github_app" | "oauth"; token?: string } | null> {
    try {
      const { DependencyContainer } = await import("@/application/DependencyContainer")
      const configLoader = await DependencyContainer.resolve<{ getSetting: (key: string) => Promise<unknown> }>("ConfigurationLoader")
      if (configLoader) {
        const token = await configLoader.getSetting("github_token")
        const authType = await configLoader.getSetting("github_auth_type")
        if (token) return { type: (authType as "pat") ?? "pat", token: token as string }
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
    await cortexEventBus.publish("github", "connector", "github.shutdown", "GitHubConnector", {
      connectorId: updated.id,
    })
    return updated
  }

  async health(): Promise<ConnectorHealth> {
    const uptime = Date.now() - this.startTime
    const isAuth = await GitHubAuth.isAuthenticated()
    const telemetry = await GitHubTelemetry.getMetrics()
    const details: Record<string, unknown> = {
      operationCount: this.operationCount,
      errorCount: this.errorCount,
      authenticated: isAuth,
      authType: await GitHubAuth.getAuthType(),
      apiCalls: telemetry.totalCalls,
      apiFailures: telemetry.totalFailures,
      successRate: telemetry.successRate,
      averageLatencyMs: telemetry.averageLatencyMs,
      rateLimitRemaining: telemetry.rateLimitRemaining,
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
      "github_operations",
      this.operationCount,
      "count",
      { state: this.definition.state },
    )
    const errorMetric = await ConnectorMetricsCollector.collectConnectorMetric(
      this.definition.id,
      "github_errors",
      this.errorCount,
      "count",
      {},
    )
    const telemetry = await GitHubTelemetry.getMetrics()
    const latencyMetric = await ConnectorMetricsCollector.collectConnectorMetric(
      this.definition.id,
      "github_api_latency_ms",
      telemetry.averageLatencyMs,
      "ms",
      {},
    )
    const apiCallsMetric = await ConnectorMetricsCollector.collectConnectorMetric(
      this.definition.id,
      "github_api_calls",
      telemetry.totalCalls,
      "count",
      {},
    )
    const rateLimitMetric = await ConnectorMetricsCollector.collectConnectorMetric(
      this.definition.id,
      "github_rate_limit_remaining",
      telemetry.rateLimitRemaining,
      "count",
      {},
    )
    return [connectorMetric, errorMetric, latencyMetric, apiCallsMetric, rateLimitMetric]
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

  repositories(): typeof GitHubRepositoryManager {
    return GitHubRepositoryManager
  }

  issues(): typeof GitHubIssueManager {
    return GitHubIssueManager
  }

  pullRequests(): typeof GitHubPullRequestManager {
    return GitHubPullRequestManager
  }

  branches(): typeof GitHubBranchManager {
    return GitHubBranchManager
  }

  commits(): typeof GitHubCommitManager {
    return GitHubCommitManager
  }

  workflows(): typeof GitHubActionManager {
    return GitHubActionManager
  }

  releases(): typeof GitHubReleaseManager {
    return GitHubReleaseManager
  }

  discussions(): typeof GitHubDiscussionManager {
    return GitHubDiscussionManager
  }

  projects(): typeof GitHubProjectManager {
    return GitHubProjectManager
  }

  security(): typeof GitHubSecurityManager {
    return GitHubSecurityManager
  }

  private async publish(event: string, data: Record<string, unknown>): Promise<void> {
    this.operationCount++
    await cortexEventBus.publish("github", "connector", `github.${event}`, "GitHubConnector", data)
  }
}
