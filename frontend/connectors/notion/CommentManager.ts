import { NotionComment } from "./types"
import { NotionClient } from "./NotionClient"

function mapApiComment(api: Record<string, unknown>): NotionComment {
  const richText = (api.rich_text as Record<string, unknown>[])?.[0]
  return {
    id: String(api.id), pageId: String((api.parent as Record<string, unknown>)?.page_id ?? ""),
    blockId: (api.parent as Record<string, unknown>)?.block_id as string ?? null,
    authorId: String((api.created_by as Record<string, unknown>)?.id ?? ""),
    body: String(richText?.plain_text ?? ""),
    edited: (api.created_time as string) !== (api.last_edited_time as string),
    createdAt: String(api.created_time ?? ""), updatedAt: String(api.last_edited_time ?? ""),
  }
}

export const CommentManager = {
  async createComment(pageId: string, body: string): Promise<NotionComment | null> {
    const result = await NotionClient.post<Record<string, unknown>>("/comments", { parent: { page_id: pageId }, rich_text: [{ type: "text", text: { content: body } }] })
    if (result.success && result.data) return mapApiComment(result.data)
    return null
  },

  async listComments(pageId: string): Promise<NotionComment[]> {
    const result = await NotionClient.get<Record<string, unknown>>(`/comments?block_id=${pageId}&page_size=100`)
    if (result.success && result.data?.results) return (result.data.results as Record<string, unknown>[]).map(mapApiComment)
    return []
  },

  async editComment(id: string, body: string): Promise<NotionComment | null> {
    return null
  },

  async deleteComment(id: string): Promise<boolean> {
    return false
  },
}