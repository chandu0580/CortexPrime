import { RedisClient } from "./RedisClient"
import type { IEventBus } from "@/platform/interfaces"

export type MemoryEventType =
  | "memory.system.initialized"
  | "memory.system.shutdown"
  | "memory.session.created"
  | "memory.session.closed"
  | "memory.entry.stored"
  | "memory.entry.updated"
  | "memory.entry.deleted"
  | "memory.entry.expired"
  | "memory.concept.registered"
  | "memory.concept.updated"
  | "memory.procedure.stored"
  | "memory.procedure.updated"
  | "memory.association.created"
  | "memory.link.created"
  | "memory.graph.node.added"
  | "memory.graph.edge.added"
  | "memory.snapshot.created"
  | "memory.entries.expired"
  | "memory.mission.context-stored"

export interface MemoryEvent {
  type: MemoryEventType
  timestamp: string
  payload: Record<string, unknown>
}

export type MemoryEventCallback = (event: MemoryEvent) => void

const PUBSUB_CHANNEL = "memory:events"
const subscribers = new Map<string, Set<MemoryEventCallback>>()
let subscriptionActive = false

export const MemoryEventBus = {
  async publish(eventBus: IEventBus, type: MemoryEventType, payload: Record<string, unknown>): Promise<void> {
    const event: MemoryEvent = {
      type,
      timestamp: new Date().toISOString(),
      payload,
    }

    await eventBus.publish("memory", type, payload)

    const client = RedisClient.getClient()
    if (client) {
      try {
        await client.publish(PUBSUB_CHANNEL, JSON.stringify(event))
      } catch {
        // Pub/Sub publish failure is non-critical
      }
    }
  },

  async subscribe(callback: MemoryEventCallback): Promise<void> {
    const channelSubscribers = subscribers.get(PUBSUB_CHANNEL) ?? new Set()
    subscribers.set(PUBSUB_CHANNEL, channelSubscribers)
    channelSubscribers.add(callback)

    if (!subscriptionActive) {
      const client = RedisClient.getClient()
      if (client) {
        try {
          await client.subscribe(PUBSUB_CHANNEL)
          client.on("message", (channel: string, message: string) => {
            if (channel === PUBSUB_CHANNEL) {
              try {
                const event: MemoryEvent = JSON.parse(message)
                const channelSubs = subscribers.get(PUBSUB_CHANNEL)
                if (channelSubs) {
                  for (const sub of channelSubs) {
                    sub(event)
                  }
                }
              } catch {
                // Invalid message format
              }
            }
          })
          subscriptionActive = true
        } catch {
          // Subscription failure is non-critical
        }
      }
    }
  },

  async unsubscribe(callback: MemoryEventCallback): Promise<void> {
    const channelSubscribers = subscribers.get(PUBSUB_CHANNEL)
    if (channelSubscribers) {
      channelSubscribers.delete(callback)
      if (channelSubscribers.size === 0) {
        subscribers.delete(PUBSUB_CHANNEL)
        const client = RedisClient.getClient()
        if (client && subscriptionActive) {
          try {
            await client.unsubscribe(PUBSUB_CHANNEL)
            subscriptionActive = false
          } catch {
            // Unsubscribe failure is non-critical
          }
        }
      }
    }
  },

  async clearAll(): Promise<void> {
    subscribers.clear()
    subscriptionActive = false
  },
}
