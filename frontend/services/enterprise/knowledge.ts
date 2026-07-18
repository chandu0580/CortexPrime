import axios from "axios"
import { apiUrl } from "@/lib/constants"

export interface SearchResult {
  source: string
  label: string
  score: number
  title: string
  description: unknown
  id: string
}

export interface SearchResponse {
  query: string
  results: SearchResult[]
  total: number
  sources_queried: string[]
}

export interface EntityType {
  label: string
  description: string
}

export interface EntityListResponse {
  type: string
  entities: Record<string, unknown>[]
  total: number
}

export interface ConnectedNode {
  node: Record<string, unknown>
  relationships: { type: string; node: Record<string, unknown> }[]
}

export interface MissionGraph {
  mission: Record<string, unknown> | null
  actions: Record<string, unknown>[]
  artifacts: Record<string, unknown>[]
  evidence: Record<string, unknown>[]
  decisions: Record<string, unknown>[]
  approvals: Record<string, unknown>[]
  risks: Record<string, unknown>[]
  recoveries: Record<string, unknown>[]
  outcomes: Record<string, unknown>[]
}

export const enterpriseKnowledgeApi = {
  search: async (q: string, sources?: string, limit = 20): Promise<SearchResponse> => {
    const params: Record<string, string | number> = { q, limit }
    if (sources) params.sources = sources
    const res = await axios.get(`${apiUrl}/api/enterprise/search`, { params })
    return res.data
  },

  listEntityTypes: async (): Promise<{ types: EntityType[] }> => {
    const res = await axios.get(`${apiUrl}/api/enterprise/graph/entities`)
    return res.data
  },

  listEntities: async (type: string, limit = 50): Promise<EntityListResponse> => {
    const res = await axios.get(`${apiUrl}/api/enterprise/graph/entities/${type}`, { params: { limit } })
    return res.data
  },

  getNode: async (nodeId: string): Promise<ConnectedNode> => {
    const res = await axios.get(`${apiUrl}/api/enterprise/graph/node/${nodeId}`)
    return res.data
  },

  getMissionGraph: async (executionId: string): Promise<MissionGraph> => {
    const res = await axios.get(`${apiUrl}/api/enterprise/graph/mission/${executionId}`)
    return res.data
  },

  getRecentMissions: async (limit = 20): Promise<{ missions: Record<string, unknown>[]; total: number }> => {
    const res = await axios.get(`${apiUrl}/api/enterprise/graph/recent-missions`, { params: { limit } })
    return res.data
  },
}
