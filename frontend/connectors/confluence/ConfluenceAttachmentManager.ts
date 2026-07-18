import { type ConfluenceAttachment, type AttachmentVersion, AttachmentType } from "./types"
import { ConfluenceClient } from "./ConfluenceClient"

function mapApiAttachment(api: Record<string, unknown>, pageId: string): ConfluenceAttachment {
  const version = api.version as Record<string, unknown> ?? {}
  return {
    id: String(api.id), pageId, title: String(api.title), filename: String(api.title), mediaType: String(api.mediaType ?? ""),
    fileSizeBytes: Number(api.fileSize ?? 0), version: Number(version.number ?? 1),
    authorId: String((version.author as Record<string, unknown>)?.id ?? ""), archived: false,
    createdAt: String(api.createdAt ?? ""), updatedAt: String(api.updatedAt ?? ""), type: AttachmentType.FILE,
  }
}

export const ConfluenceAttachmentManager = {
  async uploadAttachment(pageId: string, title: string, filename: string, mediaType: string, fileSizeBytes: number): Promise<ConfluenceAttachment | null> {
    const body: Record<string, unknown> = { id: title, mediaType, fileSize: fileSizeBytes, comment: "Upload" }
    const result = await ConfluenceClient.post<Record<string, unknown>>(`/pages/${pageId}/attachments`, body)
    if (result.success && result.data) return mapApiAttachment(result.data, pageId)
    return null
  },

  async updateAttachment(id: string, pageId: string, title: string, mediaType: string, fileSizeBytes: number): Promise<ConfluenceAttachment | null> {
    const result = await ConfluenceClient.put<Record<string, unknown>>(`/attachments/${id}`, { id: title, mediaType, fileSize: fileSizeBytes })
    if (result.success && result.data) return mapApiAttachment(result.data, pageId)
    return null
  },

  async listAttachments(pageId: string): Promise<ConfluenceAttachment[]> {
    const result = await ConfluenceClient.get<Record<string, unknown>>(`/pages/${pageId}/attachments?limit=100`)
    if (result.success && result.data?.results) return (result.data.results as Record<string, unknown>[]).map((a) => mapApiAttachment(a, pageId))
    return []
  },

  async getAttachment(id: string): Promise<ConfluenceAttachment | null> {
    const result = await ConfluenceClient.get<Record<string, unknown>>(`/attachments/${id}`)
    if (result.success && result.data) return mapApiAttachment(result.data, String((result.data as Record<string, unknown>).pageId ?? ""))
    return null
  },

  async getVersions(attachmentId: string): Promise<AttachmentVersion[]> {
    const result = await ConfluenceClient.get<Record<string, unknown>>(`/attachments/${attachmentId}/versions?limit=100`)
    if (result.success && result.data?.results) {
      return (result.data.results as Record<string, unknown>[]).map((v) => ({
        id: String(v.id), attachmentId, version: Number(v.number), filename: "", fileSizeBytes: Number(v.fileSize ?? 0),
        mediaType: String(v.mediaType ?? ""), authorId: String((v.author as Record<string, unknown>)?.id ?? ""), comment: String(v.message ?? ""), createdAt: String(v.createdAt ?? ""),
      }))
    }
    return []
  },

  async archiveAttachment(id: string): Promise<ConfluenceAttachment | null> {
    const result = await ConfluenceClient.put<Record<string, unknown>>(`/attachments/${id}`, { status: "archived" })
    if (result.success && result.data) return mapApiAttachment(result.data, String((result.data as Record<string, unknown>).pageId ?? ""))
    return null
  },
}