import type { IntegrationRoute, IntegrationEvent } from "./types"
import { generateId } from "./shared"

const routes = new Map<string, IntegrationRoute>()
const events = new Map<string, IntegrationEvent>()

export const EventRoutingEngine = {
  async createRoute(
    name: string,
    sourceConnectorId: string,
    targetConnectorId: string,
    eventTypes: string[],
    transform: string | null = null,
  ): Promise<IntegrationRoute> {
    const id = generateId("route")
    const route: IntegrationRoute = {
      id,
      name,
      sourceConnectorId,
      targetConnectorId,
      eventTypes,
      transform,
      enabled: true,
      createdAt: new Date().toISOString(),
    }
    routes.set(id, route)
    return route
  },

  async publishRoute(routeId: string, eventType: string, payload: Record<string, unknown>, correlationId: string | null = null): Promise<IntegrationEvent> {
    const route = routes.get(routeId)
    if (!route) throw new Error(`Route not found: ${routeId}`)
    if (!route.enabled) throw new Error(`Route is disabled: ${routeId}`)
    if (!route.eventTypes.includes(eventType)) throw new Error(`Event type "${eventType}" not supported by route: ${routeId}`)

    const event: IntegrationEvent = {
      id: generateId("intev"),
      source: route.sourceConnectorId,
      type: eventType,
      payload,
      timestamp: new Date().toISOString(),
      correlationId,
    }
    events.set(event.id, event)
    return event
  },

  async subscribeRoute(sourceConnectorId: string, targetConnectorId: string, eventTypes: string[]): Promise<IntegrationRoute> {
    return EventRoutingEngine.createRoute(
      `sub-${sourceConnectorId}-${targetConnectorId}`,
      sourceConnectorId,
      targetConnectorId,
      eventTypes,
    )
  },

  async resolveDestination(eventType: string, sourceConnectorId: string): Promise<IntegrationRoute[]> {
    return Array.from(routes.values()).filter(
      (r) => r.sourceConnectorId === sourceConnectorId && r.eventTypes.includes(eventType) && r.enabled,
    )
  },

  async enableRoute(routeId: string): Promise<IntegrationRoute> {
    const route = routes.get(routeId)
    if (!route) throw new Error(`Route not found: ${routeId}`)
    const updated: IntegrationRoute = { ...route, enabled: true }
    routes.set(routeId, updated)
    return updated
  },

  async disableRoute(routeId: string): Promise<IntegrationRoute> {
    const route = routes.get(routeId)
    if (!route) throw new Error(`Route not found: ${routeId}`)
    const updated: IntegrationRoute = { ...route, enabled: false }
    routes.set(routeId, updated)
    return updated
  },

  async getRoute(routeId: string): Promise<IntegrationRoute | null> {
    return routes.get(routeId) ?? null
  },

  async listRoutes(connectorId?: string): Promise<IntegrationRoute[]> {
    let result = Array.from(routes.values())
    if (connectorId) result = result.filter((r) => r.sourceConnectorId === connectorId || r.targetConnectorId === connectorId)
    return result
  },

  async getEvents(source?: string): Promise<IntegrationEvent[]> {
    let result = Array.from(events.values())
    if (source) result = result.filter((e) => e.source === source)
    return result.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
  },
}
