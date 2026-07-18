import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import {
  enterprisePatchApi,
  enterprisePatchPipelineApi,
  PatchItem,
  DiffSummary,
  PatchPlanInput,
  ValidateInput,
  CompareInput,
  AnalyzeInput,
  ApplyRefactorInput,
  PatchPlan,
  PatchCandidateDTO,
} from "@/services/enterprise/patch"

export function usePatchList(workspaceId?: string, status?: string) {
  return useQuery({
    queryKey: ["patches", workspaceId, status],
    queryFn: async () => {
      const res = await enterprisePatchApi.list(workspaceId, status)
      return res.patches as PatchItem[]
    },
    staleTime: 30_000,
  })
}

export function usePatchDetail(id: string) {
  return useQuery({
    queryKey: ["patches", id],
    queryFn: async () => {
      return enterprisePatchApi.getById(id) as Promise<PatchItem>
    },
    enabled: !!id,
    staleTime: 60_000,
  })
}

export function usePatchDiff(id: string) {
  return useQuery({
    queryKey: ["patches", id, "diff"],
    queryFn: async () => {
      return enterprisePatchApi.getDiff(id) as Promise<DiffSummary>
    },
    enabled: !!id,
    staleTime: 60_000,
  })
}

export function useCreatePatch() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (payload: {
      workspace_id: string
      title: string
      description?: string
      engineer?: string
      branch?: string
      repository_url?: string
      mission_execution_id?: string
      files_changed?: { filename: string; lines_added?: number; lines_removed?: number }[]
      categories?: string[]
    }) => {
      return enterprisePatchApi.create(payload) as Promise<PatchItem>
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["patches"] })
    },
  })
}

export function useValidatePatch() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      return enterprisePatchApi.validate(id)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["patches"] })
    },
  })
}

export function useRollbackPatch() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      return enterprisePatchApi.rollback(id) as Promise<PatchItem>
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["patches"] })
    },
  })
}

// ── Patch Pipeline hooks (Sprint 72) ──────────────────────────────────────

export function usePatchPlans() {
  return useQuery({
    queryKey: ["patch-pipeline", "plans"],
    queryFn: async () => {
      const res = await enterprisePatchPipelineApi.listPlans()
      return res.plans as PatchPlan[]
    },
    staleTime: 30_000,
  })
}

export function usePatchCandidates(planId?: string) {
  return useQuery({
    queryKey: ["patch-pipeline", "candidates", planId],
    queryFn: async () => {
      const res = await enterprisePatchPipelineApi.listCandidates(planId)
      return res.candidates as PatchCandidateDTO[]
    },
    enabled: true,
    staleTime: 30_000,
  })
}

export function useGeneratePatches() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (payload: PatchPlanInput) => {
      return enterprisePatchPipelineApi.generate(payload)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["patch-pipeline"] })
    },
  })
}

export function useValidateCandidate() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (payload: ValidateInput) => {
      return enterprisePatchPipelineApi.validate(payload)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["patch-pipeline"] })
    },
  })
}

export function useCompareCandidates() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (payload: CompareInput) => {
      return enterprisePatchPipelineApi.compare(payload)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["patch-pipeline"] })
    },
  })
}

export function useAnalyzeRefactor() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (payload: AnalyzeInput) => {
      return enterprisePatchPipelineApi.analyzeRefactor(payload)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["patch-pipeline"] })
    },
  })
}

export function useApplyRefactor() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (payload: ApplyRefactorInput) => {
      return enterprisePatchPipelineApi.applyRefactor(payload)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["patch-pipeline"] })
    },
  })
}
