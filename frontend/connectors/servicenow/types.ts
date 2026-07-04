export enum IncidentState {
  NEW = "new",
  IN_PROGRESS = "in_progress",
  ON_HOLD = "on_hold",
  RESOLVED = "resolved",
  CLOSED = "closed",
  CANCELLED = "cancelled",
}

export enum ChangeState {
  NEW = "new",
  ASSESSING = "assessing",
  AUTHORIZING = "authorizing",
  SCHEDULED = "scheduled",
  IMPLEMENTING = "implementing",
  REVIEWING = "reviewing",
  CLOSED = "closed",
  CANCELLED = "cancelled",
}

export enum ApprovalState {
  PENDING = "pending",
  APPROVED = "approved",
  REJECTED = "rejected",
  CANCELLED = "cancelled",
  NOT_REQUIRED = "not_required",
}

export enum PriorityLevel {
  CRITICAL = "critical",
  HIGH = "high",
  MEDIUM = "medium",
  LOW = "low",
  PLANNING = "planning",
}

export enum PermissionLevel {
  READ = "read",
  WRITE = "write",
  ADMIN = "admin",
  NONE = "none",
}

export interface ServiceNowInstance {
  id: string
  name: string
  url: string
  version: string
  description: string
  archived: boolean
  createdAt: string
  updatedAt: string
}

export interface Incident {
  id: string
  instanceId: string
  number: string
  shortDescription: string
  description: string
  state: IncidentState
  priority: PriorityLevel
  assignmentGroup: string
  assignedTo: string | null
  callerId: string
  category: string
  impact: string
  urgency: string
  resolutionCode: string | null
  resolutionNotes: string | null
  openedAt: string
  resolvedAt: string | null
  closedAt: string | null
  createdAt: string
  updatedAt: string
}

export interface IncidentComment {
  id: string
  incidentId: string
  author: string
  body: string
  isPublic: boolean
  createdAt: string
  updatedAt: string
}

export interface Problem {
  id: string
  instanceId: string
  number: string
  shortDescription: string
  description: string
  state: "under_investigation" | "root_cause_identified" | "known_error" | "resolved" | "closed"
  priority: PriorityLevel
  assignmentGroup: string
  assignedTo: string | null
  workaround: string | null
  knownError: boolean
  relatedIncidents: string[]
  openedAt: string
  resolvedAt: string | null
  closedAt: string | null
  createdAt: string
  updatedAt: string
}

export interface ProblemTask {
  id: string
  problemId: string
  number: string
  shortDescription: string
  description: string
  state: IncidentState
  assignedTo: string | null
  openedAt: string
  closedAt: string | null
  createdAt: string
  updatedAt: string
}

export interface ChangeRequest {
  id: string
  instanceId: string
  number: string
  shortDescription: string
  description: string
  state: ChangeState
  priority: PriorityLevel
  riskLevel: "low" | "medium" | "high" | "extreme"
  category: string
  assignmentGroup: string
  assignedTo: string | null
  approval: ApprovalState
  approver: string | null
  plannedStartDate: string | null
  plannedEndDate: string | null
  openedAt: string
  implementedAt: string | null
  closedAt: string | null
  createdAt: string
  updatedAt: string
}

export interface ChangeTask {
  id: string
  changeRequestId: string
  number: string
  shortDescription: string
  description: string
  state: IncidentState
  assignedTo: string | null
  openedAt: string
  closedAt: string | null
  createdAt: string
  updatedAt: string
}

export interface ConfigurationItem {
  id: string
  instanceId: string
  name: string
  sysClassName: string
  serialNumber: string
  assetTag: string
  category: string
  subcategory: string
  status: "operational" | "non_operational" | "under_repair" | "retired"
  version: string
  location: string
  assignedTo: string | null
  operationalStatus: string
  installDate: string | null
  lastSeenAt: string | null
  createdAt: string
  updatedAt: string
}

export interface CMDBRelationship {
  id: string
  instanceId: string
  parentId: string
  childId: string
  type: string
  direction: string
  createdAt: string
}

export interface KnowledgeArticle {
  id: string
  instanceId: string
  title: string
  text: string
  categoryId: string
  keywords: string[]
  status: "draft" | "published" | "archived" | "retired"
  author: string
  reviewer: string | null
  publishedAt: string | null
  createdAt: string
  updatedAt: string
}

export interface KnowledgeCategory {
  id: string
  instanceId: string
  name: string
  description: string
  parentId: string | null
  articles: string[]
  createdAt: string
}

export interface Catalog {
  id: string
  instanceId: string
  name: string
  description: string
  items: string[]
  createdAt: string
  updatedAt: string
}

export interface CatalogItem {
  id: string
  catalogId: string
  name: string
  shortDescription: string
  description: string
  category: string
  price: number
  deliveryTime: string
  active: boolean
  orderGuide: string | null
  createdAt: string
  updatedAt: string
}

export interface Approval {
  id: string
  recordId: string
  recordType: "incident" | "change" | "problem" | "catalog_item"
  approverId: string
  state: ApprovalState
  comments: string
  dueBy: string | null
  createdAt: string
  updatedAt: string
}

export interface AssignmentGroup {
  id: string
  instanceId: string
  name: string
  description: string
  manager: string | null
  members: string[]
  email: string
  createdAt: string
}

export interface ServiceRequest {
  id: string
  instanceId: string
  number: string
  shortDescription: string
  state: "open" | "in_progress" | "fulfilled" | "cancelled"
  requestedFor: string
  openedBy: string
  items: string[]
  approval: ApprovalState
  openedAt: string
  fulfilledAt: string | null
  createdAt: string
  updatedAt: string
}

export interface RequestItem {
  id: string
  requestId: string
  catalogItemId: string
  shortDescription: string
  quantity: number
  state: "pending" | "approved" | "fulfilled" | "cancelled"
  price: number
  configurationItemId: string | null
  createdAt: string
  updatedAt: string
}

export interface ServiceLevelAgreement {
  id: string
  instanceId: string
  name: string
  description: string
  targetResponseTime: number
  targetResolutionTime: number
  priority: PriorityLevel
  active: boolean
  createdAt: string
  updatedAt: string
}

export interface BusinessService {
  id: string
  instanceId: string
  name: string
  description: string
  category: string
  status: "operational" | "degraded" | "offline"
  owner: string | null
  configurationItems: string[]
  createdAt: string
  updatedAt: string
}

export interface UserRole {
  id: string
  instanceId: string
  name: string
  description: string
  permissions: string[]
  assignmentGroups: string[]
  createdAt: string
}

export interface ServiceNowPermission {
  resource: string
  access: PermissionLevel
  granted: boolean
}

export interface ServiceNowRequest {
  id: string
  action: string
  resource: string
  body: Record<string, unknown>
  timestamp: string
}

export interface ServiceNowResponse {
  id: string
  requestId: string
  success: boolean
  data: Record<string, unknown> | null
  errors: string[]
  timestamp: string
}

export interface ServiceNowHealth {
  status: "healthy" | "degraded" | "unhealthy" | "unknown"
  state: string
  uptimeMs: number
  lastOperation: string | null
  lastError: string | null
}

export interface ServiceNowMetrics {
  totalIncidents: number
  totalChanges: number
  totalProblems: number
  totalConfigurationItems: number
  totalKnowledgeArticles: number
  totalCatalogItems: number
  operationsSucceeded: number
  operationsFailed: number
}