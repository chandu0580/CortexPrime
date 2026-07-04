"use client"
import { useQuery } from "@tanstack/react-query"
import { queryKeys } from "@/lib/query"
import { intelligenceService } from "@/services/intelligence"

export function useMissionIntent(intentId: string | null) {
  return useQuery({
    queryKey: queryKeys.intelligence.intent(intentId ?? ""),
    queryFn: async () => {
      const result = await intelligenceService.validateIntent({
        text: "",
        timestamp: new Date().toISOString(),
      })
      return result
    },
    enabled: false,
  })
}
