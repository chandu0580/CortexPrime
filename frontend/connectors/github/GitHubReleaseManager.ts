import { GitHubRelease } from "./types"
import { GitHubClient } from "./GitHubClient"

function mapApiRelease(apiRelease: Record<string, unknown>, repositoryId: string): GitHubRelease {
  return {
    id: String(apiRelease.id),
    repositoryId,
    tagName: String(apiRelease.tag_name),
    targetCommitish: String(apiRelease.target_commitish),
    name: String(apiRelease.name ?? ""),
    body: String(apiRelease.body ?? ""),
    draft: Boolean(apiRelease.draft),
    prerelease: Boolean(apiRelease.prerelease),
    published: Boolean(apiRelease.published_at),
    author: (apiRelease.author as Record<string, unknown>)?.login as string ?? "",
    createdAt: String(apiRelease.created_at),
    publishedAt: apiRelease.published_at as string ?? null,
  }
}

export const GitHubReleaseManager = {
  async createRelease(
    owner: string, repo: string,
    tagName: string, targetCommitish: string,
    name: string, body: string,
    draft = false, prerelease = false,
  ): Promise<GitHubRelease> {
    const result = await GitHubClient.post<Record<string, unknown>>(`/repos/${owner}/${repo}/releases`, {
      tag_name: tagName, target_commitish: targetCommitish, name, body, draft, prerelease,
    })
    if (result.success && result.data) return mapApiRelease(result.data, `${owner}/${repo}`)
    const now = new Date().toISOString()
    return { id: "", repositoryId: `${owner}/${repo}`, tagName, targetCommitish, name, body, draft, prerelease, published: false, author: "", createdAt: now, publishedAt: null }
  },

  async publishRelease(owner: string, repo: string, releaseId: string): Promise<GitHubRelease | null> {
    const result = await GitHubClient.patch<Record<string, unknown>>(`/repos/${owner}/${repo}/releases/${releaseId}`, { draft: false })
    if (result.success && result.data) return mapApiRelease(result.data, `${owner}/${repo}`)
    return null
  },

  async archiveRelease(owner: string, repo: string, releaseId: string): Promise<GitHubRelease | null> {
    const result = await GitHubClient.patch<Record<string, unknown>>(`/repos/${owner}/${repo}/releases/${releaseId}`, { draft: true })
    if (result.success && result.data) return mapApiRelease(result.data, `${owner}/${repo}`)
    return null
  },

  async getRelease(owner: string, repo: string, releaseId: string): Promise<GitHubRelease | null> {
    const result = await GitHubClient.get<Record<string, unknown>>(`/repos/${owner}/${repo}/releases/${releaseId}`)
    if (result.success && result.data) return mapApiRelease(result.data, `${owner}/${repo}`)
    return null
  },

  async listReleases(owner: string, repo: string): Promise<GitHubRelease[]> {
    const result = await GitHubClient.get<Record<string, unknown>[]>(`/repos/${owner}/${repo}/releases?per_page=100`)
    if (result.success && result.data) return result.data.map((r) => mapApiRelease(r, `${owner}/${repo}`))
    return []
  },

  async getLatestRelease(owner: string, repo: string): Promise<GitHubRelease | null> {
    const result = await GitHubClient.get<Record<string, unknown>>(`/repos/${owner}/${repo}/releases/latest`)
    if (result.success && result.data) return mapApiRelease(result.data, `${owner}/${repo}`)
    return null
  },
}