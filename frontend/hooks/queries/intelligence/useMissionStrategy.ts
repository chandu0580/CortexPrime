"use client"
import { useQuery } from "@tanstack/react-query"
import { queryKeys } from "@/lib/query"

export function useMissionStrategy(strategyId: string | null) {
  return useQuery({
    queryKey: queryKeys.intelligence.strategy(strategyId ?? ""),
    queryFn: async () => {
      throw new Error("Direct strategy query not yet implemented")
    },
    enabled: false,
  })
}
