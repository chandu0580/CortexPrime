import { ConfluenceTemplate } from "./types"
import { ConfluenceClient } from "./ConfluenceClient"

function mapApiTemplate(api: Record<string, unknown>, spaceId: string): ConfluenceTemplate {
  return {
    id: String(api.id), spaceId, name: String(api.name), description: String(api.description ?? ""),
    body: String(((api.body as Record<string, unknown>)?.storage as Record<string, unknown>)?.value ?? ""),
    category: String(api.category ?? ""), createdAt: String(api.createdAt ?? ""), updatedAt: String(api.updatedAt ?? ""),
  }
}

export const ConfluenceTemplateManager = {
  async createTemplate(spaceId: string, name: string, description: string, body: string, category: string = ""): Promise<ConfluenceTemplate> {
    const payload = { spaceId, name, description, body: { representation: "storage", value: body }, category }
    const result = await ConfluenceClient.post<Record<string, unknown>>("/templates", payload)
    if (result.success && result.data) return mapApiTemplate(result.data, spaceId)
    const now = new Date().toISOString()
    return { id: "", spaceId, name, description, body, category, createdAt: now, updatedAt: now }
  },

  async updateTemplate(id: string, spaceId: string, name: string, description: string, body: string, category: string = ""): Promise<ConfluenceTemplate | null> {
    const result = await ConfluenceClient.put<Record<string, unknown>>(`/templates/${id}`, { spaceId, name, description, body: { representation: "storage", value: body }, category })
    if (result.success && result.data) return mapApiTemplate(result.data, spaceId)
    return null
  },

  async listTemplates(spaceId: string): Promise<ConfluenceTemplate[]> {
    const result = await ConfluenceClient.get<Record<string, unknown>>(`/spaces/${spaceId}/templates?limit=100`)
    if (result.success && result.data?.results) return (result.data.results as Record<string, unknown>[]).map((t) => mapApiTemplate(t, spaceId))
    return []
  },
}