import type { EventEnvelope, EventSubscription, EventChannel, EventDelivery, DeliveryStatus } from "./types"
import { EventSubscriber } from "./EventSubscriber"
import { generateId } from "./shared"

const deliveries = new Map<string, EventDelivery>()

export const EventDispatcher = {
  async dispatch(
    envelope: EventEnvelope,
    subscription: EventSubscription,
  ): Promise<EventDelivery> {
    const handler = await EventSubscriber.getHandler(subscription.handlerId)
    if (!handler) {
      return EventDispatcher.recordDelivery(envelope, subscription, "failed", "Handler not found")
    }

    const startTime = Date.now()

    try {
      await handler.handle(envelope.event)
      const duration = Date.now() - startTime
      return EventDispatcher.recordDelivery(envelope, subscription, "delivered", null, duration)
    } catch (err) {
      const duration = Date.now() - startTime
      const error = err instanceof Error ? err.message : String(err)
      return EventDispatcher.recordDelivery(envelope, subscription, "failed", error, duration)
    }
  },

  async dispatchBatch(
    envelope: EventEnvelope,
    subscriptions: EventSubscription[],
  ): Promise<EventDelivery[]> {
    const results: EventDelivery[] = []

    const sorted = [...subscriptions].sort((a, b) => {
      return a.createdAt.localeCompare(b.createdAt)
    })

    for (const sub of sorted) {
      const delivery = await EventDispatcher.dispatch(envelope, sub)
      results.push(delivery)
    }

    return results
  },

  async getDelivery(deliveryId: string): Promise<EventDelivery | null> {
    return deliveries.get(deliveryId) ?? null
  },

  async getDeliveriesByEnvelope(envelopeId: string): Promise<EventDelivery[]> {
    return Array.from(deliveries.values()).filter((d) => d.envelopeId === envelopeId)
  },

  async getDeliveredCount(): Promise<number> {
    return Array.from(deliveries.values()).filter((d) => d.status === "delivered").length
  },

  async getFailedCount(): Promise<number> {
    return Array.from(deliveries.values()).filter((d) => d.status === "failed").length
  },

  async getFilteredCount(): Promise<number> {
    return Array.from(deliveries.values()).filter((d) => d.status === "filtered").length
  },

  async recordDelivery(
    envelope: EventEnvelope,
    subscription: EventSubscription,
    status: DeliveryStatus,
    error: string | null = null,
    durationMs: number | null = null,
  ): Promise<EventDelivery> {
    const delivery: EventDelivery = {
      id: generateId("delivery"),
      envelopeId: envelope.envelopeId,
      subscriptionId: subscription.id,
      handlerId: subscription.handlerId,
      status,
      attemptedAt: new Date().toISOString(),
      completedAt: status !== "pending" ? new Date().toISOString() : null,
      error,
      durationMs,
    }
    deliveries.set(delivery.id, delivery)
    return delivery
  },
}
