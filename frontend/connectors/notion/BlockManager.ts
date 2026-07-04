import { NotionBlock, BlockType } from "./types"
import { NotionClient } from "./NotionClient"

function mapApiBlock(api: Record<string, unknown>, pageId: string): NotionBlock {
  return {
    id: String(api.id), pageId, parentBlockId: (api.parent as Record<string, unknown>)?.block_id as string ?? null,
    type: (api.type as string) as BlockType, content: api[api.type as string] as Record<string, unknown> ?? {},
    children: [], position: 0, createdAt: String(api.created_time ?? ""), updatedAt: String(api.last_edited_time ?? ""),
  }
}

export const BlockManager = {
  async appendChildren(blockId: string, children: Record<string, unknown>[]): Promise<NotionBlock[]> {
    const result = await NotionClient.patch<Record<string, unknown>>(`/blocks/${blockId}/children`, { children })
    if (result.success && result.data?.results) return (result.data.results as Record<string, unknown>[]).map((b) => mapApiBlock(b, blockId))
    return []
  },

  async listChildren(blockId: string): Promise<NotionBlock[]> {
    const result = await NotionClient.get<Record<string, unknown>>(`/blocks/${blockId}/children?page_size=100`)
    if (result.success && result.data?.results) return (result.data.results as Record<string, unknown>[]).map((b) => mapApiBlock(b, blockId))
    return []
  },

  async createBlock(pageId: string, type: BlockType, content: Record<string, unknown>): Promise<NotionBlock | null> {
    return null
  },

  async updateBlock(id: string, content: Record<string, unknown>): Promise<NotionBlock | null> {
    const result = await NotionClient.patch<Record<string, unknown>>(`/blocks/${id}`, content)
    if (result.success && result.data) return mapApiBlock(result.data, "")
    return null
  },

  async removeBlock(id: string): Promise<boolean> {
    const result = await NotionClient.delete(`/blocks/${id}`)
    return result.success
  },

  async getBlock(id: string): Promise<NotionBlock | null> {
    const result = await NotionClient.get<Record<string, unknown>>(`/blocks/${id}`)
    if (result.success && result.data) return mapApiBlock(result.data, "")
    return null
  },

  async listBlocks(pageId: string): Promise<NotionBlock[]> {
    return this.listChildren(pageId)
  },
}