export interface CiCdPipeline {
  pipeline_id: string;
  platform: string;
  event_type: string;
  workflow_name: string;
  repository: string;
  sender: string;
  head_branch: string;
  head_sha: string;
  status: string;
  conclusion: string;
  run_number: string;
  build_id?: string;
  created_at?: string;
  updated_at?: string;
}

export interface CiCdBuild {
  build_id: string;
  platform: string;
  name: string;
  workflow_name?: string;
  repository: string;
  head_branch: string;
  head_sha: string;
  status: string;
  conclusion: string;
  run_number?: string;
  sender?: string;
  logs?: string[];
  created_at?: string;
  updated_at?: string;
}

export interface CiCdDeployment {
  deployment_id: string;
  platform: string;
  environment: string;
  status: string;
  repository: string;
  version?: string;
  strategy?: string;
  sender?: string;
  logs?: string[];
  created_at?: string;
  updated_at?: string;
}

export interface CiCdArtifact {
  artifact_id: string;
  artifact_type: string;
  name: string;
  build_id?: string;
  repository?: string;
  platform?: string;
  version?: string;
  registry?: string;
  image?: string;
  tag?: string;
  chart?: string;
  size_bytes?: number;
  created_at?: string;
  updated_at?: string;
}

export interface CiCdFailure {
  failure_id: string;
  entity_id: string;
  entity_type: string;
  root_causes: { category: string; description: string }[];
  log_sample: string[];
  context?: Record<string, any>;
  analyzed_at: string;
}

export interface CiCdRecovery {
  recovery_id: string;
  deployment_id: string;
  strategy: string;
  status: string;
  initiated_by: string;
  message?: string;
  error?: string;
  result?: Record<string, any>;
  started_at: string;
  completed_at: string;
}

export interface CiCdTimelineEntry {
  source: string;
  entity_id: string;
  platform: string;
  name: string;
  status: string;
  timestamp: string;
  repository: string;
  branch?: string;
}

export interface CiCdDashboardStats {
  total_builds: number;
  passed: number;
  failed: number;
  running: number;
  total_deployments: number;
  success: number;
  failed_deployments: number;
  rolled_back: number;
  total_artifacts: number;
  docker_images: number;
  helm_charts: number;
  generic: number;
  total_failures: number;
  top_causes: { category: string; count: number }[];
  total_recoveries: number;
  completed_recoveries: number;
  failed_recoveries: number;
  total_pipelines: number;
  recent_builds: number;
  recent_deployments: number;
  recent_artifacts: number;
}
