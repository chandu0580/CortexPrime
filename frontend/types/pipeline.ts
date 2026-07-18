export interface PipelineRun {
  pipeline_id: string
  name: string
  description: string
  status: "pending" | "running" | "paused" | "completed" | "failed" | "cancelled"
  current_stage: string
  current_stage_index: number
  stages_completed: string[]
  stages_failed: string[]
  mission_id: string
  repo_url: string
  workspace_id: string
  sandbox_id: string
  trigger_policy_id: string
  artifacts: Record<string, unknown>
  delivery_id: string
  created_at: string
  updated_at: string
  started_at: string
  completed_at: string
  error: string
  metadata: Record<string, unknown>
}

export interface PipelineCreateRequest {
  name?: string
  description?: string
  mission_id?: string
  repo_url?: string
  workspace_id?: string
  sandbox_id?: string
  trigger_policy_id?: string
}

export interface PipelineDashboardStats {
  total_pipelines: number
  by_status: Record<string, number>
  completed: number
  failed: number
  running: number
  generated_at: string
}

export interface PatchToPrRequest {
  repo_url: string
  plan_id: string
  candidate_id: string
  branch_name?: string
  mission_id?: string
  commit_description?: string
  pr_title?: string
  reviewers?: string[]
  labels?: string[]
}

export interface PatchToPrResult {
  branch: Record<string, unknown>
  commit: Record<string, unknown>
  pr: Record<string, unknown>
  candidate_id: string
  plan_id: string
}

export const PIPELINE_STAGES = [
  "trigger",
  "sandbox",
  "code_intel",
  "patch",
  "git",
  "approval",
  "complete",
] as const

export type PipelineStage = (typeof PIPELINE_STAGES)[number]
