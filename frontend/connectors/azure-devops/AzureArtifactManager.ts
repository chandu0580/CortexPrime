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
    const parts = feedId.split("/")
    const projectId = parts[0] ?? ""
    const fid = parts[1] ?? feedId
    const body = { name, version, description, packageType }
    const result = await AzureDevOpsClient.post<Record<string, unknown>>(`/${projectId}/_apis/artifacts/feeds/${fid}/packages`, body)
    const now = new Date().toISOString()
    if (result.success && result.data) {
      return { id: String(result.data.id), feedId, name: String(result.data.name), version: String(result.data.version), description: String(result.data.description ?? ""), packageType, published: true, createdAt: String(result.data.createdDate ?? now), updatedAt: String(result.data.updatedDate ?? now) }
    }
    return { id: "", feedId, name, version, description, packageType, published: false, createdAt: now, updatedAt: now }
  },

  async archivePackage(id: string): Promise<AzurePackage | null> {
    const parts = id.split("/")
    const projectId = parts[0] ?? ""
    const packageId = parts[1] ?? id
    const result = await AzureDevOpsClient.patch<Record<string, unknown>>(`/${projectId}/_apis/artifacts/feeds/packages/${packageId}`, { deprecated: true })
    if (result.success && result.data) {
      return { id: String(result.data.id), feedId: "", name: String(result.data.name), version: String(result.data.version), description: String(result.data.description ?? ""), packageType: (result.data.protocolType as string) as AzurePackage["packageType"] ?? "generic", published: false, createdAt: String(result.data.createdDate ?? ""), updatedAt: String(result.data.updatedDate ?? "") }
    }
    return null
  },

  async getFeed(id: string): Promise<AzureFeed | null> {
    const parts = id.split("/")
    const projectId = parts[0] ?? ""
    const fid = parts[1] ?? id
    const result = await AzureDevOpsClient.get<Record<string, unknown>>(`/${projectId}/_apis/artifacts/feeds/${fid}`)
    if (result.success && result.data) return mapApiFeed(result.data, projectId)
    return null
  },

  async listPackages(feedId: string): Promise<AzurePackage[]> {
    const parts = feedId.split("/")
    const projectId = parts[0] ?? ""
    const fid = parts[1] ?? feedId
    const result = await AzureDevOpsClient.get<Record<string, unknown>>(`/${projectId}/_apis/artifacts/feeds/${fid}/packages?$top=100`)
    if (result.success && result.data?.value) {
      return (result.data.value as Record<string, unknown>[]).map((p) => ({
        id: String(p.id), feedId, name: String(p.name), version: String(p.version), description: String(p.description ?? ""),
        packageType: (p.protocolType as string) as AzurePackage["packageType"] ?? "generic", published: !p.deprecated,
        createdAt: String(p.createdDate ?? ""), updatedAt: String(p.updatedDate ?? ""),
      }))
    }
    return []
  },
}