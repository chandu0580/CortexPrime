import { type SearchQuery, type SearchResult, SearchScope } from "./types"
import { ConfluenceClient } from "./ConfluenceClient"

const searchHistory: SearchQuery[] = []

function mapSearchResult(api: Record<string, unknown>): SearchResult {
  return {
    id: String(api.id), type: (api.type as string ?? "page") as SearchResult["type"],
    title: String(api.title), excerpt: String(api.excerpt ?? api.body ?? ""),
    url: String((api._links as Record<string, unknown>)?.webui ?? api.url ?? ""), spaceKey: String(api.spaceKey ?? (api.space as Record<string, unknown>)?.key ?? ""),
    score: Number(api.score ?? 0), lastModified: String(api.lastModified ?? api.updatedAt ?? ""),
  }
}

export const ConfluenceSearchManager = {
  async searchPages(term: string, spaceId: string | null = null, limit: number = 25, offset: number = 0): Promise<SearchResult[]> {
    let cql = `type=page AND text~"${term.replace(/"/g, '\\"')}"`
    if (spaceId) cql += ` AND space=${spaceId}`
    return this.searchCql(cql, limit, offset)
  },

  async searchSpaces(term: string, limit: number = 25, offset: number = 0): Promise<SearchResult[]> {
    const cql = `type=space AND text~"${term.replace(/"/g, '\\"')}"`
    return this.searchCql(cql, limit, offset)
  },

  async searchAttachments(term: string, spaceId: string | null = null, limit: number = 25, offset: number = 0): Promise<SearchResult[]> {
    let cql = `type=attachment AND text~"${term.replace(/"/g, '\\"')}"`
    if (spaceId) cql += ` AND space=${spaceId}`
    return this.searchCql(cql, limit, offset)
  },

  async searchCql(cql: string, limit: number = 25, offset: number = 0): Promise<SearchResult[]> {
    const query: SearchQuery = { term: cql, scope: SearchScope.ALL, spaceId: null, label: null, limit, offset }
    searchHistory.push(query); if (searchHistory.length > 10) searchHistory.shift()

    const encoded = encodeURIComponent(cql)
    const result = await ConfluenceClient.get<Record<string, unknown>>(`/search?cql=${encoded}&limit=${limit}&start=${offset}`)
    if (result.success && result.data?.results) return (result.data.results as Record<string, unknown>[]).map(mapSearchResult)
    return []
  },

  async recentSearches(): Promise<SearchQuery[]> {
    return [...searchHistory]
  },
}