import type {
  ProviderConfig, ProviderType, LLMResponse, MissionPlan, WorkerDecision,
  ConnectorAction, BrowserAction, VoiceResponse, RecoveryDecision, StreamingChunk,
  PromptType, ReasoningStage, ReasoningMetrics,
} from "./types"
import { LLMProviderRegistry } from "./LLMProviderAdapter"
import { ReasoningPromptTemplates } from "./prompt-templates"
import { ReasoningContextBuilder } from "./context-builder"
import { ReasoningResponseValidator, ReasoningAuditor } from "./response-validator"
import { ReasoningMetricsCollector } from "./reasoning-metrics"
import { generateId } from "@/cortex-runtime/shared"

export interface PipelineOptions {
  maxRetries: number
  retryDelayMs: number
  fallbackOrder: ProviderType[]
  streaming: boolean
}

const DEFAULT_OPTIONS: PipelineOptions = {
  maxRetries: 3,
  retryDelayMs: 1000,
  fallbackOrder: ["openai", "azure-openai", "anthropic", "gemini", "ollama"],
  streaming: false,
}

let pipelineOptions: PipelineOptions = { ...DEFAULT_OPTIONS }

export const ReasoningPipeline = {
  async initialize(options?: Partial<PipelineOptions>): Promise<void> {
    if (options) {
      pipelineOptions = { ...pipelineOptions, ...options }
    }
  },

  async execute(
    sessionId: string,
    missionId: string,
    promptType: PromptType,
    missionObjective: string,
    missionPriority: string,
    providerConfig?: ProviderConfig,
    additionalContext?: Record<string, unknown>,
    onChunk?: (chunk: StreamingChunk) => void,
    abortSignal?: AbortSignal,
  ): Promise<LLMResponse> {
    const updateStage = async (stage: ReasoningStage): Promise<void> => {
      await ReasoningMetricsCollector.recordStageStart(stage)
    }

    await updateStage("context_build")

    const context = await ReasoningContextBuilder.build(
      sessionId,
      missionId,
      missionObjective,
      missionPriority,
      additionalContext,
    )

    await updateStage("memory_retrieval")

    await updateStage("knowledge_retrieval")

    await updateStage("connector_context")

    await updateStage("prompt_construction")
    const prompt = ReasoningPromptTemplates.getTemplate(promptType, context)

    const provider = providerConfig ?? await LLMProviderRegistry.selectForCapability("reasoning")
    if (!provider) throw new Error("No LLM provider available")

    await updateStage("llm_invocation")

    let lastError: Error | null = null
    let response: LLMResponse | null = null

    for (const providerType of pipelineOptions.fallbackOrder) {
      if (abortSignal?.aborted) throw new DOMException("Aborted", "AbortError")

      const config = await this.findConfigByType(providerType)
      if (!config) continue

      for (let attempt = 0; attempt <= pipelineOptions.maxRetries; attempt++) {
        if (abortSignal?.aborted) throw new DOMException("Aborted", "AbortError")

        try {
          if (pipelineOptions.streaming && onChunk) {
            response = await LLMProviderRegistry.stream(config, prompt, onChunk, abortSignal)
          } else {
            response = await LLMProviderRegistry.generate(config, prompt, true)
          }

          await ReasoningMetricsCollector.recordRetry(providerType, attempt)
          lastError = null
          break
        } catch (err) {
          if ((err as Error).name === "AbortError") throw err

          lastError = err instanceof Error ? err : new Error(String(err))
          await ReasoningMetricsCollector.recordFailure(providerType)

          if (attempt < pipelineOptions.maxRetries) {
            await new Promise((r) => setTimeout(r, pipelineOptions.retryDelayMs * (attempt + 1)))
          }
        }
      }

      if (!lastError && response) break
    }

    if (lastError || !response) {
      throw lastError ?? new Error("All providers failed")
    }

    await updateStage("response_validation")
    const validated = await ReasoningResponseValidator.validate(response, promptType)

    if (!validated.valid) {
      response.structured = null
    }

    await updateStage("structured_output")
    response.structured = validated.parsed ?? null

    await ReasoningAuditor.record({
      id: generateId("audit"),
      sessionId,
      provider: response.provider,
      model: response.model,
      promptHash: this.hashString(prompt),
      promptPreview: prompt.substring(0, 200),
      responseHash: this.hashString(response.content),
      responsePreview: response.content.substring(0, 200),
      tokensUsed: response.tokensUsed,
      latencyMs: response.latencyMs,
      success: true,
      error: null,
      validated: validated.valid,
      schemaType: promptType,
    })

    await ReasoningContextBuilder.addToHistory(sessionId, `User: ${missionObjective}`)
    await ReasoningContextBuilder.addToHistory(sessionId, `Assistant: ${response.content}`)

    return response
  },

  async executeStructured<T>(
    sessionId: string,
    missionId: string,
    promptType: PromptType,
    missionObjective: string,
    missionPriority: string,
    providerConfig?: ProviderConfig,
    additionalContext?: Record<string, unknown>,
    abortSignal?: AbortSignal,
  ): Promise<T> {
    const response = await this.execute(
      sessionId, missionId, promptType, missionObjective, missionPriority,
      providerConfig, additionalContext, undefined, abortSignal,
    )

    const parsed = response.structured as T | null
    if (!parsed) throw new Error(`Failed to get structured output for ${promptType}`)
    return parsed
  },

  async planMission(
    sessionId: string,
    missionId: string,
    objective: string,
    priority: string,
    additionalContext?: Record<string, unknown>,
  ): Promise<MissionPlan> {
    return this.executeStructured<MissionPlan>(
      sessionId, missionId, "mission_planning", objective, priority, undefined, additionalContext,
    )
  },

  async decideWorkerAction(
    sessionId: string,
    missionId: string,
    objective: string,
    priority: string,
    additionalContext?: Record<string, unknown>,
  ): Promise<WorkerDecision> {
    return this.executeStructured<WorkerDecision>(
      sessionId, missionId, "executive_reasoning", objective, priority, undefined, additionalContext,
    )
  },

  async determineConnectorAction(
    sessionId: string,
    missionId: string,
    objective: string,
    priority: string,
    additionalContext?: Record<string, unknown>,
  ): Promise<ConnectorAction> {
    return this.executeStructured<ConnectorAction>(
      sessionId, missionId, "connector_action", objective, priority, undefined, additionalContext,
    )
  },

  async determineBrowserAction(
    sessionId: string,
    missionId: string,
    objective: string,
    priority: string,
    additionalContext?: Record<string, unknown>,
  ): Promise<BrowserAction> {
    return this.executeStructured<BrowserAction>(
      sessionId, missionId, "browser_automation", objective, priority, undefined, additionalContext,
    )
  },

  async generateVoiceResponse(
    sessionId: string,
    missionId: string,
    objective: string,
    priority: string,
    additionalContext?: Record<string, unknown>,
  ): Promise<VoiceResponse> {
    return this.executeStructured<VoiceResponse>(
      sessionId, missionId, "executive_reasoning", objective, priority, undefined, additionalContext,
    )
  },

  async decideRecovery(
    sessionId: string,
    missionId: string,
    objective: string,
    priority: string,
    additionalContext?: Record<string, unknown>,
  ): Promise<RecoveryDecision> {
    return this.executeStructured<RecoveryDecision>(
      sessionId, missionId, "incident_response", objective, priority, undefined, additionalContext,
    )
  },

  async getMetrics(): Promise<ReasoningMetrics> {
    return ReasoningMetricsCollector.collect()
  },

  async findConfigByType(type: ProviderType): Promise<ProviderConfig | null> {
    const configs = await LLMProviderRegistry.listProviders()
    return configs.find((c) => c.type === type) ?? null
  },

  hashString(str: string): string {
    let hash = 0
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i)
      hash = ((hash << 5) - hash) + char
      hash = hash & hash
    }
    return Math.abs(hash).toString(16)
  },
}
