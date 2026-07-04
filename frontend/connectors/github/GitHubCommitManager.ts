import { GitHubCommit } from "./types"
import { GitHubClient } from "./GitHubClient"

function mapApiCommit(apiCommit: Record<string, unknown>, repositoryId: string, branch: string): GitHubCommit {
  const commit = apiCommit.commit as Record<string, unknown> ?? {}
  const author = commit.author as Record<string, unknown> ?? {}
  const committer = commit.committer as Record<string, unknown> ?? {}
  return {
    sha: String(apiCommit.sha),
    repositoryId,
    branch,
    message: String(commit.message ?? ""),
    author: String(author.name ?? (apiCommit.author as Record<string, unknown>)?.login ?? ""),
    committer: String(committer.name ?? (apiCommit.committer as Record<string, unknown>)?.login ?? ""),
    parents: ((apiCommit.parents as Record<string, unknown>[]) ?? []).map((p) => String(p.sha)),
    timestamp: String(author.date ?? committer.date ?? new Date().toISOString()),
  }
}

export const GitHubCommitManager = {
  async listCommits(owner: string, repo: string, branch?: string): Promise<GitHubCommit[]> {
    const shaParam = branch ? `&sha=${branch}` : ""
    const result = await GitHubClient.get<Record<string, unknown>[]>(`/repos/${owner}/${repo}/commits?per_page=100${shaParam}`)
    if (result.success && result.data) return result.data.map((c) => mapApiCommit(c, `${owner}/${repo}`, branch ?? "main"))
    return []
  },

  async findCommit(owner: string, repo: string, sha: string): Promise<GitHubCommit | null> {
    const result = await GitHubClient.get<Record<string, unknown>>(`/repos/${owner}/${repo}/commits/${sha}`)
    if (result.success && result.data) return mapApiCommit(result.data, `${owner}/${repo}`, "")
    return null
  },

  async compareCommits(owner: string, repo: string, baseSha: string, headSha: string): Promise<{ base: GitHubCommit | null; head: GitHubCommit | null; aheadBy: number; behindBy: number }> {
    const result = await GitHubClient.get<Record<string, unknown>>(`/repos/${owner}/${repo}/compare/${baseSha}...${headSha}`)
    if (result.success && result.data) {
      return {
        base: await this.findCommit(owner, repo, baseSha),
        head: await this.findCommit(owner, repo, headSha),
        aheadBy: Number((result.data as Record<string, unknown>).ahead_by ?? 0),
        behindBy: Number((result.data as Record<string, unknown>).behind_by ?? 0),
      }
    }
    return { base: null, head: null, aheadBy: 0, behindBy: 0 }
  },

  async getCommitHistory(owner: string, repo: string, branch: string, since?: string, until?: string): Promise<GitHubCommit[]> {
    let path = `/repos/${owner}/${repo}/commits?sha=${branch}&per_page=100`
    if (since) path += `&since=${since}`
    if (until) path += `&until=${until}`
    const result = await GitHubClient.get<Record<string, unknown>[]>(path)
    if (result.success && result.data) return result.data.map((c) => mapApiCommit(c, `${owner}/${repo}`, branch))
    return []
  },
}