import { Catalog, CatalogItem } from "./types"
import { ServiceNowClient } from "./ServiceNowClient"

function mapApiCatalog(api: Record<string, unknown>): Catalog {
  return { id: String(api.sys_id), instanceId: "", name: String(api.title ?? api.name ?? ""), description: String(api.description ?? ""), items: [], createdAt: String(api.sys_created_on ?? ""), updatedAt: String(api.sys_updated_on ?? "") }
}

function mapApiCatalogItem(api: Record<string, unknown>, catalogId: string): CatalogItem {
  return {
    id: String(api.sys_id), catalogId, name: String(api.name ?? api.short_description ?? ""),
    shortDescription: String(api.short_description ?? ""), description: String(api.description ?? ""),
    category: String(api.category ?? ""), price: Number(api.price ?? 0), deliveryTime: String(api.delivery_time ?? ""),
    active: Boolean(api.active ?? true), orderGuide: api.order_guide as string ?? null,
    createdAt: String(api.sys_created_on ?? ""), updatedAt: String(api.sys_updated_on ?? ""),
  }
}

export const CatalogManager = {
  async createCatalog(name: string, description: string = ""): Promise<Catalog | null> {
    const result = await ServiceNowClient.post<Record<string, unknown>>("/table/sc_catalog", { title: name, description })
    if (result.success && result.data?.result) return mapApiCatalog(result.data.result as Record<string, unknown>)
    return null
  },

  async createCatalogItem(catalogId: string, name: string, shortDescription: string, description: string, category: string = "", price: number = 0, deliveryTime: string = ""): Promise<CatalogItem | null> {
    const body = { name, short_description: shortDescription, description, category, price, delivery_time: deliveryTime, sc_catalog: catalogId }
    const result = await ServiceNowClient.post<Record<string, unknown>>("/table/sc_cat_item", body)
    if (result.success && result.data?.result) return mapApiCatalogItem(result.data.result as Record<string, unknown>, catalogId)
    return null
  },

  async updateCatalogItem(id: string, updates: Record<string, unknown>): Promise<CatalogItem | null> {
    const result = await ServiceNowClient.patch<Record<string, unknown>>(`/table/sc_cat_item/${id}`, updates)
    if (result.success && result.data?.result) return mapApiCatalogItem(result.data.result as Record<string, unknown>, "")
    return null
  },

  async archiveCatalogItem(id: string): Promise<CatalogItem | null> {
    return this.updateCatalogItem(id, { active: false })
  },

  async listCatalogItems(catalogId: string): Promise<CatalogItem[]> {
    const result = await ServiceNowClient.get<Record<string, unknown>>(`/table/sc_cat_item?sysparm_query=sc_catalog=${catalogId}&sysparm_limit=100`)
    if (result.success && result.data?.result) return (result.data.result as Record<string, unknown>[]).map((i) => mapApiCatalogItem(i, catalogId))
    return []
  },

  async listCatalogs(): Promise<Catalog[]> {
    const result = await ServiceNowClient.get<Record<string, unknown>>("/table/sc_catalog?sysparm_limit=100")
    if (result.success && result.data?.result) return (result.data.result as Record<string, unknown>[]).map(mapApiCatalog)
    return []
  },
}