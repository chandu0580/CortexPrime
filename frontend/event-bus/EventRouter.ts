import type { EventEnvelope, EventSubscription, EventChannel, ChannelType } from "./types"
import { EventRegistry } from "./EventRegistry"
import { EventSubscriber } from "./EventSubscriber"
import { EventFilteringEngine } from "./EventFilteringEngine"

export const EventRouter = {
  async route(envelope: EventEnvelope): Promise<Array<{ subscription: EventSubscription; channel: EventChannel }>> {
    const routes: Array<{ subscription: EventSubscription; channel: EventChannel }> = []
    const allChannels = await EventRegistry.getAllChannels()

    for (const channel of allChannels) {
      if (!matchesChannelType(channel, envelope)) continue

      const subscriptions = await EventSubscriber.getSubscriptions(channel.id)
      for (const subscription of subscriptions) {
        const passes = await EventFilteringEngine.passes(subscription.filter, envelope.event)
        if (passes) {
          routes.push({ subscription, channel })
        }
      }
    }

    return routes
  },

  async routeToChannel(envelope: EventEnvelope, channelId: string): Promise<EventSubscription[]> {
    const subscriptions = await EventSubscriber.getSubscriptions(channelId)
    const matched: EventSubscription[] = []

    for (const sub of subscriptions) {
      const passes = await EventFilteringEngine.passes(sub.filter, envelope.event)
      if (passes) {
        matched.push(sub)
      }
    }

    return matched
  },
}

function matchesChannelType(channel: EventChannel, envelope: EventEnvelope): boolean {
  if (channel.name === envelope.channel) return true
  if (channel.type === "broadcast") return true
  if (channel.type === "direct") return channel.name === envelope.channel
  if (channel.type === "workqueue") return channel.name === envelope.channel
  return false
}
