import type { GovernanceCapabilityDefinition } from "./types"
import { generateId } from "./shared"

const capabilities = new Map<string, GovernanceCapabilityDefinition>()

const builtInCapabilities: GovernanceCapabilityDefinition[] = [
  { id: "gov-policy", name: "governance.policy", description: "Policy registration, evaluation, and rule enforcement", version: "1.0.0", enabled: true },
  { id: "gov-compliance", name: "governance.compliance", description: "Compliance validation, violation detection, and reporting", version: "1.0.0", enabled: true },
  { id: "gov-approval", name: "governance.approval", description: "Approval workflow with request, approve, reject, revoke", version: "1.0.0", enabled: true },
  { id: "gov-audit", name: "governance.audit", description: "Governance audit trail and timeline management", version: "1.0.0", enabled: true },
  { id: "gov-risk", name: "governance.risk", description: "Risk assessment, classification, mitigation, and escalation", version: "1.0.0", enabled: true },
  { id: "gov-validation", name: "governance.validation", description: "Governance validation for policies, compliance, approvals, and audits", version: "1.0.0", enabled: true },
]

for (const cap of builtInCapabilities) {
  capabilities.set(cap.id, cap)
}

export const GovernanceCapability = {
  async isEnabled(name: string): Promise<boolean> {
    const cap = Array.from(capabilities.values()).find((c) => c.name === name)
    return cap?.enabled ?? false
  },

  async enable(name: string): Promise<GovernanceCapabilityDefinition> {
    const cap = Array.from(capabilities.values()).find((c) => c.name === name)
    if (!cap) throw new Error(`Capability not found: ${name}`)
    const updated: GovernanceCapabilityDefinition = { ...cap, enabled: true }
    capabilities.set(cap.id, updated)
    return updated
  },

  async disable(name: string): Promise<GovernanceCapabilityDefinition> {
    const cap = Array.from(capabilities.values()).find((c) => c.name === name)
    if (!cap) throw new Error(`Capability not found: ${name}`)
    const updated: GovernanceCapabilityDefinition = { ...cap, enabled: false }
    capabilities.set(cap.id, updated)
    return updated
  },

  async register(definition: Omit<GovernanceCapabilityDefinition, "id">): Promise<GovernanceCapabilityDefinition> {
    const id = generateId("cap")
    const full: GovernanceCapabilityDefinition = { ...definition, id }
    capabilities.set(id, full)
    return full
  },

  async list(): Promise<GovernanceCapabilityDefinition[]> {
    return Array.from(capabilities.values())
  },

  async get(name: string): Promise<GovernanceCapabilityDefinition | null> {
    return Array.from(capabilities.values()).find((c) => c.name === name) ?? null
  },
}
