import axios from "axios"
import { apiUrl } from "@/lib/constants"
import type {
  GitBranch,
  CreateBranchResult,
  CommitResult,
  FileChange,
  PRResult,
  MergeResult,
  IssueSyncResult,
  HistoryEntry,
  EngineeringContext,
  BranchCompareResult,
} from "@/types/git-operations"

export const enterpriseGitApi = {
  listBranches: async (repoUrl: string): Promise<{ branches: GitBranch[]; repo_url: string }> => {
    const res = await axios.get(`${apiUrl}/api/git/branches`, { params: { repo_url: repoUrl } })
    return res.data
  },

  createBranch: async (payload: {
    repo_url: string
    branch_name: string
    source_branch?: string
    workspace_id?: string
  }): Promise<CreateBranchResult> => {
    const res = await axios.post(`${apiUrl}/api/git/branches`, payload)
    return res.data
  },

  createCommit: async (payload: {
    repo_url: string
    branch: string
    description: string
    files: FileChange[]
    commit_type?: string
    scope?: string
    breaking?: boolean
    author?: Record<string, string>
    patch_candidate_id?: string
    mission_id?: string
  }): Promise<CommitResult> => {
    const res = await axios.post(`${apiUrl}/api/git/commit`, payload)
    return res.data
  },

  createPullRequest: async (payload: {
    repo_url: string
    title: string
    head: string
    base?: string
    body?: string
    reviewers?: string[]
    labels?: string[]
    milestone?: number
    mission_id?: string
    patch_plan_id?: string
    patch_candidate_id?: string
    workspace_id?: string
    files_changed?: string[]
    auto_context?: boolean
  }): Promise<PRResult> => {
    const res = await axios.post(`${apiUrl}/api/git/pull-request`, payload)
    return res.data
  },

  mergePullRequest: async (prNumber: number, payload: {
    repo_url: string
    merge_method?: string
    commit_title?: string
    commit_message?: string
    require_approval?: boolean
  }): Promise<MergeResult> => {
    const res = await axios.post(`${apiUrl}/api/git/pull-request/${prNumber}/merge`, payload)
    return res.data
  },

  syncIssue: async (payload: {
    repo_url?: string
    pr_number?: number
    issue_number?: number
    issue_key?: string
    work_item_id?: number
    provider?: string
    action?: string
    comment?: string
    labels?: string[]
    status?: string
    state?: string
  }): Promise<IssueSyncResult> => {
    const res = await axios.post(`${apiUrl}/api/git/issues/sync`, payload)
    return res.data
  },

  getHistory: async (limit?: number): Promise<{ history: HistoryEntry[]; total: number }> => {
    const res = await axios.get(`${apiUrl}/api/git/history`, { params: { limit } })
    return res.data
  },

  listPullRequests: async (repoUrl: string, state?: string): Promise<{ pull_requests: PRResult[]; repo_url: string; state: string }> => {
    const res = await axios.get(`${apiUrl}/api/git/pull-requests`, { params: { repo_url: repoUrl, state: state || "open" } })
    return res.data
  },

  getPRSummary: async (): Promise<Record<string, unknown>> => {
    const res = await axios.get(`${apiUrl}/api/git/pull-requests/summary`)
    return res.data
  },

  generateContext: async (params: {
    mission_id?: string
    patch_plan_id?: string
    patch_candidate_id?: string
    repo_url?: string
    workspace_id?: string
    files_changed?: string
  }): Promise<{ context: EngineeringContext; formatted_body: string }> => {
    const res = await axios.get(`${apiUrl}/api/git/context`, { params })
    return res.data
  },
}
