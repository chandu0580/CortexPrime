"use client"

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api-client"

export function useGovernanceHealth() {
  return useQuery<{ status: string }>({
    queryKey: ["governance-health"],
    queryFn: () => api.get("/api/governance/health").then((r) => r.data),
    refetchInterval: 30_000,
  })
}

export function usePolicies() {
  return useQuery<{ policies: unknown[]; total: number }>({
    queryKey: ["governance-policies"],
    queryFn: () => api.get("/api/governance/policies").then((r) => r.data),
  })
}

export function useApprovals() {
  return useQuery<{ approvals: unknown[]; total: number }>({
    queryKey: ["governance-approvals"],
    queryFn: () => api.get("/api/governance/approvals").then((r) => r.data),
  })
}

export function useViolations() {
  return useQuery<{ violations: unknown[]; total: number }>({
    queryKey: ["governance-violations"],
    queryFn: () => api.get("/api/governance/violations").then((r) => r.data),
  })
}

export function useAuditLog() {
  return useQuery<{ entries: unknown[]; total: number }>({
    queryKey: ["governance-audit"],
    queryFn: () => api.get("/api/governance/audit").then((r) => r.data),
  })
}

export function useEvaluateMission() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      api.post("/api/governance/evaluate", data).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["governance-approvals"] })
      qc.invalidateQueries({ queryKey: ["governance-violations"] })
    },
  })
}
