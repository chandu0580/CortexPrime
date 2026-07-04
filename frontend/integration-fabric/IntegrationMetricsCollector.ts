import type { IntegrationMetrics } from "./types"
import { ConnectorRegistry } from "./ConnectorRegistry"
import { EndpointRegistry } from "./EndpointRegistry"
import { SynchronizationPlanner } from "./SynchronizationPlanner"
import { EventRoutingEngine } from "./EventRoutingEngine"
import { CredentialReferenceManager } from "./CredentialReferenceManager"

export const IntegrationMetricsCollector = {
  async collectAll(): Promise<IntegrationMetrics> {
    const connectors = await ConnectorRegistry.listConnectors()
    const endpoints = await EndpointRegistry.endpointCount()
    const syncPlans = await SynchronizationPlanner.listPlans()
    const routes = await EventRoutingEngine.listRoutes()
    const credentials = await CredentialReferenceManager.credentialCount()
    const events = await EventRoutingEngine.getEvents()

    return {
      totalConnectors: connectors.length,
      activeConnectors: connectors.filter((c) => c.state === "active").length,
      totalEndpoints: endpoints,
      totalSyncPlans: syncPlans.length,
      totalSyncJobs: syncPlans.reduce((sum, p) => sum + p.jobs.length, 0),
      totalRoutes: routes.length,
      totalCredentials: credentials,
      totalEvents: events.length,
    }
  },

  async collectConnectors(): Promise<{ total: number; active: number }> {
    const connectors = await ConnectorRegistry.listConnectors()
    return { total: connectors.length, active: connectors.filter((c) => c.state === "active").length }
  },

  async collectEndpoints(): Promise<number> {
    return EndpointRegistry.endpointCount()
  },

  async collectSyncPlans(): Promise<number> {
    const plans = await SynchronizationPlanner.listPlans()
    return plans.length
  },

  async collectRoutes(): Promise<number> {
    const routes = await EventRoutingEngine.listRoutes()
    return routes.length
  },

  async collectCredentials(): Promise<number> {
    return CredentialReferenceManager.credentialCount()
  },
}
