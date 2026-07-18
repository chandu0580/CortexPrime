import { api } from '@/services/api';

export type ExecutionStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed'
  | 'cancelled'
  | 'rolled_back'

export interface ExecutionStageRecord {
  stage: string
  status: string
  started_at: string
  completed_at: string
  duration_seconds: number
  error: string
  result: Record<string, unknown>
}

export interface ExecutionRecord {
  execution_id: string
  mission_id: string
  delivery_id: string
  repository: string
  branch: string
  commit_sha: string
  service: string
  environment: string
  source: string
  source_event: string
  status: ExecutionStatus
  current_stage: string
  stages: Record<string, ExecutionStageRecord>
  stages_completed: string[]
  stages_failed: string[]
  objective: string
  decision_report: Record<string, unknown>
  context_snapshot_id: string
  workspace_id: string
  sandbox_id: string
  patch_plan_id: string
  patch_candidate_id: string
  pr_number: number
  pr_url: string
  build_id: string
  deployment_id: string
  verification_id: string
  prediction_id: string
  risk_score: number
  risk_level: string
  deployment_strategy: string
  artifacts: Record<string, unknown>[]
  logs: { stage: string; level: string; message: string; timestamp: string }[]
  timeline: { stage: string; status: string; message: string; timestamp: string }[]
  error_message: string
  started_at: string
  completed_at: string
  duration_seconds: number
  created_at: string
}

export interface ExecutionDashboardStats {
  total_executions: number
  by_status: Record<string, number>
  active_count: number
  completed_count: number
  failed_count: number
  recent_executions: ExecutionRecord[]
}

const BASE = '/api/engineering/execution';

export const executionApi = {
  create: (params: {
    repository?: string
    branch?: string
    commit_sha?: string
    service?: string
    environment?: string
    source?: string
    source_event?: string
    objective?: string
  }) => api.post<ExecutionRecord>(BASE, params),

  start: (executionId: string, autoApprove = false) =>
    api.post<ExecutionRecord>(`${BASE}/${executionId}/start`, { auto_approve: autoApprove }),

  startAsync: (executionId: string, autoApprove = false) =>
    api.post<{ execution_id: string; status: string }>(`${BASE}/${executionId}/start-async`, { auto_approve: autoApprove }),

  get: (executionId: string) =>
    api.get<ExecutionRecord>(`${BASE}/${executionId}`),

  list: (params?: { status?: string; repository?: string; limit?: number }) => {
    const qs = new URLSearchParams()
    if (params?.status) qs.set('status', params.status)
    if (params?.repository) qs.set('repository', params.repository)
    if (params?.limit) qs.set('limit', String(params.limit))
    const query = qs.toString()
    return api.get<ExecutionRecord[]>(`${BASE}${query ? `?${query}` : ''}`)
  },

  cancel: (executionId: string) =>
    api.post<ExecutionRecord>(`${BASE}/${executionId}/cancel`),

  rollback: (executionId: string) =>
    api.post<ExecutionRecord>(`${BASE}/${executionId}/rollback`),

  retry: (executionId: string) =>
    api.post<ExecutionRecord>(`${BASE}/${executionId}/retry`),

  dashboard: () =>
    api.get<ExecutionDashboardStats>(`${BASE}/dashboard`),
};
