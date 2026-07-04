import { type ConfluencePage, type ConfluencePageVersion, type ConfluenceLabel, PageStatus } from "./types"
import { ConfluenceClient } from "./ConfluenceClient"

function mapApiPage(api: Record<string, unknown>, spaceId: string): ConfluencePage {
  const version = api.version as Record<string, unknown> ?? {}
  return {
    id: String(api.id),
    spaceId,
    parentId: (api.parentId as string) ?? null,
    title: String(api.title),
    body: String(((api.body as Record<string, unknown>)?.storage as Record<string, unknown>)?.value ?? (api.body as Record<string, unknown>)?.value ?? ""),
    status: (api.status as string ?? "published").toLowerCase() as PageStatus,
    version: Number(version.number ?? 1),
    authorId: String((version.author as Record<string, unknown>)?.id ?? (api.authorId as string) ?? ""),
    labels: [], restrictions: [],
    createdAt: String(api.createdAt ?? api.created_at ?? version.createdAt ?? ""),
    updatedAt: String(api.updatedAt ?? api.updated_at ?? version.updatedAt ?? ""),
    publishedAt: api.publishedAt as string ?? null,
  }
}

export const ConfluencePageManager = {
  async createPage(spaceId: string, title: string, body: string, parentId: string | null = null): Promise<ConfluencePage> {
    const content: Record<string, unknown> = { spaceId, title, body: { representation: "storage", value: body }, status: "draft" }
    if (parentId) content.parentId = parentId
    const result = await ConfluenceClient.post<Record<string, unknown>>("/pages", content)
    if (result.success && result.data) return mapApiPage(result.data, spaceId)
    const now = new Date().toISOString()
    return { id: "", spaceId, parentId, title, body, status: PageStatus.DRAFT, version: 1, authorId: "", labels: [], restrictions: [], createdAt: now, updatedAt: now, publishedAt: null }
  },

  async updatePage(id: string, title: string, body: string, version: number): Promise<ConfluencePage | null> {
    const result = await ConfluenceClient.put<Record<string, unknown>>(`/pages/${id}`, { id, title, body: { representation: "storage", value: body }, version: { number: version + 1, message: `Version ${version + 1}` } })
    if (result.success && result.data) return mapApiPage(result.data, "")
    return null
  },

  async publishPage(id: string, title: string, body: string, version: number): Promise<ConfluencePage | null> {
    return this.updatePage(id, title, body, version)
  },

  async archivePage(id: string): Promise<ConfluencePage | null> {
    const result = await ConfluenceClient.put<Record<string, unknown>>(`/pages/${id}`, { status: "archived", version: { number: 1, message: "Archive" } })
    if (result.success && result.data) return mapApiPage(result.data, "")
    return null
  },

  async restorePage(id: string, title: string, body: string, version: number): Promise<ConfluencePage | null> {
    return this.updatePage(id, title, body, version)
  },

  async getPage(id: string): Promise<ConfluencePage | null> {
    const result = await ConfluenceClient.get<Record<string, unknown>>(`/pages/${id}?body-format=storage`)
    if (result.success && result.data) return mapApiPage(result.data, String((result.data as Record<string, unknown>).spaceId ?? ""))
    return null
  },

  async listPages(spaceId: string): Promise<ConfluencePage[]> {
    const result = await ConfluenceClient.get<Record<string, unknown>>(`/spaces/${spaceId}/pages?limit=100`)
    if (result.success && result.data?.results) return (result.data.results as Record<string, unknown>[]).map((p) => mapApiPage(p, spaceId))
    return []
  },

  async getVersions(pageId: string): Promise<ConfluencePageVersion[]> {
    const result = await ConfluenceClient.get<Record<string, unknown>>(`/pages/${pageId}/versions?limit=100`)
    if (result.success && result.data?.results) {
      return (result.data.results as Record<string, unknown>[]).map((v) => ({
        id: String(v.id), pageId, version: Number(v.number), title: "", body: "", authorId: String((v.author as Record<string, unknown>)?.id ?? ""), message: String(v.message ?? ""), createdAt: String(v.createdAt ?? ""),
      }))
    }
    return []
  },
}