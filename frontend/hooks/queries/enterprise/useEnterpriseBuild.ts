import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { enterpriseBuildApi, BuildItem } from "@/services/enterprise/build"

export function useBuildList(workspaceId?: string, status?: string) {
  return useQuery({
    queryKey: ["builds", workspaceId, status],
    queryFn: async () => {
      const res = await enterpriseBuildApi.list(workspaceId, status)
      return res.builds as BuildItem[]
    },
    staleTime: 30_000,
  })
}

export function useBuildDetail(id: string) {
  return useQuery({
    queryKey: ["builds", id],
    queryFn: () => enterpriseBuildApi.getById(id),
    enabled: !!id,
    staleTime: 60_000,
  })
}

export function useCreateBuild() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: Parameters<typeof enterpriseBuildApi.create>[0]) =>
      enterpriseBuildApi.create(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["builds"] }),
  })
}

export function useExecuteBuild() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => enterpriseBuildApi.execute(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["builds"] }),
  })
}

export function useCancelBuild() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => enterpriseBuildApi.cancel(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["builds"] }),
  })
}
