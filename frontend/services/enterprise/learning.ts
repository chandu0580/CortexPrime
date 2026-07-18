import axios from "axios"
import { apiUrl } from "@/lib/constants"

export interface Lesson {
  id: string
  concept: string
  content: string
  source: string
  confidence: number
  metadata: Record<string, unknown>
  created_at: string
}

export interface BestPractice {
  id: string
  concept: string
  content: string
  source: string
  confidence: number
  metadata: Record<string, unknown>
  created_at: string
}

export interface FailurePattern {
  signature: string
  count: number
  error: string
  source: string
  id?: string
  content?: string
  confidence?: number
  metadata?: Record<string, unknown>
}

export interface RecoveryPattern {
  recovery_type: string
  count?: number
  last_used?: string
  id?: string
  content?: string
  confidence?: number
  metadata?: Record<string, unknown>
}

export interface Recommendation {
  id: string
  concept: string
  content: string
  source: string
  confidence: number
  metadata: Record<string, unknown>
  created_at: string
}

export interface LearningDashboardSummary {
  total_lessons: number
  success_lessons: number
  failure_lessons: number
  total_failure_patterns: number
  total_recovery_patterns: number
  total_recommendations: number
}

export interface LearningDashboard {
  summary: LearningDashboardSummary
  recovery_stats: Record<string, { count: number; last_used: string }>
  top_failure_patterns: { signature: string; count: number; error: string; source: string }[]
  generated_at: string
}

export interface ConfidenceTrends {
  avg_lesson_confidence: number
  avg_pattern_confidence: number
  avg_recommendation_confidence: number
  total_intelligence_entries: number
  generated_at: string
}

export interface AnalyzeResult {
  execution_id?: string
  lessons_generated?: number
  analyzed?: number
  status: string
}

export const enterpriseLearningApi = {
  getLessons: async (limit = 50, domain?: string, lessonType?: string): Promise<{ lessons: Lesson[]; total: number }> => {
    const params: Record<string, string | number> = { limit }
    if (domain) params.domain = domain
    if (lessonType) params.lesson_type = lessonType
    const res = await axios.get(`${apiUrl}/api/enterprise/learning/lessons`, { params })
    return res.data
  },

  getBestPractices: async (limit = 50): Promise<{ practices: BestPractice[]; total: number }> => {
    const res = await axios.get(`${apiUrl}/api/enterprise/learning/best-practices`, { params: { limit } })
    return res.data
  },

  getFailurePatterns: async (limit = 50): Promise<{ patterns: FailurePattern[]; total: number }> => {
    const res = await axios.get(`${apiUrl}/api/enterprise/learning/failure-patterns`, { params: { limit } })
    return res.data
  },

  getRecoveryPatterns: async (): Promise<{ patterns: RecoveryPattern[]; total: number }> => {
    const res = await axios.get(`${apiUrl}/api/enterprise/learning/recovery-patterns`)
    return res.data
  },

  getRecommendations: async (limit = 20, priority?: string): Promise<{ recommendations: Recommendation[]; total: number }> => {
    const params: Record<string, string | number> = { limit }
    if (priority) params.priority = priority
    const res = await axios.get(`${apiUrl}/api/enterprise/learning/recommendations`, { params })
    return res.data
  },

  getDashboard: async (): Promise<LearningDashboard> => {
    const res = await axios.get(`${apiUrl}/api/enterprise/learning/dashboard`)
    return res.data
  },

  getConfidenceTrends: async (): Promise<ConfidenceTrends> => {
    const res = await axios.get(`${apiUrl}/api/enterprise/learning/confidence-trends`)
    return res.data
  },

  analyze: async (executionId?: string, limit = 50): Promise<{ status: string; result: AnalyzeResult }> => {
    const params: Record<string, string | number> = { limit }
    if (executionId) params.execution_id = executionId
    const res = await axios.post(`${apiUrl}/api/enterprise/learning/analyze`, null, { params })
    return res.data
  },
}
