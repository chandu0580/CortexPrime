import { JiraVersion } from "./types"
import { JiraClient } from "./JiraClient"

function mapApiVersion(api: Record<string, unknown>, projectId: string): JiraVersion {
  return {
    id: String(api.id),
    projectId,
    name: String(api.name),
    description: String(api.description ?? ""),
    released: Boolean(api.released),
    releaseDate: api.releaseDate as string ?? null,
    archived: Boolean(api.archived),
    createdAt: String(api.createdAt ?? api.created_at ?? new Date().toISOString()),
  }
}

export const JiraReleaseManager = {
  async createVersion(projectKey: string, name: string, description: string = ""): Promise<JiraVersion> {
    const result = await JiraClient.post<Record<string, unknown>>("/rest/api/3/version", { project: projectKey, name, description })
    if (result.success && result.data) return mapApiVersion(result.data, projectKey)
    const now = new Date().toISOString()
    return { id: "", projectId: projectKey, name, description, released: false, releaseDate: null, archived: false, createdAt: now }
  },

  async releaseVersion(versionId: string, releaseDate?: string): Promise<JiraVersion | null> {
    const body: Record<string, unknown> = { released: true }
    if (releaseDate) body.releaseDate = releaseDate
    const result = await JiraClient.put<Record<string, unknown>>(`/rest/api/3/version/${versionId}`, body)
    if (result.success && result.data) return mapApiVersion(result.data, String(result.data.project ?? ""))
    return null
  },

  async archiveVersion(versionId: string): Promise<JiraVersion | null> {
    const result = await JiraClient.put<Record<string, unknown>>(`/rest/api/3/version/${versionId}`, { archived: true })
    if (result.success && result.data) return mapApiVersion(result.data, String(result.data.project ?? ""))
    return null
  },

  async listVersions(projectKey: string): Promise<JiraVersion[]> {
    const result = await JiraClient.get<Record<string, unknown>>(`/rest/api/3/project/${projectKey}/versions?maxResults=100`)
    if (result.success && result.data) {
      const items = Array.isArray(result.data) ? result.data as Record<string, unknown>[] : (result.data as Record<string, unknown>).values as Record<string, unknown>[]
      return (items ?? []).map((v) => mapApiVersion(v, projectKey))
    }
    return []
  },

  async getVersion(versionId: string): Promise<JiraVersion | null> {
    const result = await JiraClient.get<Record<string, unknown>>(`/rest/api/3/version/${versionId}`)
    if (result.success && result.data) return mapApiVersion(result.data, String(result.data.project ?? ""))
    return null
  },
}