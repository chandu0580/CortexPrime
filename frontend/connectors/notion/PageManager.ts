import { type NotionPage, PageStatus } from "./types"
import { NotionClient } from "./NotionClient"

function mapApiPage(api: Record<string, unknown>): NotionPage {
  const props = api.properties as Record<string, unknown> ?? {}
  const titleProp = Object.values(props).find((p: unknown) => (p as Record<string, unknown>)?.type === "title") as Record<string, unknown>
  const title = (titleProp?.title as Record<string, unknown>[])?.[0]?.plain_text as string ?? ""
  return {
    id: String(api.id), workspaceId: "", parentId: (api.parent as Record<string, unknown>)?.page_id as string ?? null,
    title, icon: String((api.icon as Record<string, unknown>)?.emoji ?? ((api.icon as Record<string, unknown>)?.external as Record<string, unknown>)?.url ?? ""),
    cover: String(((api.cover as Record<string, unknown>)?.external as Record<string, unknown>)?.url ?? ((api.cover as Record<string, unknown>)?.file as Record<string, unknown>)?.url ?? ""),
    status: (api.archived ? PageStatus.ARCHIVED : PageStatus.PUBLISHED),
    blocks: [], properties: props,
    createdAt: String(api.created_time ?? ""), updatedAt: String(api.last_edited_time ?? ""),
    archivedAt: api.archived ? String(api.last_edited_time ?? "") : null,
  }
}

export const PageManager = {
  async createPage(parentPageId: string, title: string): Promise<NotionPage | null> {
    const body = { parent: { page_id: parentPageId }, properties: { title: { title: [{ text: { content: title } }] } } }
    const result = await NotionClient.post<Record<string, unknown>>("/pages", body)
    if (result.success && result.data) return mapApiPage(result.data)
    return null
  },

  async updatePage(id: string, title: string): Promise<NotionPage | null> {
    const result = await NotionClient.patch<Record<string, unknown>>(`/pages/${id}`, { properties: { title: { title: [{ text: { content: title } }] } } })
    if (result.success && result.data) return mapApiPage(result.data)
    return null
  },

  async archivePage(id: string): Promise<NotionPage | null> {
    const result = await NotionClient.patch<Record<string, unknown>>(`/pages/${id}`, { archived: true })
    if (result.success && result.data) return mapApiPage(result.data)
    return null
  },

  async restorePage(id: string): Promise<NotionPage | null> {
    const result = await NotionClient.patch<Record<string, unknown>>(`/pages/${id}`, { archived: false })
    if (result.success && result.data) return mapApiPage(result.data)
    return null
  },

  async getPage(id: string): Promise<NotionPage | null> {
    const result = await NotionClient.get<Record<string, unknown>>(`/pages/${id}`)
    if (result.success && result.data) return mapApiPage(result.data)
    return null
  },

  async listPages(databaseId?: string): Promise<NotionPage[]> {
    if (databaseId) {
      const result = await NotionClient.post<Record<string, unknown>>(`/databases/${databaseId}/query`, { page_size: 100 })
      if (result.success && result.data?.results) return (result.data.results as Record<string, unknown>[]).map(mapApiPage)
    }
    const result = await NotionClient.post<Record<string, unknown>>("/search", { filter: { value: "page", property: "object" }, page_size: 100 })
    if (result.success && result.data?.results) return (result.data.results as Record<string, unknown>[]).map(mapApiPage)
    return []
  },
}