import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import {
  enterpriseGovernanceApi,
  PolicyItem,
  ComplianceCheck,
  AuditEntry,
} from "@/services/enterprise/governance"

export function useGovernanceDashboard() {
  return useQuery({
    queryKey: ["governance-dashboard"],
    queryFn: () => enterpriseGovernanceApi.getDashboard(),
    staleTime: 30_000,
  })
}

export function usePolicyList(params?: { scope?: string; severity?: string; enabled?: boolean }) {
  return useQuery({
    queryKey: ["policies", params],
    queryFn: async () => {
      const res = await enterpriseGovernanceApi.listPolicies(params)
      return res.policies as PolicyItem[]
    },
    staleTime: 30_000,
  })
}

export function usePolicyDetail(id: string) {
  return useQuery({
    queryKey: ["policies", id],
    queryFn: () => enterpriseGovernanceApi.getPolicy(id),
    enabled: !!id,
    staleTime: 60_000,
  })
}

export function useCreatePolicy() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: Parameters<typeof enterpriseGovernanceApi.createPolicy>[0]) =>
      enterpriseGovernanceApi.createPolicy(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["policies"] }),
  })
}

export function useUpdatePolicy() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, updates }: { id: string; updates: Partial<PolicyItem> }) =>
      enterpriseGovernanceApi.updatePolicy(id, updates),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["policies"] }),
  })
}

export function useDeletePolicy() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => enterpriseGovernanceApi.deletePolicy(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["policies"] }),
  })
}

export function useComplianceCheck() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: { target_type: string; target_id: string; context?: Record<string, unknown> }) =>
      enterpriseGovernanceApi.runComplianceCheck(payload.target_type, payload.target_id, payload.context),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["compliance"] }),
  })
}

export function useComplianceHistory(target_type?: string, target_id?: string) {
  return useQuery({
    queryKey: ["compliance", target_type, target_id],
    queryFn: async () => {
      const res = await enterpriseGovernanceApi.getComplianceHistory(target_type, target_id)
      return res.checks as ComplianceCheck[]
    },
    staleTime: 30_000,
  })
}

export function useAuditLog(params?: { target_type?: string; actor?: string; action?: string; limit?: number }) {
  return useQuery({
    queryKey: ["audit-log", params],
    queryFn: async () => {
      const res = await enterpriseGovernanceApi.getAuditLog(params)
      return res.entries as AuditEntry[]
    },
    staleTime: 15_000,
  })
}
