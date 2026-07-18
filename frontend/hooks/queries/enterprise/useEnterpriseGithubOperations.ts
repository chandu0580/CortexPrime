import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { enterpriseGithubApi } from "@/services/enterprise/github-operations"
import type { GithubWorkflowRun, GithubPullRequest, GithubIssue, GithubRelease, GithubDeployment, GithubBranchIntel } from "@/types/github-operations"

const KEYS = {
  dashboard: (owner?: string, repo?: string) => ["github", "dashboard", owner, repo] as const,
  webhooks: ["github", "webhooks"] as const,
  activity: (owner?: string, repo?: string) => ["github", "activity", owner, repo] as const,
  workflowRuns: (owner: string, repo: string, params?: { status?: string; branch?: string }) =>
    ["github", "workflow-runs", owner, repo, params] as const,
  workflowRun: (owner: string, repo: string, id: string) => ["github", "workflow-runs", owner, repo, id] as const,
  workflows: (owner: string, repo: string) => ["github", "workflows", owner, repo] as const,
  pullRequests: (owner: string, repo: string, state?: string) => ["github", "pull-requests", owner, repo, state] as const,
  pullRequest: (owner: string, repo: string, num: number) => ["github", "pull-requests", owner, repo, num] as const,
  reviews: (owner: string, repo: string, num: number) => ["github", "reviews", owner, repo, num] as const,
  issues: (owner: string, repo: string, state?: string) => ["github", "issues", owner, repo, state] as const,
  issue: (owner: string, repo: string, num: number) => ["github", "issues", owner, repo, num] as const,
  releases: (owner: string, repo: string) => ["github", "releases", owner, repo] as const,
  release: (owner: string, repo: string, tag: string) => ["github", "releases", owner, repo, tag] as const,
  latestRelease: (owner: string, repo: string) => ["github", "releases", owner, repo, "latest"] as const,
  deployments: (owner: string, repo: string, environment?: string) =>
    ["github", "deployments", owner, repo, environment] as const,
  deployment: (owner: string, repo: string, id: string) => ["github", "deployments", owner, repo, id] as const,
  branches: (owner: string, repo: string) => ["github", "branches", owner, repo] as const,
  branchProtection: (owner: string, repo: string, name: string) =>
    ["github", "branches", owner, repo, name, "protection"] as const,
  commitStatus: (owner: string, repo: string, ref: string) =>
    ["github", "commits", owner, repo, ref, "status"] as const,
}

// ---- Dashboard ----

export function useGithubDashboard(owner?: string, repo?: string) {
  return useQuery({
    queryKey: KEYS.dashboard(owner, repo),
    queryFn: () => enterpriseGithubApi.getDashboard(owner, repo),
    enabled: !!owner && !!repo,
    refetchInterval: 10_000,
  })
}

// ---- Webhooks ----

export function useGithubWebhooks(limit = 20) {
  return useQuery({
    queryKey: [...KEYS.webhooks, limit],
    queryFn: () => enterpriseGithubApi.listWebhooks(limit),
    refetchInterval: 10_000,
  })
}

// ---- Activity ----

export function useGithubActivity(owner?: string, repo?: string, limit = 20) {
  return useQuery({
    queryKey: [...KEYS.activity(owner, repo), limit],
    queryFn: () => enterpriseGithubApi.getActivity(owner, repo, limit),
    enabled: !!owner && !!repo,
    refetchInterval: 10_000,
  })
}

// ---- Workflow Runs ----

export function useGithubWorkflowRuns(owner: string, repo: string, params?: { status?: string; branch?: string }) {
  return useQuery({
    queryKey: KEYS.workflowRuns(owner, repo, params),
    queryFn: () => enterpriseGithubApi.listWorkflowRuns(owner, repo, params),
    enabled: !!owner && !!repo,
    refetchInterval: params?.status === "in_progress" ? 5_000 : 30_000,
  })
}

export function useGithubWorkflowRun(owner: string, repo: string, runId: string) {
  return useQuery({
    queryKey: KEYS.workflowRun(owner, repo, runId),
    queryFn: () => enterpriseGithubApi.getWorkflowRun(owner, repo, runId),
    enabled: !!owner && !!repo && !!runId,
  })
}

// ---- Workflows ----

export function useGithubWorkflows(owner: string, repo: string) {
  return useQuery({
    queryKey: KEYS.workflows(owner, repo),
    queryFn: () => enterpriseGithubApi.listWorkflows(owner, repo),
    enabled: !!owner && !!repo,
    refetchInterval: 30_000,
  })
}

// ---- Pull Requests ----

export function useGithubPullRequests(owner: string, repo: string, state = "open") {
  return useQuery({
    queryKey: KEYS.pullRequests(owner, repo, state),
    queryFn: () => enterpriseGithubApi.listPullRequests(owner, repo, state),
    enabled: !!owner && !!repo,
    refetchInterval: 30_000,
  })
}

export function useGithubPullRequest(owner: string, repo: string, prNumber: number) {
  return useQuery({
    queryKey: KEYS.pullRequest(owner, repo, prNumber),
    queryFn: () => enterpriseGithubApi.getPullRequest(owner, repo, prNumber),
    enabled: !!owner && !!repo && prNumber > 0,
  })
}

export function useGithubReviews(owner: string, repo: string, prNumber: number) {
  return useQuery({
    queryKey: KEYS.reviews(owner, repo, prNumber),
    queryFn: () => enterpriseGithubApi.listReviews(owner, repo, prNumber),
    enabled: !!owner && !!repo && prNumber > 0,
  })
}

// ---- Issues ----

export function useGithubIssues(owner: string, repo: string, state = "open") {
  return useQuery({
    queryKey: KEYS.issues(owner, repo, state),
    queryFn: () => enterpriseGithubApi.listIssues(owner, repo, state),
    enabled: !!owner && !!repo,
    refetchInterval: 30_000,
  })
}

export function useGithubIssue(owner: string, repo: string, issueNumber: number) {
  return useQuery({
    queryKey: KEYS.issue(owner, repo, issueNumber),
    queryFn: () => enterpriseGithubApi.getIssue(owner, repo, issueNumber),
    enabled: !!owner && !!repo && issueNumber > 0,
  })
}

// ---- Releases ----

export function useGithubReleases(owner: string, repo: string) {
  return useQuery({
    queryKey: KEYS.releases(owner, repo),
    queryFn: () => enterpriseGithubApi.listReleases(owner, repo),
    enabled: !!owner && !!repo,
    refetchInterval: 60_000,
  })
}

export function useGithubRelease(owner: string, repo: string, tag: string) {
  return useQuery({
    queryKey: KEYS.release(owner, repo, tag),
    queryFn: () => enterpriseGithubApi.getRelease(owner, repo, tag),
    enabled: !!owner && !!repo && !!tag,
  })
}

export function useGithubLatestRelease(owner: string, repo: string) {
  return useQuery({
    queryKey: KEYS.latestRelease(owner, repo),
    queryFn: () => enterpriseGithubApi.getLatestRelease(owner, repo),
    enabled: !!owner && !!repo,
  })
}

// ---- Deployments ----

export function useGithubDeployments(owner: string, repo: string, environment?: string) {
  return useQuery({
    queryKey: KEYS.deployments(owner, repo, environment),
    queryFn: () => enterpriseGithubApi.listDeployments(owner, repo, environment),
    enabled: !!owner && !!repo,
    refetchInterval: 15_000,
  })
}

export function useGithubDeployment(owner: string, repo: string, deploymentId: string) {
  return useQuery({
    queryKey: KEYS.deployment(owner, repo, deploymentId),
    queryFn: () => enterpriseGithubApi.getDeployment(owner, repo, deploymentId),
    enabled: !!owner && !!repo && !!deploymentId,
  })
}

// ---- Branches ----

export function useGithubBranches(owner: string, repo: string) {
  return useQuery({
    queryKey: KEYS.branches(owner, repo),
    queryFn: () => enterpriseGithubApi.listBranches(owner, repo),
    enabled: !!owner && !!repo,
    refetchInterval: 30_000,
  })
}

export function useGithubBranchProtection(owner: string, repo: string, branchName: string) {
  return useQuery({
    queryKey: KEYS.branchProtection(owner, repo, branchName),
    queryFn: () => enterpriseGithubApi.getBranchProtection(owner, repo, branchName),
    enabled: !!owner && !!repo && !!branchName,
  })
}

// ---- Commit Status ----

export function useGithubCommitStatus(owner: string, repo: string, ref: string) {
  return useQuery({
    queryKey: KEYS.commitStatus(owner, repo, ref),
    queryFn: () => enterpriseGithubApi.getCommitStatus(owner, repo, ref),
    enabled: !!owner && !!repo && !!ref,
  })
}

// ---- Sync ----

export function useSyncRepositories() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (params: { owner: string; repos?: string[] }) =>
      enterpriseGithubApi.syncRepositories(params.owner, params.repos),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["github"] })
    },
  })
}

// ---- Mutations (Webhook, Translate, Mission) ----

export function useReceiveWebhook() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (params: { payload: Record<string, any>; eventType: string; signature?: string; secret?: string }) =>
      enterpriseGithubApi.receiveWebhook(params.payload, params.eventType, params.signature, params.secret),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.dashboard() })
      qc.invalidateQueries({ queryKey: KEYS.webhooks })
      qc.invalidateQueries({ queryKey: KEYS.activity() })
    },
  })
}

export function useTranslateEvent() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (params: { eventType: string; payload: Record<string, any> }) =>
      enterpriseGithubApi.translateEvent(params.eventType, params.payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.dashboard() })
      qc.invalidateQueries({ queryKey: KEYS.activity() })
      qc.invalidateQueries({ queryKey: ["github"] })
    },
  })
}

export function useLaunchMission() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (params: { eventType: string; payload: Record<string, any> }) =>
      enterpriseGithubApi.launchMission(params.eventType, params.payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.dashboard() })
      qc.invalidateQueries({ queryKey: ["engineering-executive"] })
    },
  })
}
