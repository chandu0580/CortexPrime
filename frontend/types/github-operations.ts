export interface GithubWebhook {
  event_id: string;
  event_type: string;
  received_at: string;
  repository: string;
  sender: string;
  action: string;
  verified: boolean;
  ref?: string;
  commit_count?: number;
  commits?: { id: string; message: string; author: string; timestamp: string; url: string }[];
}

export interface GithubWorkflowRun {
  run_id?: string;
  id?: number;
  name: string;
  head_branch: string;
  head_sha: string;
  status: string;
  conclusion: string;
  html_url: string;
  workflow_id?: number;
  run_number?: number;
  event?: string;
  actor?: string;
  created_at?: string;
  updated_at?: string;
}

export interface GithubPullRequest {
  number: number;
  repo: string;
  title: string;
  body: string;
  state: string;
  merged: boolean;
  draft: boolean;
  author: string;
  head_branch: string;
  base_branch: string;
  head_sha: string;
  html_url: string;
  checks_passed?: boolean;
  check_details?: { name: string; status: string; conclusion: string }[];
  created_at?: string;
  updated_at?: string;
}

export interface GithubIssue {
  number: number;
  repo: string;
  title: string;
  body: string;
  state: string;
  author: string;
  labels: string[];
  html_url: string;
  created_at?: string;
  updated_at?: string;
}

export interface GithubRelease {
  tag_name: string;
  repo: string;
  name: string;
  body: string;
  prerelease: boolean;
  draft: boolean;
  author: string;
  html_url: string;
  published_at: string;
  created_at?: string;
  updated_at?: string;
}

export interface GithubDeployment {
  deployment_id?: string;
  id?: string;
  environment: string;
  state: string;
  description: string;
  log_url: string;
  environment_url: string;
  updated_by?: string;
  created_at?: string;
  updated_at?: string;
}

export interface GithubBranchIntel {
  name: string;
  repo: string;
  ref: string;
  last_commit: string;
  commit_count: number;
  updated_by?: string;
  deleted?: boolean;
  deleted_at?: string;
  created_at?: string;
  updated_at?: string;
}

export interface GithubDashboardStats {
  total_webhooks: number;
  total_workflow_runs: number;
  total_prs: number;
  total_issues: number;
  total_releases: number;
  total_deployments: number;
  total_branches: number;
  recent_activity: {
    type: string;
    data: any;
    timestamp: string;
  }[];
}

export interface WebhookTranslateResult {
  internal_event: string;
  context: Record<string, any>;
}

export interface MissionLaunchResult {
  task: Record<string, any>;
  plan: Record<string, any>;
  context: Record<string, any>;
}
