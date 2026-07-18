"use client"

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api-client"
import type { MissionSummary, OrchestratorMission } from "@/types/enterprise"

export function useMissions(status?: string) {
  return useQuery<{ missions: OrchestratorMission[]; total: number }>({
    queryKey: ["missions", status],
    queryFn: () => api.get("/api/orchestrator/", { params: { status } }).then((r) => r.data),
    refetchInterval: 10_000,
  })
}

export function useMission(missionId: string) {
  return useQuery<MissionSummary>({
    queryKey: ["mission", missionId],
    queryFn: () =>
      api
        .get(`/api/orchestrator/${missionId}`, { params: { include_reasoning: true } })
        .then((r) => r.data),
    enabled: !!missionId,
    refetchInterval: 5_000,
  })
}

export function useStartMission() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: {
      goal: string
      mission_id?: string
      tenant_id?: string
      user_id?: string
      permissions?: string[]
      metadata?: Record<string, unknown>
    }) => api.post("/api/orchestrator/start", data).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["missions"] }),
  })
}

export function usePauseMission() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (mission_id: string) => api.post("/api/orchestrator/pause", { mission_id }).then((r) => r.data),
    onSuccess: (_data, mission_id) => qc.invalidateQueries({ queryKey: ["mission", mission_id] }),
  })
}

export function useResumeMission() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (mission_id: string) => api.post("/api/orchestrator/resume", { mission_id }).then((r) => r.data),
    onSuccess: (_data, mission_id) => qc.invalidateQueries({ queryKey: ["mission", mission_id] }),
  })
}

export function useCancelMission() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (mission_id: string) => api.post("/api/orchestrator/cancel", { mission_id }).then((r) => r.data),
    onSuccess: (_data, mission_id) => qc.invalidateQueries({ queryKey: ["mission", mission_id] }),
  })
}

export function useRestartMission() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (mission_id: string) => api.post("/api/orchestrator/restart", { mission_id }).then((r) => r.data),
    onSuccess: (_data, mission_id) => qc.invalidateQueries({ queryKey: ["mission", mission_id] }),
  })
}
