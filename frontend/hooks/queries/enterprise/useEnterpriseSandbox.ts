import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { enterpriseSandboxApi } from "@/services/enterprise/sandbox"
import type { Sandbox } from "@/types/sandbox"

export function useSandboxList(status?: string, language?: string) {
  return useQuery({
    queryKey: ["sandboxes", status, language],
    queryFn: async () => {
      const res = await enterpriseSandboxApi.list(status, language)
      return res.sandboxes as Sandbox[]
    },
    staleTime: 5_000,
  })
}

export function useSandbox(id: string) {
  return useQuery({
    queryKey: ["sandbox", id],
    queryFn: () => enterpriseSandboxApi.get(id),
    enabled: !!id,
    staleTime: 5_000,
  })
}

export function useSandboxLanguages() {
  return useQuery({
    queryKey: ["sandbox-languages"],
    queryFn: () => enterpriseSandboxApi.getLanguages(),
    staleTime: 300_000,
  })
}

export function useCreateSandbox() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: Parameters<typeof enterpriseSandboxApi.create>[0]) =>
      enterpriseSandboxApi.create(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["sandboxes"] }),
  })
}

export function usePrepareSandbox() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => enterpriseSandboxApi.prepare(id),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["sandboxes"] })
      queryClient.invalidateQueries({ queryKey: ["sandbox", (data as Sandbox).sandbox_id] })
    },
  })
}

export function useExecuteSandbox() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, command, language, timeout }: {
      id: string; command?: string; language?: string; timeout?: number
    }) => enterpriseSandboxApi.execute(id, command, language, timeout),
    onSuccess: (_, vars) => {
      queryClient.invalidateQueries({ queryKey: ["sandbox", vars.id] })
      queryClient.invalidateQueries({ queryKey: ["sandboxes"] })
    },
  })
}

export function usePauseSandbox() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => enterpriseSandboxApi.pause(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["sandboxes"] }),
  })
}

export function useResumeSandbox() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => enterpriseSandboxApi.resume(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["sandboxes"] }),
  })
}

export function useDestroySandbox() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => enterpriseSandboxApi.destroy(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["sandboxes"] }),
  })
}

export function useSandboxArtifacts(id: string) {
  return useQuery({
    queryKey: ["sandbox-artifacts", id],
    queryFn: () => enterpriseSandboxApi.getArtifacts(id),
    enabled: !!id,
    staleTime: 10_000,
  })
}

export function useSandboxLogs(id: string) {
  return useQuery({
    queryKey: ["sandbox-logs", id],
    queryFn: () => enterpriseSandboxApi.getLogs(id),
    enabled: !!id,
    staleTime: 5_000,
  })
}

export function useSandboxResources(id: string) {
  return useQuery({
    queryKey: ["sandbox-resources", id],
    queryFn: () => enterpriseSandboxApi.getResources(id),
    enabled: !!id,
    staleTime: 5_000,
  })
}
