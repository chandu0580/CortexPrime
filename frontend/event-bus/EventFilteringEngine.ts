import type { EventFilter, CortexEvent, EventCategory, EventPriority } from "./types"
import { generateId } from "./shared"

const filters = new Map<string, EventFilter>()

const priorityRank: Record<EventPriority, number> = {
  critical: 4,
  high: 3,
  normal: 2,
  low: 1,
}

export const EventFilteringEngine = {
  async createFilter(
    categories: EventCategory[] | null = null,
    types: string[] | null = null,
    sources: string[] | null = null,
    priorityMin: EventPriority | null = null,
  ): Promise<EventFilter> {
    const filter: EventFilter = {
      id: generateId("filter"),
      categories,
      types,
      sources,
      priorityMin,
    }
    filters.set(filter.id, filter)
    return filter
  },

  async getFilter(filterId: string): Promise<EventFilter | null> {
    return filters.get(filterId) ?? null
  },

  async passes(filter: EventFilter | null, event: CortexEvent, eventPriority?: EventPriority): Promise<boolean> {
    if (!filter) return true

    if (filter.categories && filter.categories.length > 0) {
      if (!filter.categories.includes(event.category)) return false
    }

    if (filter.types && filter.types.length > 0) {
      if (!filter.types.includes(event.type)) return false
    }

    if (filter.sources && filter.sources.length > 0) {
      if (!filter.sources.includes(event.source)) return false
    }

    if (filter.priorityMin && eventPriority) {
      const minRank = priorityRank[filter.priorityMin]
      const eventRank = priorityRank[eventPriority]
      if (eventRank < minRank) return false
    }

    return true
  },

  async filterEvents(
    events: CortexEvent[],
    filter: EventFilter,
    priorities?: Map<string, EventPriority>,
  ): Promise<CortexEvent[]> {
    const results: CortexEvent[] = []
    for (const event of events) {
      const ep = priorities?.get(event.id)
      if (await EventFilteringEngine.passes(filter, event, ep)) {
        results.push(event)
      }
    }
    return results
  },
}
