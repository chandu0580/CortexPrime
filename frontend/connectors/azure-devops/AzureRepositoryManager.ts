import { AzureRepository, AzureBranch, AzurePullRequest, RepositoryVisibility } from "./types"
import { AzureDevOpsClient } from "./AzureDevOpsClient"

function mapApiRepo(api: Record<string, unknown>, projectId: string): AzureRepository {
  return {
    id: String(api.id), projectId, name: String(api.name), description: String(api.description ?? ""),
    visibility: (api.visibility as string ?? "private").toLowerCase() as RepositoryVisibility,
    defaultBranch: String(api.defaultBranch ?? api.default_branch ?? "main").replace("refs/heads/", ""),
    branches: [], archived: Boolean(api.isDisabled), createdAt: String(api.createdAt ?? ""), updatedAt: String(api.updatedAt ?? ""),
  }
}

function mapApiPr(api: Record<string, unknown>, repositoryId: string): AzurePullRequest {
  return {
    id: String(api.pullRequestId ?? api.id), repositoryId,
    title: String(api.title), description: String(api.description ?? ""),
    sourceBranch: String(api.sourceRefName ?? api.sourceBranch ?? "").replace("refs/heads/", ""),
    targetBranch: String(api.targetRefName ?? api.targetBranch ?? "").replace("refs/heads/", ""),
    author: String((api.createdBy as Record<string, unknown>)?.displayName ?? api.author ?? ""),
    reviewers: (api.reviewers as Record<string, unknown>[] ?? []).map((r) => String(r.displayName ?? r.id ?? "")),
    status: (api.status as string ?? "active").toLowerCase() as AzurePullRequest["status"],
    mergeStatus: (api.mergeStatus as string ?? "not_set").toLowerCase() as AzurePullRequest["mergeStatus"],
    createdAt: String(api.creationDate ?? api.created_at ?? ""),
    updatedAt: String((api.lastMergeSourceCommit as Record<string, unknown>)?.date ?? api.updatedAt ?? ""),
    closedAt: api.closedDate as string ?? null,
  }
}

export const AzureRepositoryManager = {
  async createRepository(projectId: string, name: string, description: string = ""): Promise<AzureRepository | null> {
    const result = await AzureDevOpsClient.post<Record<string, unknown>>(`/${projectId}/_apis/git/repositories`, { name, description })
    if (result.success && result.data) return mapApiRepo(result.data, projectId)
    return null
  },

  async listRepositories(projectId: string): Promise<AzureRepository[]> {
    const result = await AzureDevOpsClient.get<Record<string, unknown>>(`/${projectId}/_apis/git/repositories?$top=100`)
    if (result.success && result.data?.value) return (result.data.value as Record<string, unknown>[]).map((r) => mapApiRepo(r, projectId))
    return []
  },

  async createBranch(projectId: string, repositoryId: string, name: string, sourceBranch: string = "main"): Promise<AzureBranch | null> {
    const repoResult = await AzureDevOpsClient.get<Record<string, unknown>>(`/${projectId}/_apis/git/repositories/${repositoryId}/refs?filter=heads/${sourceBranch}`)
    const refs = repoResult.data?.value as unknown[] | undefined
    if (repoResult.success && refs?.[0]) {
      const objectId = (refs[0] as Record<string, unknown>).objectId as string
      const result = await AzureDevOpsClient.post<Record<string, unknown>>(`/${projectId}/_apis/git/repositories/${repositoryId}/refs`, [{ name: `refs/heads/${name}`, newObjectId: objectId, oldObjectId: "0000000000000000000000000000000000000000" }])
      if (result.success) return { id: name, repositoryId, name, commitSha: objectId, protected: false, createdAt: new Date().toISOString() }
    }
    return null
  },

  async createPullRequest(projectId: string, repositoryId: string, title: string, description: string, sourceBranch: string, targetBranch: string): Promise<AzurePullRequest | null> {
    const result = await AzureDevOpsClient.post<Record<string, unknown>>(`/${projectId}/_apis/git/repositories/${repositoryId}/pullrequests`, { title, description, sourceRefName: `refs/heads/${sourceBranch}`, targetRefName: `refs/heads/${targetBranch}` })
    if (result.success && result.data) return mapApiPr(result.data, repositoryId)
    return null
  },

  async listPullRequests(projectId: string, repositoryId: string): Promise<AzurePullRequest[]> {
    const result = await AzureDevOpsClient.get<Record<string, unknown>>(`/${projectId}/_apis/git/repositories/${repositoryId}/pullrequests?$top=100`)
    if (result.success && result.data?.value) return (result.data.value as Record<string, unknown>[]).map((pr) => mapApiPr(pr, repositoryId))
    return []
  },

  async getPullRequest(projectId: string, repositoryId: string, prId: string): Promise<AzurePullRequest | null> {
    const result = await AzureDevOpsClient.get<Record<string, unknown>>(`/${projectId}/_apis/git/repositories/${repositoryId}/pullrequests/${prId}`)
    if (result.success && result.data) return mapApiPr(result.data, repositoryId)
    return null
  },

  async getRepository(id: string): Promise<AzureRepository | null> {
    const parts = id.split("/")
    const projectId = parts[0] ?? ""
    const repoId = parts[1] ?? id
    const result = await AzureDevOpsClient.get<Record<string, unknown>>(`/${projectId}/_apis/git/repositories/${repoId}`)
    if (result.success && result.data) return mapApiRepo(result.data, projectId)
    return null
  },
}