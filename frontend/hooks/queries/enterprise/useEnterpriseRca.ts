import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { enterpriseRcaApi } from "@/services/enterprise/rca"

const KEYS = {
  dashboard: ["rca", "dashboard"] as const,
  analyses: (limit?: number) => ["rca", "analyses", limit] as const,
  analysis: (id: string) => ["rca", "analyses", id] as const,
  incidents: (limit?: number) => ["rca", "incidents", limit] as const,
  incident: (id: string) => ["rca", "incidents", id] as const,
  events: ["rca", "events"] as const,
}

// ---- Dashboard ----

export function useRcaDashboard() {
  return useQuery({
    queryKey: KEYS.dashboard,
    queryFn: () => enterpriseRcaApi.getDashboard(),
    refetchInterval: 15_000,
  })
}

// ---- Analyses ----

export function useRcaAnalyses(limit = 50) {
  return useQuery({
    queryKey: KEYS.analyses(limit),
    queryFn: () => enterpriseRcaApi.listAnalyses(limit),
    refetchInterval: 30_000,
  })
}

export function useRcaAnalysis(analysisId: string) {
  return useQuery({
    queryKey: KEYS.analysis(analysisId),
    queryFn: () => enterpriseRcaApi.getAnalysis(analysisId),
    enabled: !!analysisId,
  })
}

// ---- Incidents ----

export function useRcaIncidents(limit = 50) {
  return useQuery({
    queryKey: KEYS.incidents(limit),
    queryFn: () => enterpriseRcaApi.listIncidents(limit),
    refetchInterval: 30_000,
  })
}

export function useRcaIncident(incidentId: string) {
  return useQuery({
    queryKey: KEYS.incident(incidentId),
    queryFn: () => enterpriseRcaApi.getIncident(incidentId),
    enabled: !!incidentId,
  })
}

// ---- Mutations ----

export function useRunAnalysis() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (params?: { incident_id?: string; problem?: string; hours_back?: number }) =>
      enterpriseRcaApi.runAnalysis(params),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.dashboard })
      qc.invalidateQueries({ queryKey: KEYS.analyses() })
      qc.invalidateQueries({ queryKey: KEYS.incidents() })
    },
  })
}
