import { type SearchQuery, type SearchResult, SearchScope } from "./types"
import { NotionClient } from "./NotionClient"

const searchHistory: SearchQuery[] = []

export const SearchManager = {
  async searchPages(term: string, limit: number = 25, offset: number = 0): Promise<SearchResult[]> {
    const result = await NotionClient.post<Record<string, unknown>>("/search", { query: term, page_size: limit, start_cursor: offset > 0 ? String(offset) : undefined, filter: { value: "page", property: "object" } })
    return this.processResults(result, term)
  },

  async searchDatabases(term: string, limit: number = 25, offset: number = 0): Promise<SearchResult[]> {
    const result = await NotionClient.post<Record<string, unknown>>("/search", { query: term, page_size: limit, start_cursor: offset > 0 ? String(offset) : undefined, filter: { value: "database", property: "object" } })
    return this.processResults(result, term)
  },

  async searchBlocks(term: string, limit: number = 25, offset: number = 0): Promise<SearchResult[]> {
    const result = await NotionClient.post<Record<string, unknown>>("/search", { query: term, page_size: limit, start_cursor: offset > 0 ? String(offset) : undefined })
    return this.processResults(result, term)
  },

  processResults(result: { success: boolean; data: Record<string, unknown> | null }, term: string): SearchResult[] {
    const query: SearchQuery = { term, scope: SearchScope.ALL, limit: 25, offset: 0 }
    searchHistory.push(query); if (searchHistory.length > 10) searchHistory.shift()
    if (result.success && result.data?.results) {
      return (result.data.results as Record<string, unknown>[]).map((r) => ({
        id: String(r.id), type: (r.object as string === "database" ? "database" : "page") as SearchResult["type"],
        title: "", excerpt: "", workspaceId: "", score: 0, lastModified: String(r.last_edited_time ?? ""),
      }))
    }
    return []
  },

  async recentSearches(): Promise<SearchQuery[]> { return [...searchHistory] },
}