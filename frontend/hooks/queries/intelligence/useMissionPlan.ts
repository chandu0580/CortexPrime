"use client"
import { useQuery } from "@tanstack/react-query"
import { queryKeys } from "@/lib/query"

export function useMissionPlan(planId: string | null) {
  return useQuery({
    queryKey: queryKeys.intelligence.plan(planId ?? ""),
    queryFn: async () => {
      throw new Error("Direct plan query not yet implemented")
    },
    enabled: false,
  })
}
