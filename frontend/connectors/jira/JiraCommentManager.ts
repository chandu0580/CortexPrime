import { JiraComment } from "./types"
import { JiraClient } from "./JiraClient"

export const JiraCommentManager = {
  async addComment(issueKey: string, author: string, body: string): Promise<JiraComment> {
    const result = await JiraClient.post<Record<string, unknown>>(`/rest/api/3/issue/${issueKey}/comment`, {
      body: { type: "doc", version: 1, content: [{ type: "paragraph", content: [{ type: "text", text: body }] }] },
    })
    if (result.success && result.data) {
      const authorObj = result.data.author as Record<string, unknown> ?? {}
      return { id: String(result.data.id), issueId: issueKey, author: String(authorObj.displayName ?? author), body, edited: false, createdAt: String(result.data.created), updatedAt: String(result.data.updated) }
    }
    const now = new Date().toISOString()
    return { id: "", issueId: issueKey, author, body, edited: false, createdAt: now, updatedAt: now }
  },

  async editComment(issueKey: string, commentId: string, body: string): Promise<JiraComment | null> {
    const result = await JiraClient.put<Record<string, unknown>>(`/rest/api/3/issue/${issueKey}/comment/${commentId}`, {
      body: { type: "doc", version: 1, content: [{ type: "paragraph", content: [{ type: "text", text: body }] }] },
    })
    if (result.success && result.data) {
      const authorObj = result.data.author as Record<string, unknown> ?? {}
      return { id: String(result.data.id), issueId: issueKey, author: String(authorObj.displayName ?? ""), body, edited: true, createdAt: String(result.data.created), updatedAt: String(result.data.updated) }
    }
    return null
  },

  async listComments(issueKey: string): Promise<JiraComment[]> {
    const result = await JiraClient.get<Record<string, unknown>>(`/rest/api/3/issue/${issueKey}/comment?maxResults=100`)
    if (result.success && result.data) {
      const comments = (result.data as Record<string, unknown>).comments as Record<string, unknown>[]
      return (comments ?? []).map((c) => {
        const authorObj = c.author as Record<string, unknown> ?? {}
        return { id: String(c.id), issueId: issueKey, author: String(authorObj.displayName ?? ""), body: String((c.body as string) ?? ""), edited: Boolean(c.updated !== c.created), createdAt: String(c.created), updatedAt: String(c.updated) }
      })
    }
    return []
  },
}