import { api } from '@/services/api';
import type {
  GithubWebhook,
  GithubWorkflowRun,
  GithubPullRequest,
  GithubIssue,
  GithubRelease,
  GithubDeployment,
  GithubBranchIntel,
  GithubDashboardStats,
  WebhookTranslateResult,
  MissionLaunchResult,
} from '@/types/github-operations';

const BASE = '/api/github';

export const enterpriseGithubApi = {
  // ---- Webhooks ----
  receiveWebhook: (payload: Record<string, any>, eventType: string, signature?: string, secret?: string) =>
    api.post<GithubWebhook>(`${BASE}/webhook/payload`, { payload, event_type: eventType, signature: signature || '', secret: secret || '' }),

  listWebhooks: (limit = 20) =>
    api.get<{ webhooks: GithubWebhook[] }>(`${BASE}/webhooks`, { params: { limit } }),

  translateEvent: (eventType: string, payload: Record<string, any>) =>
    api.post<WebhookTranslateResult>(`${BASE}/translate`, { event_type: eventType, payload }),

  launchMission: (eventType: string, payload: Record<string, any>) =>
    api.post<MissionLaunchResult>(`${BASE}/launch-mission`, { event_type: eventType, payload }),

  // ---- Dashboard ----
  getDashboard: (owner?: string, repo?: string) =>
    api.get<GithubDashboardStats>(`${BASE}/dashboard`, { params: { owner, repo } }),

  getActivity: (owner?: string, repo?: string, limit = 20) =>
    api.get<{ activity: any[] }>(`${BASE}/activity`, { params: { owner, repo, limit } }),

  // ---- Workflow Runs ----
  listWorkflowRuns: (owner: string, repo: string, params?: { status?: string; branch?: string }) =>
    api.get<{ workflow_runs: GithubWorkflowRun[] }>(`${BASE}/workflow-runs`, { params: { owner, repo, ...params } }),

  getWorkflowRun: (owner: string, repo: string, runId: string) =>
    api.get<GithubWorkflowRun>(`${BASE}/workflow-runs/${runId}`, { params: { owner, repo } }),

  // ---- Workflows ----
  listWorkflows: (owner: string, repo: string) =>
    api.get<{ workflows: any[] }>(`${BASE}/workflows`, { params: { owner, repo } }),

  // ---- Pull Requests ----
  listPullRequests: (owner: string, repo: string, state = 'open') =>
    api.get<{ pull_requests: GithubPullRequest[] }>(`${BASE}/pull-requests`, { params: { owner, repo, state } }),

  getPullRequest: (owner: string, repo: string, prNumber: number) =>
    api.get<GithubPullRequest>(`${BASE}/pull-requests/${prNumber}`, { params: { owner, repo } }),

  listReviews: (owner: string, repo: string, prNumber: number) =>
    api.get<{ reviews: any[] }>(`${BASE}/pull-requests/${prNumber}/reviews`, { params: { owner, repo } }),

  // ---- Issues ----
  listIssues: (owner: string, repo: string, state = 'open') =>
    api.get<{ issues: GithubIssue[] }>(`${BASE}/issues`, { params: { owner, repo, state } }),

  getIssue: (owner: string, repo: string, issueNumber: number) =>
    api.get<GithubIssue>(`${BASE}/issues/${issueNumber}`, { params: { owner, repo } }),

  // ---- Releases ----
  listReleases: (owner: string, repo: string) =>
    api.get<{ releases: GithubRelease[] }>(`${BASE}/releases`, { params: { owner, repo } }),

  getRelease: (owner: string, repo: string, tag: string) =>
    api.get<GithubRelease>(`${BASE}/releases/${encodeURIComponent(tag)}`, { params: { owner, repo } }),

  getLatestRelease: (owner: string, repo: string) =>
    api.get<GithubRelease>(`${BASE}/releases/latest`, { params: { owner, repo } }),

  // ---- Deployments ----
  listDeployments: (owner: string, repo: string, environment?: string) =>
    api.get<{ deployments: GithubDeployment[] }>(`${BASE}/deployments`, { params: { owner, repo, environment } }),

  getDeployment: (owner: string, repo: string, deploymentId: string) =>
    api.get<GithubDeployment>(`${BASE}/deployments/${deploymentId}`, { params: { owner, repo } }),

  // ---- Branches ----
  listBranches: (owner: string, repo: string) =>
    api.get<{ branches: GithubBranchIntel[] }>(`${BASE}/branches`, { params: { owner, repo } }),

  getBranchProtection: (owner: string, repo: string, branchName: string) =>
    api.get<any>(`${BASE}/branches/${encodeURIComponent(branchName)}/protection`, { params: { owner, repo } }),

  // ---- Commit Status ----
  getCommitStatus: (owner: string, repo: string, ref: string) =>
    api.get<any>(`${BASE}/commits/${encodeURIComponent(ref)}/status`, { params: { owner, repo } }),

  // ---- Sync ----
  syncRepositories: (owner: string, repos?: string[]) =>
    api.post<{ synced: any }>(`${BASE}/sync`, { owner, repos }),
};
