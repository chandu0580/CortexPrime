import type { CorrelationContext } from "./types"
import { generateId } from "./shared"

const correlations = new Map<string, CorrelationContext>()

export const CorrelationManager = {
  async createCorrelation(sessionId: string, parentCorrelationId: string | null = null): Promise<CorrelationContext> {
    const id = generateId("corr")
    const corr: CorrelationContext = {
      id,
      sessionId,
      parentCorrelationId,
      engineIds: [],
      startedAt: new Date().toISOString(),
      hops: [],
    }
    correlations.set(id, corr)
    return corr
  },

  async getCorrelation(id: string): Promise<CorrelationContext | null> {
    return correlations.get(id) ?? null
  },

  async addEngineHop(correlationId: string, engineId: string): Promise<CorrelationContext> {
    const corr = correlations.get(correlationId)
    if (!corr) throw new Error(`Correlation not found: ${correlationId}`)
    const updated: CorrelationContext = {
      ...corr,
      engineIds: [...corr.engineIds, engineId],
      hops: [...corr.hops, `${engineId}@${new Date().toISOString()}`],
    }
    correlations.set(correlationId, updated)
    return updated
  },

  async getCorrelationChain(correlationId: string): Promise<CorrelationContext[]> {
    const chain: CorrelationContext[] = []
    let current = correlations.get(correlationId)
    while (current) {
      chain.push(current)
      if (current.parentCorrelationId) {
        current = correlations.get(current.parentCorrelationId) ?? undefined
      } else {
        current = undefined
      }
    }
    return chain
  },

  async getSessionCorrelations(sessionId: string): Promise<CorrelationContext[]> {
    return Array.from(correlations.values()).filter((c) => c.sessionId === sessionId)
  },

  async closeCorrelation(correlationId: string): Promise<void> {
    const corr = correlations.get(correlationId)
    if (corr) {
      correlations.set(correlationId, {
        ...corr,
        hops: [...corr.hops, `closed@${new Date().toISOString()}`],
      })
    }
  },
}
