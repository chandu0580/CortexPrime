import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import {
  enterpriseDeployApi,
  EnvironmentItem,
  DeploymentItem,
} from "@/services/enterprise/deploy"

export function useEnvironmentList() {
  return useQuery({
    queryKey: ["environments"],
    queryFn: async () => {
      const res = await enterpriseDeployApi.listEnvironments()
      return res.environments as EnvironmentItem[]
    },
    staleTime: 30_000,
  })
}

export function useEnvironmentDetail(id: string) {
  return useQuery({
    queryKey: ["environments", id],
    queryFn: () => enterpriseDeployApi.getEnvironment(id),
    enabled: !!id,
    staleTime: 60_000,
  })
}

export function useCreateEnvironment() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: Parameters<typeof enterpriseDeployApi.createEnvironment>[0]) =>
      enterpriseDeployApi.createEnvironment(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["environments"] }),
  })
}

export function useDeploymentList(params?: {
  workspace_id?: string
  environment_id?: string
  status?: string
  limit?: number
}) {
  return useQuery({
    queryKey: ["deployments", params],
    queryFn: async () => {
      const res = await enterpriseDeployApi.listDeployments(params)
      return res.deployments as DeploymentItem[]
    },
    staleTime: 30_000,
  })
}

export function useDeploymentDetail(id: string) {
  return useQuery({
    queryKey: ["deployments", id],
    queryFn: () => enterpriseDeployApi.getDeployment(id),
    enabled: !!id,
    staleTime: 60_000,
  })
}

export function useCreateDeployment() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: Parameters<typeof enterpriseDeployApi.createDeployment>[0]) =>
      enterpriseDeployApi.createDeployment(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["deployments"] }),
  })
}

export function useExecuteDeployment() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => enterpriseDeployApi.executeDeployment(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["deployments"] }),
  })
}

export function useRollbackDeployment() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => enterpriseDeployApi.rollbackDeployment(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["deployments"] }),
  })
}
