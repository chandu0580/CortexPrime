export enum SpaceType {
  GLOBAL = "global",
  PERSONAL = "personal",
  COLLABORATION = "collaboration",
  KNOWLEDGE_BASE = "knowledge_base",
}

export enum PageStatus {
  DRAFT = "draft",
  PUBLISHED = "published",
  ARCHIVED = "archived",
  TRASHED = "trashed",
}

export enum AttachmentType {
  FILE = "file",
  IMAGE = "image",
  DOCUMENT = "document",
  ARCHIVE = "archive",
}

export enum PermissionLevel {
  VIEW = "view",
  EDIT = "edit",
  ADMIN = "admin",
  NONE = "none",
}

export enum SearchScope {
  TITLE = "title",
  CONTENT = "content",
  LABEL = "label",
  ATTACHMENT = "attachment",
  ALL = "all",
}

export interface ConfluenceSpace {
  id: string
  key: string
  name: string
  description: string
  type: SpaceType
  homepageId: string | null
  pages: string[]
  archived: boolean
  createdAt: string
  updatedAt: string
}

export interface ConfluencePage {
  id: string
  spaceId: string
  parentId: string | null
  title: string
  body: string
  status: PageStatus
  version: number
  authorId: string
  labels: ConfluenceLabel[]
  restrictions: PageRestriction[]
  createdAt: string
  updatedAt: string
  publishedAt: string | null
}

export interface ConfluencePageVersion {
  id: string
  pageId: string
  version: number
  title: string
  body: string
  authorId: string
  message: string
  createdAt: string
}

export interface ConfluenceBlogPost {
  id: string
  spaceId: string
  title: string
  body: string
  status: PageStatus
  authorId: string
  labels: ConfluenceLabel[]
  createdAt: string
  updatedAt: string
  publishedAt: string | null
}

export interface ConfluenceAttachment {
  id: string
  pageId: string
  title: string
  filename: string
  mediaType: string
  type: AttachmentType
  fileSizeBytes: number
  version: number
  authorId: string
  archived: boolean
  createdAt: string
  updatedAt: string
}

export interface AttachmentVersion {
  id: string
  attachmentId: string
  version: number
  filename: string
  fileSizeBytes: number
  mediaType: string
  authorId: string
  comment: string
  createdAt: string
}

export interface ConfluenceComment {
  id: string
  pageId: string
  parentCommentId: string | null
  body: string
  authorId: string
  edited: boolean
  labels: ConfluenceLabel[]
  createdAt: string
  updatedAt: string
}

export interface ConfluenceLabel {
  id: string
  name: string
  color: string
}

export interface ConfluenceTemplate {
  id: string
  spaceId: string
  name: string
  description: string
  body: string
  category: string
  createdAt: string
  updatedAt: string
}

export interface SearchQuery {
  term: string
  scope: SearchScope
  spaceId: string | null
  label: string | null
  limit: number
  offset: number
}

export interface SearchResult {
  id: string
  type: "page" | "blog" | "attachment" | "space"
  title: string
  excerpt: string
  url: string
  spaceKey: string
  score: number
  lastModified: string
}

export interface SpacePermission {
  resource: string
  level: PermissionLevel
  granted: boolean
}

export interface UserPermission {
  userId: string
  spaceId: string
  level: PermissionLevel
  granted: boolean
}

export interface PageRestriction {
  id: string
  pageId: string
  type: "view" | "edit"
  userIds: string[]
  groupIds: string[]
}

export interface KnowledgeArticle {
  id: string
  spaceId: string
  title: string
  body: string
  categoryId: string
  authorId: string
  labels: ConfluenceLabel[]
  status: PageStatus
  createdAt: string
  updatedAt: string
}

export interface KnowledgeCategory {
  id: string
  spaceId: string
  name: string
  description: string
  articles: string[]
  createdAt: string
}

export interface ConfluenceRequest {
  id: string
  action: string
  resource: string
  body: Record<string, unknown>
  timestamp: string
}

export interface ConfluenceResponse {
  id: string
  requestId: string
  success: boolean
  data: Record<string, unknown> | null
  errors: string[]
  timestamp: string
}

export interface ConfluenceHealth {
  status: "healthy" | "degraded" | "unhealthy" | "unknown"
  state: string
  uptimeMs: number
  lastOperation: string | null
  lastError: string | null
}

export interface ConfluenceMetrics {
  totalSpaces: number
  totalPages: number
  totalBlogPosts: number
  totalAttachments: number
  totalComments: number
  totalTemplates: number
  operationsSucceeded: number
  operationsFailed: number
}