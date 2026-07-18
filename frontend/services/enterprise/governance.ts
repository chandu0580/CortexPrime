import axios from "axios"
import { apiUrl } from "@/lib/constants"

export interface PolicyItem {
  id: string
  name: string
  description: string
  scope: string
  rule_type: string
  condition: Record<string, unknown>
  action: string
  severity: string
  enabled: boolean
  tags: string[]
  violation_count: number
  created_at: string
  updated_at: string
}

export interface ComplianceCheck {
  id: string
  target_type: string
  target_id: string
  status: string
  policies_evaluated: number
  violations: ComplianceViolation[]
  violation_count: number
  check_time: string
}

export interface ComplianceViolation {
  policy_id: string
  policy_name: string
  severity: string
  reason: string
  action: string
}

export interface AuditEntry {
  id: string
  action: string
  actor: string
  target_type: string
  target_id: string
  details: Record<string, unknown>
  result: string
  timestamp: string
}

export interface GovernanceDashboard {
  total_policies: number
  enabled_policies: number
  total_violations: number
  non_compliant_checks: number
  total_audit_entries: number
  policies_by_severity: Record<string, number>
  compliance_rate: number
}

export const enterpriseGovernanceApi = {
  getDashboard: async (): Promise<GovernanceDashboard> => {
    const res = await axios.get(`${apiUrl}/api/governance/dashboard`)
    return res.data
  },

  createPolicy: async (payload: {
    name: string
    description?: string
    scope?: string
    rule_type?: string
    condition?: Record<string, unknown>
    action?: string
    severity?: string
    enabled?: boolean
    tags?: string[]
  }): Promise<PolicyItem> => {
    const res = await axios.post(`${apiUrl}/api/governance/policies`, payload)
    return res.data
  },

  listPolicies: async (params?: { scope?: string; severity?: string; enabled?: boolean }): Promise<{ policies: PolicyItem[] }> => {
    const searchParams = new URLSearchParams()
    if (params?.scope) searchParams.set("scope", params.scope)
    if (params?.severity) searchParams.set("severity", params.severity)
    if (params?.enabled !== undefined) searchParams.set("enabled", String(params.enabled))
    const res = await axios.get(`${apiUrl}/api/governance/policies?${searchParams}`)
    return res.data
  },

  getPolicy: async (id: string): Promise<PolicyItem> => {
    const res = await axios.get(`${apiUrl}/api/governance/policies/${id}`)
    return res.data
  },

  updatePolicy: async (id: string, updates: Partial<PolicyItem>): Promise<PolicyItem> => {
    const res = await axios.put(`${apiUrl}/api/governance/policies/${id}`, updates)
    return res.data
  },

  deletePolicy: async (id: string): Promise<void> => {
    await axios.delete(`${apiUrl}/api/governance/policies/${id}`)
  },

  runComplianceCheck: async (target_type: string, target_id: string, context?: Record<string, unknown>): Promise<ComplianceCheck> => {
    const res = await axios.post(`${apiUrl}/api/governance/compliance/check`, { target_type, target_id, context })
    return res.data
  },

  getComplianceHistory: async (target_type?: string, target_id?: string, limit?: number): Promise<{ checks: ComplianceCheck[] }> => {
    const params = new URLSearchParams()
    if (target_type) params.set("target_type", target_type)
    if (target_id) params.set("target_id", target_id)
    if (limit) params.set("limit", String(limit))
    const res = await axios.get(`${apiUrl}/api/governance/compliance/history?${params}`)
    return res.data
  },

  recordAudit: async (payload: {
    action: string
    actor: string
    target_type: string
    target_id: string
    details?: Record<string, unknown>
    result?: string
  }): Promise<AuditEntry> => {
    const res = await axios.post(`${apiUrl}/api/governance/audit`, payload)
    return res.data
  },

  getAuditLog: async (params?: { target_type?: string; actor?: string; action?: string; limit?: number }): Promise<{ entries: AuditEntry[] }> => {
    const searchParams = new URLSearchParams()
    if (params?.target_type) searchParams.set("target_type", params.target_type)
    if (params?.actor) searchParams.set("actor", params.actor)
    if (params?.action) searchParams.set("action", params.action)
    if (params?.limit) searchParams.set("limit", String(params.limit))
    const res = await axios.get(`${apiUrl}/api/governance/audit?${searchParams}`)
    return res.data
  },
}
