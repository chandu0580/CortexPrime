"use client"

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api-client"
import type { AgentInfo, AgentRunResponse } from "@/types/enterprise"

export function useAgents() {
  return useQuery<{ agents: AgentInfo[]; total: number }>({
    queryKey: ["agents"],
    queryFn: () => api.get("/api/agents/").then((r) => r.data),
    refetchInterval: 10_000,
  })
}

export function useAgent(agentId: string) {
  return useQuery<AgentInfo>({
    queryKey: ["agent", agentId],
    queryFn: () => api.get(`/api/agents/${agentId}`).then((r) => r.data),
    enabled: !!agentId,
  })
}

export function useAgentHistory(agentId: string) {
  return useQuery<{ history: Record<string, unknown>[]; count: number }>({
    queryKey: ["agent-history", agentId],
    queryFn: () => api.get(`/api/agents/${agentId}/history`).then((r) => r.data),
    enabled: !!agentId,
  })
}

export function useRunAgents() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: {
      goal: string
      mission_id?: string
      tenant_id?: string
      user_id?: string
      tasks?: Record<string, unknown>[]
      mode?: string
    }) => api.post("/api/agents/run", data).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["agents"] })
      qc.invalidateQueries({ queryKey: ["missions"] })
    },
  })
}

export function useDelegate() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: {
      mission_id: string
      task_id?: string
      description: string
      target_agent_type: string
      input_data?: Record<string, unknown>
    }) => api.post("/api/agents/delegate", data).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["agents"] }),
  })
}

export function useRuntimeStatus() {
  return useQuery<{ runtimes: Record<string, boolean> }>({
    queryKey: ["runtime-status"],
    queryFn: () => api.get("/api/orchestrator/runtime-status").then((r) => r.data),
    refetchInterval: 30_000,
  })
}

export function useHealthStatus() {
  return useQuery<{ status: string; active_missions: number; total_missions: number }>({
    queryKey: ["orchestrator-health"],
    queryFn: () => api.get("/api/orchestrator/health").then((r) => r.data),
    refetchInterval: 15_000,
  })
}
