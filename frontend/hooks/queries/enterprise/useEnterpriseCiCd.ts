import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { enterpriseCiCdApi } from "@/services/enterprise/cicd"

const KEYS = {
  dashboard: ["cicd", "dashboard"] as const,
  timeline: (limit?: number) => ["cicd", "timeline", limit] as const,
  builds: (params?: { platform?: string; status?: string }) => ["cicd", "builds", params] as const,
  build: (id: string) => ["cicd", "builds", id] as const,
  buildTrends: ["cicd", "builds", "trends"] as const,
  deployments: (params?: { environment?: string; status?: string }) => ["cicd", "deployments", params] as const,
  deployment: (id: string) => ["cicd", "deployments", id] as const,
  envHealth: ["cicd", "deployments", "environments", "health"] as const,
  artifacts: (params?: { artifact_type?: string; build_id?: string }) => ["cicd", "artifacts", params] as const,
  artifact: (id: string) => ["cicd", "artifacts", id] as const,
  failures: (entityType?: string) => ["cicd", "failures", entityType] as const,
  failure: (id: string) => ["cicd", "failures", id] as const,
  recoveries: (limit?: number) => ["cicd", "recoveries", limit] as const,
  recovery: (id: string) => ["cicd", "recoveries", id] as const,
  platforms: ["cicd", "platforms"] as const,
}

// ---- Dashboard ----

export function useCiCdDashboard() {
  return useQuery({
    queryKey: KEYS.dashboard,
    queryFn: () => enterpriseCiCdApi.getDashboard(),
    refetchInterval: 10_000,
  })
}

export function useCiCdTimeline(limit = 50) {
  return useQuery({
    queryKey: KEYS.timeline(limit),
    queryFn: () => enterpriseCiCdApi.getTimeline(limit),
    refetchInterval: 15_000,
  })
}

// ---- Builds ----

export function useCiCdBuilds(params?: { platform?: string; status?: string }) {
  return useQuery({
    queryKey: KEYS.builds(params),
    queryFn: () => enterpriseCiCdApi.listBuilds(params),
    refetchInterval: 15_000,
  })
}

export function useCiCdBuild(buildId: string) {
  return useQuery({
    queryKey: KEYS.build(buildId),
    queryFn: () => enterpriseCiCdApi.getBuild(buildId),
    enabled: !!buildId,
  })
}

export function useCiCdBuildTrends() {
  return useQuery({
    queryKey: KEYS.buildTrends,
    queryFn: () => enterpriseCiCdApi.getBuildTrends(),
    staleTime: 60_000,
  })
}

// ---- Deployments ----

export function useCiCdDeployments(params?: { environment?: string; status?: string }) {
  return useQuery({
    queryKey: KEYS.deployments(params),
    queryFn: () => enterpriseCiCdApi.listDeployments(params),
    refetchInterval: 15_000,
  })
}

export function useCiCdDeployment(deploymentId: string) {
  return useQuery({
    queryKey: KEYS.deployment(deploymentId),
    queryFn: () => enterpriseCiCdApi.getDeployment(deploymentId),
    enabled: !!deploymentId,
  })
}

export function useCiCdEnvironmentHealth() {
  return useQuery({
    queryKey: KEYS.envHealth,
    queryFn: () => enterpriseCiCdApi.getEnvironmentHealth(),
    refetchInterval: 30_000,
  })
}

// ---- Artifacts ----

export function useCiCdArtifacts(params?: { artifact_type?: string; build_id?: string }) {
  return useQuery({
    queryKey: KEYS.artifacts(params),
    queryFn: () => enterpriseCiCdApi.listArtifacts(params),
    refetchInterval: 30_000,
  })
}

export function useCiCdArtifact(artifactId: string) {
  return useQuery({
    queryKey: KEYS.artifact(artifactId),
    queryFn: () => enterpriseCiCdApi.getArtifact(artifactId),
    enabled: !!artifactId,
  })
}

// ---- Failures ----

export function useCiCdFailures(entityType?: string) {
  return useQuery({
    queryKey: KEYS.failures(entityType),
    queryFn: () => enterpriseCiCdApi.listFailures(entityType),
    refetchInterval: 30_000,
  })
}

export function useCiCdFailure(failureId: string) {
  return useQuery({
    queryKey: KEYS.failure(failureId),
    queryFn: () => enterpriseCiCdApi.getFailure(failureId),
    enabled: !!failureId,
  })
}

// ---- Recoveries ----

export function useCiCdRecoveries(limit = 100) {
  return useQuery({
    queryKey: KEYS.recoveries(limit),
    queryFn: () => enterpriseCiCdApi.listRecoveries(limit),
    refetchInterval: 30_000,
  })
}

export function useCiCdRecovery(recoveryId: string) {
  return useQuery({
    queryKey: KEYS.recovery(recoveryId),
    queryFn: () => enterpriseCiCdApi.getRecovery(recoveryId),
    enabled: !!recoveryId,
  })
}

// ---- Platforms ----

export function useCiCdPlatforms() {
  return useQuery({
    queryKey: KEYS.platforms,
    queryFn: () => enterpriseCiCdApi.listPlatforms(),
    staleTime: 300_000,
  })
}

// ---- Mutations ----

export function useIngestPipelineEvent() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (params: { eventType: string; payload: Record<string, any> }) =>
      enterpriseCiCdApi.ingestPipelineEvent(params.eventType, params.payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.dashboard })
      qc.invalidateQueries({ queryKey: KEYS.timeline() })
      qc.invalidateQueries({ queryKey: KEYS.builds() })
    },
  })
}

export function useIngestBuildEvent() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (params: { platform: string; buildData: Record<string, any> }) =>
      enterpriseCiCdApi.ingestBuildEvent(params.platform, params.buildData),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.dashboard })
      qc.invalidateQueries({ queryKey: KEYS.builds() })
      qc.invalidateQueries({ queryKey: KEYS.timeline() })
    },
  })
}

export function useIngestDeploymentEvent() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (params: { platform: string; deployData: Record<string, any> }) =>
      enterpriseCiCdApi.ingestDeploymentEvent(params.platform, params.deployData),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.dashboard })
      qc.invalidateQueries({ queryKey: KEYS.deployments() })
      qc.invalidateQueries({ queryKey: KEYS.envHealth })
      qc.invalidateQueries({ queryKey: KEYS.timeline() })
    },
  })
}

export function useIngestArtifactEvent() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (artifactData: Record<string, any>) =>
      enterpriseCiCdApi.ingestArtifactEvent(artifactData),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.dashboard })
      qc.invalidateQueries({ queryKey: KEYS.artifacts() })
      qc.invalidateQueries({ queryKey: KEYS.timeline() })
    },
  })
}

export function useFailureAndRecover() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (params: { entityId: string; entityType: string; logs: string[]; strategy?: string }) =>
      enterpriseCiCdApi.failureAndRecover(params.entityId, params.entityType, params.logs, params.strategy),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.dashboard })
      qc.invalidateQueries({ queryKey: KEYS.failures() })
      qc.invalidateQueries({ queryKey: KEYS.recoveries() })
      qc.invalidateQueries({ queryKey: KEYS.deployments() })
    },
  })
}

export function useCreateRecovery() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (params: { entityId: string; strategy: string }) =>
      enterpriseCiCdApi.createRecovery(params.entityId, params.strategy),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.recoveries() })
      qc.invalidateQueries({ queryKey: KEYS.dashboard })
      qc.invalidateQueries({ queryKey: KEYS.deployments() })
    },
  })
}
