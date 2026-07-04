import { GitHubBranch } from "./types"
import { GitHubClient } from "./GitHubClient"

function mapApiBranch(apiBranch: Record<string, unknown>, repositoryId: string): GitHubBranch {
  const protection = apiBranch.protection as Record<string, unknown>
  return {
    id: String(apiBranch.name),
    repositoryId,
    name: String(apiBranch.name),
    commitSha: ((apiBranch.commit as Record<string, unknown>)?.sha as string) ?? "",
    protected: Boolean(apiBranch.protected ?? false),
    protectionRules: protection ? Object.keys(protection) : [],
    createdAt: new Date().toISOString(),
  }
}

export const GitHubBranchManager = {
  async createBranch(owner: string, repo: string, name: string, headSha: string): Promise<GitHubBranch | null> {
    const result = await GitHubClient.post<Record<string, unknown>>(`/repos/${owner}/${repo}/git/refs`, {
      ref: `refs/heads/${name}`, sha: headSha,
    })
    if (result.success && result.data) {
      return { id: name, repositoryId: `${owner}/${repo}`, name, commitSha: String((result.data.object as Record<string, unknown>)?.sha ?? ""), protected: false, protectionRules: [], createdAt: new Date().toISOString() }
    }
    return null
  },

  async deleteBranch(owner: string, repo: string, branchName: string): Promise<boolean> {
    const result = await GitHubClient.delete(`/repos/${owner}/${repo}/git/refs/heads/${branchName}`)
    return result.success
  },

  async protectBranch(owner: string, repo: string, branchName: string, rules: string[]): Promise<GitHubBranch | null> {
    const result = await GitHubClient.put<Record<string, unknown>>(`/repos/${owner}/${repo}/branches/${branchName}/protection`, {
      required_status_checks: null, enforce_admins: true, required_pull_request_reviews: { required_approving_review_count: 1 }, restrictions: null,
    })
    if (result.success) {
      return { id: branchName, repositoryId: `${owner}/${repo}`, name: branchName, commitSha: "", protected: true, protectionRules: rules, createdAt: new Date().toISOString() }
    }
    return null
  },

  async getBranch(owner: string, repo: string, branchName: string): Promise<GitHubBranch | null> {
    const result = await GitHubClient.get<Record<string, unknown>>(`/repos/${owner}/${repo}/branches/${branchName}`)
    if (result.success && result.data) return mapApiBranch(result.data, `${owner}/${repo}`)
    return null
  },

  async listBranches(owner: string, repo: string): Promise<GitHubBranch[]> {
    const result = await GitHubClient.get<Record<string, unknown>[]>(`/repos/${owner}/${repo}/branches?per_page=100`)
    if (result.success && result.data) return result.data.map((b) => mapApiBranch(b, `${owner}/${repo}`))
    return []
  },
}