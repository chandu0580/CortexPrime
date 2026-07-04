import type { CapabilityPolicy, CapabilityPolicyRule, CapabilityRequirement, CapabilityCandidate } from "./types"
import { generateId } from "./shared"

const policies: CapabilityPolicy[] = []

const builtInRules: CapabilityPolicyRule[] = [
  {
    id: generateId("rule"),
    condition: "candidate.precision === 'none'",
    action: "deny",
    details: "Capability must have at least partial feature match",
  },
  {
    id: generateId("rule"),
    condition: "candidate.versionMatch === 'incompatible'",
    action: "deny",
    details: "Worker version is incompatible with requirement",
  },
  {
    id: generateId("rule"),
    condition: "candidate.worker.status === 'error'",
    action: "deny",
    details: "Worker is in error state and cannot accept tasks",
  },
  {
    id: generateId("rule"),
    condition: "candidate.worker.status === 'offline'",
    action: "deny",
    details: "Worker is offline and cannot accept tasks",
  },
  {
    id: generateId("rule"),
    condition: "candidate.precision === 'cross_train'",
    action: "warn",
    details: "Worker requires cross-training for this capability",
  },
  {
    id: generateId("rule"),
    condition: "requirement.maxConcurrency > 1",
    action: "warn",
    details: "Multiple concurrent tasks requested",
  },
]

export const CapabilityPolicyEngine = {
  async initialize(): Promise<void> {
    if (policies.length === 0) {
      policies.push({
        id: generateId("policy"),
        name: "Capability Resolution Policy",
        description: "Built-in rules for capability matching and worker selection",
        rules: builtInRules,
      })
    }
  },

  async getPolicies(): Promise<CapabilityPolicy[]> {
    return [...policies]
  },

  async addPolicy(policy: CapabilityPolicy): Promise<void> {
    policies.push(policy)
  },

  async evaluate(requirement: CapabilityRequirement, candidates: CapabilityCandidate[]): Promise<{
    allowed: CapabilityCandidate[]
    denied: CapabilityCandidate[]
    warnings: string[]
  }> {
    await CapabilityPolicyEngine.initialize()

    const allowed: CapabilityCandidate[] = []
    const denied: CapabilityCandidate[] = []
    const warnings: string[] = []

    for (const candidate of candidates) {
      let candidateAllowed = true

      for (const policy of policies) {
        for (const rule of policy.rules) {
          const result = evaluateRule(rule, requirement, candidate)

          if (result === "deny") {
            candidateAllowed = false
            denied.push(candidate)
            break
          }

          if (result === "warn") {
            warnings.push(`Candidate ${candidate.id}: ${rule.details}`)
          }
        }

        if (!candidateAllowed) break
      }

      if (candidateAllowed) {
        allowed.push(candidate)
      }
    }

    return { allowed, denied, warnings }
  },
}

function evaluateRule(
  rule: CapabilityPolicyRule,
  requirement: CapabilityRequirement,
  candidate: CapabilityCandidate,
): "allow" | "deny" | "warn" | "require_additional" | "none" {
  if (rule.condition === "candidate.precision === 'none'" && candidate.match.precision === "none") {
    return rule.action === "deny" ? "deny" : rule.action
  }
  if (rule.condition === "candidate.versionMatch === 'incompatible'" && candidate.match.versionMatch === "incompatible") {
    return rule.action === "deny" ? "deny" : rule.action
  }
  if (rule.condition === "candidate.worker.status === 'error'" && candidate.worker.status === "error") {
    return rule.action === "deny" ? "deny" : rule.action
  }
  if (rule.condition === "candidate.worker.status === 'offline'" && candidate.worker.status === "offline") {
    return rule.action === "deny" ? "deny" : rule.action
  }
  if (rule.condition === "candidate.precision === 'cross_train'" && candidate.match.precision === "cross_train") {
    return rule.action === "warn" ? "warn" : rule.action
  }
  if (rule.condition === "requirement.maxConcurrency > 1" && requirement.maxConcurrency > 1) {
    return rule.action === "warn" ? "warn" : rule.action
  }
  return "none"
}
