import { useQuery } from "@tanstack/react-query"
import { enterpriseKnowledgeApi, SearchResult } from "@/services/enterprise/knowledge"

export function useEnterpriseSearch(q: string, sources?: string) {
  return useQuery({
    queryKey: ["enterprise-search", q, sources],
    queryFn: async () => {
      const res = await enterpriseKnowledgeApi.search(q, sources)
      return res.results as SearchResult[]
    },
    enabled: q.length >= 2,
    staleTime: 30_000,
  })
}

export function useEnterpriseEntityTypes() {
  return useQuery({
    queryKey: ["enterprise-entity-types"],
    queryFn: async () => {
      const res = await enterpriseKnowledgeApi.listEntityTypes()
      return res.types
    },
    staleTime: 300_000,
  })
}

export function useEnterpriseEntities(type: string) {
  return useQuery({
    queryKey: ["enterprise-entities", type],
    queryFn: async () => {
      const res = await enterpriseKnowledgeApi.listEntities(type)
      return res.entities
    },
    enabled: !!type,
    staleTime: 60_000,
  })
}

export function useEnterpriseNode(nodeId: string) {
  return useQuery({
    queryKey: ["enterprise-node", nodeId],
    queryFn: async () => {
      const res = await enterpriseKnowledgeApi.getNode(nodeId)
      return res
    },
    enabled: !!nodeId,
    staleTime: 30_000,
  })
}

export function useEnterpriseMissionGraph(executionId: string) {
  return useQuery({
    queryKey: ["enterprise-mission-graph", executionId],
    queryFn: async () => {
      const res = await enterpriseKnowledgeApi.getMissionGraph(executionId)
      return res
    },
    enabled: !!executionId,
    staleTime: 30_000,
  })
}

export function useEnterpriseRecentMissions() {
  return useQuery({
    queryKey: ["enterprise-recent-missions"],
    queryFn: async () => {
      const res = await enterpriseKnowledgeApi.getRecentMissions()
      return res.missions
    },
    staleTime: 60_000,
  })
}
