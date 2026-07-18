import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { enterpriseInfraApi } from "@/services/enterprise/infrastructure"

const KEYS = {
  dashboard: ["infra", "dashboard"] as const,
  timeline: (limit?: number) => ["infra", "timeline", limit] as const,
  clusters: (limit?: number) => ["infra", "clusters", limit] as const,
  cluster: (id: string) => ["infra", "clusters", id] as const,
  pods: (params?: { namespace?: string; status?: string }) => ["infra", "pods", params] as const,
  podHealth: (namespace?: string) => ["infra", "pods", "health", namespace] as const,
  nodes: (clusterId?: string) => ["infra", "nodes", clusterId] as const,
  nodeUtilization: (clusterId?: string) => ["infra", "nodes", "utilization", clusterId] as const,
  deployments: (params?: { namespace?: string; cluster_id?: string }) => ["infra", "deployments", params] as const,
  deploymentHealth: (clusterId?: string) => ["infra", "deployments", "health", clusterId] as const,
  pvcs: (params?: { namespace?: string }) => ["infra", "pvcs", params] as const,
  networkFailures: (params?: { resolved?: boolean }) => ["infra", "network-failures", params] as const,
  dockerContainers: (params?: { status?: string; host?: string }) => ["infra", "docker", "containers", params] as const,
  dockerContainer: (id: string) => ["infra", "docker", "containers", id] as const,
  dockerHealth: ["infra", "docker", "health"] as const,
  helmReleases: (params?: { namespace?: string; status?: string }) => ["infra", "helm", "releases", params] as const,
  helmRelease: (id: string) => ["infra", "helm", "releases", id] as const,
  helmHealth: ["infra", "helm", "health"] as const,
  prometheusAlerts: (params?: { severity?: string; status?: string }) => ["infra", "prometheus", "alerts", params] as const,
  correlatedAlerts: (threshold?: number) => ["infra", "prometheus", "correlated", threshold] as const,
  prometheusStats: ["infra", "prometheus", "stats"] as const,
  grafanaDashboards: (folder?: string) => ["infra", "grafana", "dashboards", folder] as const,
  grafanaDashboard: (id: string) => ["infra", "grafana", "dashboards", id] as const,
  grafanaStats: ["infra", "grafana", "stats"] as const,
  lokiAnalyses: (stream?: string) => ["infra", "loki", "analyses", stream] as const,
  lokiAnalysis: (id: string) => ["infra", "loki", "analyses", id] as const,
  lokiSearch: (query?: string) => ["infra", "loki", "search", query] as const,
  traces: (params?: { service_name?: string; status?: string }) => ["infra", "traces", params] as const,
  trace: (id: string) => ["infra", "traces", id] as const,
  traceHealth: ["infra", "traces", "health"] as const,
  platforms: ["infra", "platforms"] as const,
  events: ["infra", "events"] as const,
}

// ---- Dashboard ----

export function useInfraDashboard() {
  return useQuery({
    queryKey: KEYS.dashboard,
    queryFn: () => enterpriseInfraApi.getDashboard(),
    refetchInterval: 10_000,
  })
}

export function useInfraTimeline(limit = 50) {
  return useQuery({
    queryKey: KEYS.timeline(limit),
    queryFn: () => enterpriseInfraApi.getTimeline(limit),
    refetchInterval: 15_000,
  })
}

// ---- Clusters ----

export function useInfraClusters(limit = 100) {
  return useQuery({
    queryKey: KEYS.clusters(limit),
    queryFn: () => enterpriseInfraApi.listClusters(limit),
    refetchInterval: 30_000,
  })
}

export function useInfraCluster(clusterId: string) {
  return useQuery({
    queryKey: KEYS.cluster(clusterId),
    queryFn: () => enterpriseInfraApi.getCluster(clusterId),
    enabled: !!clusterId,
  })
}

// ---- Pods ----

export function useInfraPods(params?: { namespace?: string; status?: string }) {
  return useQuery({
    queryKey: KEYS.pods(params),
    queryFn: () => enterpriseInfraApi.listPods(params),
    refetchInterval: 15_000,
  })
}

export function useInfraPodHealth(namespace?: string) {
  return useQuery({
    queryKey: KEYS.podHealth(namespace),
    queryFn: () => enterpriseInfraApi.getPodHealth(namespace),
    refetchInterval: 15_000,
  })
}

// ---- Nodes ----

export function useInfraNodes(clusterId?: string) {
  return useQuery({
    queryKey: KEYS.nodes(clusterId),
    queryFn: () => enterpriseInfraApi.listNodes(clusterId),
    refetchInterval: 30_000,
  })
}

export function useInfraNodeUtilization(clusterId?: string) {
  return useQuery({
    queryKey: KEYS.nodeUtilization(clusterId),
    queryFn: () => enterpriseInfraApi.getNodeUtilization(clusterId),
    refetchInterval: 30_000,
  })
}

// ---- Deployments ----

export function useInfraDeployments(params?: { namespace?: string; cluster_id?: string }) {
  return useQuery({
    queryKey: KEYS.deployments(params),
    queryFn: () => enterpriseInfraApi.listDeployments(params),
    refetchInterval: 15_000,
  })
}

export function useInfraDeploymentHealth(clusterId?: string) {
  return useQuery({
    queryKey: KEYS.deploymentHealth(clusterId),
    queryFn: () => enterpriseInfraApi.getDeploymentHealth(clusterId),
    refetchInterval: 15_000,
  })
}

// ---- PVCs ----

export function useInfraPvcs(params?: { namespace?: string; cluster_id?: string }) {
  return useQuery({
    queryKey: KEYS.pvcs(params),
    queryFn: () => enterpriseInfraApi.listPvcs(params),
    refetchInterval: 30_000,
  })
}

// ---- Network Failures ----

export function useInfraNetworkFailures(params?: { cluster_id?: string; resolved?: boolean }) {
  return useQuery({
    queryKey: KEYS.networkFailures(params),
    queryFn: () => enterpriseInfraApi.listNetworkFailures(params),
    refetchInterval: 30_000,
  })
}

// ---- Docker ----

export function useInfraDockerContainers(params?: { status?: string; host?: string }) {
  return useQuery({
    queryKey: KEYS.dockerContainers(params),
    queryFn: () => enterpriseInfraApi.listDockerContainers(params),
    refetchInterval: 30_000,
  })
}

export function useInfraDockerContainer(dockerId: string) {
  return useQuery({
    queryKey: KEYS.dockerContainer(dockerId),
    queryFn: () => enterpriseInfraApi.getDockerContainer(dockerId),
    enabled: !!dockerId,
  })
}

export function useInfraDockerHealth() {
  return useQuery({
    queryKey: KEYS.dockerHealth,
    queryFn: () => enterpriseInfraApi.getDockerHealth(),
    refetchInterval: 30_000,
  })
}

// ---- Helm ----

export function useInfraHelmReleases(params?: { namespace?: string; status?: string }) {
  return useQuery({
    queryKey: KEYS.helmReleases(params),
    queryFn: () => enterpriseInfraApi.listHelmReleases(params),
    refetchInterval: 30_000,
  })
}

export function useInfraHelmRelease(releaseId: string) {
  return useQuery({
    queryKey: KEYS.helmRelease(releaseId),
    queryFn: () => enterpriseInfraApi.getHelmRelease(releaseId),
    enabled: !!releaseId,
  })
}

export function useInfraHelmHealth() {
  return useQuery({
    queryKey: KEYS.helmHealth,
    queryFn: () => enterpriseInfraApi.getHelmHealth(),
    refetchInterval: 30_000,
  })
}

// ---- Prometheus ----

export function useInfraPrometheusAlerts(params?: { severity?: string; status?: string }) {
  return useQuery({
    queryKey: KEYS.prometheusAlerts(params),
    queryFn: () => enterpriseInfraApi.listPrometheusAlerts(params),
    refetchInterval: 15_000,
  })
}

export function useInfraCorrelatedAlerts(threshold = 3) {
  return useQuery({
    queryKey: KEYS.correlatedAlerts(threshold),
    queryFn: () => enterpriseInfraApi.getCorrelatedAlerts(threshold),
    refetchInterval: 30_000,
  })
}

export function useInfraPrometheusStats() {
  return useQuery({
    queryKey: KEYS.prometheusStats,
    queryFn: () => enterpriseInfraApi.getPrometheusStats(),
    refetchInterval: 30_000,
  })
}

// ---- Prometheus Live Query / Targets / Metrics ----

export function usePrometheusQuery() {
  return useMutation({
    mutationFn: (promql: string) => enterpriseInfraApi.prometheusQuery(promql),
  })
}

export function usePrometheusCollect() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => enterpriseInfraApi.prometheusCollect(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["infra", "prometheus", "metrics"] })
    },
  })
}

export function usePrometheusSyncAlerts() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => enterpriseInfraApi.prometheusSyncAlerts(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.prometheusAlerts() })
      qc.invalidateQueries({ queryKey: KEYS.prometheusStats })
    },
  })
}

export function usePrometheusTargets() {
  return useQuery({
    queryKey: ["infra", "prometheus", "targets"] as const,
    queryFn: () => enterpriseInfraApi.prometheusTargets(),
    refetchInterval: 30_000,
  })
}

export function usePrometheusLiveAlerts() {
  return useQuery({
    queryKey: ["infra", "prometheus", "live-alerts"] as const,
    queryFn: () => enterpriseInfraApi.prometheusLiveAlerts(),
    refetchInterval: 30_000,
  })
}

export function usePrometheusMetricsSnapshot() {
  return useQuery({
    queryKey: ["infra", "prometheus", "metrics"] as const,
    queryFn: () => enterpriseInfraApi.prometheusMetrics(),
    refetchInterval: 30_000,
  })
}

// ---- Grafana ----

export function useInfraGrafanaDashboards(folder?: string) {
  return useQuery({
    queryKey: KEYS.grafanaDashboards(folder),
    queryFn: () => enterpriseInfraApi.listGrafanaDashboards(folder),
    refetchInterval: 60_000,
  })
}

export function useInfraGrafanaDashboard(dashboardId: string) {
  return useQuery({
    queryKey: KEYS.grafanaDashboard(dashboardId),
    queryFn: () => enterpriseInfraApi.getGrafanaDashboard(dashboardId),
    enabled: !!dashboardId,
  })
}

export function useInfraGrafanaStats() {
  return useQuery({
    queryKey: KEYS.grafanaStats,
    queryFn: () => enterpriseInfraApi.getGrafanaStats(),
    staleTime: 120_000,
  })
}

// ---- Loki (Real Loki HTTP API) ----

export function useLokiLabels() {
  return useQuery({
    queryKey: ["infra", "loki", "labels"] as const,
    queryFn: () => enterpriseInfraApi.lokiLabels(),
    refetchInterval: 60_000,
  })
}

export function useLokiLabelValues(label: string) {
  return useQuery({
    queryKey: ["infra", "loki", "labels", label, "values"] as const,
    queryFn: () => enterpriseInfraApi.lokiLabelValues(label),
    enabled: !!label,
  })
}

export function useLokiQuery(query: string, limit = 100) {
  return useQuery({
    queryKey: ["infra", "loki", "query", query, limit] as const,
    queryFn: () => enterpriseInfraApi.lokiQuery(query, limit),
    enabled: !!query,
    staleTime: 15_000,
  })
}

export function useLokiStreams(match = "{}") {
  return useQuery({
    queryKey: ["infra", "loki", "streams", match] as const,
    queryFn: () => enterpriseInfraApi.lokiStreams(match),
    refetchInterval: 30_000,
  })
}

export function useLokiTargetLogs(targetType: string, targetName: string, minutes = 15) {
  return useQuery({
    queryKey: ["infra", "loki", "target", targetType, targetName, minutes] as const,
    queryFn: () => enterpriseInfraApi.lokiTargetLogs(targetType, targetName, minutes),
    enabled: !!targetType && !!targetName,
    refetchInterval: 30_000,
  })
}

export function useLokiAnalyze() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: { logql?: string; limit?: number }) => enterpriseInfraApi.lokiAnalyze(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["infra", "loki", "analyze"] })
    },
  })
}

export function useLokiCorrelate() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: { logql?: string; entities?: Record<string, string[]> }) => enterpriseInfraApi.lokiCorrelate(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["infra", "loki", "correlate"] })
    },
  })
}

// ---- Loki (Legacy) ----

export function useInfraLokiAnalyses(stream?: string) {
  return useQuery({
    queryKey: KEYS.lokiAnalyses(stream),
    queryFn: () => enterpriseInfraApi.listLokiAnalyses(stream),
    refetchInterval: 30_000,
  })
}

export function useInfraLokiAnalysis(analysisId: string) {
  return useQuery({
    queryKey: KEYS.lokiAnalysis(analysisId),
    queryFn: () => enterpriseInfraApi.getLokiAnalysis(analysisId),
    enabled: !!analysisId,
  })
}

export function useInfraLokiSearch(query: string) {
  return useQuery({
    queryKey: KEYS.lokiSearch(query),
    queryFn: () => enterpriseInfraApi.lokiSearch(query),
    enabled: !!query,
    staleTime: 30_000,
  })
}

// ---- Traces ----

export function useInfraTraces(params?: { service_name?: string; status?: string }) {
  return useQuery({
    queryKey: KEYS.traces(params),
    queryFn: () => enterpriseInfraApi.listTraces(params),
    refetchInterval: 30_000,
  })
}

export function useInfraTrace(traceEntryId: string) {
  return useQuery({
    queryKey: KEYS.trace(traceEntryId),
    queryFn: () => enterpriseInfraApi.getTrace(traceEntryId),
    enabled: !!traceEntryId,
  })
}

export function useInfraTraceHealth() {
  return useQuery({
    queryKey: KEYS.traceHealth,
    queryFn: () => enterpriseInfraApi.getTraceHealth(),
    refetchInterval: 30_000,
  })
}

// ---- Service Dependency Graph (OTLP) ----

export function useInfraTraceGraph() {
  return useQuery({
    queryKey: ["infra", "traces", "graph"] as const,
    queryFn: () => enterpriseInfraApi.getTraceGraph(),
    refetchInterval: 30_000,
  })
}

export function useInfraServiceGraphHealth() {
  return useQuery({
    queryKey: ["infra", "traces", "graph", "health"] as const,
    queryFn: () => enterpriseInfraApi.getServiceGraphHealth(),
    refetchInterval: 30_000,
  })
}

export function useOtelServices() {
  return useQuery({
    queryKey: ["infra", "traces", "services"] as const,
    queryFn: () => enterpriseInfraApi.listOtelServices(),
    refetchInterval: 30_000,
  })
}

// ---- Platforms & Events ----

export function useInfraPlatforms() {
  return useQuery({
    queryKey: KEYS.platforms,
    queryFn: () => enterpriseInfraApi.listPlatforms(),
    staleTime: 300_000,
  })
}

export function useInfraEvents() {
  return useQuery({
    queryKey: KEYS.events,
    queryFn: () => enterpriseInfraApi.listEvents(),
    staleTime: 300_000,
  })
}

// ---- Mutations ----

export function useIngestCluster() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: Record<string, any>) => enterpriseInfraApi.ingestCluster(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.dashboard })
      qc.invalidateQueries({ queryKey: KEYS.clusters() })
      qc.invalidateQueries({ queryKey: KEYS.timeline() })
    },
  })
}

export function useIngestPod() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: Record<string, any>) => enterpriseInfraApi.ingestPod(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.dashboard })
      qc.invalidateQueries({ queryKey: KEYS.pods() })
      qc.invalidateQueries({ queryKey: KEYS.podHealth() })
      qc.invalidateQueries({ queryKey: KEYS.timeline() })
    },
  })
}

export function useIngestNode() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: Record<string, any>) => enterpriseInfraApi.ingestNode(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.dashboard })
      qc.invalidateQueries({ queryKey: KEYS.nodes() })
      qc.invalidateQueries({ queryKey: KEYS.nodeUtilization() })
    },
  })
}

export function useIngestDeployment() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: Record<string, any>) => enterpriseInfraApi.ingestDeployment(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.dashboard })
      qc.invalidateQueries({ queryKey: KEYS.deployments() })
      qc.invalidateQueries({ queryKey: KEYS.deploymentHealth() })
      qc.invalidateQueries({ queryKey: KEYS.timeline() })
    },
  })
}

export function useIngestPvc() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: Record<string, any>) => enterpriseInfraApi.ingestPvc(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.dashboard })
      qc.invalidateQueries({ queryKey: KEYS.pvcs() })
    },
  })
}

export function useIngestNetworkFailure() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: Record<string, any>) => enterpriseInfraApi.ingestNetworkFailure(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.dashboard })
      qc.invalidateQueries({ queryKey: KEYS.networkFailures() })
    },
  })
}

export function useIngestDocker() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: Record<string, any>) => enterpriseInfraApi.ingestDocker(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.dashboard })
      qc.invalidateQueries({ queryKey: KEYS.dockerContainers() })
      qc.invalidateQueries({ queryKey: KEYS.dockerHealth })
    },
  })
}

// ---- Docker Images ----

export function useInfraDockerImages(limit?: number) {
  return useQuery({
    queryKey: ["infra", "docker", "images", limit],
    queryFn: () => enterpriseInfraApi.listDockerImages(limit),
    refetchInterval: 30_000,
  })
}

export function useInfraDockerImage(imageEntryId: string) {
  return useQuery({
    queryKey: ["infra", "docker", "images", imageEntryId],
    queryFn: () => enterpriseInfraApi.getDockerImage(imageEntryId),
    enabled: !!imageEntryId,
  })
}

// ---- Docker Volumes ----

export function useInfraDockerVolumes(limit?: number) {
  return useQuery({
    queryKey: ["infra", "docker", "volumes", limit],
    queryFn: () => enterpriseInfraApi.listDockerVolumes(limit),
    refetchInterval: 30_000,
  })
}

// ---- Docker Networks ----

export function useInfraDockerNetworks(limit?: number) {
  return useQuery({
    queryKey: ["infra", "docker", "networks", limit],
    queryFn: () => enterpriseInfraApi.listDockerNetworks(limit),
    refetchInterval: 30_000,
  })
}

// ---- Docker Sync ----

export function useDockerSync() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => enterpriseInfraApi.syncDocker(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.dashboard })
      qc.invalidateQueries({ queryKey: KEYS.dockerContainers() })
      qc.invalidateQueries({ queryKey: KEYS.dockerHealth })
      qc.invalidateQueries({ queryKey: ["infra", "docker", "images"] })
      qc.invalidateQueries({ queryKey: ["infra", "docker", "volumes"] })
      qc.invalidateQueries({ queryKey: ["infra", "docker", "networks"] })
    },
  })
}

export function useIngestHelm() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: Record<string, any>) => enterpriseInfraApi.ingestHelm(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.dashboard })
      qc.invalidateQueries({ queryKey: KEYS.helmReleases() })
      qc.invalidateQueries({ queryKey: KEYS.helmHealth })
    },
  })
}

export function useIngestPrometheus() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: Record<string, any>) => enterpriseInfraApi.ingestPrometheus(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.dashboard })
      qc.invalidateQueries({ queryKey: KEYS.prometheusAlerts() })
      qc.invalidateQueries({ queryKey: KEYS.prometheusStats })
      qc.invalidateQueries({ queryKey: KEYS.correlatedAlerts() })
    },
  })
}

export function useIngestGrafana() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: Record<string, any>) => enterpriseInfraApi.ingestGrafana(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.dashboard })
      qc.invalidateQueries({ queryKey: KEYS.grafanaDashboards() })
      qc.invalidateQueries({ queryKey: KEYS.grafanaStats })
    },
  })
}

export function useIngestLoki() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: Record<string, any>) => enterpriseInfraApi.ingestLoki(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.dashboard })
      qc.invalidateQueries({ queryKey: KEYS.lokiAnalyses() })
    },
  })
}

export function useIngestOpenTelemetry() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: Record<string, any>) => enterpriseInfraApi.ingestOpenTelemetry(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.dashboard })
      qc.invalidateQueries({ queryKey: KEYS.traces() })
      qc.invalidateQueries({ queryKey: KEYS.traceHealth })
    },
  })
}

export function useKubernetesWebhook() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: Record<string, any>) => enterpriseInfraApi.kubernetesWebhook(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.dashboard })
      qc.invalidateQueries({ queryKey: KEYS.timeline() })
      qc.invalidateQueries({ queryKey: KEYS.pods() })
      qc.invalidateQueries({ queryKey: KEYS.deployments() })
      qc.invalidateQueries({ queryKey: KEYS.nodes() })
    },
  })
}

export function useInfraSync() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (context?: string) => enterpriseInfraApi.syncFromKubernetes(context),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.dashboard })
      qc.invalidateQueries({ queryKey: KEYS.timeline() })
      qc.invalidateQueries({ queryKey: KEYS.clusters() })
      qc.invalidateQueries({ queryKey: KEYS.pods() })
      qc.invalidateQueries({ queryKey: KEYS.nodes() })
      qc.invalidateQueries({ queryKey: KEYS.deployments() })
      qc.invalidateQueries({ queryKey: KEYS.pvcs() })
      qc.invalidateQueries({ queryKey: KEYS.dockerContainers() })
      qc.invalidateQueries({ queryKey: KEYS.helmReleases() })
      qc.invalidateQueries({ queryKey: KEYS.prometheusAlerts() })
      qc.invalidateQueries({ queryKey: KEYS.nodeUtilization() })
      qc.invalidateQueries({ queryKey: KEYS.podHealth() })
      qc.invalidateQueries({ queryKey: KEYS.deploymentHealth() })
    },
  })
}

// ---- Grafana (Real Grafana) ----

export function useGrafanaReady() {
  return useQuery({
    queryKey: ["infra", "grafana", "ready"] as const,
    queryFn: () => enterpriseInfraApi.grafanaReady(),
    refetchInterval: 60_000,
  })
}

export function useGrafanaDashboardsReal(query?: string, limit = 100) {
  return useQuery({
    queryKey: ["infra", "grafana", "dashboards", query, limit] as const,
    queryFn: () => enterpriseInfraApi.grafanaDashboardsReal(query, limit),
    refetchInterval: 60_000,
  })
}

export function useGrafanaDatasources() {
  return useQuery({
    queryKey: ["infra", "grafana", "datasources"] as const,
    queryFn: () => enterpriseInfraApi.grafanaDatasources(),
    refetchInterval: 60_000,
  })
}

export function useGrafanaFolders() {
  return useQuery({
    queryKey: ["infra", "grafana", "folders"] as const,
    queryFn: () => enterpriseInfraApi.grafanaFolders(),
    refetchInterval: 120_000,
  })
}

export function useGrafanaAlerts() {
  return useQuery({
    queryKey: ["infra", "grafana", "alerts"] as const,
    queryFn: () => enterpriseInfraApi.grafanaAlerts(),
    refetchInterval: 30_000,
  })
}

export function useGrafanaAnnotations() {
  return useQuery({
    queryKey: ["infra", "grafana", "annotations"] as const,
    queryFn: () => enterpriseInfraApi.grafanaAnnotations(),
    refetchInterval: 60_000,
  })
}

// ---- Unified Observability ----

export function useObservability() {
  return useQuery({
    queryKey: ["infra", "observability"] as const,
    queryFn: () => enterpriseInfraApi.getObservability(),
    refetchInterval: 30_000,
  })
}

// ---- Correlation ----

export function useCorrelateFromAlert() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (alert: string) => enterpriseInfraApi.correlateFromAlert(alert),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["infra", "correlate"] })
    },
  })
}

// ---- ArgoCD (Enterprise GitOps) ----

export function useArgoCDApplications() {
  return useQuery({
    queryKey: ["infra", "argocd", "applications"] as const,
    queryFn: () => enterpriseInfraApi.argocdApplications(),
    refetchInterval: 30_000,
  })
}

export function useArgoCDApplication(name: string) {
  return useQuery({
    queryKey: ["infra", "argocd", "applications", name] as const,
    queryFn: () => enterpriseInfraApi.argocdApplication(name),
    enabled: !!name,
  })
}

export function useArgoCDRevisions(name: string) {
  return useQuery({
    queryKey: ["infra", "argocd", "applications", name, "revisions"] as const,
    queryFn: () => enterpriseInfraApi.argocdRevisions(name),
    enabled: !!name,
  })
}

export function useArgoCDProjects() {
  return useQuery({
    queryKey: ["infra", "argocd", "projects"] as const,
    queryFn: () => enterpriseInfraApi.argocdProjects(),
    refetchInterval: 120_000,
  })
}

export function useArgoCDRepositories() {
  return useQuery({
    queryKey: ["infra", "argocd", "repositories"] as const,
    queryFn: () => enterpriseInfraApi.argocdRepositories(),
    refetchInterval: 120_000,
  })
}

export function useArgoCDClusters() {
  return useQuery({
    queryKey: ["infra", "argocd", "clusters"] as const,
    queryFn: () => enterpriseInfraApi.argocdClusters(),
    refetchInterval: 120_000,
  })
}

export function useArgoCDDrift() {
  return useQuery({
    queryKey: ["infra", "argocd", "drift"] as const,
    queryFn: () => enterpriseInfraApi.argocdDrift(),
    refetchInterval: 60_000,
  })
}

export function useArgoCDSync() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ name, revision }: { name: string; revision?: string }) => enterpriseInfraApi.argocdSync(name, revision),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["infra", "argocd", "applications"] })
    },
  })
}

export function useArgoCDRefresh() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (name: string) => enterpriseInfraApi.argocdRefresh(name),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["infra", "argocd", "applications"] })
    },
  })
}

export function useArgoCDRollback() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ name, revisionId }: { name: string; revisionId: number }) => enterpriseInfraApi.argocdRollback(name, revisionId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["infra", "argocd", "applications"] })
    },
  })
}

export function useArgoCDCorrelate() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (appName: string) => enterpriseInfraApi.argocdCorrelate(appName),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["infra", "argocd", "correlate"] })
    },
  })
}

// ---- Terraform (Enterprise IaC) ----

export function useTerraformReady() {
  return useQuery({
    queryKey: ["infra", "terraform", "ready"] as const,
    queryFn: () => enterpriseInfraApi.terraformReady(),
    refetchInterval: 60_000,
  })
}

export function useTerraformWorkspaces() {
  return useQuery({
    queryKey: ["infra", "terraform", "workspaces"] as const,
    queryFn: () => enterpriseInfraApi.terraformWorkspaces(),
    refetchInterval: 30_000,
  })
}

export function useTerraformCurrentWorkspace() {
  return useQuery({
    queryKey: ["infra", "terraform", "workspace", "current"] as const,
    queryFn: () => enterpriseInfraApi.terraformCurrentWorkspace(),
    refetchInterval: 60_000,
  })
}

export function useTerraformState() {
  return useQuery({
    queryKey: ["infra", "terraform", "state"] as const,
    queryFn: () => enterpriseInfraApi.terraformState(),
    refetchInterval: 60_000,
  })
}

export function useTerraformOutputs() {
  return useQuery({
    queryKey: ["infra", "terraform", "outputs"] as const,
    queryFn: () => enterpriseInfraApi.terraformOutputs(),
    refetchInterval: 60_000,
  })
}

export function useTerraformProviders() {
  return useQuery({
    queryKey: ["infra", "terraform", "providers"] as const,
    queryFn: () => enterpriseInfraApi.terraformProviders(),
    refetchInterval: 120_000,
  })
}

export function useTerraformGraph() {
  return useQuery({
    queryKey: ["infra", "terraform", "graph"] as const,
    queryFn: () => enterpriseInfraApi.terraformGraph(),
    refetchInterval: 120_000,
  })
}

export function useTerraformDrift() {
  return useQuery({
    queryKey: ["infra", "terraform", "drift"] as const,
    queryFn: () => enterpriseInfraApi.terraformDrift(),
    refetchInterval: 60_000,
  })
}

export function useTerraformPlans() {
  return useQuery({
    queryKey: ["infra", "terraform", "plans"] as const,
    queryFn: () => enterpriseInfraApi.terraformPlans(),
    refetchInterval: 30_000,
  })
}

export function useTerraformInit() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ upgrade, workspace }: { upgrade?: boolean; workspace?: string }) => enterpriseInfraApi.terraformInit(upgrade, workspace),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["infra", "terraform", "state"] })
    },
  })
}

export function useTerraformValidate() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => enterpriseInfraApi.terraformValidate(),
  })
}

export function useTerraformPlan() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ workspace, destroy, varFile }: { workspace?: string; destroy?: boolean; varFile?: string }) => enterpriseInfraApi.terraformPlan(workspace, destroy, varFile),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["infra", "terraform", "plans"] })
    },
  })
}

export function useTerraformApply() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ planId, workspace }: { planId: string; workspace?: string }) => enterpriseInfraApi.terraformApply(planId, workspace),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["infra", "terraform", "state"] })
      qc.invalidateQueries({ queryKey: ["infra", "terraform", "plans"] })
    },
  })
}

export function useTerraformDestroy() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (workspace?: string) => enterpriseInfraApi.terraformDestroy(workspace),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["infra", "terraform", "workspaces"] })
      qc.invalidateQueries({ queryKey: ["infra", "terraform", "state"] })
    },
  })
}

export function useTerraformCorrelate() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (workspace: string) => enterpriseInfraApi.terraformCorrelate(workspace),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["infra", "terraform", "correlate"] })
    },
  })
}
