import { GitHubIssue, GitHubIssueComment, GitHubLabel, GitHubMilestone, IssueState } from "./types"
import { GitHubClient } from "./GitHubClient"

function mapApiIssue(apiIssue: Record<string, unknown>, repositoryId: string): GitHubIssue {
  return {
    id: String(apiIssue.id),
    repositoryId,
    number: Number(apiIssue.number),
    title: String(apiIssue.title),
    body: String(apiIssue.body ?? ""),
    state: (apiIssue.state as IssueState) ?? "open",
    author: (apiIssue.user as Record<string, unknown>)?.login as string ?? "",
    assignees: ((apiIssue.assignees as Record<string, unknown>[]) ?? []).map((a) => String(a.login)),
    labels: ((apiIssue.labels as Record<string, unknown>[]) ?? []).map((l) => ({
      id: String(l.id), repositoryId, name: String(l.name), color: String(l.color), description: String(l.description ?? ""),
    })),
    milestone: apiIssue.milestone ? {
      id: String((apiIssue.milestone as Record<string, unknown>).id),
      repositoryId,
      number: Number((apiIssue.milestone as Record<string, unknown>).number),
      title: String((apiIssue.milestone as Record<string, unknown>).title),
      description: String((apiIssue.milestone as Record<string, unknown>).description ?? ""),
      state: ((apiIssue.milestone as Record<string, unknown>).state as IssueState) ?? "open",
      dueOn: (apiIssue.milestone as Record<string, unknown>).due_on as string ?? null,
      closedAt: (apiIssue.milestone as Record<string, unknown>).closed_at as string ?? null,
      createdAt: String((apiIssue.milestone as Record<string, unknown>).created_at),
      updatedAt: String((apiIssue.milestone as Record<string, unknown>).updated_at),
    } : null,
    comments: Number(apiIssue.comments),
    locked: Boolean(apiIssue.locked),
    createdAt: String(apiIssue.created_at),
    updatedAt: String(apiIssue.updated_at),
    closedAt: apiIssue.closed_at as string ?? null,
  }
}

export const GitHubIssueManager = {
  async createIssue(
    owner: string,
    repo: string,
    title: string,
    body: string,
    labels: string[] = [],
    assignees: string[] = [],
  ): Promise<GitHubIssue> {
    const result = await GitHubClient.post<Record<string, unknown>>(`/repos/${owner}/${repo}/issues`, { title, body, labels, assignees })
    if (result.success && result.data) return mapApiIssue(result.data, `${owner}/${repo}`)
    const now = new Date().toISOString()
    return { id: "", repositoryId: `${owner}/${repo}`, number: 0, title, body, state: "open", author: "", assignees, labels: [], milestone: null, comments: 0, locked: false, createdAt: now, updatedAt: now, closedAt: null }
  },

  async updateIssue(owner: string, repo: string, issueNumber: number, updates: Partial<GitHubIssue>): Promise<GitHubIssue | null> {
    const body: Record<string, unknown> = {}
    if (updates.title) body.title = updates.title
    if (updates.body !== undefined) body.body = updates.body
    if (updates.state) body.state = updates.state
    if (updates.assignees) body.assignees = updates.assignees
    if (updates.labels) body.labels = updates.labels.map((l) => l.name)
    const result = await GitHubClient.patch<Record<string, unknown>>(`/repos/${owner}/${repo}/issues/${issueNumber}`, body)
    if (result.success && result.data) return mapApiIssue(result.data, `${owner}/${repo}`)
    return null
  },

  async assignIssue(owner: string, repo: string, issueNumber: number, assignees: string[]): Promise<GitHubIssue | null> {
    const result = await GitHubClient.post<Record<string, unknown>>(`/repos/${owner}/${repo}/issues/${issueNumber}/assignees`, { assignees })
    if (result.success && result.data) return mapApiIssue(result.data, `${owner}/${repo}`)
    return null
  },

  async closeIssue(owner: string, repo: string, issueNumber: number): Promise<GitHubIssue | null> {
    return this.updateIssue(owner, repo, issueNumber, { state: "closed" })
  },

  async reopenIssue(owner: string, repo: string, issueNumber: number): Promise<GitHubIssue | null> {
    return this.updateIssue(owner, repo, issueNumber, { state: "open" })
  },

  async getIssue(owner: string, repo: string, issueNumber: number): Promise<GitHubIssue | null> {
    const result = await GitHubClient.get<Record<string, unknown>>(`/repos/${owner}/${repo}/issues/${issueNumber}`)
    if (result.success && result.data) return mapApiIssue(result.data, `${owner}/${repo}`)
    return null
  },

  async listIssues(owner: string, repo: string, state?: IssueState): Promise<GitHubIssue[]> {
    const stateParam = state ? `&state=${state}` : ""
    const result = await GitHubClient.get<Record<string, unknown>[]>(`/repos/${owner}/${repo}/issues?per_page=100${stateParam}`)
    if (result.success && result.data) return result.data.map((i) => mapApiIssue(i, `${owner}/${repo}`))
    return []
  },

  async addComment(owner: string, repo: string, issueNumber: number, body: string): Promise<GitHubIssueComment | null> {
    const result = await GitHubClient.post<Record<string, unknown>>(`/repos/${owner}/${repo}/issues/${issueNumber}/comments`, { body })
    if (result.success && result.data) {
      return { id: String(result.data.id), issueId: String(issueNumber), author: (result.data.user as Record<string, unknown>)?.login as string ?? "", body: String(result.data.body), createdAt: String(result.data.created_at), updatedAt: String(result.data.updated_at) }
    }
    return null
  },
}