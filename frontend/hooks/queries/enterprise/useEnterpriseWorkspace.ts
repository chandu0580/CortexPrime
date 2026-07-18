import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import {
  enterpriseWorkspaceApi,
  WorkspaceItem,
  RepositoryInfo,
  WorkspaceStatus,
  WorkspaceArtifact,
} from "@/services/enterprise/workspace"

export function useWorkspaceList(status?: string) {
  return useQuery({
    queryKey: ["workspaces", status],
    queryFn: async () => {
      const res = await enterpriseWorkspaceApi.listWorkspaces(status)
      return res.workspaces as WorkspaceItem[]
    },
    staleTime: 30_000,
  })
}

export function useWorkspaceDetail(id: string) {
  return useQuery({
    queryKey: ["workspaces", id],
    queryFn: async () => {
      return enterpriseWorkspaceApi.getWorkspace(id) as Promise<WorkspaceItem>
    },
    enabled: !!id,
    staleTime: 30_000,
  })
}

export function useWorkspaceStatus(id: string) {
  return useQuery({
    queryKey: ["workspaces", id, "status"],
    queryFn: async () => {
      return enterpriseWorkspaceApi.getWorkspaceStatus(id) as Promise<WorkspaceStatus>
    },
    enabled: !!id,
    staleTime: 15_000,
  })
}

export function useWorkspaceArtifacts(id: string) {
  return useQuery({
    queryKey: ["workspaces", id, "artifacts"],
    queryFn: async () => {
      const res = await enterpriseWorkspaceApi.getWorkspaceArtifacts(id)
      return res.artifacts as WorkspaceArtifact[]
    },
    enabled: !!id,
    staleTime: 30_000,
  })
}

export function useRepositories() {
  return useQuery({
    queryKey: ["engineering-repositories"],
    queryFn: async () => {
      const res = await enterpriseWorkspaceApi.listRepositories()
      return res.repositories as { url: string; name: string; languages: Record<string, number>; analyzed_at: string }[]
    },
    staleTime: 60_000,
  })
}

export function useRepositoryIntelligence(repoUrl: string, branch = "main") {
  return useQuery({
    queryKey: ["engineering-repository-intelligence", repoUrl, branch],
    queryFn: async () => {
      return enterpriseWorkspaceApi.getRepositoryIntelligence(repoUrl, branch) as Promise<RepositoryInfo>
    },
    enabled: !!repoUrl,
    staleTime: 300_000,
  })
}

export function useCreateWorkspace() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ name, repoUrl, branch }: { name: string; repoUrl?: string; branch?: string }) => {
      return enterpriseWorkspaceApi.createWorkspace(name, repoUrl, branch) as Promise<WorkspaceItem>
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["workspaces"] })
      queryClient.invalidateQueries({ queryKey: ["engineering-repositories"] })
    },
  })
}

export function useDestroyWorkspace() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      return enterpriseWorkspaceApi.destroyWorkspace(id)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["workspaces"] })
    },
  })
}

export function useCheckoutBranch() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ wsId, branch }: { wsId: string; branch: string }) => {
      return enterpriseWorkspaceApi.checkoutBranch(wsId, branch)
    },
    onSuccess: (_, vars) => {
      queryClient.invalidateQueries({ queryKey: ["workspaces", vars.wsId] })
      queryClient.invalidateQueries({ queryKey: ["workspaces", vars.wsId, "status"] })
    },
  })
}
