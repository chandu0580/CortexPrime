"use client"
import { useQuery } from "@tanstack/react-query"
import { queryKeys } from "@/lib/query"

export function useMissionAssessment(analysisId: string | null) {
  return useQuery({
    queryKey: queryKeys.intelligence.assessment(analysisId ?? ""),
    queryFn: async () => {
      throw new Error("Direct assessment query not yet implemented")
    },
    enabled: false,
  })
}
