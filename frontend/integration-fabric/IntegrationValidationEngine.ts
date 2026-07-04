import type { ValidationResult, IntegrationConnector, ConnectorEndpoint, SynchronizationPlan, IntegrationRoute, CredentialReference } from "./types"
import { generateId } from "./shared"

const validations = new Map<string, ValidationResult>()

export const IntegrationValidationEngine = {
  async validateConnectorIntegrity(connector: IntegrationConnector): Promise<ValidationResult> {
    const errors: string[] = []
    const warnings: string[] = []

    if (!connector.id) errors.push("Connector missing id")
    if (!connector.name) errors.push("Connector missing name")
    if (!connector.descriptor) errors.push("Connector missing descriptor")
    if (!connector.descriptor?.name) errors.push("Connector descriptor missing name")

    if (connector.capabilities.length === 0) warnings.push("Connector has no capabilities registered")
    if (connector.endpoints.length === 0) warnings.push("Connector has no endpoints registered")

    const result: ValidationResult = {
      id: generateId("ival"),
      type: "connector_integrity",
      passed: errors.length === 0,
      errors,
      warnings,
      details: { connectorId: connector.id, endpointCount: connector.endpoints.length, capabilityCount: connector.capabilities.length },
    }
    validations.set(result.id, result)
    return result
  },

  async validateEndpointConsistency(endpoints: ConnectorEndpoint[]): Promise<ValidationResult> {
    const errors: string[] = []
    const warnings: string[] = []

    for (const ep of endpoints) {
      if (!ep.id) errors.push("Endpoint missing id")
      if (!ep.connectorId) errors.push(`Endpoint ${ep.id} missing connectorId`)
      if (!ep.name) errors.push(`Endpoint ${ep.id} missing name`)
      if (!ep.url) errors.push(`Endpoint ${ep.id} missing url`)
    }

    if (endpoints.length === 0) warnings.push("No endpoints to validate")

    const result: ValidationResult = {
      id: generateId("ival"),
      type: "endpoint_consistency",
      passed: errors.length === 0,
      errors,
      warnings,
      details: { endpointCount: endpoints.length },
    }
    validations.set(result.id, result)
    return result
  },

  async validateSynchronizationReadiness(plan: SynchronizationPlan): Promise<ValidationResult> {
    const errors: string[] = []
    const warnings: string[] = []

    if (!plan.id) errors.push("Synchronization plan missing id")
    if (!plan.sourceEndpointId) errors.push("Plan missing source endpoint")
    if (!plan.targetEndpointId) errors.push("Plan missing target endpoint")
    if (plan.jobs.length === 0) warnings.push("Plan has no jobs scheduled")

    const result: ValidationResult = {
      id: generateId("ival"),
      type: "sync_readiness",
      passed: errors.length === 0,
      errors,
      warnings,
      details: { planId: plan.id, jobCount: plan.jobs.length },
    }
    validations.set(result.id, result)
    return result
  },

  async validateRoutingCorrectness(routes: IntegrationRoute[]): Promise<ValidationResult> {
    const errors: string[] = []
    const warnings: string[] = []

    for (const route of routes) {
      if (!route.id) errors.push("Route missing id")
      if (!route.sourceConnectorId) errors.push(`Route ${route.id} missing source connector`)
      if (!route.targetConnectorId) errors.push(`Route ${route.id} missing target connector`)
      if (route.eventTypes.length === 0) errors.push(`Route ${route.id} has no event types`)
    }

    if (routes.length === 0) warnings.push("No routes to validate")

    const result: ValidationResult = {
      id: generateId("ival"),
      type: "routing_correctness",
      passed: errors.length === 0,
      errors,
      warnings,
      details: { routeCount: routes.length },
    }
    validations.set(result.id, result)
    return result
  },

  async validateCredentialReferences(refs: CredentialReference[]): Promise<ValidationResult> {
    const errors: string[] = []
    const warnings: string[] = []

    for (const ref of refs) {
      if (!ref.id) errors.push("Credential reference missing id")
      if (!ref.name) errors.push(`Credential ${ref.id} missing name`)
      if (!ref.reference) errors.push(`Credential ${ref.id} missing reference`)
      if (ref.revokedAt) warnings.push(`Credential "${ref.name}" has been revoked`)
      if (ref.expiresAt && new Date(ref.expiresAt) < new Date()) warnings.push(`Credential "${ref.name}" has expired`)
    }

    if (refs.length === 0) warnings.push("No credential references to validate")

    const result: ValidationResult = {
      id: generateId("ival"),
      type: "credential_references",
      passed: errors.length === 0,
      errors,
      warnings,
      details: { refCount: refs.length },
    }
    validations.set(result.id, result)
    return result
  },

  async getValidations(type?: string): Promise<ValidationResult[]> {
    let result = Array.from(validations.values())
    if (type) result = result.filter((v) => v.type === type)
    return result
  },
}
