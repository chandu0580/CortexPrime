import type { IntegrationConnector, IntegrationRoute, IntegrationEvent, IntegrationPolicy, IntegrationDecision, SynchronizationPlan, SynchronizationJob, ConnectorEndpoint, IntegrationMetrics, IntegrationHealth, IntegrationCapabilityDefinition, ValidationResult, HealthSnapshot, ConnectorCapability, CredentialReference, IntegrationCheckpoint } from "./types"
import type { ConnectorState, ConnectorType, EndpointType, SynchronizationState, IntegrationResult } from "./types"
import { ConnectorRegistry } from "./ConnectorRegistry"
import { ConnectorLifecycleManager } from "./ConnectorLifecycleManager"
import { ConnectorCapabilityResolver } from "./ConnectorCapabilityResolver"
import { EndpointRegistry } from "./EndpointRegistry"
import { SynchronizationPlanner } from "./SynchronizationPlanner"
import { CredentialReferenceManager } from "./CredentialReferenceManager"
import { EventRoutingEngine } from "./EventRoutingEngine"
import { IntegrationPolicyEngine } from "./IntegrationPolicyEngine"
import { IntegrationValidationEngine } from "./IntegrationValidationEngine"
import { IntegrationMetricsCollector } from "./IntegrationMetricsCollector"
import { IntegrationHealthManager } from "./IntegrationHealthManager"
import { IntegrationCapability } from "./IntegrationCapability"
import { cortexEventBus } from "@/event-bus/cortexEventBus"

export const IntegrationFabric = {
  async register(type: "connector" | "endpoint" | "route" | "policy", data: Record<string, unknown>): Promise<Record<string, unknown>> {
    switch (type) {
      case "connector": {
        const { name, connectorType, descriptor, capabilities, endpoints, metadata } = data as unknown as {
          name: string
          connectorType: ConnectorType
          descriptor: import("./types").ConnectorDescriptor
          capabilities?: ConnectorCapability[]
          endpoints?: ConnectorEndpoint[]
          metadata?: Record<string, unknown>
        }
        const connector = await ConnectorRegistry.registerConnector(name, connectorType, descriptor, capabilities, endpoints, metadata)
        await cortexEventBus.publish("integration", "analytics", "integration.connector.registered", "IntegrationFabric", {
          connectorId: connector.id,
          name,
          type: connectorType,
        }, "low", connector.id)
        return { connector }
      }
      case "endpoint": {
        const { connectorId, name, endpointType, url, credentialRef, config } = data as unknown as {
          connectorId: string
          name: string
          endpointType: EndpointType
          url: string
          credentialRef?: string
          config?: Record<string, unknown>
        }
        const endpoint = await EndpointRegistry.registerEndpoint(connectorId, name, endpointType, url, credentialRef ?? null, config)
        await cortexEventBus.publish("integration", "analytics", "integration.endpoint.registered", "IntegrationFabric", {
          endpointId: endpoint.id,
          connectorId,
          name,
          type: endpointType,
        }, "low", connectorId)
        return { endpoint }
      }
      case "route": {
        const { name: routeName, sourceConnectorId, targetConnectorId, eventTypes, transform } = data as unknown as {
          name: string
          sourceConnectorId: string
          targetConnectorId: string
          eventTypes: string[]
          transform?: string
        }
        const route = await EventRoutingEngine.createRoute(routeName, sourceConnectorId, targetConnectorId, eventTypes, transform)
        await cortexEventBus.publish("integration", "analytics", "integration.route.created", "IntegrationFabric", {
          routeId: route.id,
          sourceConnectorId,
          targetConnectorId,
          eventTypes,
        }, "low", "integration")
        return { route }
      }
      case "policy": {
        const policyData = data as unknown as Omit<IntegrationPolicy, "id">
        const policy = await IntegrationPolicyEngine.registerPolicy(policyData)
        return { policy }
      }
      default:
        throw new Error(`Unknown registration type: ${type}`)
    }
  },

  async synchronize(planId: string, actions?: string[]): Promise<{ plan: SynchronizationPlan; jobs: SynchronizationJob[] }> {
    let plan = await SynchronizationPlanner.getPlan(planId)
    if (!plan) throw new Error(`Synchronization plan not found: ${planId}`)

    if (actions) {
      plan = await SynchronizationPlanner.scheduleSynchronization(planId, actions)
    }

    await cortexEventBus.publish("integration", "analytics", "integration.sync.started", "IntegrationFabric", {
      planId,
      connectorId: plan.connectorId,
      jobCount: plan.jobs.length,
    }, "normal", plan.connectorId)

    return { plan, jobs: plan.jobs }
  },

  async completeSyncJob(planId: string, jobId: string, result: IntegrationResult, details?: string): Promise<SynchronizationJob> {
    const job = await SynchronizationPlanner.completeJob(planId, jobId, result, details)
    if (result === "failure") {
      await IntegrationHealthManager.recordFailedSync()
    }
    return job
  },

  async validate(type: string, data: Record<string, unknown>): Promise<ValidationResult> {
    let result: ValidationResult

    switch (type) {
      case "connector_integrity": {
        const connector = data as unknown as IntegrationConnector
        result = await IntegrationValidationEngine.validateConnectorIntegrity(connector)
        break
      }
      case "endpoint_consistency": {
        const endpoints = data as unknown as ConnectorEndpoint[]
        result = await IntegrationValidationEngine.validateEndpointConsistency(endpoints)
        break
      }
      case "sync_readiness": {
        const plan = data as unknown as SynchronizationPlan
        result = await IntegrationValidationEngine.validateSynchronizationReadiness(plan)
        break
      }
      case "routing_correctness": {
        const routes = data as unknown as IntegrationRoute[]
        result = await IntegrationValidationEngine.validateRoutingCorrectness(routes)
        break
      }
      case "credential_references": {
        const refs = data as unknown as CredentialReference[]
        result = await IntegrationValidationEngine.validateCredentialReferences(refs)
        break
      }
      default:
        throw new Error(`Unknown validation type: ${type}`)
    }

    await cortexEventBus.publish("integration", "analytics", `integration.validate.${type}`, "IntegrationFabric", {
      validationId: result.id,
      passed: result.passed,
      errors: result.errors.length,
    }, result.passed ? "low" : "high", "integration")

    return result
  },

  async publish(routeId: string, eventType: string, payload: Record<string, unknown>, correlationId?: string): Promise<IntegrationEvent> {
    const event = await EventRoutingEngine.publishRoute(routeId, eventType, payload, correlationId ?? null)

    await cortexEventBus.publish("integration", "analytics", "integration.event.published", "IntegrationFabric", {
      eventId: event.id,
      routeId,
      eventType,
    }, "low", "integration")

    return event
  },

  async subscribe(sourceConnectorId: string, targetConnectorId: string, eventTypes: string[]): Promise<IntegrationRoute> {
    const route = await EventRoutingEngine.subscribeRoute(sourceConnectorId, targetConnectorId, eventTypes)

    await cortexEventBus.publish("integration", "analytics", "integration.route.subscribed", "IntegrationFabric", {
      routeId: route.id,
      sourceConnectorId,
      targetConnectorId,
      eventTypes,
    }, "low", "integration")

    return route
  },

  async metrics(): Promise<IntegrationMetrics> {
    return IntegrationMetricsCollector.collectAll()
  },

  async health(): Promise<IntegrationHealth> {
    return IntegrationHealthManager.getHealth()
  },

  async initializeConnector(connectorId: string): Promise<IntegrationConnector> {
    const connector = await ConnectorLifecycleManager.initializeConnector(connectorId)
    await cortexEventBus.publish("integration", "analytics", "integration.connector.initialized", "IntegrationFabric", {
      connectorId,
    }, "low", connectorId)
    return connector
  },

  async activateConnector(connectorId: string): Promise<IntegrationConnector> {
    const connector = await ConnectorLifecycleManager.activateConnector(connectorId)
    await cortexEventBus.publish("integration", "analytics", "integration.connector.activated", "IntegrationFabric", {
      connectorId,
    }, "low", connectorId)
    return connector
  },

  async pauseConnector(connectorId: string): Promise<IntegrationConnector> {
    const connector = await ConnectorLifecycleManager.pauseConnector(connectorId)
    await IntegrationHealthManager.recordInactiveConnector()
    await cortexEventBus.publish("integration", "analytics", "integration.connector.paused", "IntegrationFabric", {
      connectorId,
    }, "normal", connectorId)
    return connector
  },

  async resolveCapabilities(connectorId: string): Promise<ConnectorCapability[]> {
    const connector = await ConnectorRegistry.getConnector(connectorId)
    if (!connector) throw new Error(`Connector not found: ${connectorId}`)
    return ConnectorCapabilityResolver.resolveCapabilities(connector.capabilities)
  },

  async registerCredential(name: string, connectorId: string, type: string, reference: string, endpointId?: string, expiresAt?: string): Promise<CredentialReference> {
    const ref = await CredentialReferenceManager.registerReference(name, connectorId, type, reference, endpointId ?? null, expiresAt ?? null)
    await cortexEventBus.publish("integration", "analytics", "integration.credential.registered", "IntegrationFabric", {
      credentialId: ref.id,
      connectorId,
      name,
      type,
    }, "low", connectorId)
    return ref
  },

  async getCapabilities(): Promise<IntegrationCapabilityDefinition[]> {
    return IntegrationCapability.list()
  },

  async isCapabilityEnabled(name: string): Promise<boolean> {
    return IntegrationCapability.isEnabled(name)
  },

  async snapshot(component: string, metrics: Record<string, number>, details?: string): Promise<HealthSnapshot> {
    return IntegrationHealthManager.snapshot(component, metrics, details)
  },

  async listConnectors(type?: ConnectorType, state?: ConnectorState): Promise<IntegrationConnector[]> {
    return ConnectorRegistry.listConnectors(type, state)
  },

  async listEndpoints(connectorId?: string): Promise<ConnectorEndpoint[]> {
    return EndpointRegistry.queryEndpoints(connectorId)
  },

  async listSyncPlans(connectorId?: string): Promise<SynchronizationPlan[]> {
    return SynchronizationPlanner.listPlans(connectorId)
  },

  async listCredentials(connectorId?: string): Promise<CredentialReference[]> {
    return CredentialReferenceManager.listReferences(connectorId)
  },
}
