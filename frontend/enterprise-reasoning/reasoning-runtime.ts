import type {
  ProviderConfig, LLMResponse, MissionPlan, WorkerDecision,
  ConnectorAction, BrowserAction, VoiceResponse, RecoveryDecision,
  StreamingChunk, ReasoningConfig, ReasoningMetrics,
} from "./types"
import { LLMProviderRegistry } from "./LLMProviderAdapter"
import { ReasoningPipeline, type PipelineOptions } from "./reasoning-pipeline"
import { ReasoningMetricsCollector } from "./reasoning-metrics"
import { ReasoningContextBuilder } from "./context-builder"
import { ReasoningAuditor } from "./response-validator"
import { ReasoningStreamManager } from "./stream-manager"
import { cortexEventBus } from "@/event-bus/cortexEventBus"
import type { IEventBus, ITelemetry } from "@/platform/interfaces"

let initialized = false
let runtimeId: string
let telemetry: ITelemetry | null = null

function generateId(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`
}

async function publishEvent(type: string, data: Record<string, unknown>): Promise<void> {
  await cortexEventBus.publish("reasoning", "mission", `reasoning.${type}`, "ReasoningRuntime", data)
}

export class ReasoningRuntime {
  static async initialize(config?: Partial<ReasoningConfig & PipelineOptions>, eb?: IEventBus, tel?: ITelemetry): Promise<void> {
    if (initialized) return

    runtimeId = generateId("reasoning-runtime")
    telemetry = tel ?? null

    await ReasoningMetricsCollector.initialize()

    if (config?.providers) {
      for (const providerConfig of config.providers) {
        await LLMProviderRegistry.register(providerConfig)
      }
    }

    await ReasoningPipeline.initialize({
      maxRetries: config?.maxRetries ?? 3,
      retryDelayMs: config?.retryDelayMs ?? 1000,
      fallbackOrder: config?.fallbackOrder ?? ["openai", "azure-openai", "anthropic", "gemini", "ollama"],
      streaming: config?.streamingEnabled ?? false,
    })

    initialized = true

    await publishEvent("initialized", { runtimeId })
    await telemetry?.recordEvent("reasoning.initialized", { runtimeId })
  }

  static async shutdown(): Promise<void> {
    if (!initialized) return

    await ReasoningStreamManager.cancelAll()
    initialized = false

    await publishEvent("shutdown", { runtimeId })
    await telemetry?.recordEvent("reasoning.shutdown", { runtimeId })
  }

  static async registerProvider(config: ProviderConfig): Promise<void> {
    await LLMProviderRegistry.register(config)
  }

  static async planMission(
    sessionId: string,
    missionId: string,
    objective: string,
    priority: "low" | "medium" | "high" | "critical",
    additionalContext?: Record<string, unknown>,
  ): Promise<MissionPlan> {
    this.requireInitialized()
    const startTime = Date.now()

    try {
      const result = await ReasoningPipeline.planMission(sessionId, missionId, objective, priority, additionalContext)

      await publishEvent("mission-planned", {
        runtimeId, sessionId, missionId, durationMs: Date.now() - startTime,
      })
      await telemetry?.recordEvent("reasoning.mission-planned", {
        runtimeId, sessionId, missionId, durationMs: Date.now() - startTime,
      })

      return result
    } catch (err) {
      await publishEvent("mission-plan-failed", {
        runtimeId, sessionId, missionId, error: (err as Error).message,
      })
      await telemetry?.recordEvent("reasoning.mission-plan-failed", {
        runtimeId, sessionId, missionId, error: (err as Error).message,
      })
      throw err
    }
  }

  static async decideWorkerAction(
    sessionId: string,
    missionId: string,
    objective: string,
    priority: string,
    additionalContext?: Record<string, unknown>,
  ): Promise<WorkerDecision> {
    this.requireInitialized()
    return ReasoningPipeline.decideWorkerAction(sessionId, missionId, objective, priority, additionalContext)
  }

  static async determineConnectorAction(
    sessionId: string,
    missionId: string,
    objective: string,
    priority: string,
    additionalContext?: Record<string, unknown>,
  ): Promise<ConnectorAction> {
    this.requireInitialized()
    return ReasoningPipeline.determineConnectorAction(sessionId, missionId, objective, priority, additionalContext)
  }

  static async determineBrowserAction(
    sessionId: string,
    missionId: string,
    objective: string,
    priority: string,
    additionalContext?: Record<string, unknown>,
  ): Promise<BrowserAction> {
    this.requireInitialized()
    return ReasoningPipeline.determineBrowserAction(sessionId, missionId, objective, priority, additionalContext)
  }

  static async generateVoiceResponse(
    sessionId: string,
    missionId: string,
    objective: string,
    priority: string,
    additionalContext?: Record<string, unknown>,
  ): Promise<VoiceResponse> {
    this.requireInitialized()
    return ReasoningPipeline.generateVoiceResponse(sessionId, missionId, objective, priority, additionalContext)
  }

  static async decideRecovery(
    sessionId: string,
    missionId: string,
    objective: string,
    priority: string,
    additionalContext?: Record<string, unknown>,
  ): Promise<RecoveryDecision> {
    this.requireInitialized()
    return ReasoningPipeline.decideRecovery(sessionId, missionId, objective, priority, additionalContext)
  }

  static async streamReasoning(
    sessionId: string,
    missionId: string,
    objective: string,
    priority: string,
    onChunk: (chunk: StreamingChunk) => void,
    additionalContext?: Record<string, unknown>,
  ): Promise<LLMResponse> {
    this.requireInitialized()
    const signal = await ReasoningStreamManager.createStream(sessionId)
    return ReasoningPipeline.execute(
      sessionId, missionId, "executive_reasoning", objective, priority,
      undefined, additionalContext, onChunk, signal,
    )
  }

  static async cancelStream(sessionId: string): Promise<boolean> {
    return ReasoningStreamManager.cancelStream(sessionId)
  }

  static async getMetrics(): Promise<ReasoningMetrics> {
    this.requireInitialized()
    return ReasoningPipeline.getMetrics()
  }

  static async getAuditStats(): Promise<{ totalInteractions: number; totalValidated: number; totalFailed: number; totalTokens: number }> {
    this.requireInitialized()
    return ReasoningAuditor.getStats()
  }

  static async getProviderAvailability(): Promise<Record<string, boolean>> {
    this.requireInitialized()
    return LLMProviderRegistry.getAvailability()
  }

  static async clearSession(sessionId: string): Promise<void> {
    await ReasoningContextBuilder.clearSession(sessionId)
    await ReasoningStreamManager.cancelStream(sessionId)
  }

  static getRuntimeId(): string {
    return runtimeId
  }

  static isInitialized(): boolean {
    return initialized
  }

  private static requireInitialized(): void {
    if (!initialized) {
      throw new Error("ReasoningRuntime not initialized. Call initialize() first.")
    }
  }
}
