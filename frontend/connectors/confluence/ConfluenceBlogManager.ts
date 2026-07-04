import { type ConfluenceBlogPost, PageStatus } from "./types"
import { ConfluenceClient } from "./ConfluenceClient"

function mapApiBlog(api: Record<string, unknown>, spaceId: string): ConfluenceBlogPost {
  const version = api.version as Record<string, unknown> ?? {}
  return {
    id: String(api.id), spaceId, title: String(api.title),
    body: String(((api.body as Record<string, unknown>)?.storage as Record<string, unknown>)?.value ?? ""),
    status: (api.status as string ?? "published").toLowerCase() as PageStatus,
    authorId: String((version.author as Record<string, unknown>)?.id ?? ""),
    labels: [], createdAt: String(api.createdAt ?? ""), updatedAt: String(api.updatedAt ?? ""),
    publishedAt: api.publishedAt as string ?? null,
  }
}

export const ConfluenceBlogManager = {
  async createBlogPost(spaceId: string, title: string, body: string): Promise<ConfluenceBlogPost> {
    const result = await ConfluenceClient.post<Record<string, unknown>>("/blogposts", { spaceId, title, body: { representation: "storage", value: body }, status: "draft" })
    if (result.success && result.data) return mapApiBlog(result.data, spaceId)
    const now = new Date().toISOString()
    return { id: "", spaceId, title, body, status: PageStatus.DRAFT, authorId: "", labels: [], createdAt: now, updatedAt: now, publishedAt: null }
  },

  async publishBlogPost(id: string, title: string, body: string, version: number): Promise<ConfluenceBlogPost | null> {
    const result = await ConfluenceClient.put<Record<string, unknown>>(`/blogposts/${id}`, { id, title, body: { representation: "storage", value: body }, version: { number: version + 1, message: "Publish" }, status: "published" })
    if (result.success && result.data) return mapApiBlog(result.data, "")
    return null
  },

  async archiveBlogPost(id: string): Promise<ConfluenceBlogPost | null> {
    const result = await ConfluenceClient.put<Record<string, unknown>>(`/blogposts/${id}`, { status: "archived", version: { number: 1, message: "Archive" } })
    if (result.success && result.data) return mapApiBlog(result.data, "")
    return null
  },

  async listBlogPosts(spaceId: string): Promise<ConfluenceBlogPost[]> {
    const result = await ConfluenceClient.get<Record<string, unknown>>(`/spaces/${spaceId}/blogposts?limit=100`)
    if (result.success && result.data?.results) return (result.data.results as Record<string, unknown>[]).map((b) => mapApiBlog(b, spaceId))
    return []
  },
}