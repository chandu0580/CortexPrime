import { api } from '@/services/api';
import type {
  InfraCluster,
  InfraNode,
  InfraPod,
  InfraDeployment,
  InfraPvc,
  InfraContainer,
  InfraHelmRelease,
  InfraAlert,
  InfraDashboard,
  InfraLogAnalysis,
  InfraTrace,
  InfraNetworkFailure,
  InfraDashboardStats,
  InfraTimelineEntry,
} from '@/types/infrastructure';

const BASE = '/api/infrastructure';

export const enterpriseInfraApi = {
  // ---- Ingestion ----
  ingestCluster: (payload: Record<string, any>) =>
    api.post(`${BASE}/ingest/cluster`, { payload }),

  ingestPod: (payload: Record<string, any>) =>
    api.post(`${BASE}/ingest/pod`, { payload }),

  ingestNode: (payload: Record<string, any>) =>
    api.post(`${BASE}/ingest/node`, { payload }),

  ingestDeployment: (payload: Record<string, any>) =>
    api.post(`${BASE}/ingest/deployment`, { payload }),

  ingestPvc: (payload: Record<string, any>) =>
    api.post(`${BASE}/ingest/pvc`, { payload }),

  ingestNetworkFailure: (payload: Record<string, any>) =>
    api.post(`${BASE}/ingest/network-failure`, { payload }),

  ingestDocker: (payload: Record<string, any>) =>
    api.post(`${BASE}/ingest/docker`, { payload }),

  ingestHelm: (payload: Record<string, any>) =>
    api.post(`${BASE}/ingest/helm`, { payload }),

  ingestPrometheus: (payload: Record<string, any>) =>
    api.post(`${BASE}/ingest/prometheus`, { payload }),

  ingestGrafana: (payload: Record<string, any>) =>
    api.post(`${BASE}/ingest/grafana`, { payload }),

  ingestLoki: (payload: Record<string, any>) =>
    api.post(`${BASE}/ingest/loki`, { payload }),

  ingestOpenTelemetry: (payload: Record<string, any>) =>
    api.post(`${BASE}/ingest/opentelemetry`, { payload }),

  kubernetesWebhook: (payload: Record<string, any>) =>
    api.post(`${BASE}/webhook/kubernetes`, { payload }),

  // ---- Dashboard ----
  getDashboard: () =>
    api.get<InfraDashboardStats>(`${BASE}/dashboard`),

  getTimeline: (limit = 50) =>
    api.get<{ timeline: InfraTimelineEntry[] }>(`${BASE}/timeline`, { params: { limit } }),

  // ---- Clusters ----
  listClusters: (limit = 100) =>
    api.get<{ clusters: InfraCluster[] }>(`${BASE}/clusters`, { params: { limit } }),

  getCluster: (clusterId: string) =>
    api.get<InfraCluster>(`${BASE}/clusters/${clusterId}`),

  // ---- Pods ----
  listPods: (params?: { namespace?: string; status?: string; limit?: number }) =>
    api.get<{ pods: InfraPod[] }>(`${BASE}/pods`, { params }),

  getPodHealth: (namespace?: string) =>
    api.get(`${BASE}/pods/health`, { params: { namespace } }),

  // ---- Nodes ----
  listNodes: (clusterId?: string, limit = 100) =>
    api.get<{ nodes: InfraNode[] }>(`${BASE}/nodes`, { params: { cluster_id: clusterId, limit } }),

  getNodeUtilization: (clusterId?: string) =>
    api.get(`${BASE}/nodes/utilization`, { params: { cluster_id: clusterId } }),

  // ---- Deployments ----
  listDeployments: (params?: { namespace?: string; cluster_id?: string; limit?: number }) =>
    api.get<{ deployments: InfraDeployment[] }>(`${BASE}/deployments`, { params }),

  getDeploymentHealth: (clusterId?: string) =>
    api.get(`${BASE}/deployments/health`, { params: { cluster_id: clusterId } }),

  // ---- PVCs ----
  listPvcs: (params?: { namespace?: string; cluster_id?: string; limit?: number }) =>
    api.get<{ pvcs: InfraPvc[] }>(`${BASE}/pvcs`, { params }),

  // ---- Network Failures ----
  listNetworkFailures: (params?: { cluster_id?: string; resolved?: boolean; limit?: number }) =>
    api.get<{ network_failures: InfraNetworkFailure[] }>(`${BASE}/network-failures`, { params }),

  // ---- Docker ----
  listDockerContainers: (params?: { status?: string; host?: string; limit?: number }) =>
    api.get<{ containers: InfraContainer[] }>(`${BASE}/docker/containers`, { params }),

  getDockerContainer: (dockerId: string) =>
    api.get<InfraContainer>(`${BASE}/docker/containers/${dockerId}`),

  getDockerHealth: () =>
    api.get(`${BASE}/docker/health`),

  listDockerImages: (limit?: number) =>
    api.get<{ images: any[] }>(`${BASE}/docker/images`, { params: { limit } }),

  getDockerImage: (imageEntryId: string) =>
    api.get<any>(`${BASE}/docker/images/${imageEntryId}`),

  listDockerVolumes: (limit?: number) =>
    api.get<{ volumes: any[] }>(`${BASE}/docker/volumes`, { params: { limit } }),

  listDockerNetworks: (limit?: number) =>
    api.get<{ networks: any[] }>(`${BASE}/docker/networks`, { params: { limit } }),

  syncDocker: () =>
    api.post(`${BASE}/docker/sync`),

  // ---- Helm ----
  listHelmReleases: (params?: { namespace?: string; status?: string; limit?: number }) =>
    api.get<{ releases: InfraHelmRelease[] }>(`${BASE}/helm/releases`, { params }),

  getHelmRelease: (releaseId: string) =>
    api.get<InfraHelmRelease>(`${BASE}/helm/releases/${releaseId}`),

  getHelmHealth: () =>
    api.get(`${BASE}/helm/health`),

  // ---- Prometheus ----
  listPrometheusAlerts: (params?: { severity?: string; status?: string; limit?: number }) =>
    api.get<{ alerts: InfraAlert[] }>(`${BASE}/prometheus/alerts`, { params }),

  getCorrelatedAlerts: (threshold = 3) =>
    api.get(`${BASE}/prometheus/alerts/correlated`, { params: { threshold } }),

  getPrometheusStats: () =>
    api.get(`${BASE}/prometheus/stats`),

  prometheusQuery: (query: string) =>
    api.post(`${BASE}/prometheus/query`, null, { params: { query } }),

  prometheusQueryRange: (query: string, start: string, end: string, step = "15s") =>
    api.post(`${BASE}/prometheus/query_range`, null, { params: { query, start, end, step } }),

  prometheusTargets: () =>
    api.get(`${BASE}/prometheus/targets`),

  prometheusRules: () =>
    api.get(`${BASE}/prometheus/rules`),

  prometheusLiveAlerts: () =>
    api.get(`${BASE}/prometheus/live-alerts`),

  prometheusMetrics: () =>
    api.get(`${BASE}/prometheus/metrics`),

  prometheusCollect: () =>
    api.post(`${BASE}/prometheus/collect`),

  prometheusSyncAlerts: () =>
    api.post(`${BASE}/prometheus/sync-alerts`),

  // ---- Grafana ----
  listGrafanaDashboards: (folder?: string, limit = 100) =>
    api.get<{ dashboards: InfraDashboard[] }>(`${BASE}/grafana/dashboards`, { params: { folder, limit } }),

  getGrafanaDashboard: (dashboardId: string) =>
    api.get<InfraDashboard>(`${BASE}/grafana/dashboards/${dashboardId}`),

  getGrafanaStats: () =>
    api.get(`${BASE}/grafana/stats`),

  // ---- Loki (Real Loki HTTP API) ----
  lokiReady: () =>
    api.get<{ ready: boolean }>(`${BASE}/loki/ready`),

  lokiLabels: () =>
    api.get<{ status: string; labels: string[] }>(`${BASE}/loki/labels`),

  lokiLabelValues: (label: string) =>
    api.get<{ status: string; label: string; values: string[] }>(`${BASE}/loki/labels/${encodeURIComponent(label)}/values`),

  lokiQuery: (query: string, limit = 100) =>
    api.get<{ status: string; streams: any[]; total_entries: number }>(`${BASE}/loki/query`, { params: { query, limit } }),

  lokiQueryRange: (query: string, start: string, end: string, step = "1m", limit = 1000) =>
    api.get(`${BASE}/loki/query_range`, { params: { query, start, end, step, limit } }),

  lokiStreams: (match = "{}") =>
    api.get<{ status: string; streams: Record<string, string>[] }>(`${BASE}/loki/streams`, { params: { match } }),

  lokiStreamLogs: (streamSelector: string, start: string, end: string, limit = 500) =>
    api.get(`${BASE}/loki/streams/logs`, { params: { stream_selector: streamSelector, start, end, limit } }),

  lokiTargetLogs: (targetType: string, targetName: string, minutes = 15, limit = 500) =>
    api.get(`${BASE}/loki/targets`, { params: { target_type: targetType, target_name: targetName, minutes, limit } }),

  lokiAnalyze: (payload: { logql?: string; limit?: number; start?: string; end?: string }) =>
    api.post(`${BASE}/loki/analyze`, payload),

  lokiAnalyzeStream: (payload: { logql?: string; limit?: number }) =>
    api.post(`${BASE}/loki/analyze/stream`, payload),

  lokiCorrelate: (payload: { logql?: string; entities?: Record<string, string[]>; limit?: number }) =>
    api.post(`${BASE}/loki/correlate`, payload),

  // ---- Loki (Legacy) ----
  listLokiAnalyses: (stream?: string, limit = 100) =>
    api.get<{ analyses: InfraLogAnalysis[] }>(`${BASE}/loki/analyses`, { params: { stream, limit } }),

  getLokiAnalysis: (analysisId: string) =>
    api.get<InfraLogAnalysis>(`${BASE}/loki/analyses/${analysisId}`),

  lokiSearch: (query: string, limit = 50) =>
    api.get(`${BASE}/loki/search`, { params: { query, limit } }),

  // ---- Traces ----
  listTraces: (params?: { service_name?: string; status?: string; limit?: number }) =>
    api.get<{ traces: InfraTrace[] }>(`${BASE}/traces`, { params }),

  getTrace: (traceEntryId: string) =>
    api.get<InfraTrace>(`${BASE}/traces/${traceEntryId}`),

  getTraceHealth: () =>
    api.get(`${BASE}/traces/health`),

  // ---- Service Dependency Graph (OTLP) ----
  getTraceGraph: () =>
    api.get<{ nodes: any[]; edges: any[]; node_count: number; edge_count: number }>(`${BASE}/traces/graph`),

  listOtelServices: () =>
    api.get<{ services: any[] }>(`${BASE}/traces/services`),

  getOtelServiceDetail: (serviceName: string) =>
    api.get<any>(`${BASE}/traces/services/${encodeURIComponent(serviceName)}`),

  getServiceGraphHealth: () =>
    api.get<{ total_services: number; healthy_services: number; services_with_errors: number; total_edges: number }>(`${BASE}/traces/graph/health`),

  // ---- Platforms & Events ----
  listPlatforms: () =>
    api.get<{ platforms: string[] }>(`${BASE}/platforms`),

  listEvents: () =>
    api.get<{ events: Record<string, string> }>(`${BASE}/events`),

  // ---- Sync (Kubernetes live pull) ----
  syncFromKubernetes: (context?: string) =>
    api.post(`${BASE}/sync`, { context: context || "" }),

  // ---- Recommendations ----
  recommend: (clusterId?: string) =>
    api.post(`${BASE}/recommend`, null, { params: { cluster_id: clusterId } }),

  // ---- Grafana (Real Grafana HTTP API) ----
  grafanaReady: () =>
    api.get<{ ready: boolean; org: string }>(`${BASE}/grafana/ready`),

  grafanaHealth: () =>
    api.get<any>(`${BASE}/grafana/health`),

  grafanaOrg: () =>
    api.get<any>(`${BASE}/grafana/org`),

  grafanaDashboardsReal: (query?: string, limit = 100) =>
    api.get<{ dashboards: any[]; total: number; discovered_at: string }>(`${BASE}/grafana/dashboards`, { params: { query, limit } }),

  grafanaDashboardByUid: (uid: string) =>
    api.get<any>(`${BASE}/grafana/dashboards/uid/${encodeURIComponent(uid)}`),

  grafanaFolders: () =>
    api.get<{ folders: any[] }>(`${BASE}/grafana/folders`),

  grafanaDatasources: () =>
    api.get<{ datasources: any[]; total: number; type_counts: Record<string, number>; known_types: string[]; health_status: any }>(`${BASE}/grafana/datasources`),

  grafanaAnnotations: (limit = 100) =>
    api.get<{ annotations: any[] }>(`${BASE}/grafana/annotations`, { params: { limit } }),

  grafanaAlerts: (limit = 100) =>
    api.get<{ alerts: any[] }>(`${BASE}/grafana/alerts`, { params: { limit } }),

  grafanaRules: () =>
    api.get<{ rules: any }>(`${BASE}/grafana/rules`),

  // ---- Unified Observability ----
  getObservability: () =>
    api.get<any>(`${BASE}/observability`),

  // ---- Correlation Chain ----
  correlateFromAlert: (alert: string) =>
    api.post<any>(`${BASE}/correlate`, { alert }),

  // ---- ArgoCD (Enterprise GitOps) ----
  argocdReady: () =>
    api.get<{ ready: boolean }>(`${BASE}/argocd/ready`),

  argocdApplications: () =>
    api.get<{ applications: any[]; total: number; sync_counts: Record<string, number>; health_counts: Record<string, number>; out_of_sync: number; degraded: number }>(`${BASE}/argocd/applications`),

  argocdApplication: (name: string) =>
    api.get<any>(`${BASE}/argocd/applications/${encodeURIComponent(name)}`),

  argocdRevisions: (name: string) =>
    api.get<any>(`${BASE}/argocd/applications/${encodeURIComponent(name)}/revisions`),

  argocdResources: (name: string) =>
    api.get<any>(`${BASE}/argocd/applications/${encodeURIComponent(name)}/resources`),

  argocdEvents: (name: string) =>
    api.get<any>(`${BASE}/argocd/applications/${encodeURIComponent(name)}/events`),

  argocdSync: (name: string, revision?: string) =>
    api.post<any>(`${BASE}/argocd/applications/${encodeURIComponent(name)}/sync`, { revision }),

  argocdRefresh: (name: string) =>
    api.post<any>(`${BASE}/argocd/applications/${encodeURIComponent(name)}/refresh`),

  argocdRollback: (name: string, revisionId: number) =>
    api.post<any>(`${BASE}/argocd/applications/${encodeURIComponent(name)}/rollback`, { revision_id: revisionId }),

  argocdProjects: () =>
    api.get<{ projects: any[]; total: number }>(`${BASE}/argocd/projects`),

  argocdRepositories: () =>
    api.get<{ repos: any[]; total: number }>(`${BASE}/argocd/repositories`),

  argocdClusters: () =>
    api.get<{ clusters: any[]; total: number }>(`${BASE}/argocd/clusters`),

  argocdDrift: () =>
    api.get<any>(`${BASE}/argocd/drift`),

  argocdCorrelate: (appName: string) =>
    api.post<any>(`${BASE}/argocd/correlate`, { application: appName }),

  // ---- Terraform (Enterprise IaC) ----

  terraformReady: () =>
    api.get<{ ready: boolean; version: string }>(`${BASE}/terraform/ready`),

  terraformVersion: () =>
    api.get<{ version: string; output: string }>(`${BASE}/terraform/version`),

  terraformWorkspaces: () =>
    api.get<{ workspaces: any[]; current: string; total: number }>(`${BASE}/terraform/workspaces`),

  terraformCurrentWorkspace: () =>
    api.get<{ workspace: string }>(`${BASE}/terraform/workspaces/current`),

  terraformSelectWorkspace: (name: string) =>
    api.post<{ status: string; workspace: string }>(`${BASE}/terraform/workspaces/select`, { name }),

  terraformState: () =>
    api.get<{ status: string; resources: any[]; resource_count: number; providers: string[] }>(`${BASE}/terraform/state`),

  terraformOutputs: () =>
    api.get<{ status: string; outputs: Record<string, any> }>(`${BASE}/terraform/outputs`),

  terraformProviders: () =>
    api.get<{ status: string; providers: any[] }>(`${BASE}/terraform/providers`),

  terraformGraph: () =>
    api.get<{ status: string; graph: any }>(`${BASE}/terraform/graph`),

  terraformDrift: () =>
    api.get<{ status: string; drifts: any[]; drift_count: number; risk_score: number }>(`${BASE}/terraform/drift`),

  terraformInit: (upgrade?: boolean, workspace?: string) =>
    api.post<{ status: string; stdout: string; stderr: string; duration_seconds: number }>(`${BASE}/terraform/init`, { upgrade, workspace }),

  terraformValidate: () =>
    api.post<{ status: string; stdout: string; stderr: string }>(`${BASE}/terraform/validate`),

  terraformPlan: (workspace?: string, destroy?: boolean, varFile?: string) =>
    api.post<{ status: string; plan: any }>(`${BASE}/terraform/plan`, { workspace, destroy, var_file: varFile }),

  terraformApply: (planId: string, workspace?: string) =>
    api.post<{ status: string; plan: any; output: string }>(`${BASE}/terraform/apply`, { plan_id: planId, workspace }),

  terraformDestroy: (workspace?: string) =>
    api.post<{ status: string }>(`${BASE}/terraform/destroy`, { workspace }),

  terraformPlans: () =>
    api.get<{ plans: any[] }>(`${BASE}/terraform/plans`),

  terraformCorrelate: (workspace: string) =>
    api.post<any>(`${BASE}/terraform/correlate`, { workspace }),
};
