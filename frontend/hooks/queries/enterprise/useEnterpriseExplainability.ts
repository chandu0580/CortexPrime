import { useQuery } from "@tanstack/react-query"
import {
  enterpriseExplainabilityApi,
  ExplainableMission,
  MissionExplanation,
  TimelineEntry,
  ReasoningStep,
  EvidenceItem,
  PolicyEvaluation,
  VerificationResult,
  ConfidenceAnalysis,
  ExplainabilityDashboard,
} from "@/services/enterprise/explainability"

export function useExplainableMissions(limit = 50) {
  return useQuery({
    queryKey: ["explainability-missions", limit],
    queryFn: async () => {
      const res = await enterpriseExplainabilityApi.listMissions(limit)
      return res.missions as ExplainableMission[]
    },
    staleTime: 60_000,
  })
}

export function useMissionExplanation(executionId: string) {
  return useQuery({
    queryKey: ["explainability-mission", executionId],
    queryFn: async () => {
      const res = await enterpriseExplainabilityApi.getMissionExplanation(executionId)
      return res as MissionExplanation
    },
    enabled: !!executionId,
    staleTime: 120_000,
  })
}

export function useMissionTimeline(executionId: string) {
  return useQuery({
    queryKey: ["explainability-timeline", executionId],
    queryFn: async () => {
      const res = await enterpriseExplainabilityApi.getTimeline(executionId)
      return res.timeline as TimelineEntry[]
    },
    enabled: !!executionId,
    staleTime: 120_000,
  })
}

export function useMissionReasoning(executionId: string) {
  return useQuery({
    queryKey: ["explainability-reasoning", executionId],
    queryFn: async () => {
      const res = await enterpriseExplainabilityApi.getReasoning(executionId)
      return res.reasoning as ReasoningStep[]
    },
    enabled: !!executionId,
    staleTime: 120_000,
  })
}

export function useMissionEvidence(executionId: string) {
  return useQuery({
    queryKey: ["explainability-evidence", executionId],
    queryFn: async () => {
      const res = await enterpriseExplainabilityApi.getEvidence(executionId)
      return res.evidence as EvidenceItem[]
    },
    enabled: !!executionId,
    staleTime: 120_000,
  })
}

export function useMissionVerification(executionId: string) {
  return useQuery({
    queryKey: ["explainability-verification", executionId],
    queryFn: async () => {
      const res = await enterpriseExplainabilityApi.getVerification(executionId)
      return res.verification as { results: VerificationResult[] }
    },
    enabled: !!executionId,
    staleTime: 120_000,
  })
}

export function useMissionConfidence(executionId: string) {
  return useQuery({
    queryKey: ["explainability-confidence", executionId],
    queryFn: async () => {
      const res = await enterpriseExplainabilityApi.getConfidence(executionId)
      return res.confidence as ConfidenceAnalysis
    },
    enabled: !!executionId,
    staleTime: 120_000,
  })
}

export function useMissionPolicy(executionId: string) {
  return useQuery({
    queryKey: ["explainability-policies", executionId],
    queryFn: async () => {
      const res = await enterpriseExplainabilityApi.getPolicies(executionId)
      return res.policies.policies as PolicyEvaluation[]
    },
    enabled: !!executionId,
    staleTime: 120_000,
  })
}

export function useExplainabilityDashboard() {
  return useQuery({
    queryKey: ["explainability-dashboard"],
    queryFn: async () => {
      const res = await enterpriseExplainabilityApi.getDashboard()
      return res as ExplainabilityDashboard
    },
    staleTime: 60_000,
  })
}
