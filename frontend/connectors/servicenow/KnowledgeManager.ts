import { KnowledgeArticle, KnowledgeCategory } from "./types"
import { ServiceNowClient } from "./ServiceNowClient"

function mapApiArticle(api: Record<string, unknown>): KnowledgeArticle {
  return {
    id: String(api.sys_id), instanceId: "", title: String(api.short_description ?? api.title ?? ""),
    text: String(api.text ?? ""), categoryId: String(api.kb_category ?? ""),
    keywords: ((api.keywords as string) ?? "").split(",").map((k) => k.trim()).filter(Boolean),
    status: (api.workflow_state as string ?? "draft").toLowerCase() as KnowledgeArticle["status"],
    author: String((api.sys_created_by as string) ?? ""), reviewer: null,
    publishedAt: api.publish_date as string ?? null, createdAt: String(api.sys_created_on ?? ""), updatedAt: String(api.sys_updated_on ?? ""),
  }
}

export const KnowledgeManager = {
  async createKnowledgeArticle(title: string, text: string, categoryId: string, author: string, keywords: string[] = []): Promise<KnowledgeArticle | null> {
    const body = { short_description: title, text, kb_category: categoryId, sys_created_by: author, keywords: keywords.join(",") }
    const result = await ServiceNowClient.post<Record<string, unknown>>("/table/kb_knowledge", body)
    if (result.success && result.data?.result) return mapApiArticle(result.data.result as Record<string, unknown>)
    return null
  },

  async updateKnowledgeArticle(id: string, title: string, text: string, keywords: string[]): Promise<KnowledgeArticle | null> {
    const result = await ServiceNowClient.patch<Record<string, unknown>>(`/table/kb_knowledge/${id}`, { short_description: title, text, keywords: keywords.join(",") })
    if (result.success && result.data?.result) return mapApiArticle(result.data.result as Record<string, unknown>)
    return null
  },

  async archiveKnowledgeArticle(id: string): Promise<KnowledgeArticle | null> {
    const result = await ServiceNowClient.patch<Record<string, unknown>>(`/table/kb_knowledge/${id}`, { workflow_state: "archived" })
    if (result.success && result.data?.result) return mapApiArticle(result.data.result as Record<string, unknown>)
    return null
  },

  async listKnowledgeArticles(): Promise<KnowledgeArticle[]> {
    const result = await ServiceNowClient.get<Record<string, unknown>>("/table/kb_knowledge?sysparm_limit=100")
    if (result.success && result.data?.result) return (result.data.result as Record<string, unknown>[]).map(mapApiArticle)
    return []
  },

  async createCategory(name: string, description: string = ""): Promise<KnowledgeCategory | null> {
    const body = { title: name, description }
    const result = await ServiceNowClient.post<Record<string, unknown>>("/table/kb_category", body)
    if (result.success && result.data?.result) {
      const r = result.data.result as Record<string, unknown>
      return { id: String(r.sys_id), instanceId: "", name: String(r.title ?? ""), description: String(r.description ?? ""), parentId: null, articles: [], createdAt: String(r.sys_created_on ?? "") }
    }
    return null
  },
}