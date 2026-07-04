import type { GraphPolicy, GraphPolicyRule } from "./types"
import { EntityManager } from "./EntityManager"
import { Neo4jClient } from "./Neo4jClient"

function serializePolicy(policy: GraphPolicy): Record<string, unknown> {
  return {
    policyId: policy.id,
    name: policy.name,
    description: policy.description,
    category: policy.category,
    effect: policy.effect,
    rules: JSON.stringify(policy.rules),
    priority: policy.priority,
    enabled: policy.enabled,
  }
}

function deserializePolicy(record: Record<string, unknown>): GraphPolicy {
  return {
    id: record.policyId as string,
    name: record.name as string,
    description: record.description as string,
    category: record.category as GraphPolicy["category"],
    effect: record.effect as GraphPolicy["effect"],
    rules: JSON.parse((record.rules as string) || "[]"),
    priority: record.priority as number,
    enabled: record.enabled as boolean,
  }
}

export const GraphPolicyEngine = {
  async registerPolicy(policy: GraphPolicy): Promise<void> {
    const client = Neo4jClient.getDriver()
    if (client) {
      const existing = await this.getPolicy(policy.id)
      if (existing) throw new Error(`Graph policy ${policy.id} already exists`)

      await Neo4jClient.run(
        `CREATE (p:GraphPolicy $props) RETURN p`,
        { props: serializePolicy(policy) },
      )
    }
  },

  async updatePolicy(policy: GraphPolicy): Promise<void> {
    const client = Neo4jClient.getDriver()
    if (client) {
      await Neo4jClient.run(
        `MATCH (p:GraphPolicy {policyId: $policyId})
         SET p += $props`,
        { policyId: policy.id, props: serializePolicy(policy) },
      )
    }
  },

  async removePolicy(policyId: string): Promise<void> {
    const client = Neo4jClient.getDriver()
    if (client) {
      await Neo4jClient.run(
        `MATCH (p:GraphPolicy {policyId: $policyId})
         DELETE p`,
        { policyId },
      )
    }
  },

  async getPolicy(policyId: string): Promise<GraphPolicy | null> {
    const client = Neo4jClient.getDriver()
    if (!client) return null

    const result = await Neo4jClient.run(
      `MATCH (p:GraphPolicy {policyId: $policyId}) RETURN p`,
      { policyId },
    )

    if (result.records.length === 0) return null
    return deserializePolicy(result.records[0].get("p").properties)
  },

  async listPolicies(): Promise<GraphPolicy[]> {
    const client = Neo4jClient.getDriver()
    if (!client) return []

    const result = await Neo4jClient.run(
      `MATCH (p:GraphPolicy) RETURN p ORDER BY p.priority DESC`,
    )

    return result.records.map((record) => deserializePolicy(record.get("p").properties))
  },

  evaluateRule(rule: GraphPolicyRule, context: Record<string, unknown>): { passed: boolean; message: string } {
    const contextValue = context[rule.field]

    switch (rule.operator) {
      case "eq":
        return contextValue === rule.value
          ? { passed: true, message: "" }
          : { passed: false, message: rule.message }
      case "neq":
        return contextValue !== rule.value
          ? { passed: true, message: "" }
          : { passed: false, message: rule.message }
      case "gt":
        return Number(contextValue) > Number(rule.value)
          ? { passed: true, message: "" }
          : { passed: false, message: rule.message }
      case "gte":
        return Number(contextValue) >= Number(rule.value)
          ? { passed: true, message: "" }
          : { passed: false, message: rule.message }
      case "lt":
        return Number(contextValue) < Number(rule.value)
          ? { passed: true, message: "" }
          : { passed: false, message: rule.message }
      case "lte":
        return Number(contextValue) <= Number(rule.value)
          ? { passed: true, message: "" }
          : { passed: false, message: rule.message }
      case "in":
        return Array.isArray(rule.value) && rule.value.includes(contextValue)
          ? { passed: true, message: "" }
          : { passed: false, message: rule.message }
      case "not_in":
        return Array.isArray(rule.value) && !rule.value.includes(contextValue)
          ? { passed: true, message: "" }
          : { passed: false, message: rule.message }
      case "exists":
        return contextValue !== undefined && contextValue !== null
          ? { passed: true, message: "" }
          : { passed: false, message: rule.message }
      case "not_exists":
        return contextValue === undefined || contextValue === null
          ? { passed: true, message: "" }
          : { passed: false, message: rule.message }
      case "matches": {
        if (typeof rule.value !== "string" || typeof contextValue !== "string") {
          return { passed: false, message: rule.message }
        }
        try {
          const regex = new RegExp(rule.value)
          return regex.test(contextValue)
            ? { passed: true, message: "" }
            : { passed: false, message: rule.message }
        } catch {
          return { passed: false, message: `Invalid regex pattern: ${rule.value}` }
        }
      }
      default:
        return { passed: true, message: "" }
    }
  },

  async evaluate(context: Record<string, unknown>): Promise<{ allowed: boolean; policyId: string | null; reasons: string[] }> {
    const policies = await this.listPolicies()
    const sorted = policies.filter((p) => p.enabled)

    for (const policy of sorted) {
      const results = policy.rules.map((rule) => this.evaluateRule(rule, context))
      const allPassed = results.every((r) => r.passed)

      if (allPassed) {
        switch (policy.effect) {
          case "allow":
            return { allowed: true, policyId: policy.id, reasons: [`Allowed by policy ${policy.name}`] }
          case "deny":
            return { allowed: false, policyId: policy.id, reasons: [`Denied by policy ${policy.name}`] }
          case "audit":
            return { allowed: true, policyId: policy.id, reasons: [`Audited by policy ${policy.name}`] }
        }
      }
    }

    return { allowed: true, policyId: null, reasons: ["No matching policy, default allow"] }
  },

  async checkEntityUniqueness(name: string, type: string): Promise<{ unique: boolean; reason: string }> {
    const entities = await EntityManager.queryEntities({ name, field: "type", value: type })
    const unique = entities.length === 0
    return {
      unique,
      reason: unique ? `Entity '${name}' of type '${type}' is unique` : `Entity '${name}' of type '${type}' already exists (${entities.length} matches)`,
    }
  },

  async clearPolicies(): Promise<void> {
    const client = Neo4jClient.getDriver()
    if (client) {
      await Neo4jClient.run(`MATCH (p:GraphPolicy) DELETE p`)
    }
  },
}
