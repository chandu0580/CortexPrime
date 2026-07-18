import { useQuery, useMutation } from "@tanstack/react-query"
import { enterpriseCodeApi } from "@/services/enterprise/code-intelligence"
import type { RepositoryScan, DependencyGraph, ImpactResult } from "@/types/code-intelligence"

export function useCodeRepositories() {
  return useQuery({
    queryKey: ["code-repositories"],
    queryFn: () => enterpriseCodeApi.listRepositories(),
    staleTime: 30_000,
  })
}

export function useScanRepository() {
  return useMutation({
    mutationFn: (path: string) => enterpriseCodeApi.scan(path),
  })
}

export function useCodeGraph(repoId?: string) {
  return useQuery({
    queryKey: ["code-graph", repoId],
    queryFn: () => enterpriseCodeApi.getGraph(repoId) as Promise<DependencyGraph>,
    staleTime: 30_000,
  })
}

export function useCodeFunctions(repoId?: string) {
  return useQuery({
    queryKey: ["code-functions", repoId],
    queryFn: () => enterpriseCodeApi.getFunctions(repoId),
    staleTime: 30_000,
  })
}

export function useCodeClasses(repoId?: string) {
  return useQuery({
    queryKey: ["code-classes", repoId],
    queryFn: () => enterpriseCodeApi.getClasses(repoId),
    staleTime: 30_000,
  })
}

export function useCodeDependencies(nodeId?: string) {
  return useQuery({
    queryKey: ["code-dependencies", nodeId],
    queryFn: () => enterpriseCodeApi.getDependencies(nodeId),
    enabled: !!nodeId,
    staleTime: 30_000,
  })
}

export function useAnalyzeImpact() {
  return useMutation({
    mutationFn: ({ changedFile, repoId }: { changedFile: string; repoId?: string }) =>
      enterpriseCodeApi.analyzeImpact(changedFile, repoId) as Promise<ImpactResult>,
  })
}
