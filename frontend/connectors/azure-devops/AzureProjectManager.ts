import { RepositoryVisibility, type AzureProject } from "./types"
import { AzureDevOpsClient } from "./AzureDevOpsClient"

function mapApiProject(api: Record<string, unknown>): AzureProject {
  return {
    id: String(api.id), organizationId: "",
    name: String(api.name), description: String(api.description ?? ""),
    visibility: (api.visibility as string ?? "private").toLowerCase() as RepositoryVisibility,
    teams: [], archived: Boolean(api.status === "deleting" || api.status === "deleted"),
    createdAt: String(api.createdAt ?? ""), updatedAt: String(api.updatedAt ?? ""),
  }
}

export const AzureProjectManager = {
  async createProject(name: string, description: string = "", visibility: RepositoryVisibility = RepositoryVisibility.PRIVATE): Promise<AzureProject | null> {
    const capabilities: Record<string, unknown> = { versioncontrol: { sourceControlType: "Git" }, processTemplate: { templateTypeId: "adcc42ab-9882-485e-a3ed-7678f01f66bc" } }
    const result = await AzureDevOpsClient.post<Record<string, unknown>>("/_apis/projects", { name, description, visibility: visibility.toUpperCase(), capabilities })
    if (result.success && result.data) return mapApiProject(result.data)
    return null
  },

  async updateProject(id: string, name: string, description: string): Promise<AzureProject | null> {
    const result = await AzureDevOpsClient.patch<Record<string, unknown>>(`/_apis/projects/${id}`, { name, description })
    if (result.success && result.data) return mapApiProject(result.data)
    return null
  },

  async archiveProject(id: string): Promise<AzureProject | null> {
    const result = await AzureDevOpsClient.delete(`/_apis/projects/${id}`)
    if (result.success) return null
    return null
  },

  async listProjects(): Promise<AzureProject[]> {
    const result = await AzureDevOpsClient.get<Record<string, unknown>>("/_apis/projects?$top=100")
    if (result.success && result.data?.value) return (result.data.value as Record<string, unknown>[]).map(mapApiProject)
    return []
  },

  async getProject(id: string): Promise<AzureProject | null> {
    const result = await AzureDevOpsClient.get<Record<string, unknown>>(`/_apis/projects/${id}`)
    if (result.success && result.data) return mapApiProject(result.data)
    return null
  },
}