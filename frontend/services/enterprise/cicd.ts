import { api } from '@/services/api';
import type {
  CiCdBuild,
  CiCdDeployment,
  CiCdArtifact,
  CiCdFailure,
  CiCdRecovery,
  CiCdTimelineEntry,
  CiCdDashboardStats,
} from '@/types/cicd';

const BASE = '/api/cicd';

export const enterpriseCiCdApi = {
  // ---- Ingestion ----
  ingestPipelineEvent: (eventType: string, payload: Record<string, any>) =>
    api.post(`${BASE}/ingest/pipeline`, { event_type: eventType, payload }),

  ingestBuildEvent: (platform: string, buildData: Record<string, any>) =>
    api.post(`${BASE}/ingest/build`, { platform, build_data: buildData }),

  ingestDeploymentEvent: (platform: string, deployData: Record<string, any>) =>
    api.post(`${BASE}/ingest/deployment`, { platform, deploy_data: deployData }),

  ingestArtifactEvent: (artifactData: Record<string, any>) =>
    api.post(`${BASE}/ingest/artifact`, { artifact_data: artifactData }),

  failureAndRecover: (entityId: string, entityType: string, logs: string[], strategy?: string) =>
    api.post(`${BASE}/failure-recover`, { entity_id: entityId, entity_type: entityType, logs, strategy: strategy || '' }),

  // ---- Dashboard ----
  getDashboard: () =>
    api.get<CiCdDashboardStats>(`${BASE}/dashboard`),

  getTimeline: (limit = 50) =>
    api.get<{ timeline: CiCdTimelineEntry[] }>(`${BASE}/timeline`, { params: { limit } }),

  // ---- Builds ----
  listBuilds: (params?: { platform?: string; status?: string; limit?: number }) =>
    api.get<{ builds: CiCdBuild[] }>(`${BASE}/builds`, { params }),

  getBuild: (buildId: string) =>
    api.get<CiCdBuild>(`${BASE}/builds/${buildId}`),

  getBuildTrends: () =>
    api.get(`${BASE}/builds/stats/trends`),

  // ---- Deployments ----
  listDeployments: (params?: { environment?: string; status?: string; limit?: number }) =>
    api.get<{ deployments: CiCdDeployment[] }>(`${BASE}/deployments`, { params }),

  getDeployment: (deploymentId: string) =>
    api.get<CiCdDeployment>(`${BASE}/deployments/${deploymentId}`),

  getEnvironmentHealth: () =>
    api.get<{ environments: Record<string, any> }>(`${BASE}/deployments/environments/health`),

  // ---- Artifacts ----
  listArtifacts: (params?: { artifact_type?: string; build_id?: string; limit?: number }) =>
    api.get<{ artifacts: CiCdArtifact[] }>(`${BASE}/artifacts`, { params }),

  getArtifact: (artifactId: string) =>
    api.get<CiCdArtifact>(`${BASE}/artifacts/${artifactId}`),

  // ---- Failures ----
  listFailures: (entityType?: string, limit?: number) =>
    api.get<{ failures: CiCdFailure[] }>(`${BASE}/failures`, { params: { entity_type: entityType, limit } }),

  getFailure: (failureId: string) =>
    api.get<CiCdFailure>(`${BASE}/failures/${failureId}`),

  // ---- Recoveries ----
  listRecoveries: (limit?: number) =>
    api.get<{ recoveries: CiCdRecovery[] }>(`${BASE}/recoveries`, { params: { limit } }),

  getRecovery: (recoveryId: string) =>
    api.get<CiCdRecovery>(`${BASE}/recoveries/${recoveryId}`),

  createRecovery: (entityId: string, strategy: string) =>
    api.post<CiCdRecovery>(`${BASE}/recoveries`, { entity_id: entityId, entity_type: 'deployment', logs: [], strategy }),

  // ---- Platforms ----
  listPlatforms: () =>
    api.get<{ platforms: string[] }>(`${BASE}/platforms`),
};
