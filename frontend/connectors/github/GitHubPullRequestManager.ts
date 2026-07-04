import { GitHubPullRequest, GitHubReview, PullRequestState, ReviewState } from "./types"
import { GitHubClient } from "./GitHubClient"

function mapApiPr(apiPr: Record<string, unknown>, repositoryId: string): GitHubPullRequest {
  const head = apiPr.head as Record<string, unknown> ?? {}
  const base = apiPr.base as Record<string, unknown> ?? {}
  return {
    id: String(apiPr.id),
    repositoryId,
    number: Number(apiPr.number),
    title: String(apiPr.title),
    body: String(apiPr.body ?? ""),
    state: (apiPr.merged === true ? "merged" : apiPr.state as PullRequestState) ?? "open",
    author: (apiPr.user as Record<string, unknown>)?.login as string ?? "",
    headBranch: String(head.ref ?? ""),
    baseBranch: String(base.ref ?? ""),
    headSha: String(head.sha ?? ""),
    baseSha: String(base.sha ?? ""),
    assignees: ((apiPr.assignees as Record<string, unknown>[]) ?? []).map((a) => String(a.login)),
    reviewers: ((apiPr.requested_reviewers as Record<string, unknown>[]) ?? []).map((r) => String(r.login)),
    labels: ((apiPr.labels as Record<string, unknown>[]) ?? []).map((l) => ({ id: String(l.id), repositoryId, name: String(l.name), color: String(l.color), description: String(l.description ?? "") })),
    milestone: null,
    draft: Boolean(apiPr.draft ?? false),
    mergeable: apiPr.mergeable === true,
    merged: Boolean(apiPr.merged),
    mergedBy: (apiPr.merged_by as Record<string, unknown>)?.login as string ?? null,
    comments: Number(apiPr.comments),
    reviewComments: Number(apiPr.review_comments),
    additions: Number(apiPr.additions),
    deletions: Number(apiPr.deletions),
    createdAt: String(apiPr.created_at),
    updatedAt: String(apiPr.updated_at),
    mergedAt: apiPr.merged_at as string ?? null,
    closedAt: apiPr.closed_at as string ?? null,
  }
}

export const GitHubPullRequestManager = {
  async createPullRequest(
    owner: string,
    repo: string,
    title: string,
    body: string,
    headBranch: string,
    baseBranch: string,
    draft = false,
  ): Promise<GitHubPullRequest> {
    const result = await GitHubClient.post<Record<string, unknown>>(`/repos/${owner}/${repo}/pulls`, { title, body, head: headBranch, base: baseBranch, draft })
    if (result.success && result.data) return mapApiPr(result.data, `${owner}/${repo}`)
    const now = new Date().toISOString()
    return { id: "", repositoryId: `${owner}/${repo}`, number: 0, title, body, state: draft ? "draft" : "open", author: "", headBranch, baseBranch, headSha: "", baseSha: "", assignees: [], reviewers: [], labels: [], milestone: null, draft, mergeable: false, merged: false, mergedBy: null, comments: 0, reviewComments: 0, additions: 0, deletions: 0, createdAt: now, updatedAt: now, mergedAt: null, closedAt: null }
  },

  async mergePullRequest(owner: string, repo: string, prNumber: number): Promise<GitHubPullRequest | null> {
    const result = await GitHubClient.put<Record<string, unknown>>(`/repos/${owner}/${repo}/pulls/${prNumber}/merge`)
    if (result.success && result.data) return this.getPullRequest(owner, repo, prNumber)
    return null
  },

  async closePullRequest(owner: string, repo: string, prNumber: number): Promise<GitHubPullRequest | null> {
    const result = await GitHubClient.patch<Record<string, unknown>>(`/repos/${owner}/${repo}/pulls/${prNumber}`, { state: "closed" })
    if (result.success && result.data) return mapApiPr(result.data, `${owner}/${repo}`)
    return null
  },

  async requestReview(owner: string, repo: string, prNumber: number, reviewers: string[]): Promise<GitHubPullRequest | null> {
    const result = await GitHubClient.post<Record<string, unknown>>(`/repos/${owner}/${repo}/pulls/${prNumber}/requested_reviewers`, { reviewers })
    if (result.success && result.data) return mapApiPr(result.data, `${owner}/${repo}`)
    return null
  },

  async submitReview(owner: string, repo: string, prNumber: number, state: ReviewState, body: string): Promise<GitHubReview | null> {
    const result = await GitHubClient.post<Record<string, unknown>>(`/repos/${owner}/${repo}/pulls/${prNumber}/reviews`, { body, event: state === "approved" ? "APPROVE" : state === "changes_requested" ? "REQUEST_CHANGES" : "COMMENT" })
    if (result.success && result.data) {
      return { id: String(result.data.id), pullRequestId: String(prNumber), author: (result.data.user as Record<string, unknown>)?.login as string ?? "", state, body, commitSha: String((result.data as Record<string, unknown>).commit_id ?? ""), submittedAt: String(result.data.submitted_at) }
    }
    return null
  },

  async getPullRequest(owner: string, repo: string, prNumber: number): Promise<GitHubPullRequest | null> {
    const result = await GitHubClient.get<Record<string, unknown>>(`/repos/${owner}/${repo}/pulls/${prNumber}`)
    if (result.success && result.data) return mapApiPr(result.data, `${owner}/${repo}`)
    return null
  },

  async listPullRequests(owner: string, repo: string, state?: PullRequestState): Promise<GitHubPullRequest[]> {
    const stateParam = state ? `&state=${state}` : ""
    const result = await GitHubClient.get<Record<string, unknown>[]>(`/repos/${owner}/${repo}/pulls?per_page=100${stateParam}`)
    if (result.success && result.data) return result.data.map((pr) => mapApiPr(pr, `${owner}/${repo}`))
    return []
  },
}