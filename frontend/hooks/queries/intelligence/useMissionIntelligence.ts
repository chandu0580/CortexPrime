"use client"
import { useMutation } from "@tanstack/react-query"
import { queryClient } from "@/lib/query"
import { queryKeys } from "@/lib/query"
import { missionIntelligenceEngine } from "@/mission-intelligence"
import type { MissionAnalysis } from "@/types/intelligence"

export function useMissionIntelligence() {
  return useMutation({
    mutationFn: (analysis: MissionAnalysis) => missionIntelligenceEngine.analyze(analysis),
    onSuccess: (data) => {
      const id = data.strategy.id
      queryClient.setQueryData(queryKeys.intelligence.strategy(id), data.strategy)
      queryClient.setQueryData(queryKeys.intelligence.plan(id), data.plan)
      queryClient.setQueryData(queryKeys.intelligence.capabilities(id), data.capabilities)
      queryClient.setQueryData(queryKeys.intelligence.risks(id), data.risks)
      queryClient.setQueryData(queryKeys.intelligence.graph(id), data.graph)
      queryClient.setQueryData(queryKeys.intelligence.report(id), data)
    },
  })
}
