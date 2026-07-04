import { ConfluenceComment, ConfluenceLabel } from "./types"
import { ConfluenceClient } from "./ConfluenceClient"

function mapApiComment(api: Record<string, unknown>, pageId: string): ConfluenceComment {
  const version = api.version as Record<string, unknown> ?? {}
  return {
    id: String(api.id), pageId, parentCommentId: (api.parentId as string) ?? null,
    body: String(((api.body as Record<string, unknown>)?.storage as Record<string, unknown>)?.value ?? (api.body as Record<string, unknown>)?.value ?? ""),
    authorId: String((version.author as Record<string, unknown>)?.id ?? (api.authorId as string) ?? ""),
    edited: (api.updatedAt as string) !== (api.createdAt as string), labels: [],
    createdAt: String(api.createdAt ?? ""), updatedAt: String(api.updatedAt ?? ""),
  }
}

export const ConfluenceCommentManager = {
  async createComment(pageId: string, body: string): Promise<ConfluenceComment | null> {
    const result = await ConfluenceClient.post<Record<string, unknown>>(`/pages/${pageId}/comments`, { body: { representation: "storage", value: body } })
    if (result.success && result.data) return mapApiComment(result.data, pageId)
    return null
  },

  async editComment(id: string, pageId: string, body: string, version: number): Promise<ConfluenceComment | null> {
    const result = await ConfluenceClient.put<Record<string, unknown>>(`/comments/${id}`, { id, body: { representation: "storage", value: body }, version: { number: version + 1, message: "Edit" } })
    if (result.success && result.data) return mapApiComment(result.data, pageId)
    return null
  },

  async deleteComment(id: string): Promise<boolean> {
    const result = await ConfluenceClient.delete(`/comments/${id}`)
    return result.success
  },

  async listComments(pageId: string): Promise<ConfluenceComment[]> {
    const result = await ConfluenceClient.get<Record<string, unknown>>(`/pages/${pageId}/comments?limit=100`)
    if (result.success && result.data?.results) return (result.data.results as Record<string, unknown>[]).map((c) => mapApiComment(c, pageId))
    return []
  },
}