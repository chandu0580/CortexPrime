export enum PageStatus {
  PUBLISHED = "published",
  ARCHIVED = "archived",
  DRAFT = "draft",
  TRASHED = "trashed",
}

export enum BlockType {
  PARAGRAPH = "paragraph",
  HEADING_1 = "heading_1",
  HEADING_2 = "heading_2",
  HEADING_3 = "heading_3",
  BULLETED_LIST = "bulleted_list",
  NUMBERED_LIST = "numbered_list",
  TOGGLE = "toggle",
  CALLOUT = "callout",
  QUOTE = "quote",
  DIVIDER = "divider",
  IMAGE = "image",
  CODE = "code",
  TABLE = "table",
  EMBED = "embed",
  BOOKMARK = "bookmark",
  EQUATION = "equation",
  FILE = "file",
  VIDEO = "video",
  AUDIO = "audio",
  COLUMN = "column",
  COLUMN_LIST = "column_list",
  BREADCRUMB = "breadcrumb",
  LINK_PREVIEW = "link_preview",
  SYNCED_BLOCK = "synced_block",
  TABLE_OF_CONTENTS = "table_of_contents",
  TEMPLATE = "template",
  LINK_TO_PAGE = "link_to_page",
  UNSUPPORTED = "unsupported",
}

export enum PropertyType {
  TITLE = "title",
  RICH_TEXT = "rich_text",
  NUMBER = "number",
  SELECT = "select",
  MULTI_SELECT = "multi_select",
  DATE = "date",
  PEOPLE = "people",
  FILES = "files",
  CHECKBOX = "checkbox",
  URL = "url",
  EMAIL = "email",
  PHONE = "phone",
  FORMULA = "formula",
  RELATION = "relation",
  ROLLUP = "rollup",
  CREATED_TIME = "created_time",
  CREATED_BY = "created_by",
  LAST_EDITED_TIME = "last_edited_time",
  LAST_EDITED_BY = "last_edited_by",
  STATUS = "status",
}

export enum PermissionLevel {
  VIEW = "view",
  EDIT = "edit",
  ADMIN = "admin",
  NONE = "none",
}

export enum SearchScope {
  PAGES = "pages",
  DATABASES = "databases",
  BLOCKS = "blocks",
  ALL = "all",
}

export interface NotionWorkspace {
  id: string
  name: string
  domain: string
  description: string
  pages: string[]
  databases: string[]
  archived: boolean
  createdAt: string
  updatedAt: string
}

export interface NotionPage {
  id: string
  workspaceId: string
  parentId: string | null
  title: string
  icon: string
  cover: string
  status: PageStatus
  blocks: string[]
  properties: Record<string, unknown>
  createdAt: string
  updatedAt: string
  archivedAt: string | null
}

export interface NotionDatabase {
  id: string
  workspaceId: string
  parentPageId: string | null
  title: string
  description: string
  icon: string
  properties: DatabaseProperty[]
  rows: string[]
  archived: boolean
  createdAt: string
  updatedAt: string
}

export interface DatabaseProperty {
  id: string
  databaseId: string
  name: string
  type: PropertyType
  options: string[]
  required: boolean
}

export interface DatabaseRow {
  id: string
  databaseId: string
  properties: Record<string, unknown>
  createdAt: string
  updatedAt: string
}

export interface NotionBlock {
  id: string
  pageId: string
  parentBlockId: string | null
  type: BlockType
  content: Record<string, unknown>
  children: string[]
  position: number
  createdAt: string
  updatedAt: string
}

export interface BlockChild {
  id: string
  blockId: string
  childBlockId: string
  position: number
}

export interface NotionTemplate {
  id: string
  workspaceId: string
  name: string
  description: string
  content: Record<string, unknown>
  category: string
  createdAt: string
  updatedAt: string
}

export interface NotionComment {
  id: string
  pageId: string
  blockId: string | null
  authorId: string
  body: string
  edited: boolean
  createdAt: string
  updatedAt: string
}

export interface SearchQuery {
  term: string
  scope: SearchScope
  limit: number
  offset: number
}

export interface SearchResult {
  id: string
  type: "page" | "database" | "block"
  title: string
  excerpt: string
  workspaceId: string
  score: number
  lastModified: string
}

export interface WorkspacePermission {
  resource: string
  level: PermissionLevel
  granted: boolean
}

export interface PagePermission {
  userId: string
  pageId: string
  level: PermissionLevel
  granted: boolean
}

export interface DatabasePermission {
  userId: string
  databaseId: string
  level: PermissionLevel
  granted: boolean
}

export interface UserPermission {
  userId: string
  workspaceId: string
  level: PermissionLevel
  granted: boolean
}

export interface ShareLink {
  id: string
  pageId: string
  url: string
  allowEdit: boolean
  allowComment: boolean
  expiresAt: string | null
  createdAt: string
}

export interface PageHistory {
  id: string
  pageId: string
  version: number
  title: string
  editedBy: string
  editedAt: string
}

export interface NotionRequest {
  id: string
  action: string
  resource: string
  body: Record<string, unknown>
  timestamp: string
}

export interface NotionResponse {
  id: string
  requestId: string
  success: boolean
  data: Record<string, unknown> | null
  errors: string[]
  timestamp: string
}

export interface NotionHealth {
  status: "healthy" | "degraded" | "unhealthy" | "unknown"
  state: string
  uptimeMs: number
  lastOperation: string | null
  lastError: string | null
}

export interface NotionMetrics {
  totalWorkspaces: number
  totalPages: number
  totalDatabases: number
  totalBlocks: number
  totalTemplates: number
  totalComments: number
  operationsSucceeded: number
  operationsFailed: number
}