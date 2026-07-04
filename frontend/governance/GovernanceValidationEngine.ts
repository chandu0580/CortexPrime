import type { ValidationResult, GovernancePolicy, ComplianceResult, ApprovalRequest, GovernanceAudit } from "./types"
import { generateId } from "./shared"

const validations = new Map<string, ValidationResult>()

export const GovernanceValidationEngine = {
  async validatePolicyIntegrity(policy: GovernancePolicy): Promise<ValidationResult> {
    const errors: string[] = []
    const warnings: string[] = []

    if (!policy.id) errors.push("Policy missing id")
    if (!policy.name) errors.push("Policy missing name")
    if (!policy.description) errors.push("Policy missing description")
    if (policy.rules.length === 0) warnings.push("Policy has no rules")

    for (const rule of policy.rules) {
      if (!rule.id) errors.push("Rule missing id")
      if (!rule.field) errors.push(`Rule ${rule.id} missing field`)
      if (!rule.operator) errors.push(`Rule ${rule.id} missing operator`)
    }

    const result: ValidationResult = {
      id: generateId("gval"),
      type: "policy_integrity",
      passed: errors.length === 0,
      errors,
      warnings,
      details: { policyId: policy.id, ruleCount: policy.rules.length },
    }
    validations.set(result.id, result)
    return result
  },

  async validateComplianceConsistency(results: ComplianceResult[]): Promise<ValidationResult> {
    const errors: string[] = []
    const warnings: string[] = []

    if (results.length === 0) {
      warnings.push("No compliance results to validate")
    }

    for (const result of results) {
      if (!result.id) errors.push("Compliance result missing id")
      if (!result.policyId) errors.push(`Compliance result ${result.id} missing policyId`)
    }

    const result: ValidationResult = {
      id: generateId("gval"),
      type: "compliance_consistency",
      passed: errors.length === 0,
      errors,
      warnings,
      details: { resultCount: results.length },
    }
    validations.set(result.id, result)
    return result
  },

  async validateApprovalChain(requests: ApprovalRequest[]): Promise<ValidationResult> {
    const errors: string[] = []
    const warnings: string[] = []

    for (const request of requests) {
      if (!request.id) errors.push("Approval request missing id")
      if (!request.requestedBy) errors.push(`Approval ${request.id} missing requester`)
      if (!request.action) errors.push(`Approval ${request.id} missing action`)

      if (request.state === "approved" && !request.approver) {
        errors.push(`Approval ${request.id} is approved but has no approver`)
      }
    }

    if (requests.length === 0) {
      warnings.push("No approval requests in chain")
    }

    const result: ValidationResult = {
      id: generateId("gval"),
      type: "approval_chain",
      passed: errors.length === 0,
      errors,
      warnings,
      details: { requestCount: requests.length },
    }
    validations.set(result.id, result)
    return result
  },

  async validateGovernanceRules(policies: GovernancePolicy[]): Promise<ValidationResult> {
    const errors: string[] = []
    const warnings: string[] = []

    const nameMap = new Map<string, string>()
    for (const policy of policies) {
      if (nameMap.has(policy.name)) {
        errors.push(`Duplicate policy name: ${policy.name}`)
      }
      nameMap.set(policy.name, policy.id)

      if (!policy.category) warnings.push(`Policy "${policy.name}" has no category`)
    }

    const result: ValidationResult = {
      id: generateId("gval"),
      type: "governance_rules",
      passed: errors.length === 0,
      errors,
      warnings,
      details: { policyCount: policies.length, duplicateNames: errors.length },
    }
    validations.set(result.id, result)
    return result
  },

  async validateAuditCompleteness(records: GovernanceAudit[]): Promise<ValidationResult> {
    const errors: string[] = []
    const warnings: string[] = []

    for (const record of records) {
      if (!record.id) errors.push("Audit record missing id")
      if (!record.sessionId) errors.push(`Audit ${record.id} missing sessionId`)
      if (!record.action) errors.push(`Audit ${record.id} missing action`)
      if (!record.actor) errors.push(`Audit ${record.id} missing actor`)
    }

    if (records.length === 0) {
      warnings.push("No audit records to validate")
    }

    const result: ValidationResult = {
      id: generateId("gval"),
      type: "audit_completeness",
      passed: errors.length === 0,
      errors,
      warnings,
      details: { recordCount: records.length },
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
