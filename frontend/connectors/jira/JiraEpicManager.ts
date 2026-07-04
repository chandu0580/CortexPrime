import { JiraEpic } from "./types"
import { IssueStatus } from "./types"
import { JiraClient } from "./JiraClient"

export const JiraEpicManager = {
  async createEpic(projectKey: string, name: string, summary: string, color = "#4A90D9"): Promise<JiraEpic> {
    const body = { fields: { project: { key: projectKey }, issuetype: { name: "Epic" }, summary: name, description: { type: "doc", version: 1, content: [{ type: "paragraph", content: [{ type: "text", text: summary }] }] }, customfield_10011: name } }
    const result = await JiraClient.post<Record<string, unknown>>("/rest/api/3/issue", body)
    if (result.success && result.data) {
      return { id: String(result.data.id), projectId: projectKey, key: String(result.data.key), name, summary, status: IssueStatus.BACKLOG, color, startDate: null, endDate: null, issues: [], createdAt: new Date().toISOString(), updatedAt: new Date().toISOString(), completedAt: null }
    }
    const now = new Date().toISOString()
    return { id: "", projectId: projectKey, key: `EPIC-${now}`, name, summary, status: IssueStatus.BACKLOG, color, startDate: null, endDate: null, issues: [], createdAt: now, updatedAt: now, completedAt: null }
  },

  async updateEpic(epicKey: string, name: string, summary: string, color: string): Promise<JiraEpic | null> {
    const result = await JiraClient.put(`/rest/api/3/issue/${epicKey}`, { fields: { summary: name, customfield_10011: name, description: { type: "doc", version: 1, content: [{ type: "paragraph", content: [{ type: "text", text: summary }] }] } } })
    if (result.success) return this.getEpic(epicKey)
    return null
  },

  async linkIssue(epicKey: string, issueKey: string): Promise<JiraEpic | null> {
    const result = await JiraClient.put(`/rest/api/3/issue/${issueKey}`, { fields: { customfield_10014: epicKey } })
    if (result.success) return this.getEpic(epicKey)
    return null
  },

  async completeEpic(epicKey: string): Promise<JiraEpic | null> {
    const transitionsResult = await JiraClient.get<Record<string, unknown>>(`/rest/api/3/issue/${epicKey}/transitions`)
    if (transitionsResult.success && transitionsResult.data) {
      const transitions = (transitionsResult.data as Record<string, unknown>).transitions as Record<string, unknown>[]
      const done = transitions?.find((t) => ((t.to as Record<string, unknown>)?.name as string ?? "").toLowerCase().includes("done") || (t.name as string ?? "").toLowerCase().includes("close"))
      if (done) {
        await JiraClient.post(`/rest/api/3/issue/${epicKey}/transitions`, { transition: { id: done.id } })
      }
    }
    return this.getEpic(epicKey)
  },

  async getEpic(epicKey: string): Promise<JiraEpic | null> {
    const result = await JiraClient.get<Record<string, unknown>>(`/rest/api/3/issue/${epicKey}?fields=summary,description,status,customfield_10014,customfield_10011,created,updated,resolutiondate`)
    if (result.success && result.data) {
      const fields = result.data.fields as Record<string, unknown> ?? {}
      return { id: String(result.data.id), projectId: "", key: String(result.data.key), name: String(fields.customfield_10011 ?? fields.summary ?? ""), summary: String(fields.description ?? ""), status: ((fields.status as Record<string, unknown>)?.name as string ?? "backlog").toLowerCase().replace(/ /g, "_") as IssueStatus, color: "", startDate: null, endDate: fields.resolutiondate as string ?? null, issues: [], createdAt: String(fields.created ?? ""), updatedAt: String(fields.updated ?? ""), completedAt: fields.resolutiondate as string ?? null }
    }
    return null
  },

  async listEpics(projectKey: string): Promise<JiraEpic[]> {
    const result = await JiraClient.post<Record<string, unknown>>("/rest/api/3/search", { jql: `project=${projectKey} AND issuetype=Epic`, maxResults: 100, fields: ["summary", "description", "status", "customfield_10011", "customfield_10014", "created", "updated", "resolutiondate"] })
    if (result.success && result.data) {
      const issues = (result.data as Record<string, unknown>).issues as Record<string, unknown>[]
      return (issues ?? []).map((i) => {
        const fields = i.fields as Record<string, unknown> ?? {}
        return { id: String(i.id), projectId: projectKey, key: String(i.key), name: String(fields.customfield_10011 ?? fields.summary ?? ""), summary: String(fields.description ?? ""), status: ((fields.status as Record<string, unknown>)?.name as string ?? "backlog").toLowerCase().replace(/ /g, "_") as IssueStatus, color: "", startDate: null, endDate: fields.resolutiondate as string ?? null, issues: [], createdAt: String(fields.created ?? ""), updatedAt: String(fields.updated ?? ""), completedAt: fields.resolutiondate as string ?? null }
      })
    }
    return []
  },

  async listEpicIssues(epicKey: string): Promise<string[]> {
    const result = await JiraClient.post<Record<string, unknown>>("/rest/api/3/search", { jql: `"Epic Link"=${epicKey}`, maxResults: 100, fields: ["key"] })
    if (result.success && result.data) {
      const issues = (result.data as Record<string, unknown>).issues as Record<string, unknown>[]
      return (issues ?? []).map((i) => String(i.key))
    }
    return []
  },
}