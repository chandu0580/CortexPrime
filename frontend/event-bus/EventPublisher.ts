import type { CortexEvent, EventEnvelope, EventChannel, EventPriority, EventCategory } from "./types"
import { generateId } from "./shared"

const published = new Map<string, EventEnvelope>()

export const EventPublisher = {
  async publish(
    channel: EventChannel,
    category: EventCategory,
    type: string,
    source: string,
    data: Record<string, unknown>,
    priority: EventPriority = "normal",
    correlationId: string = generateId("corr"),
    ttl: number = 300000,
  ): Promise<EventEnvelope> {
    const event: CortexEvent = {
      id: generateId("event"),
      category,
      type,
      source,
      data,
      timestamp: new Date().toISOString(),
    }

    const envelope: EventEnvelope = {
      event,
      envelopeId: generateId("envelope"),
      correlationId,
      channel: channel.name,
      priority,
      ttl,
      publishedAt: new Date().toISOString(),
    }

    published.set(envelope.envelopeId, envelope)
    return envelope
  },

  async getEnvelope(envelopeId: string): Promise<EventEnvelope | null> {
    return published.get(envelopeId) ?? null
  },

  async getEnvelopesByCorrelation(correlationId: string): Promise<EventEnvelope[]> {
    return Array.from(published.values()).filter((e) => e.correlationId === correlationId)
  },

  async getPublishedCount(): Promise<number> {
    return published.size
  },
}
