export interface EngineeringTask {
  task_id: string;
  description: string;
  task_type: string;
  task_label: string;
  confidence: number;
  repo_url: string;
  branch: string;
  status: string;
  plan_id?: string;
  created_at: string;
  updated_at: string;
}

export interface EngineeringStage {
  stage_id: string;
  stage_index: number;
  stage_type: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  subsystem: string;
  retry_count: number;
  max_retries: number;
  artifacts: any[];
  error: string | null;
  started_at: string | null;
  completed_at: string | null;
}

export interface EngineeringPlan {
  plan_id: string;
  task_id: string;
  task_type: string;
  task_label: string;
  description: string;
  repo_url: string;
  branch: string;
  stages: EngineeringStage[];
  current_stage_index: number;
  status: string;
  participating_subsystems: string[];
  artifacts: any[];
  recovery_log: RecoveryEntry[];
  created_at: string;
  updated_at: string;
}

export interface RecoveryEntry {
  stage_index: number;
  stage_type: string;
  action: 'retry' | 'escalate' | 'fallback' | 'rollback';
  reason: string;
  timestamp: string;
}

export interface ExecutionStatus {
  plan_id: string;
  status: string;
  current_stage_index: number;
  stages: StageStatus[];
  recovery_log: RecoveryEntry[];
  updated_at: string;
}

export interface StageStatus {
  stage_index: number;
  stage_type: string;
  status: string;
  retry_count: number;
  error: string | null;
}

export interface EngineeringReport {
  report_id: string;
  plan_id: string;
  task_id: string;
  task_type: string;
  task_label: string;
  overall_status: string;
  total_stages: number;
  completed_stages: number;
  failed_stages: number;
  total_duration_seconds: number;
  subsystems_used: string[];
  recovery_actions_taken: string[];
  artifacts_summary: {
    workspace_id: string;
    sandbox_id: string;
    plan_id: string;
    branch_name: string;
    pr_number: number;
    delivery_id: string;
    code_intel_entities: number;
    candidate_count: number;
    delivery_summary: string;
  };
  stage_summary: {
    stage_type: string;
    stage_index: number;
    status: string;
    retry_count: number;
    error: string | null;
  }[];
  recovery_log: RecoveryEntry[];
  generated_at: string;
}

export interface ExecutiveDashboardStats {
  total_tasks: number;
  total_plans: number;
  total_reports: number;
  tasks_by_status: Record<string, number>;
  plans_by_status: Record<string, number>;
  plans_by_type: Record<string, number>;
  supported_task_types: { type: string; label: string; stages: string[] }[];
}

export interface SupportedTaskType {
  type: string;
  label: string;
  stages: string[];
}
