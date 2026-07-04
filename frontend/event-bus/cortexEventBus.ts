import type {
  CortexEvent,
  EventEnvelope,
  EventChannel,
  EventSubscription,
  EventHandler,
  EventFilter,
  EventDelivery,
  EventHistoryEntry,
  EventMetrics,
  EventCategory,
  EventPriority,
  ChannelType,
} from "./types"
import { EventRegistry } from "./EventRegistry"
import { EventPublisher } from "./EventPublisher"
import { EventSubscriber } from "./EventSubscriber"
import { EventRouter } from "./EventRouter"
import { EventDispatcher } from "./EventDispatcher"
import { EventHistoryStore } from "./EventHistoryStore"
import { EventFilteringEngine } from "./EventFilteringEngine"
import { EventMetricsCollector } from "./EventMetricsCollector"

export const cortexEventBus = {
  async publish(
    channelName: string,
    category: EventCategory,
    type: string,
    source: string,
    data: Record<string, unknown>,
    priority: EventPriority = "normal",
    correlationId?: string,
  ): Promise<{ envelope: EventEnvelope; deliveries: EventDelivery[] }> {
    let channel = await EventRegistry.findChannel(channelName)
    if (!channel) {
      channel = await EventRegistry.registerChannel(channelName, category, "broadcast", `Auto-created channel for ${channelName}`)
    }

    const envelope = await EventPublisher.publish(channel, category, type, source, data, priority, correlationId)
    await EventHistoryStore.record(envelope)

    const routes = await EventRouter.route(envelope)
    const deliveries: EventDelivery[] = []

    for (const { subscription } of routes) {
      const delivery = await EventDispatcher.dispatch(envelope, subscription)
      deliveries.push(delivery)
    }

    await EventHistoryStore.updateDeliveryStats(envelope.envelopeId)

    return { envelope, deliveries }
  },

  async subscribe(
    channelName: string,
    handlerName: string,
    handlerDescription: string,
    handlerFn: (event: CortexEvent) => Promise<void>,
    filter?: { categories?: EventCategory[]; types?: string[]; sources?: string[]; priorityMin?: EventPriority },
  ): Promise<{ subscription: EventSubscription; handler: EventHandler }> {
    let channel = await EventRegistry.findChannel(channelName)
    if (!channel) {
      channel = await EventRegistry.registerChannel(channelName, "kernel", "broadcast", `Auto-created channel for ${channelName}`)
    }

    const handler = await EventSubscriber.registerHandler(handlerName, handlerDescription, handlerFn)
    let eventFilter: EventFilter | null = null

    if (filter) {
      eventFilter = await EventFilteringEngine.createFilter(
        filter.categories ?? null,
        filter.types ?? null,
        filter.sources ?? null,
        filter.priorityMin ?? null,
      )
    }

    const subscription = await EventSubscriber.subscribe(channel.id, handler.id, eventFilter)
    return { subscription, handler }
  },

  async unsubscribe(subscriptionId: string): Promise<void> {
    return EventSubscriber.unsubscribe(subscriptionId)
  },

  async dispatch(
    envelopeId: string,
    subscriptionId: string,
  ): Promise<EventDelivery> {
    const envelope = await EventPublisher.getEnvelope(envelopeId)
    if (!envelope) throw new Error(`Envelope not found: ${envelopeId}`)

    const subs = await EventSubscriber.getAllSubscriptions()
    const subscription = subs.find((s) => s.id === subscriptionId)
    if (!subscription) throw new Error(`Subscription not found: ${subscriptionId}`)

    return EventDispatcher.dispatch(envelope, subscription)
  },

  async route(
    envelopeId: string,
  ): Promise<Array<{ subscription: EventSubscription; channel: EventChannel }>> {
    const envelope = await EventPublisher.getEnvelope(envelopeId)
    if (!envelope) throw new Error(`Envelope not found: ${envelopeId}`)
    return EventRouter.route(envelope)
  },

  async filter(
    events: CortexEvent[],
    categories?: EventCategory[],
    types?: string[],
    sources?: string[],
  ): Promise<CortexEvent[]> {
    const filter = await EventFilteringEngine.createFilter(categories ?? null, types ?? null, sources ?? null)
    return EventFilteringEngine.filterEvents(events, filter)
  },

  async replay(envelopeId: string): Promise<EventHistoryEntry | null> {
    return EventHistoryStore.replay(envelopeId)
  },

  async history(category?: string): Promise<EventHistoryEntry[]> {
    return EventHistoryStore.getHistory(category)
  },

  async metrics(): Promise<EventMetrics> {
    return EventMetricsCollector.collectMetrics()
  },

  async clear(): Promise<void> {
    return EventHistoryStore.clear()
  },
}
