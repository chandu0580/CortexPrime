import { type JiraIssue, type JiraComment, type IssueType, IssueStatus } from "./types"
import { JiraClient } from "./JiraClient"

function mapApiIssue(api: Record<string, unknown>, projectId: string): JiraIssue {
  const fields = api.fields as Record<string, unknown> ?? {}
  const assignee = fields.assignee as Record<string, unknown> ?? null
  const reporter = fields.reporter as Record<string, unknown> ?? {}
  const labels = (api.labels as string[] ?? fields.labels as string[] ?? []).map((n: string) => ({ id: n, name: n, color: "" }))
  const components = (fields.components as Record<string, unknown>[] ?? []).map((c: Record<string, unknown>) => ({ id: String(c.id), projectId, name: String(c.name), description: String(c.description ?? ""), lead: (c.lead as Record<string, unknown>)?.displayName as string ?? null, assigneeType: String(c.assigneeType ?? ""), createdAt: "" }))
  const attachments = (fields.attachment as Record<string, unknown>[] ?? []).map((a: Record<string, unknown>) => ({ id: String(a.id), issueId: String(api.id), filename: String(a.filename), mimeType: String(a.mimeType ?? ""), sizeBytes: Number(a.size ?? 0), author: (a.author as Record<string, unknown>)?.displayName as string ?? "", url: String(a.content ?? ""), createdAt: String(a.created ?? "") }))
  const issuelinks = fields.issuelinks as Record<string, unknown>[] ?? []
  const epicLink = fields.epic as Record<string, unknown> ?? fields.customfield_10014

  return {
    id: String(api.id),
    projectId,
    key: String(api.key ?? fields.key ?? ""),
    issueType: ((fields.issuetype as Record<string, unknown>)?.name as string ?? "task").toLowerCase() as IssueType,
    status: ((fields.status as Record<string, unknown>)?.name as string ?? "backlog").toLowerCase().replace(/ /g, "_") as IssueStatus,
    title: String(fields.summary ?? api.title ?? ""),
    description: String(fields.description ?? api.description ?? ""),
    assignee: assignee ? { id: String(assignee.accountId ?? assignee.id ?? ""), displayName: String(assignee.displayName ?? ""), email: String(assignee.emailAddress ?? ""), avatarUrl: String(((assignee.avatarUrls as Record<string, unknown>)?.square48 as string) ?? ""), active: Boolean(assignee.active ?? true) } : null,
    reporter: { id: String(reporter.accountId ?? reporter.id ?? ""), displayName: String(reporter.displayName ?? ""), email: String(reporter.emailAddress ?? ""), avatarUrl: String(((reporter.avatarUrls as Record<string, unknown>)?.square48 as string) ?? "") },
    epicId: epicLink ? String(epicLink.id ?? "") : null,
    sprintId: null,
    labels, components, attachments,
    storyPoints: Number(fields.customfield_10016 ?? fields.storyPoints ?? 0),
    priority: String((fields.priority as Record<string, unknown>)?.name ?? "medium"),
    resolution: (fields.resolution as Record<string, unknown>)?.name as string ?? null,
    votes: Number((fields.votes as Record<string, unknown>)?.votes ?? 0),
    watchers: Number((fields.watches as Record<string, unknown>)?.watchCount ?? 0),
    createdAt: String(fields.created ?? api.createdAt ?? new Date().toISOString()),
    updatedAt: String(fields.updated ?? api.updatedAt ?? new Date().toISOString()),
    resolvedAt: fields.resolutiondate as string ?? null,
  }
}

export const JiraIssueManager = {
  async createIssue(projectKey: string, issueType: IssueType, title: string, description: string, reporterId: string): Promise<JiraIssue> {
    const body = { fields: { project: { key: projectKey }, issuetype: { name: issueType.charAt(0).toUpperCase() + issueType.slice(1) }, summary: title, description: { type: "doc", version: 1, content: [{ type: "paragraph", content: [{ type: "text", text: description }] }] }, reporter: { id: reporterId } } }
    const result = await JiraClient.post<Record<string, unknown>>("/rest/api/3/issue", body)
    if (result.success && result.data) return mapApiIssue(result.data, projectKey)
    const now = new Date().toISOString()
    return { id: "", projectId: projectKey, key: "", issueType, status: IssueStatus.BACKLOG, title, description, assignee: null, reporter: { id: reporterId, displayName: "", email: "", avatarUrl: "" }, epicId: null, sprintId: null, labels: [], components: [], attachments: [], storyPoints: 0, priority: "medium", resolution: null, votes: 0, watchers: 0, createdAt: now, updatedAt: now, resolvedAt: null }
  },

  async updateIssue(issueKey: string, updates: Partial<JiraIssue>): Promise<JiraIssue | null> {
    const body: Record<string, unknown> = { fields: {} }
    const fields = body.fields as Record<string, unknown>
    if (updates.title) fields.summary = updates.title
    if (updates.description !== undefined) fields.description = { type: "doc", version: 1, content: [{ type: "paragraph", content: [{ type: "text", text: updates.description }] }] }
    if (updates.assignee) fields.assignee = { id: updates.assignee.id }
    const result = await JiraClient.put<Record<string, unknown>>(`/rest/api/3/issue/${issueKey}`, body)
    if (result.success) return this.getIssue(issueKey)
    return null
  },

  async assignIssue(issueKey: string, assigneeId: string): Promise<JiraIssue | null> {
    const result = await JiraClient.put(`/rest/api/3/issue/${issueKey}/assignee`, { accountId: assigneeId })
    if (result.success) return this.getIssue(issueKey)
    return null
  },

  async transitionIssue(issueKey: string, transitionId: string): Promise<JiraIssue | null> {
    const result = await JiraClient.post(`/rest/api/3/issue/${issueKey}/transitions`, { transition: { id: transitionId } })
    if (result.success) return this.getIssue(issueKey)
    return null
  },

  async closeIssue(issueKey: string): Promise<JiraIssue | null> {
    const transitions = await this.getTransitions(issueKey)
    const closeTransition = transitions.find((t) => t.toStatus?.toLowerCase().includes("done") || t.name?.toLowerCase().includes("close"))
    if (closeTransition) return this.transitionIssue(issueKey, closeTransition.id)
    return null
  },

  async reopenIssue(issueKey: string): Promise<JiraIssue | null> {
    const transitions = await this.getTransitions(issueKey)
    const reopenTransition = transitions.find((t) => t.toStatus?.toLowerCase().includes("backlog") || t.name?.toLowerCase().includes("reopen"))
    if (reopenTransition) return this.transitionIssue(issueKey, reopenTransition.id)
    return null
  },

  async getTransitions(issueKey: string): Promise<{ id: string; name: string; toStatus: string }[]> {
    const result = await JiraClient.get<Record<string, unknown>>(`/rest/api/3/issue/${issueKey}/transitions`)
    if (result.success && result.data) {
      const t = (result.data as Record<string, unknown>).transitions as Record<string, unknown>[]
      return (t ?? []).map((tr) => ({ id: String(tr.id), name: String(tr.name), toStatus: ((tr.to as Record<string, unknown>)?.name as string) ?? "" }))
    }
    return []
  },

  async addComment(issueKey: string, author: string, body: string): Promise<JiraComment | null> {
    const result = await JiraClient.post<Record<string, unknown>>(`/rest/api/3/issue/${issueKey}/comment`, { body: { type: "doc", version: 1, content: [{ type: "paragraph", content: [{ type: "text", text: body }] }] } })
    if (result.success && result.data) {
      const authorObj = result.data.author as Record<string, unknown> ?? {}
      return { id: String(result.data.id), issueId: issueKey, author: String(authorObj.displayName ?? author), body, edited: String(result.data.created) !== String(result.data.updated), createdAt: String(result.data.created), updatedAt: String(result.data.updated) }
    }
    return null
  },

  async getIssue(issueKey: string): Promise<JiraIssue | null> {
    const result = await JiraClient.get<Record<string, unknown>>(`/rest/api/3/issue/${issueKey}?expand=renderedFields,transitions,names`)
    if (result.success && result.data) return mapApiIssue(result.data, (result.data.fields as Record<string, unknown>)?.project as string ?? "")
    return null
  },

  async listIssues(projectKey: string): Promise<JiraIssue[]> {
    const result = await JiraClient.get<Record<string, unknown>>(`/rest/api/3/search?jql=project=${projectKey}&maxResults=100`)
    if (result.success && result.data) {
      const issues = (result.data as Record<string, unknown>).issues as Record<string, unknown>[]
      return (issues ?? []).map((i) => mapApiIssue(i, projectKey))
    }
    return []
  },

  async searchIssues(jql: string): Promise<JiraIssue[]> {
    const result = await JiraClient.post<Record<string, unknown>>("/rest/api/3/search", { jql, maxResults: 100 })
    if (result.success && result.data) {
      const issues = (result.data as Record<string, unknown>).issues as Record<string, unknown>[]
      return (issues ?? []).map((i) => mapApiIssue(i, ""))
    }
    return []
  },
}