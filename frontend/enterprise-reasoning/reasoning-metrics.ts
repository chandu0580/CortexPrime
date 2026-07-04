import type { ReasoningMetrics, ProviderType, TokenUsage, ReasoningStage } from "./types"

interface CollectedMetrics {
  totalRequests: number
  totalTokens: number
  totalCost: number
  totalLatencyMs: number
  requestsByProvider: Record<string, number>
  tokensByProvider: Record<string, number>
  costByProvider: Record<string, number>
  failuresByProvider: Record<string, number>
  retriesByProvider: Record<string, number>
  stageTimings: Record<string, number>
}

let metrics: CollectedMetrics = {
  totalRequests: 0,
  totalTokens: 0,
  totalCost: 0,
  totalLatencyMs: 0,
  requestsByProvider: {},
  tokensByProvider: {},
  costByProvider: {},
  failuresByProvider: {},
  retriesByProvider: {},
  stageTimings: {},
}

export const ReasoningMetricsCollector = {
  async initialize(): Promise<void> {
    metrics = {
      totalRequests: 0,
      totalTokens: 0,
      totalCost: 0,
      totalLatencyMs: 0,
      requestsByProvider: {},
      tokensByProvider: {},
      costByProvider: {},
      failuresByProvider: {},
      retriesByProvider: {},
      stageTimings: {},
    }
  },

  async recordRequest(provider: ProviderType, tokens: TokenUsage, latencyMs: number, cost: number, success: boolean): Promise<void> {
    const providerKey = provider
    metrics.totalRequests++
    metrics.totalTokens += tokens.total
    metrics.totalCost += cost
    metrics.totalLatencyMs += latencyMs

    metrics.requestsByProvider[providerKey] = (metrics.requestsByProvider[providerKey] ?? 0) + 1
    metrics.tokensByProvider[providerKey] = (metrics.tokensByProvider[providerKey] ?? 0) + tokens.total
    metrics.costByProvider[providerKey] = (metrics.costByProvider[providerKey] ?? 0) + cost

    if (!success) {
      metrics.failuresByProvider[providerKey] = (metrics.failuresByProvider[providerKey] ?? 0) + 1
    }
  },

  async recordFailure(provider: ProviderType): Promise<void> {
    metrics.failuresByProvider[provider] = (metrics.failuresByProvider[provider] ?? 0) + 1
  },

  async recordRetry(provider: ProviderType, attempt: number): Promise<void> {
    if (attempt > 0) {
      metrics.retriesByProvider[provider] = (metrics.retriesByProvider[provider] ?? 0) + 1
    }
  },

  async recordStageStart(stage: ReasoningStage): Promise<void> {
    metrics.stageTimings[`${stage}_start`] = Date.now()
  },

  async collect(): Promise<ReasoningMetrics> {
    const configs = (await (await import("./LLMProviderAdapter")).LLMProviderRegistry.listProviders())
    const availability: Record<string, boolean> = {}
    for (const c of configs) {
      availability[`${c.type}:${c.model}`] = true
    }

    return {
      totalRequests: metrics.totalRequests,
      totalTokens: metrics.totalTokens,
      totalCost: Math.round(metrics.totalCost * 1000000) / 1000000,
      averageLatencyMs: metrics.totalRequests > 0 ? Math.round(metrics.totalLatencyMs / metrics.totalRequests) : 0,
      requestsByProvider: { ...metrics.requestsByProvider },
      tokensByProvider: { ...metrics.tokensByProvider },
      failuresByProvider: { ...metrics.failuresByProvider },
      retriesByProvider: { ...metrics.retriesByProvider },
      providerAvailability: availability,
      lastUpdated: new Date().toISOString(),
    }
  },

  async reset(): Promise<void> {
    await this.initialize()
  },
}
