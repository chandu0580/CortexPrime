import type { EventMetrics, EventCategory } from "./types"
import { EventRegistry } from "./EventRegistry"
import { EventSubscriber } from "./EventSubscriber"
import { EventDispatcher } from "./EventDispatcher"
import { EventPublisher } from "./EventPublisher"
import { EventHistoryStore } from "./EventHistoryStore"

export const EventMetricsCollector = {
  async collectMetrics(): Promise<EventMetrics> {
    const totalPublished = await EventPublisher.getPublishedCount()
    const totalDelivered = await EventDispatcher.getDeliveredCount()
    const totalFailed = await EventDispatcher.getFailedCount()
    const totalFiltered = await EventDispatcher.getFilteredCount()
    const activeSubscriptions = await EventSubscriber.subscriptionCount()
    const activeHandlers = await EventSubscriber.handlerCount()
    const registeredChannels = await EventRegistry.channelCount()
    const historySize = await EventHistoryStore.size()

    const historyEntries = await EventHistoryStore.getAllEntries()
    const eventsByCategory: Record<string, number> = {}
    for (const entry of historyEntries) {
      const cat = entry.envelope.event.category
      eventsByCategory[cat] = (eventsByCategory[cat] ?? 0) + 1
    }

    const allDeliveries = historyEntries.reduce((sum, e) => sum + e.deliveryCount, 0)

    return {
      totalPublished,
      totalDelivered,
      totalFailed,
      totalFiltered,
      activeSubscriptions,
      activeHandlers,
      registeredChannels,
      historySize,
      eventsByCategory,
      averageDeliveryMs: allDeliveries > 0 ? 0 : 0,
    }
  },
}
