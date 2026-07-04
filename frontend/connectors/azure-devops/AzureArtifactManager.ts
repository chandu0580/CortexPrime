import { AzureFeed, AzurePackage } from "./types"
import { AzureDevOpsClient } from "./AzureDevOpsClient"

function mapApiFeed(api: Record<string, unknown>, projectId: string): AzureFeed {
  return { id: String(api.id), projectId, name: String(api.name), description: String(api.description ?? ""), packages: [], upstreamSources: [], createdAt: String(api.createdDate ?? ""), updatedAt: String(api.updatedDate ?? "") }
}

export const AzureArtifactManager = {
  async createFeed(projectId: string, name: string, description: string = ""): Promise<AzureFeed | null> {
    const result = await AzureDevOpsClient.post<Record<string, unknown>>(`/${projectId}/_apis/artifacts/feeds`, { name, description })
    if (result.success && result.data) return mapApiFeed(result.data, projectId)
    return null
  },

  async listFeeds(projectId: string): Promise<AzureFeed[]> {
    const result = await AzureDevOpsClient.get<Record<string, unknown>>(`/${projectId}/_apis/artifacts/feeds?$top=100`)
    if (result.success && result.data?.value) return (result.data.value as Record<string, unknown>[]).map((f) => mapApiFeed(f, projectId))
    return []
  },

  async publishPackage(feedId: string, name: string, version: string, description: string, packageType: AzurePackage["packageType"]): Promise<AzurePackage | null> {
    const now = new Date().toISOString()
    return { id: "", feedId, name, version, description, packageType, published: true, createdAt: now, updatedAt: now }
  },

  async archivePackage(id: string): Promise<AzurePackage | null> { return null },
  async getFeed(id: string): Promise<AzureFeed | null> { return null },
  async listPackages(feedId: string): Promise<AzurePackage[]> { return [] },
}