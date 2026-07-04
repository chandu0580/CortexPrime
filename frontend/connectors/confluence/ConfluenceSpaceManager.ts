import { type ConfluenceSpace, SpaceType } from "./types"
import { ConfluenceClient } from "./ConfluenceClient"

function mapApiSpace(api: Record<string, unknown>): ConfluenceSpace {
  return {
    id: String(api.id),
    key: String(api.key),
    name: String(api.name),
    description: String(((api.description as Record<string, unknown>)?.plain as Record<string, unknown>)?.value ?? (api.description as Record<string, unknown>)?.value ?? ""),
    type: (api.type as string ?? "global").toLowerCase() as SpaceType,
    homepageId: (api.homepage as string ?? api.homepageId) as string ?? null,
    pages: [], archived: Boolean(api.archived ?? api.status === "archived"),
    createdAt: String(api.createdAt ?? api.created_at ?? ""),
    updatedAt: String(api.updatedAt ?? api.updated_at ?? ""),
  }
}

export const ConfluenceSpaceManager = {
  async createSpace(key: string, name: string, description: string = "", type: SpaceType = SpaceType.GLOBAL): Promise<ConfluenceSpace> {
    const body: Record<string, unknown> = { key, name, description: { plain: { value: description, representation: "plain" } } }
    const result = await ConfluenceClient.post<Record<string, unknown>>("/spaces", body)
    if (result.success && result.data) return mapApiSpace(result.data)
    const now = new Date().toISOString()
    return { id: "", key, name, description, type, homepageId: null, pages: [], archived: false, createdAt: now, updatedAt: now }
  },

  async updateSpace(id: string, name: string, description: string): Promise<ConfluenceSpace | null> {
    const body: Record<string, unknown> = { name, description: { plain: { value: description, representation: "plain" } } }
    const result = await ConfluenceClient.put<Record<string, unknown>>(`/spaces/${id}`, body)
    if (result.success && result.data) return mapApiSpace(result.data)
    return null
  },

  async archiveSpace(id: string): Promise<ConfluenceSpace | null> {
    const result = await ConfluenceClient.delete(`/spaces/${id}`)
    if (result.success) return { id, key: "", name: "", description: "", type: "global" as SpaceType, homepageId: null, pages: [], archived: true, createdAt: "", updatedAt: "" }
    return null
  },

  async listSpaces(): Promise<ConfluenceSpace[]> {
    const result = await ConfluenceClient.get<Record<string, unknown>>("/spaces?limit=100")
    if (result.success && result.data?.results) return (result.data.results as Record<string, unknown>[]).map(mapApiSpace)
    return []
  },

  async getSpace(id: string): Promise<ConfluenceSpace | null> {
    const result = await ConfluenceClient.get<Record<string, unknown>>(`/spaces/${id}`)
    if (result.success && result.data) return mapApiSpace(result.data)
    return null
  },
}