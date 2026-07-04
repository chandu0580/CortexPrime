import { NotionTemplate } from "./types"

const templates: NotionTemplate[] = []

export const TemplateManager = {
  async createTemplate(workspaceId: string, name: string, description: string, content: Record<string, unknown> = {}, category: string = ""): Promise<NotionTemplate> {
    const now = new Date().toISOString()
    const tpl: NotionTemplate = { id: name, workspaceId, name, description, content, category, createdAt: now, updatedAt: now }
    templates.push(tpl)
    return tpl
  },

  async updateTemplate(id: string, name: string, description: string, content: Record<string, unknown>, category: string): Promise<NotionTemplate | null> {
    const tpl = templates.find((t) => t.id === id)
    if (!tpl) return null
    Object.assign(tpl, { name, description, content, category, updatedAt: new Date().toISOString() })
    return { ...tpl }
  },

  async listTemplates(workspaceId: string): Promise<NotionTemplate[]> {
    return templates.filter((t) => t.workspaceId === workspaceId)
  },
}