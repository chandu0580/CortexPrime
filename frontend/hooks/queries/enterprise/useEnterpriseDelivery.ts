import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { enterpriseDeliveryApi } from "@/services/enterprise/delivery"
import type { DeliveryItem } from "@/types/delivery"

export function useDeliveryList(status?: string, mission?: string) {
  return useQuery({
    queryKey: ["deliveries", status, mission],
    queryFn: async () => {
      const res = await enterpriseDeliveryApi.list(status, mission)
      return res.deliveries as DeliveryItem[]
    },
    staleTime: 10_000,
  })
}

export function useDeliveryDetail(id: string) {
  return useQuery({
    queryKey: ["deliveries", id],
    queryFn: () => enterpriseDeliveryApi.getById(id),
    enabled: !!id,
    staleTime: 15_000,
  })
}

export function useDeliveryTimeline(id: string) {
  return useQuery({
    queryKey: ["deliveries", id, "timeline"],
    queryFn: () => enterpriseDeliveryApi.getTimeline(id),
    enabled: !!id,
    staleTime: 15_000,
  })
}

export function useDeliveryArtifacts(id: string) {
  return useQuery({
    queryKey: ["deliveries", id, "artifacts"],
    queryFn: () => enterpriseDeliveryApi.getArtifacts(id),
    enabled: !!id,
    staleTime: 15_000,
  })
}

export function useDeliveryBlueprint(id: string) {
  return useQuery({
    queryKey: ["deliveries", id, "blueprint"],
    queryFn: () => enterpriseDeliveryApi.getBlueprint(id),
    enabled: !!id,
    staleTime: 15_000,
  })
}

export function useDeliveryStats() {
  return useQuery({
    queryKey: ["deliveries", "stats"],
    queryFn: () => enterpriseDeliveryApi.getStats(),
    staleTime: 10_000,
  })
}

export function useStartDelivery() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: Parameters<typeof enterpriseDeliveryApi.start>[0]) =>
      enterpriseDeliveryApi.start(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["deliveries"] }),
  })
}

export function usePauseDelivery() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => enterpriseDeliveryApi.pause(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["deliveries"] }),
  })
}

export function useResumeDelivery() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => enterpriseDeliveryApi.resume(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["deliveries"] }),
  })
}

export function useCancelDelivery() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => enterpriseDeliveryApi.cancel(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["deliveries"] }),
  })
}

export function useRollbackDelivery() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => enterpriseDeliveryApi.rollback(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["deliveries"] }),
  })
}
