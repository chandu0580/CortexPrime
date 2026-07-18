export interface InfraCluster {
  cluster_id: string;
  name: string;
  provider: string;
  version: string;
  nodes_total: number;
  nodes_ready: number;
  status: string;
  created_at?: string;
  updated_at?: string;
}

export interface InfraNode {
  node_id: string;
  cluster_id: string;
  name: string;
  status: string;
  cpu_usage: number;
  memory_usage: number;
  disk_usage: number;
  created_at?: string;
  updated_at?: string;
}

export interface InfraPod {
  pod_id: string;
  cluster_id: string;
  namespace: string;
  name: string;
  status: string;
  phase: string;
  restarts: number;
  container_statuses: Record<string, any>[];
  node_name: string;
  oom_detected?: boolean;
  crashloop_detected?: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface InfraDeployment {
  deployment_id: string;
  cluster_id: string;
  namespace: string;
  name: string;
  replicas: number;
  available: number;
  status: string;
  rollout_status: string;
  image: string;
  strategy: string;
  created_at?: string;
  updated_at?: string;
}

export interface InfraPvc {
  pvc_id: string;
  cluster_id: string;
  namespace: string;
  name: string;
  status: string;
  capacity_bytes: number;
  used_bytes: number;
  volume_name: string;
  created_at?: string;
  updated_at?: string;
}

export interface InfraContainer {
  docker_id: string;
  container_id: string;
  name: string;
  image: string;
  status: string;
  ports: string[];
  restart_count: number;
  host: string;
  created_at?: string;
  updated_at?: string;
}

export interface InfraHelmRelease {
  release_id: string;
  name: string;
  namespace: string;
  chart: string;
  version: string;
  revision: number;
  status: string;
  cluster_id?: string;
  values?: Record<string, any>;
  notes?: string;
  created_at?: string;
  updated_at?: string;
}

export interface InfraAlert {
  alert_id: string;
  alert_name: string;
  severity: string;
  status: string;
  labels?: Record<string, string>;
  annotations?: Record<string, string>;
  starts_at?: string;
  ends_at?: string;
  value?: number;
  generator_url?: string;
  created_at?: string;
  updated_at?: string;
}

export interface InfraDashboard {
  dashboard_id: string;
  uid: string;
  title: string;
  folder: string;
  url?: string;
  datasources?: string[];
  tags?: string[];
  panels?: number;
  starred?: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface InfraLogAnalysis {
  analysis_id: string;
  stream: string;
  queries?: string[];
  labels?: Record<string, string>;
  total_lines: number;
  error_count: number;
  warn_count: number;
  info_count: number;
  log_sample?: string[];
  analyzed_at: string;
}

export interface InfraTrace {
  trace_entry_id: string;
  trace_id: string;
  service_name: string;
  spans?: Record<string, any>[];
  total_spans: number;
  error_spans: number;
  root_operation?: string;
  duration_ms: number;
  status: string;
  latency_p50: number;
  latency_p95: number;
  latency_p99: number;
  tags?: Record<string, string>;
  created_at?: string;
  updated_at?: string;
}

export interface InfraNetworkFailure {
  failure_id: string;
  cluster_id: string;
  namespace: string;
  source: string;
  destination: string;
  reason: string;
  protocol: string;
  port: number;
  detected_at: string;
  resolved: boolean;
}

export interface InfraDashboardStats {
  clusters: { total: number; healthy: number; degraded: number };
  pods: { total: number; running: number; pending: number; failed: number; oom: number; crashloop: number };
  deployments: { total: number; available: number; degraded: number; unavailable: number; rollouts_in_progress: number; rollbacks: number };
  nodes: { avg_cpu: number; avg_memory: number; avg_disk: number; node_count: number };
  containers: { total: number; running: number; stopped: number; error: number };
  helm_releases: { total: number; deployed: number; failed: number; pending: number };
  alerts: { total: number; firing: number; resolved: number; critical: number; warning: number; info: number };
  grafana_dashboards: { total: number; folders: number; datasource_count: number };
  traces: { total: number; ok: number; error: number; avg_duration_ms: number; avg_p95_ms: number };
  active_network_failures: number;
  total_pvcs: number;
}

export interface InfraTimelineEntry {
  source: string;
  entity_id: string;
  name: string;
  status: string;
  timestamp: string;
  namespace: string;
  cluster_id: string;
}
