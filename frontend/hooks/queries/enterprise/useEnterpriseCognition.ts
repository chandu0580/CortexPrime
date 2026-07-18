import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { enterpriseCognitionApi, CognitionDashboard, CognitionStatus, CognitionHealth, TimelineEntry, IntervalConfig } from "@/services/enterprise/cognition"
import { queryKeys } from "@/lib/query/queryKeys"

export function useCognitionStatus() {
  return useQuery({
    queryKey: [...queryKeys.enterpriseCognition.all, "status"],
    queryFn: async () => {
      const res = await enterpriseCognitionApi.getStatus()
      return res as CognitionStatus
    },
    refetchInterval: 30_000,
    staleTime: 10_000,
  })
}

export function useCognitionDashboard() {
  return useQuery({
    queryKey: [...queryKeys.enterpriseCognition.all, "dashboard"],
    queryFn: async () => {
      const res = await enterpriseCognitionApi.getDashboard()
      return res as CognitionDashboard
    },
    refetchInterval: 30_000,
    staleTime: 10_000,
  })
}

export function useCognitionTimeline(limit = 50, changeType?: string) {
  return useQuery({
    queryKey: [...queryKeys.enterpriseCognition.all, "timeline", limit, changeType],
    queryFn: async () => {
      const res = await enterpriseCognitionApi.getTimeline(limit, 0, changeType)
      return res as TimelineEntry[]
    },
    staleTime: 15_000,
  })
}

export function useCognitionHealth() {
  return useQuery({
    queryKey: [...queryKeys.enterpriseCognition.all, "health"],
    queryFn: async () => {
      const res = await enterpriseCognitionApi.getHealth()
      return res as CognitionHealth
    },
    staleTime: 30_000,
  })
}

export function useStartCognition() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (config?: IntervalConfig) => {
      const res = await enterpriseCognitionApi.start(config)
      return res
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.enterpriseCognition.all })
    },
  })
}

export function useStopCognition() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      const res = await enterpriseCognitionApi.stop()
      return res
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.enterpriseCognition.all })
    },
  })
}

export function usePauseCognition() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      const res = await enterpriseCognitionApi.pause()
      return res
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.enterpriseCognition.all })
    },
  })
}

export function useResumeCognition() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      const res = await enterpriseCognitionApi.resume()
      return res
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.enterpriseCognition.all })
    },
  })
}
