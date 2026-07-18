import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import * as archApi from "@/services/enterprise/architecture"

export function useArchitectureProjects(status = "") {
  return useQuery({
    queryKey: ["architecture_projects", status],
    queryFn: () => archApi.listProjects(status),
    staleTime: 15_000,
  })
}

export function useArchitectureProject(id: string) {
  return useQuery({
    queryKey: ["architecture_projects", id],
    queryFn: () => archApi.getProject(id),
    enabled: !!id,
    staleTime: 30_000,
  })
}

export function useArchitectureDashboard() {
  return useQuery({
    queryKey: ["architecture_projects", "dashboard"],
    queryFn: () => archApi.getArchitectureDashboard(),
    staleTime: 30_000,
  })
}

export function useCreateArchitectureProject() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (p: { name: string; description?: string; inputText?: string; inputType?: string }) =>
      archApi.createProject(p.name, p.description, p.inputText, p.inputType),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["architecture_projects"] }),
  })
}

export function useAnalyzeArchitecture() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (p: { name?: string; description?: string; inputText: string }) =>
      archApi.analyzeProject(p.name, p.description, p.inputText),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["architecture_projects"] }),
  })
}

export function useAnalyzeExistingArchitecture() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => archApi.analyzeExistingProject(id),
    onSuccess: (_, id) => {
      qc.invalidateQueries({ queryKey: ["architecture_projects"] })
      qc.invalidateQueries({ queryKey: ["architecture_projects", id] })
    },
  })
}

export function useDeleteArchitectureProject() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => archApi.deleteProject(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["architecture_projects"] }),
  })
}

export function useArchitectureDomains(projectId: string) {
  return useQuery({
    queryKey: ["architecture_projects", projectId, "domains"],
    queryFn: () => archApi.getDomains(projectId),
    enabled: !!projectId,
  })
}

export function useArchitectureServices(projectId: string) {
  return useQuery({
    queryKey: ["architecture_projects", projectId, "services"],
    queryFn: () => archApi.getServices(projectId),
    enabled: !!projectId,
  })
}

export function useArchitectureDatabase(projectId: string) {
  return useQuery({
    queryKey: ["architecture_projects", projectId, "database"],
    queryFn: () => archApi.getDatabase(projectId),
    enabled: !!projectId,
  })
}

export function useArchitectureApis(projectId: string) {
  return useQuery({
    queryKey: ["architecture_projects", projectId, "apis"],
    queryFn: () => archApi.getApis(projectId),
    enabled: !!projectId,
  })
}

export function useArchitectureEvents(projectId: string) {
  return useQuery({
    queryKey: ["architecture_projects", projectId, "events"],
    queryFn: () => archApi.getEvents(projectId),
    enabled: !!projectId,
  })
}

export function useArchitectureMissions(projectId: string) {
  return useQuery({
    queryKey: ["architecture_projects", projectId, "missions"],
    queryFn: () => archApi.getMissions(projectId),
    enabled: !!projectId,
  })
}

export function useArchitectureGraph(projectId: string) {
  return useQuery({
    queryKey: ["architecture_projects", projectId, "graph"],
    queryFn: () => archApi.getGraph(projectId),
    enabled: !!projectId,
  })
}
