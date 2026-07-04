export enum IssueType {
  EPIC = "epic",
  STORY = "story",
  TASK = "task",
  SUBTASK = "subtask",
  BUG = "bug",
}

export enum IssueStatus {
  BACKLOG = "backlog",
  SELECTED_FOR_DEVELOPMENT = "selected_for_development",
  IN_PROGRESS = "in_progress",
  IN_REVIEW = "in_review",
  DONE = "done",
}

export enum SprintState {
  FUTURE = "future",
  ACTIVE = "active",
  CLOSED = "closed",
}

export enum BoardType {
  SCRUM = "scrum",
  KANBAN = "kanban",
}

export enum WorkflowState {
  DRAFT = "draft",
  ACTIVE = "active",
  ARCHIVED = "archived",
}

export interface JiraProject {
  id: string
  key: string
  name: string
  description: string
  lead: string
  url: string
  avatarUrl: string
  archived: boolean
  components: JiraComponent[]
  versions: JiraVersion[]
  createdAt: string
  updatedAt: string
}

export interface JiraIssue {
  id: string
  projectId: string
  key: string
  issueType: IssueType
  status: IssueStatus
  title: string
  description: string
  assignee: JiraAssignee | null
  reporter: JiraReporter
  epicId: string | null
  sprintId: string | null
  labels: JiraLabel[]
  components: JiraComponent[]
  attachments: JiraAttachment[]
  storyPoints: number
  priority: string
  resolution: string | null
  votes: number
  watchers: number
  createdAt: string
  updatedAt: string
  resolvedAt: string | null
}

export interface JiraEpic {
  id: string
  projectId: string
  key: string
  name: string
  summary: string
  status: IssueStatus
  color: string
  startDate: string | null
  endDate: string | null
  issues: string[]
  createdAt: string
  updatedAt: string
  completedAt: string | null
}

export interface JiraStory {
  id: string
  projectId: string
  key: string
  epicId: string | null
  sprintId: string | null
  title: string
  description: string
  status: IssueStatus
  assignee: JiraAssignee | null
  reporter: JiraReporter
  storyPoints: number
  priority: string
  labels: JiraLabel[]
  acceptanceCriteria: string[]
  createdAt: string
  updatedAt: string
}

export interface JiraTask {
  id: string
  projectId: string
  key: string
  epicId: string | null
  sprintId: string | null
  title: string
  description: string
  status: IssueStatus
  assignee: JiraAssignee | null
  reporter: JiraReporter
  priority: string
  labels: JiraLabel[]
  createdAt: string
  updatedAt: string
}

export interface JiraSubTask {
  id: string
  projectId: string
  parentIssueId: string
  key: string
  title: string
  description: string
  status: IssueStatus
  assignee: JiraAssignee | null
  reporter: JiraReporter
  priority: string
  createdAt: string
  updatedAt: string
}

export interface JiraSprint {
  id: string
  projectId: string
  boardId: string
  name: string
  goal: string
  state: SprintState
  startDate: string | null
  endDate: string | null
  completedDate: string | null
  issues: string[]
  createdAt: string
}

export interface JiraBoard {
  id: string
  projectId: string
  name: string
  type: BoardType
  columns: string[]
  active: boolean
  sprints: string[]
  createdAt: string
  updatedAt: string
}

export interface JiraWorkflow {
  id: string
  projectId: string
  name: string
  description: string
  states: JiraWorkflowState[]
  transitions: JiraTransition[]
  state: WorkflowState
  createdAt: string
  updatedAt: string
}

export interface JiraWorkflowState {
  id: string
  workflowId: string
  name: string
  status: IssueStatus
  position: number
  category: string
}

export interface JiraTransition {
  id: string
  workflowId: string
  name: string
  fromStateId: string
  toStateId: string
  conditions: string[]
}

export interface JiraComment {
  id: string
  issueId: string
  author: string
  body: string
  edited: boolean
  createdAt: string
  updatedAt: string
}

export interface JiraAttachment {
  id: string
  issueId: string
  filename: string
  mimeType: string
  sizeBytes: number
  author: string
  url: string
  createdAt: string
}

export interface JiraVersion {
  id: string
  projectId: string
  name: string
  description: string
  released: boolean
  releaseDate: string | null
  archived: boolean
  createdAt: string
}

export interface JiraRelease {
  id: string
  projectId: string
  versionId: string
  name: string
  description: string
  released: boolean
  releaseDate: string | null
  issues: string[]
  createdAt: string
}

export interface JiraComponent {
  id: string
  projectId: string
  name: string
  description: string
  lead: string | null
  assigneeType: string
  createdAt: string
}

export interface JiraLabel {
  id: string
  name: string
  color: string
}

export interface JiraAssignee {
  id: string
  displayName: string
  email: string
  avatarUrl: string
  active: boolean
}

export interface JiraReporter {
  id: string
  displayName: string
  email: string
  avatarUrl: string
}

export interface JiraPermission {
  resource: string
  access: "read" | "write" | "admin" | "none"
  granted: boolean
}

export interface JiraRequest {
  id: string
  action: string
  resource: string
  body: Record<string, unknown>
  timestamp: string
}

export interface JiraResponse {
  id: string
  requestId: string
  success: boolean
  data: Record<string, unknown> | null
  errors: string[]
  timestamp: string
}

export interface JiraHealth {
  status: "healthy" | "degraded" | "unhealthy" | "unknown"
  state: string
  uptimeMs: number
  lastOperation: string | null
  lastError: string | null
}

export interface JiraMetrics {
  totalProjects: number
  totalIssues: number
  totalEpics: number
  totalSprints: number
  totalBoards: number
  totalWorkflows: number
  totalReleases: number
  operationsSucceeded: number
  operationsFailed: number
}
