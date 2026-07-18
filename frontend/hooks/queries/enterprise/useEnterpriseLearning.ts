import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import {
  enterpriseLearningApi,
  Lesson,
  BestPractice,
  FailurePattern,
  RecoveryPattern,
  Recommendation,
  LearningDashboard,
  ConfidenceTrends,
} from "@/services/enterprise/learning"

export function useEnterpriseLessons(limit = 50, domain?: string, lessonType?: string) {
  return useQuery({
    queryKey: ["enterprise-learning-lessons", limit, domain, lessonType],
    queryFn: async () => {
      const res = await enterpriseLearningApi.getLessons(limit, domain, lessonType)
      return res.lessons as Lesson[]
    },
    staleTime: 60_000,
  })
}

export function useEnterpriseBestPractices(limit = 50) {
  return useQuery({
    queryKey: ["enterprise-learning-best-practices", limit],
    queryFn: async () => {
      const res = await enterpriseLearningApi.getBestPractices(limit)
      return res.practices as BestPractice[]
    },
    staleTime: 120_000,
  })
}

export function useEnterpriseFailurePatterns(limit = 50) {
  return useQuery({
    queryKey: ["enterprise-learning-failure-patterns", limit],
    queryFn: async () => {
      const res = await enterpriseLearningApi.getFailurePatterns(limit)
      return res.patterns as FailurePattern[]
    },
    staleTime: 120_000,
  })
}

export function useEnterpriseRecoveryPatterns() {
  return useQuery({
    queryKey: ["enterprise-learning-recovery-patterns"],
    queryFn: async () => {
      const res = await enterpriseLearningApi.getRecoveryPatterns()
      return res.patterns as RecoveryPattern[]
    },
    staleTime: 120_000,
  })
}

export function useEnterpriseRecommendations(limit = 20, priority?: string) {
  return useQuery({
    queryKey: ["enterprise-learning-recommendations", limit, priority],
    queryFn: async () => {
      const res = await enterpriseLearningApi.getRecommendations(limit, priority)
      return res.recommendations as Recommendation[]
    },
    staleTime: 120_000,
  })
}

export function useEnterpriseLearningDashboard() {
  return useQuery({
    queryKey: ["enterprise-learning-dashboard"],
    queryFn: async () => {
      const res = await enterpriseLearningApi.getDashboard()
      return res as LearningDashboard
    },
    staleTime: 60_000,
  })
}

export function useEnterpriseLearningConfidenceTrends() {
  return useQuery({
    queryKey: ["enterprise-learning-confidence-trends"],
    queryFn: async () => {
      const res = await enterpriseLearningApi.getConfidenceTrends()
      return res as ConfidenceTrends
    },
    staleTime: 120_000,
  })
}

export function useEnterpriseLearningAnalyze() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (params: { executionId?: string; limit?: number }) => {
      const res = await enterpriseLearningApi.analyze(params.executionId, params.limit)
      return res.result
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["enterprise-learning"] })
    },
  })
}
