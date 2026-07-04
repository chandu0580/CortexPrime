"use client"
import { useMutation } from "@tanstack/react-query"
import { queryClient } from "@/lib/query"
import { intelligenceService } from "@/services/intelligence"
import { queryKeys } from "@/lib/query"
import type { IntentInput } from "@/types/intelligence"

export function useAnalyzeIntent() {
  return useMutation({
    mutationFn: (input: IntentInput) => intelligenceService.analyzeIntent(input),
    onSuccess: (data) => {
      queryClient.setQueryData(queryKeys.intelligence.intent(data.intentId), data.intent)
      queryClient.setQueryData(queryKeys.intelligence.analysis(data.intentId), data)
      queryClient.setQueryData(queryKeys.intelligence.assessment(data.intentId), data.assessment)
      queryClient.setQueryData(queryKeys.intelligence.preview(data.intentId), data.preview)
    },
  })
}
