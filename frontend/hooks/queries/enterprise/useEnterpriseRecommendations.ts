import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import {
  enterpriseRecommendationsApi,
  RecommendationItem,
  RecommendationDashboard,
  CategoryGroup,
} from "@/services/enterprise/recommendations"

export function useRecommendations(category?: string, priority?: string) {
  return useQuery({
    queryKey: ["recommendations", category, priority],
    queryFn: async () => {
      const res = await enterpriseRecommendationsApi.list(category, priority)
      return res.recommendations as RecommendationItem[]
    },
    staleTime: 30_000,
  })
}

export function useRecommendationDashboard() {
  return useQuery({
    queryKey: ["recommendations-dashboard"],
    queryFn: async () => {
      const res = await enterpriseRecommendationsApi.getDashboard()
      return res as RecommendationDashboard
    },
    staleTime: 30_000,
  })
}

export function useRecommendationCategories() {
  return useQuery({
    queryKey: ["recommendations-categories"],
    queryFn: async () => {
      const res = await enterpriseRecommendationsApi.getCategories()
      return res.categories as CategoryGroup[]
    },
    staleTime: 30_000,
  })
}

export function useRecommendationDetail(id: string) {
  return useQuery({
    queryKey: ["recommendations", id],
    queryFn: async () => {
      const res = await enterpriseRecommendationsApi.getById(id)
      return res as RecommendationItem
    },
    enabled: !!id,
    staleTime: 60_000,
  })
}

export function useRecommendationHistory(limit = 100) {
  return useQuery({
    queryKey: ["recommendations-history", limit],
    queryFn: async () => {
      const res = await enterpriseRecommendationsApi.getHistory(limit)
      return res.history as RecommendationItem[]
    },
    staleTime: 60_000,
  })
}

export function useDismissRecommendation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      return enterpriseRecommendationsApi.dismiss(id)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["recommendations"] })
      queryClient.invalidateQueries({ queryKey: ["recommendations-dashboard"] })
      queryClient.invalidateQueries({ queryKey: ["recommendations-categories"] })
      queryClient.invalidateQueries({ queryKey: ["recommendations-history"] })
    },
  })
}

export function useExecuteRecommendation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      return enterpriseRecommendationsApi.execute(id)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["recommendations"] })
      queryClient.invalidateQueries({ queryKey: ["recommendations-dashboard"] })
      queryClient.invalidateQueries({ queryKey: ["recommendations-categories"] })
      queryClient.invalidateQueries({ queryKey: ["recommendations-history"] })
    },
  })
}
