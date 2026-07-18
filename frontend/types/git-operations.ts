export interface GitBranch {
  name: string
  sha: string
  protected: boolean
}

export interface CreateBranchResult {
  repo_url: string
  branch_name: string
  source_branch: string
  ref: string
  sha: string
  created_at: string
}

export interface CommitResult {
  repo_url: string
  branch: string
  sha: string
  message: string
  author: Record<string, string>
  files_count: number
  files: string[]
  created_at: string
}

export interface FileChange {
  path: string
  content: string
  encoding?: string
  mode?: string
}

export interface PRResult {
  repo_url: string
  pr_number: number
  title: string
  head: string
  base: string
  state: string
  html_url: string
  reviewers: string[]
  labels: string[]
  milestone: number | null
  created_at: string
}

export interface MergeResult {
  repo_url: string
  pr_number: number
  merged: boolean
  sha: string
  message: string
  merged_at: string
}

export interface IssueSyncResult {
  provider: string
  issue_number?: number
  issue_key?: string
  work_item_id?: number
  action: string
  synced_at: string
  error?: string
}

export interface HistoryEntry {
  action: string
  entity_id: string
  timestamp: string
  metadata: Record<string, unknown>
}

export interface EngineeringContext {
  mission: Record<string, unknown> | null
  root_cause: string
  affected_files: string[]
  impact_analysis: Record<string, unknown>[] | null
  validation_results: Record<string, unknown> | null
  coverage: Record<string, unknown> | null
  security_scan: Record<string, unknown> | null
  replay_references: Record<string, unknown>[]
  learning_references: Record<string, unknown>[]
  recommendation_references: Record<string, unknown>[]
  generated_at: string
}

export interface BranchCompareResult {
  repo_url: string
  base: string
  head: string
  ahead_by: number
  behind_by: number
  total_commits: number
  files: { filename: string; status: string; additions: number; deletions: number }[]
  compared_at: string
}
