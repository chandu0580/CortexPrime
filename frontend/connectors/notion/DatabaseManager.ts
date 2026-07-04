import { NotionDatabase, DatabaseProperty, DatabaseRow, PropertyType } from "./types"
import { NotionClient } from "./NotionClient"

function mapApiDb(api: Record<string, unknown>): NotionDatabase {
  const props = api.properties as Record<string, unknown> ?? {}
  return {
    id: String(api.id), workspaceId: "", parentPageId: (api.parent as Record<string, unknown>)?.page_id as string ?? null,
    title: String((api.title as Record<string, unknown>[])?.[0]?.plain_text ?? ""),
    description: "", icon: String((api.icon as Record<string, unknown>)?.emoji ?? ""),
    properties: Object.entries(props).map(([name, p]) => {
      const prop = p as Record<string, unknown>
      return { id: String(prop.id), databaseId: String(api.id), name, type: prop.type as PropertyType, options: [], required: false }
    }),
    rows: [], archived: Boolean(api.archived ?? false),
    createdAt: String(api.created_time ?? ""), updatedAt: String(api.last_edited_time ?? ""),
  }
}

function mapApiRow(api: Record<string, unknown>, databaseId: string): DatabaseRow {
  return { id: String(api.id), databaseId, properties: api.properties as Record<string, unknown> ?? {}, createdAt: String(api.created_time ?? ""), updatedAt: String(api.last_edited_time ?? "") }
}

export const DatabaseManager = {
  async createDatabase(parentPageId: string, title: string, properties: Record<string, Record<string, unknown>>): Promise<NotionDatabase | null> {
    const body = { parent: { page_id: parentPageId }, title: [{ type: "text", text: { content: title } }], properties }
    const result = await NotionClient.post<Record<string, unknown>>("/databases", body)
    if (result.success && result.data) return mapApiDb(result.data)
    return null
  },

  async updateDatabase(id: string, title: string, description?: string): Promise<NotionDatabase | null> {
    const body: Record<string, unknown> = { title: [{ type: "text", text: { content: title } }] }
    if (description) body.description = [{ type: "text", text: { content: description } }]
    const result = await NotionClient.patch<Record<string, unknown>>(`/databases/${id}`, body)
    if (result.success && result.data) return mapApiDb(result.data)
    return null
  },

  async archiveDatabase(id: string): Promise<NotionDatabase | null> {
    const result = await NotionClient.patch<Record<string, unknown>>(`/databases/${id}`, { archived: true })
    if (result.success && result.data) return mapApiDb(result.data)
    return null
  },

  async queryDatabase(id: string, filter?: Record<string, unknown>, sorts?: Record<string, unknown>[]): Promise<DatabaseRow[]> {
    const body: Record<string, unknown> = { page_size: 100 }
    if (filter) body.filter = filter
    if (sorts) body.sorts = sorts
    const result = await NotionClient.post<Record<string, unknown>>(`/databases/${id}/query`, body)
    if (result.success && result.data?.results) return (result.data.results as Record<string, unknown>[]).map((r) => mapApiRow(r, id))
    return []
  },

  async insertRow(databaseId: string, properties: Record<string, unknown>): Promise<DatabaseRow | null> {
    const result = await NotionClient.post<Record<string, unknown>>("/pages", { parent: { database_id: databaseId }, properties })
    if (result.success && result.data) return mapApiRow(result.data, databaseId)
    return null
  },

  async updateRow(pageId: string, properties: Record<string, unknown>): Promise<DatabaseRow | null> {
    const result = await NotionClient.patch<Record<string, unknown>>(`/pages/${pageId}`, { properties })
    if (result.success && result.data) return mapApiRow(result.data, "")
    return null
  },

  async addProperty(databaseId: string, name: string, type: PropertyType, options?: Record<string, unknown>): Promise<DatabaseProperty | null> {
    const body: Record<string, unknown> = { [name]: { type, [type]: options ?? {} } }
    const result = await NotionClient.patch<Record<string, unknown>>(`/databases/${databaseId}`, body)
    if (result.success && result.data) {
      const props = result.data.properties as Record<string, unknown> ?? {}
      const prop = props[name] as Record<string, unknown> ?? {}
      return { id: String(prop.id), databaseId, name, type: prop.type as PropertyType, options: (prop[prop.type as string] as Record<string, unknown>[])?.map((o) => String(o.name)) ?? [], required: false }
    }
    return null
  },
}