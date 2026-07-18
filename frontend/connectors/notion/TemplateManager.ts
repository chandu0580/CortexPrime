import { NotionTemplate } from "./types"
import { NotionClient } from "./NotionClient"

export const TemplateManager = {
  async createTemplate(workspaceId: string, name: string, description: string, content: Record<string, unknown> = {}, category: string = ""): Promise<NotionTemplate> {
    const now = new Date().toISOString()
    const tpl: NotionTemplate = { id: `${Date.now()}`, workspaceId, name, description, content, category, createdAt: now, updatedAt: now }
    return tpl
  },

  async updateTemplate(id: string, name: string, description: string, content: Record<string, unknown>, category: string): Promise<NotionTemplate | null> {
    const tpl = await this.getTemplate(id)
    if (!tpl) return null
    const updated = { ...tpl, name, description, content, category, updatedAt: new Date().toISOString() }
    return updated
  },

  async getTemplate(id: string): Promise<NotionTemplate | null> {
    const result = await NotionClient.get<Record<string, unknown>>(`/blocks/${id}`)
    if (result.success && result.data) {
      return { id: String(result.data.id), workspaceId: "", name: String((result.data as Record<string, unknown>).type ?? ""), description: "", content: result.data[String((result.data as Record<string, unknown>).type ?? "")] as Record<string, unknown> ?? {}, category: "", createdAt: String(result.data.created_time ?? ""), updatedAt: String(result.data.last_edited_time ?? "") }
    }
    return null
  },

  async listTemplates(workspaceId: string): Promise<NotionTemplate[]> {
    const result = await NotionClient.post<Record<string, unknown>>("/search", { filter: { value: "page", property: "object" }, page_size: 100 })
    if (result.success && result.data?.results) {
      return (result.data.results as Record<string, unknown>[]).map((r) => ({
        id: String(r.id), workspaceId, name: String(r.type ?? ""), description: "", content: r[String(r.type ?? "")] as Record<string, unknown> ?? {}, category: "", createdAt: String(r.created_time ?? ""), updatedAt: String(r.last_edited_time ?? ""),
      }))
    }
    return []
  },
}