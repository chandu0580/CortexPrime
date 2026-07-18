import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { enterpriseTriggerApi } from "@/services/enterprise/triggers"
import type { TriggerPolicy } from "@/types/triggers"

export function useTriggerPolicies(source?: string, enabled?: boolean) {
  return useQuery({
    queryKey: ["trigger-policies", source, enabled],
    queryFn: async () => {
      const res = await enterpriseTriggerApi.listPolicies(source, enabled)
      return res.policies as TriggerPolicy[]
    },
    staleTime: 10_000,
  })
}

export function useTriggerSources() {
  return useQuery({
    queryKey: ["trigger-sources"],
    queryFn: () => enterpriseTriggerApi.getSources(),
    staleTime: 300_000,
  })
}

export function useTriggerHistory(source?: string, status?: string, limit?: number) {
  return useQuery({
    queryKey: ["trigger-history", source, status, limit],
    queryFn: () => enterpriseTriggerApi.getHistory(source, status, limit),
    staleTime: 5_000,
  })
}

export function useTriggerStats() {
  return useQuery({
    queryKey: ["trigger-stats"],
    queryFn: () => enterpriseTriggerApi.getStats(),
    staleTime: 10_000,
  })
}

export function useCreateTriggerPolicy() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: Parameters<typeof enterpriseTriggerApi.createPolicy>[0]) =>
      enterpriseTriggerApi.createPolicy(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["trigger-policies"] }),
  })
}

export function useUpdateTriggerPolicy() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Partial<TriggerPolicy> }) =>
      enterpriseTriggerApi.updatePolicy(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["trigger-policies"] }),
  })
}

export function useDeleteTriggerPolicy() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => enterpriseTriggerApi.deletePolicy(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["trigger-policies"] }),
  })
}

export function useSimulateTrigger() {
  return useMutation({
    mutationFn: (payload: { source: string; event_type: string; payload: Record<string, unknown> }) =>
      enterpriseTriggerApi.simulate(payload.source, payload.event_type, payload.payload),
  })
}
