import type { EventSubscription, EventHandler, EventFilter } from "./types"
import { generateId } from "./shared"

const subscriptions = new Map<string, EventSubscription>()
const handlers = new Map<string, EventHandler>()

export const EventSubscriber = {
  async registerHandler(name: string, description: string, handle: (event: import("./types").CortexEvent) => Promise<void>): Promise<EventHandler> {
    const handler: EventHandler = {
      id: generateId("handler"),
      name,
      description,
      handle,
    }
    handlers.set(handler.id, handler)
    return handler
  },

  async getHandler(handlerId: string): Promise<EventHandler | null> {
    return handlers.get(handlerId) ?? null
  },

  async getAllHandlers(): Promise<EventHandler[]> {
    return Array.from(handlers.values())
  },

  async handlerCount(): Promise<number> {
    return handlers.size
  },

  async subscribe(channelId: string, handlerId: string, filter: EventFilter | null = null): Promise<EventSubscription> {
    const handler = handlers.get(handlerId)
    if (!handler) throw new Error(`Handler not found: ${handlerId}`)

    const subscription: EventSubscription = {
      id: generateId("subscription"),
      channelId,
      handlerId,
      handlerName: handler.name,
      filter,
      createdAt: new Date().toISOString(),
      active: true,
    }
    subscriptions.set(subscription.id, subscription)
    return subscription
  },

  async unsubscribe(subscriptionId: string): Promise<void> {
    const sub = subscriptions.get(subscriptionId)
    if (sub) {
      subscriptions.set(subscriptionId, { ...sub, active: false })
    }
  },

  async getSubscriptions(channelId: string): Promise<EventSubscription[]> {
    return Array.from(subscriptions.values()).filter(
      (s) => s.channelId === channelId && s.active,
    )
  },

  async getAllSubscriptions(): Promise<EventSubscription[]> {
    return Array.from(subscriptions.values()).filter((s) => s.active)
  },

  async subscriptionCount(): Promise<number> {
    return (await EventSubscriber.getAllSubscriptions()).length
  },
}
