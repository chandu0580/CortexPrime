"use client"
import { useQuery } from "@tanstack/react-query"
import { queryKeys } from "@/lib/query"

export function useMissionPreview(analysisId: string | null) {
  return useQuery({
    queryKey: queryKeys.intelligence.preview(analysisId ?? ""),
    queryFn: async () => {
      throw new Error("Direct preview query not yet implemented")
    },
    enabled: false,
  })
}
