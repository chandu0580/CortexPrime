import type { ConnectorPolicy, ConnectorValidation } from "./types"
import { generateId } from "./shared"

export const ConnectorPolicyEngine = {
  async evaluateConnectorPolicy(policy: ConnectorPolicy, context: Record<string, unknown>): Promise<ConnectorValidation> {
    const errors: string[] = []
    if (!policy.enabled) errors.push("policy is disabled")
    if (policy.type !== "connector_policy") errors.push("policy type mismatch: expected connector_policy")
    return createPolicyResult(policy, "connector_policy", errors)
  },

  async evaluateCapabilityPolicy(policy: ConnectorPolicy, context: Record<string, unknown>): Promise<ConnectorValidation> {
    const errors: string[] = []
    if (!policy.enabled) errors.push("policy is disabled")
    if (policy.type !== "capability_policy") errors.push("policy type mismatch: expected capability_policy")
    return createPolicyResult(policy, "capability_policy", errors)
  },

  async evaluatePermissionPolicy(policy: ConnectorPolicy, context: Record<string, unknown>): Promise<ConnectorValidation> {
    const errors: string[] = []
    if (!policy.enabled) errors.push("policy is disabled")
    if (policy.type !== "permission_policy") errors.push("policy type mismatch: expected permission_policy")
    return createPolicyResult(policy, "permission_policy", errors)
  },

  async evaluateLifecyclePolicy(policy: ConnectorPolicy, context: Record<string, unknown>): Promise<ConnectorValidation> {
    const errors: string[] = []
    if (!policy.enabled) errors.push("policy is disabled")
    if (policy.type !== "lifecycle_policy") errors.push("policy type mismatch: expected lifecycle_policy")
    return createPolicyResult(policy, "lifecycle_policy", errors)
  },

  async evaluateConfigurationPolicy(policy: ConnectorPolicy, context: Record<string, unknown>): Promise<ConnectorValidation> {
    const errors: string[] = []
    if (!policy.enabled) errors.push("policy is disabled")
    if (policy.type !== "configuration_policy") errors.push("policy type mismatch: expected configuration_policy")
    return createPolicyResult(policy, "configuration_policy", errors)
  },
}

async function createPolicyResult(
  policy: ConnectorPolicy,
  expectedType: string,
  errors: string[]
): Promise<ConnectorValidation> {
  const warnings: string[] = []
  if (!policy.name) warnings.push("policy has no name")
  return {
    id: generateId("policy"),
    connectorId: "",
    type: expectedType,
    result: errors.length > 0 ? "failed" : "passed",
    errors,
    warnings,
    details: { policyId: policy.id, name: policy.name, priority: policy.priority },
    timestamp: new Date().toISOString(),
  }
}
