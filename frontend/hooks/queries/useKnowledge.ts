"use client"

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api-client"
import type { KnowledgeEntry } from "@/types/enterprise"

export function useKnowledgeSearch(query: string) {
  return useQuery<{ entries: KnowledgeEntry[]; total: number }>({
    queryKey: ["knowledge-search", query],
    queryFn: () =>
      api.get("/api/knowledge/search", { params: { query, limit: 50 } }).then((r) => r.data),
    enabled: query.length > 2,
  })
}

export function useKnowledgeGraph() {
  return useQuery<{ nodes: unknown[]; edges: unknown[] }>({
    queryKey: ["knowledge-graph"],
    queryFn: () => api.get("/api/knowledge/graph").then((r) => r.data),
    refetchInterval: 30_000,
  })
}

export function useIndexMission() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { mission_id: string; content: string; title: string }) =>
      api.post("/api/knowledge/index", data).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["knowledge-search"] }),
  })
}
