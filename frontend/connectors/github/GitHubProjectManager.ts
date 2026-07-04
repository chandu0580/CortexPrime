import { GitHubProject, GitHubColumn, GitHubCard } from "./types"
import { GitHubClient } from "./GitHubClient"

function mapApiProject(apiProject: Record<string, unknown>, repositoryId: string): GitHubProject {
  return {
    id: String(apiProject.id),
    repositoryId,
    name: String(apiProject.name),
    body: String(apiProject.body ?? ""),
    state: (apiProject.state as GitHubProject["state"]) ?? "open",
    columns: [],
    createdAt: String(apiProject.created_at),
    updatedAt: String(apiProject.updated_at),
  }
}

export const GitHubProjectManager = {
  async createProject(owner: string, repo: string, name: string, body: string): Promise<GitHubProject | null> {
    const result = await GitHubClient.post<Record<string, unknown>>(`/repos/${owner}/${repo}/projects`, { name, body })
    if (result.success && result.data) return mapApiProject(result.data, `${owner}/${repo}`)
    return null
  },

  async listProjects(owner: string, repo: string): Promise<GitHubProject[]> {
    const result = await GitHubClient.get<Record<string, unknown>[]>(`/repos/${owner}/${repo}/projects?per_page=100`)
    if (result.success && result.data) return result.data.map((p) => mapApiProject(p, `${owner}/${repo}`))
    return []
  },

  async getProject(owner: string, repo: string, projectId: string): Promise<GitHubProject | null> {
    const result = await GitHubClient.get<Record<string, unknown>>(`/projects/${projectId}`)
    if (result.success && result.data) return mapApiProject(result.data, `${owner}/${repo}`)
    return null
  },

  async createColumn(projectId: string, name: string): Promise<GitHubColumn | null> {
    const result = await GitHubClient.post<Record<string, unknown>>(`/projects/${projectId}/columns`, { name })
    if (result.success && result.data) {
      return { id: String(result.data.id), projectId, name: String(result.data.name), cards: [], createdAt: String(result.data.created_at) }
    }
    return null
  },

  async moveCard(columnId: string, contentId: string, contentType: string = "Issue", position: string = "bottom"): Promise<GitHubCard | null> {
    const result = await GitHubClient.post<Record<string, unknown>>(`/projects/columns/${columnId}/cards`, { content_id: parseInt(contentId, 10), content_type: contentType })
    if (result.success && result.data) {
      return { id: String(result.data.id), columnId, contentId: String(result.data.content_id), contentType: String(result.data.content_type), note: result.data.note as string ?? null, position: 0, archived: Boolean(result.data.archived), createdAt: String(result.data.created_at) }
    }
    return null
  },

  async listColumns(projectId: string): Promise<GitHubColumn[]> {
    const result = await GitHubClient.get<Record<string, unknown>[]>(`/projects/${projectId}/columns?per_page=100`)
    if (result.success && result.data) return result.data.map((c) => ({ id: String(c.id), projectId, name: String(c.name), cards: [], createdAt: String(c.created_at) }))
    return []
  },
}