import { GitHubRepository, RepositoryVisibility } from "./types"
import { GitHubClient } from "./GitHubClient"

function mapApiRepo(apiRepo: Record<string, unknown>): GitHubRepository {
  return {
    id: String(apiRepo.id),
    owner: (apiRepo.owner as Record<string, unknown>)?.login as string ?? "",
    name: String(apiRepo.name),
    fullName: String(apiRepo.full_name),
    description: String(apiRepo.description ?? ""),
    visibility: (apiRepo.visibility as RepositoryVisibility) ?? "public",
    defaultBranch: String(apiRepo.default_branch ?? "main"),
    topics: (apiRepo.topics as string[]) ?? [],
    archived: Boolean(apiRepo.archived),
    forked: Boolean(apiRepo.fork),
    createdAt: String(apiRepo.created_at),
    updatedAt: String(apiRepo.updated_at),
  }
}

export const GitHubRepositoryManager = {
  async createRepository(
    owner: string,
    name: string,
    description: string,
    visibility: RepositoryVisibility,
    defaultBranch = "main",
    topics: string[] = [],
  ): Promise<GitHubRepository> {
    const result = await GitHubClient.post<Record<string, unknown>>("/user/repos", {
      name, description, private: visibility === "private", auto_init: true, ...(topics.length > 0 && { topics }),
    })
    if (result.success && result.data) return mapApiRepo(result.data)
    const now = new Date().toISOString()
    return { id: "", owner, name, fullName: `${owner}/${name}`, description, visibility, defaultBranch, topics, archived: false, forked: false, createdAt: now, updatedAt: now }
  },

  async archiveRepository(owner: string, repo: string): Promise<GitHubRepository | null> {
    const result = await GitHubClient.patch<Record<string, unknown>>(`/repos/${owner}/${repo}`, { archived: true })
    if (result.success && result.data) return mapApiRepo(result.data)
    return null
  },

  async forkRepository(owner: string, repo: string, newOwner?: string, newName?: string): Promise<GitHubRepository | null> {
    const body: Record<string, unknown> = {}
    if (newOwner) body.organization = newOwner
    if (newName) body.name = newName
    const result = await GitHubClient.post<Record<string, unknown>>(`/repos/${owner}/${repo}/forks`, body)
    if (result.success && result.data) return mapApiRepo(result.data)
    return null
  },

  async listRepositories(owner?: string): Promise<GitHubRepository[]> {
    const path = owner ? `/orgs/${owner}/repos?per_page=100` : "/user/repos?per_page=100&type=all"
    const result = await GitHubClient.get<Record<string, unknown>[]>(path)
    if (result.success && result.data) return result.data.map(mapApiRepo)
    return []
  },

  async getRepository(owner: string, repo: string): Promise<GitHubRepository | null> {
    const result = await GitHubClient.get<Record<string, unknown>>(`/repos/${owner}/${repo}`)
    if (result.success && result.data) return mapApiRepo(result.data)
    return null
  },

  async updateRepository(owner: string, repo: string, updates: Partial<GitHubRepository>): Promise<GitHubRepository | null> {
    const body: Record<string, unknown> = {}
    if (updates.description !== undefined) body.description = updates.description
    if (updates.visibility !== undefined) body.private = updates.visibility === "private"
    if (updates.defaultBranch !== undefined) body.default_branch = updates.defaultBranch
    if (updates.topics !== undefined) body.topics = updates.topics
    const result = await GitHubClient.patch<Record<string, unknown>>(`/repos/${owner}/${repo}`, body)
    if (result.success && result.data) return mapApiRepo(result.data)
    return null
  },
}