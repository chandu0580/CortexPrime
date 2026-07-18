import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import {
  enterpriseMonitoringApi,
  WatcherInfo,
  MonitoringRule,
  DetectedEvent,
  AutoMission,
  MonitoringStatistics,
  MonitoringHealth,
} from "@/services/enterprise/monitoring"

export function useMonitoringWatchers() {
  return useQuery({
    queryKey: ["monitoring-watchers"],
    queryFn: async () => {
      const res = await enterpriseMonitoringApi.getWatchers()
      return res.watchers as WatcherInfo[]
    },
    staleTime: 30_000,
  })
}

export function useMonitoringRules() {
  return useQuery({
    queryKey: ["monitoring-rules"],
    queryFn: async () => {
      const res = await enterpriseMonitoringApi.getRules()
      return res.rules as MonitoringRule[]
    },
    staleTime: 30_000,
  })
}

export function useMonitoringEvents(limit = 100, connector?: string, severity?: string) {
  return useQuery({
    queryKey: ["monitoring-events", limit, connector, severity],
    queryFn: async () => {
      const res = await enterpriseMonitoringApi.getEvents(limit, connector, severity)
      return res.events as DetectedEvent[]
    },
    staleTime: 15_000,
  })
}

export function useMonitoringMissions(limit = 50, connector?: string) {
  return useQuery({
    queryKey: ["monitoring-missions", limit, connector],
    queryFn: async () => {
      const res = await enterpriseMonitoringApi.getMissions(limit, connector)
      return res.missions as AutoMission[]
    },
    staleTime: 30_000,
  })
}

export function useMonitoringStatistics() {
  return useQuery({
    queryKey: ["monitoring-statistics"],
    queryFn: async () => {
      const res = await enterpriseMonitoringApi.getStatistics()
      return res as MonitoringStatistics
    },
    staleTime: 30_000,
  })
}

export function useMonitoringHealth() {
  return useQuery({
    queryKey: ["monitoring-health"],
    queryFn: async () => {
      const res = await enterpriseMonitoringApi.getHealth()
      return res as MonitoringHealth
    },
    staleTime: 15_000,
  })
}

export function useCreateMonitoringRule() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (ruleData: Record<string, unknown>) => {
      return enterpriseMonitoringApi.createRule(ruleData)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["monitoring-rules"] })
    },
  })
}

export function useUpdateMonitoringRule() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ ruleId, ruleData }: { ruleId: string; ruleData: Record<string, unknown> }) => {
      return enterpriseMonitoringApi.updateRule(ruleId, ruleData)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["monitoring-rules"] })
    },
  })
}

export function useDeleteMonitoringRule() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (ruleId: string) => {
      return enterpriseMonitoringApi.deleteRule(ruleId)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["monitoring-rules"] })
    },
  })
}

export function useTriggerPoll() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (connector: string | undefined = undefined) => {
      return enterpriseMonitoringApi.triggerPoll(connector)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["monitoring"] })
      queryClient.invalidateQueries({ queryKey: ["enterprise-learning"] })
    },
  })
}
