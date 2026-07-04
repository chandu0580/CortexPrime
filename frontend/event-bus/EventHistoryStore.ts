import type { EventEnvelope, EventDelivery, EventHistoryEntry } from "./types"
import { EventDispatcher } from "./EventDispatcher"

const history = new Map<string, EventHistoryEntry>()

export const EventHistoryStore = {
  async record(envelope: EventEnvelope): Promise<EventHistoryEntry> {
    const existing = history.get(envelope.envelopeId)

    if (existing) {
      return existing
    }

    const entry: EventHistoryEntry = {
      envelope,
      deliveryCount: 0,
      completedDeliveries: 0,
      failedDeliveries: 0,
      firstAttemptedAt: new Date().toISOString(),
      lastAttemptedAt: new Date().toISOString(),
    }
    history.set(envelope.envelopeId, entry)

    await EventHistoryStore.updateDeliveryStats(envelope.envelopeId)
    return entry
  },

  async getEntry(envelopeId: string): Promise<EventHistoryEntry | null> {
    return history.get(envelopeId) ?? null
  },

  async getHistory(category?: string): Promise<EventHistoryEntry[]> {
    const entries = Array.from(history.values())
    if (category) {
      return entries.filter((e) => e.envelope.event.category === category)
    }
    return entries.sort((a, b) => b.firstAttemptedAt.localeCompare(a.firstAttemptedAt))
  },

  async replay(envelopeId: string): Promise<EventHistoryEntry | null> {
    const entry = history.get(envelopeId)
    if (!entry) return null
    return entry
  },

  async updateDeliveryStats(envelopeId: string): Promise<void> {
    const deliveries = await EventDispatcher.getDeliveriesByEnvelope(envelopeId)
    const entry = history.get(envelopeId)
    if (!entry) return

    const completed = deliveries.filter((d) => d.status === "delivered").length
    const failed = deliveries.filter((d) => d.status === "failed").length

    history.set(envelopeId, {
      ...entry,
      deliveryCount: deliveries.length,
      completedDeliveries: completed,
      failedDeliveries: failed,
      lastAttemptedAt: new Date().toISOString(),
    })
  },

  async clear(): Promise<void> {
    history.clear()
  },

  async size(): Promise<number> {
    return history.size
  },

  async getAllEntries(): Promise<EventHistoryEntry[]> {
    return Array.from(history.values())
  },
}
