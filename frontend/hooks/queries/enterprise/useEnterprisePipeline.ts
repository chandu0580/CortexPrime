import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import type { PipelineRun, PipelineCreateRequest, PipelineDashboardStats, PatchToPrResult } from "@/types/pipeline"
import * as pipelineApi from "@/services/enterprise/pipeline"

export function usePipelineList(status = "") {
  return useQuery({
    queryKey: ["pipelines", status],
    queryFn: () => pipelineApi.listPipelines(status),
    staleTime: 15_000,
  })
}

export function usePipelineDetail(id: string) {
  return useQuery({
    queryKey: ["pipelines", id],
    queryFn: () => pipelineApi.getPipeline(id),
    enabled: !!id,
    staleTime: 10_000,
    refetchInterval: (query) =>
      query.state.data?.status === "running" ? 5_000 : false,
  })
}

export function usePipelineDashboard() {
  return useQuery({
    queryKey: ["pipelines", "dashboard"],
    queryFn: () => pipelineApi.getPipelineDashboard(),
    staleTime: 30_000,
  })
}

export function useCreatePipeline() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (req: PipelineCreateRequest) => pipelineApi.createPipeline(req),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pipelines"] })
    },
  })
}

export function useStartPipeline() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => pipelineApi.startPipeline(id),
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: ["pipelines"] })
      queryClient.invalidateQueries({ queryKey: ["pipelines", id] })
    },
  })
}

export function usePausePipeline() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => pipelineApi.pausePipeline(id),
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: ["pipelines", id] })
    },
  })
}

export function useResumePipeline() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => pipelineApi.resumePipeline(id),
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: ["pipelines", id] })
    },
  })
}

export function useCancelPipeline() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => pipelineApi.cancelPipeline(id),
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: ["pipelines"] })
      queryClient.invalidateQueries({ queryKey: ["pipelines", id] })
    },
  })
}

export function useDeletePipeline() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => pipelineApi.deletePipeline(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pipelines"] })
    },
  })
}

export function usePatchToPr() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (req: Parameters<typeof pipelineApi.patchToPr>[0]) =>
      pipelineApi.patchToPr(req),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pipelines"] })
    },
  })
}
