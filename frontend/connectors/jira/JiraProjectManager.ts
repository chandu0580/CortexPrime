import { JiraProject, JiraComponent, JiraVersion } from "./types"
import { JiraClient } from "./JiraClient"

function mapApiProject(api: Record<string, unknown>): JiraProject {
  const lead = api.lead as Record<string, unknown> ?? {}
  return {
    id: String(api.id),
    key: String(api.key),
    name: String(api.name),
    description: String(api.description ?? api.name ?? ""),
    lead: String(lead.displayName ?? lead.name ?? ""),
    url: String(api.self ?? ""),
    avatarUrl: ((api.avatarUrls as Record<string, unknown>)?.square48 as string) ?? "",
    archived: Boolean(api.archived),
    components: (api.components as Record<string, unknown>[] ?? []).map((c) => ({ id: String(c.id), projectId: String(api.id), name: String(c.name), description: String(c.description ?? ""), lead: (c.lead as Record<string, unknown>)?.displayName as string ?? null, assigneeType: String(c.assigneeType ?? ""), createdAt: "" })),
    versions: (api.versions as Record<string, unknown>[] ?? []).map((v) => ({ id: String(v.id), projectId: String(api.id), name: String(v.name), description: String(v.description ?? ""), released: Boolean(v.released), releaseDate: v.releaseDate as string ?? null, archived: Boolean(v.archived), createdAt: "" })),
    createdAt: String(api.createdAt ?? api.created_at ?? new Date().toISOString()),
    updatedAt: String(api.updatedAt ?? api.updated_at ?? new Date().toISOString()),
  }
}

export const JiraProjectManager = {
  async createProject(key: string, name: string, description: string, lead: string): Promise<JiraProject> {
    const result = await JiraClient.post<Record<string, unknown>>("/rest/api/3/project", { key, name, description, leadAccountId: lead, projectTypeKey: "software" })
    if (result.success && result.data) return mapApiProject(result.data)
    const now = new Date().toISOString()
    return { id: "", key, name, description, lead, url: "", avatarUrl: "", archived: false, components: [], versions: [], createdAt: now, updatedAt: now }
  },

  async updateProject(projectKey: string, updates: Partial<JiraProject>): Promise<JiraProject | null> {
    const body: Record<string, unknown> = {}
    if (updates.name) body.name = updates.name
    if (updates.description !== undefined) body.description = updates.description
    if (updates.lead) body.leadAccountId = updates.lead
    const result = await JiraClient.put<Record<string, unknown>>(`/rest/api/3/project/${projectKey}`, body)
    if (result.success && result.data) return mapApiProject(result.data)
    return null
  },

  async archiveProject(projectKey: string): Promise<JiraProject | null> {
    const result = await JiraClient.post<Record<string, unknown>>(`/rest/api/3/project/${projectKey}/archive`, {})
    if (result.success) return this.getProject(projectKey)
    return null
  },

  async listProjects(): Promise<JiraProject[]> {
    const result = await JiraClient.get<Record<string, unknown>>("/rest/api/3/project?expand=description,lead,url,avatarUrls,insight")
    if (result.success && result.data) {
      const values = (result.data as Record<string, unknown>).values as Record<string, unknown>[] ?? result.data as unknown as Record<string, unknown>[]
      const items = Array.isArray(result.data) ? result.data as Record<string, unknown>[] : values ?? []
      return items.map(mapApiProject)
    }
    return []
  },

  async getProject(projectKey: string): Promise<JiraProject | null> {
    const result = await JiraClient.get<Record<string, unknown>>(`/rest/api/3/project/${projectKey}?expand=description,lead,url,avatarUrls,insight`)
    if (result.success && result.data) return mapApiProject(result.data)
    return null
  },
}