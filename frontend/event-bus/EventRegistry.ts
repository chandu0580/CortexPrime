import type { EventChannel, EventCategory, ChannelType } from "./types"
import { generateId } from "./shared"

const channels = new Map<string, EventChannel>()

export const EventRegistry = {
  async registerChannel(
    name: string,
    category: EventCategory,
    type: ChannelType = "broadcast",
    description: string = "",
  ): Promise<EventChannel> {
    const channel: EventChannel = {
      id: generateId("channel"),
      name,
      category,
      type,
      description,
      created_at: new Date().toISOString(),
    }
    channels.set(channel.id, channel)
    return channel
  },

  async getChannel(channelId: string): Promise<EventChannel | null> {
    return channels.get(channelId) ?? null
  },

  async findChannel(name: string): Promise<EventChannel | null> {
    return Array.from(channels.values()).find((c) => c.name === name) ?? null
  },

  async getChannelsByCategory(category: EventCategory): Promise<EventChannel[]> {
    return Array.from(channels.values()).filter((c) => c.category === category)
  },

  async getAllChannels(): Promise<EventChannel[]> {
    return Array.from(channels.values())
  },

  async channelCount(): Promise<number> {
    return channels.size
  },
}
