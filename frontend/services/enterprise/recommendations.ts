import axios from "axios"
import { apiUrl } from "@/lib/constants"

export interface RecommendationAction {
  action_type: string
  label: string
  endpoint: string
  method: string
  description: string
}

export interface RecommendationEvidence {
  source: string
  detail?: string
  [key: string]: unknown
}

export interface RecommendationItem {
  id: string
  category: string
  title: string
  description: string
  reason: string
  evidence: RecommendationEvidence[]
  confidence: number
  risk: string
  priority: string
  estimated_impact: string
  estimated_cost_savings: string
  estimated_time_savings: string
  related_mission: string | null
  related_connector: string | null
  related_workflow: string | null
  learning_references: { type: string; [key: string]: unknown }[]
  replay_references: { execution_id: string; [key: string]: unknown }[]
  knowledge_graph_references: { [key: string]: unknown }[]
  verification_references: { [key: string]: unknown }[]
  actions: RecommendationAction[]
  source: string
  created_at: string
  dismissed: boolean
  dismissed_at: string | null
  executed: boolean
  executed_at: string | null
}

export interface RecommendationDashboard {
  total_recommendations: number
  active_recommendations: number
  dismissed_recommendations: number
  executed_recommendations: number
  by_priority: Record<string, number>
  by_category: Record<string, number>
  critical_count: number
  high_count: number
  medium_count: number
  low_count: number
  top_risks: RecommendationItem[]
  top_opportunities: RecommendationItem[]
  last_full_scan: string | null
  generated_at: string
}

export interface CategoryGroup {
  category: string
  count: number
  recommendations: RecommendationItem[]
  total: number
}

export const enterpriseRecommendationsApi = {
  list: async (category?: string, priority?: string): Promise<{ recommendations: RecommendationItem[]; total: number }> => {
    const params: Record<string, string> = {}
    if (category) params.category = category
    if (priority) params.priority = priority
    const res = await axios.get(`${apiUrl}/api/recommendations`, { params })
    return res.data
  },

  getDashboard: async (): Promise<RecommendationDashboard> => {
    const res = await axios.get(`${apiUrl}/api/recommendations/dashboard`)
    return res.data
  },

  getCategories: async (): Promise<{ categories: CategoryGroup[]; total_categories: number }> => {
    const res = await axios.get(`${apiUrl}/api/recommendations/categories`)
    return res.data
  },

  getById: async (id: string): Promise<RecommendationItem> => {
    const res = await axios.get(`${apiUrl}/api/recommendations/${id}`)
    return res.data
  },

  dismiss: async (id: string): Promise<{ status: string; id: string }> => {
    const res = await axios.post(`${apiUrl}/api/recommendations/${id}/dismiss`)
    return res.data
  },

  execute: async (id: string): Promise<{ status: string; id: string }> => {
    const res = await axios.post(`${apiUrl}/api/recommendations/${id}/execute`)
    return res.data
  },

  getHistory: async (limit = 100): Promise<{ history: RecommendationItem[]; total: number }> => {
    const res = await axios.get(`${apiUrl}/api/recommendations/history`, { params: { limit } })
    return res.data
  },
}
