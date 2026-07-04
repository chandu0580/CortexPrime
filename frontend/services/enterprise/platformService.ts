import { api } from "@/services/api"
import type { ApiError } from "@/services/api"

export interface LoadingState<T> {
  data: T | null
  isLoading: boolean
  error: string | null
  refetch: () => Promise<void>
}

export function createLoading<T>(data: T | null = null): LoadingState<T> {
  return { data, isLoading: false, error: null, refetch: async () => {} }
}

export async function fetchData<T>(url: string, signal?: AbortSignal): Promise<T> {
  const response = await api.get<T>(url, signal ? { signal } : {})
  return response
}

export async function postData<T>(url: string, body?: Record<string, unknown>): Promise<T> {
  return await api.post<T>(url, body || {})
}

async function safeFetch<T>(url: string, signal?: AbortSignal): Promise<{ data: T | null; error: string | null }> {
  try {
    const data = await fetchData<T>(url, signal)
    return { data, error: null }
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err)
    if (message.includes("abort") || message.includes("Abort")) return { data: null, error: null }
    return { data: null, error: message }
  }
}

async function safePost<T>(url: string, body?: Record<string, unknown>): Promise<{ data: T | null; error: string | null }> {
  try {
    const data = await postData<T>(url, body)
    return { data, error: null }
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err)
    return { data: null, error: message }
  }
}

export const LiveDataService = {
  // --- Health ---
  async getHealth(signal?: AbortSignal) {
    return safeFetch<{
      status: string; agents: number; event_bus: string; runtime: string
      websocket_streaming: boolean; infrastructure: Record<string, string>
    }>("/api/health", signal)
  },

  async getSystemHealth(signal?: AbortSignal) {
    return safeFetch<{
      status: string; components: Record<string, { status: string; latency_ms: number; detail: string }>
    }>("/health/system", signal)
  },

  async getDatabaseHealth(signal?: AbortSignal) {
    return safeFetch<{ status: string; connectivity: Record<string, unknown>; migration: Record<string, unknown> }>("/health/database", signal)
  },

  async getRuntimeHealth(signal?: AbortSignal) {
    return safeFetch<{ status: string; active_executions: number; recovered_sessions: number }>("/health/runtime", signal)
  },

  // --- Executive ---
  async getExecutiveSnapshot(signal?: AbortSignal) {
    return safeFetch<Record<string, unknown>>("/api/executive/snapshot", signal)
  },

  async getExecutiveAnalytics(signal?: AbortSignal) {
    return safeFetch<Record<string, unknown>>("/api/executive/analytics", signal)
  },

  // --- Runtime ---
  async getRuntimeTelemetry(signal?: AbortSignal) {
    return safeFetch<{
      timestamp: string; active_executions: number; active_agents: number
      total_completed: number; total_failed: number; agents: Record<string, unknown>[]
      recent_executions: Record<string, unknown>[]; queue_depth: number
    }>("/api/telemetry/runtime", signal)
  },

  async getRuntimeExecutions(signal?: AbortSignal) {
    return safeFetch<{ executions: Record<string, unknown>[]; count: number }>("/api/runtime/executions", signal)
  },

  async getRuntimeInfrastructure(signal?: AbortSignal) {
    return safeFetch<Record<string, unknown>>("/api/runtime/infrastructure", signal)
  },

  async getRuntimeAgents(signal?: AbortSignal) {
    return safeFetch<Record<string, unknown>>("/api/runtime/agents", signal)
  },

  async executeMission(objective: string, sessionId?: string) {
    return safePost<Record<string, unknown>>("/api/runtime/execute", { objective, session_id: sessionId || "global" })
  },

  async executeMissionSync(objective: string, sessionId?: string) {
    return safePost<Record<string, unknown>>("/execute/sync", { objective, session_id: sessionId || "global" })
  },

  // --- Mission Library ---
  async getMissions(signal?: AbortSignal) {
    return safeFetch<{ missions: Record<string, unknown>[]; total: number }>("/api/mission-library/missions", signal)
  },

  async getMissionDetail(missionId: string, signal?: AbortSignal) {
    return safeFetch<Record<string, unknown>>(`/api/mission-library/missions/${missionId}`, signal)
  },

  async executeMissionById(missionId: string, params?: Record<string, unknown>) {
    return safePost<Record<string, unknown>>(`/api/mission-library/missions/${missionId}/execute`, { params: params || {} })
  },

  // --- Missions (legacy) ---
  async getActiveMissions(signal?: AbortSignal) {
    return safeFetch<Record<string, unknown>>("/api/missions/active", signal)
  },

  async getCompletedMissions(signal?: AbortSignal) {
    return safeFetch<Record<string, unknown>>("/api/missions/completed", signal)
  },

  // --- Orchestrator ---
  async executeOrchestrator(objective: string) {
    return safePost<Record<string, unknown>>("/api/orchestrator/execute", { objective })
  },

  async getActiveLoops(signal?: AbortSignal) {
    return safeFetch<Record<string, unknown>>("/api/orchestrator/loops/active", signal)
  },

  // --- Memory ---
  async getMemoryStatus(signal?: AbortSignal) {
    return safeFetch<Record<string, unknown>>("/api/memory/status", signal)
  },

  async searchMemory(query: string, nResults?: number, signal?: AbortSignal) {
    return safeFetch<Record<string, unknown>[]>(`/api/memory/search?q=${encodeURIComponent(query)}&n=${nResults || 10}`, signal)
  },

  async getMemoryContext(sessionId: string, query?: string, signal?: AbortSignal) {
    let url = `/api/memory/context/${sessionId}`
    if (query) url += `?query=${encodeURIComponent(query)}`
    return safeFetch<Record<string, unknown>>(url, signal)
  },

  async getMemoryTimeline(days = 7, signal?: AbortSignal) {
    return safeFetch<Record<string, unknown>>(`/api/memory/explorer/timeline?days=${days}`, signal)
  },

  async getMemoryStats(signal?: AbortSignal) {
    return safeFetch<Record<string, unknown>>("/api/memory/explorer/stats", signal)
  },

  // --- Knowledge Graph ---
  async getGraphHealth(signal?: AbortSignal) {
    return safeFetch<Record<string, unknown>>("/api/graph/health", signal)
  },

  async getGraphAgents(signal?: AbortSignal) {
    return safeFetch<Record<string, unknown>>("/api/graph/agents", signal)
  },

  async getGraphFull(signal?: AbortSignal) {
    return safeFetch<Record<string, unknown>>("/api/graph/agents/graph/full", signal)
  },

  async getMemoryGraph(limit = 50, signal?: AbortSignal) {
    return safeFetch<Record<string, unknown>>(`/api/memory/explorer/graph?limit=${limit}`, signal)
  },

  // --- Approval Center ---
  async getApprovalPolicies(signal?: AbortSignal) {
    return safeFetch<{ policies: Record<string, unknown>[]; total: number }>("/api/approval-center/policies", signal)
  },

  async getApprovalWorkflows(status?: string, signal?: AbortSignal) {
    const url = status ? `/api/approval-center/workflows?status=${status}` : "/api/approval-center/workflows"
    return safeFetch<{ workflows: Record<string, unknown>[]; total: number }>(url, signal)
  },

  async getApprovalSummary(signal?: AbortSignal) {
    return safeFetch<Record<string, unknown>>("/api/approval-center/summary", signal)
  },

  async getApprovalAnalytics(signal?: AbortSignal) {
    return safeFetch<Record<string, unknown>>("/api/approval-center/analytics", signal)
  },

  async approveWorkflowStep(workflowId: string, approver: string, role: string, reason?: string) {
    const params = new URLSearchParams({ workflow_id: workflowId, approver, role })
    if (reason) params.set("reason", reason)
    return safePost<Record<string, unknown>>(`/api/approval-center/workflows/${workflowId}/approve?${params}`)
  },

  async rejectWorkflowStep(workflowId: string, approver: string, reason: string) {
    const params = new URLSearchParams({ workflow_id: workflowId, approver, reason })
    return safePost<Record<string, unknown>>(`/api/approval-center/workflows/${workflowId}/reject?${params}`)
  },

  // --- Security Center ---
  async getUsers(signal?: AbortSignal) {
    return safeFetch<{ users: Record<string, unknown>[]; total: number }>("/api/security/users", signal)
  },

  async getRoles(signal?: AbortSignal) {
    return safeFetch<{ roles: Record<string, unknown>[]; total: number }>("/api/security/roles", signal)
  },

  async getGroups(signal?: AbortSignal) {
    return safeFetch<{ groups: Record<string, unknown>[]; total: number }>("/api/security/groups", signal)
  },

  async getOrganizations(signal?: AbortSignal) {
    return safeFetch<{ organizations: Record<string, unknown>[]; total: number }>("/api/security/organizations", signal)
  },

  async getApiKeys(userId?: string, signal?: AbortSignal) {
    const url = userId ? `/api/security/api-keys?user_id=${userId}` : "/api/security/api-keys"
    return safeFetch<{ api_keys: Record<string, unknown>[]; total: number }>(url, signal)
  },

  async getSecrets(signal?: AbortSignal) {
    return safeFetch<{ secrets: Record<string, unknown>[]; total: number }>("/api/security/secrets", signal)
  },

  async getSecurityStatus(signal?: AbortSignal) {
    return safeFetch<Record<string, unknown>>("/api/security/status", signal)
  },

  // --- Analytics ---
  async getCostSummary(signal?: AbortSignal) {
    return safeFetch<Record<string, unknown>>("/api/costs/summary", signal)
  },

  async getCostDaily(days = 30, signal?: AbortSignal) {
    return safeFetch<Record<string, unknown>>(`/api/costs/daily?days=${days}`, signal)
  },

  // --- Governance ---
  async getGovernanceOverview(signal?: AbortSignal) {
    return safeFetch<Record<string, unknown>>("/api/governance-center/overview", signal)
  },

  async getGovernanceAudit(signal?: AbortSignal) {
    return safeFetch<Record<string, unknown>>("/governance/audit/summary", signal)
  },

  // --- Replay ---
  async getMissionReplay(executionId: string, signal?: AbortSignal) {
    return safeFetch<Record<string, unknown>>(`/api/mission-replay/${executionId}`, signal)
  },

  async getMissionReplayGraph(executionId: string, signal?: AbortSignal) {
    return safeFetch<Record<string, unknown>>(`/api/mission-replay/${executionId}/graph`, signal)
  },

  // --- WebSocket ---
  async getWebSocketStatus(signal?: AbortSignal) {
    return safeFetch<Record<string, unknown>>("/api/websocket/status", signal)
  },

  // --- Connector center data from various endpoints ---
  async getRabbitMQHealth(signal?: AbortSignal) {
    return safeFetch<Record<string, unknown>>("/api/rabbitmq/health", signal)
  },

  async getGraphHealthStatus(signal?: AbortSignal) {
    return safeFetch<Record<string, unknown>>("/api/graph/health", signal)
  },

  async getLLMHealth(signal?: AbortSignal) {
    return safeFetch<Record<string, unknown>>("/health/llm", signal)
  },
}

export async function fetchAllHealth(signal?: AbortSignal) {
  const results = await Promise.allSettled([
    LiveDataService.getHealth(signal),
    LiveDataService.getSystemHealth(signal),
    LiveDataService.getDatabaseHealth(signal),
    LiveDataService.getRuntimeHealth(signal),
    LiveDataService.getRuntimeTelemetry(signal),
    LiveDataService.getRuntimeInfrastructure(signal),
    LiveDataService.getExecutiveSnapshot(signal),
    LiveDataService.getMemoryStatus(signal),
    LiveDataService.getGraphHealth(signal),
    LiveDataService.getApprovalSummary(signal),
    LiveDataService.getSecurityStatus(signal),
    LiveDataService.getRabbitMQHealth(signal),
    LiveDataService.getLLMHealth(signal),
  ])
  return results.map((r) => r.status === "fulfilled" ? r.value : { data: null, error: String(r.reason) })
}