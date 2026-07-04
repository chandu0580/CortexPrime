export enum WorkItemState {
  NEW = "new",
  ACTIVE = "active",
  RESOLVED = "resolved",
  CLOSED = "closed",
  REMOVED = "removed",
}

export enum PipelineStatus {
  QUEUED = "queued",
  IN_PROGRESS = "in_progress",
  SUCCEEDED = "succeeded",
  FAILED = "failed",
  CANCELLED = "cancelled",
  SKIPPED = "skipped",
}

export enum RepositoryVisibility {
  PUBLIC = "public",
  PRIVATE = "private",
  ORG_VISIBLE = "org_visible",
}

export enum PermissionLevel {
  READ = "read",
  WRITE = "write",
  ADMIN = "admin",
  NONE = "none",
}

export enum TestStatus {
  NOT_RUN = "not_run",
  PASSED = "passed",
  FAILED = "failed",
  BLOCKED = "blocked",
  SKIPPED = "skipped",
  IN_PROGRESS = "in_progress",
}

export interface AzureOrganization {
  id: string
  name: string
  displayName: string
  description: string
  projects: string[]
  archived: boolean
  createdAt: string
  updatedAt: string
}

export interface AzureProject {
  id: string
  organizationId: string
  name: string
  description: string
  visibility: RepositoryVisibility
  teams: string[]
  archived: boolean
  createdAt: string
  updatedAt: string
}

export interface AzureTeam {
  id: string
  projectId: string
  name: string
  description: string
  members: string[]
  createdAt: string
}

export interface AzureBoard {
  id: string
  projectId: string
  name: string
  description: string
  columns: string[]
  workItems: string[]
  createdAt: string
  updatedAt: string
}

export interface AzureWorkItem {
  id: string
  boardId: string
  projectId: string
  title: string
  description: string
  state: WorkItemState
  assignedTo: string | null
  workItemType: "epic" | "feature" | "story" | "task" | "bug"
  priority: number
  storyPoints: number
  tags: string[]
  createdAt: string
  updatedAt: string
  closedAt: string | null
}

export interface AzureEpic {
  id: string
  projectId: string
  title: string
  description: string
  state: WorkItemState
  features: string[]
  priority: number
  createdAt: string
  updatedAt: string
}

export interface AzureFeature {
  id: string
  projectId: string
  epicId: string | null
  title: string
  description: string
  state: WorkItemState
  stories: string[]
  priority: number
  createdAt: string
  updatedAt: string
}

export interface AzureUserStory {
  id: string
  projectId: string
  featureId: string | null
  title: string
  description: string
  state: WorkItemState
  acceptanceCriteria: string[]
  storyPoints: number
  priority: number
  createdAt: string
  updatedAt: string
}

export interface AzureTask {
  id: string
  projectId: string
  parentId: string | null
  title: string
  description: string
  state: WorkItemState
  assignedTo: string | null
  estimatedHours: number
  remainingHours: number
  priority: number
  createdAt: string
  updatedAt: string
}

export interface AzureBug {
  id: string
  projectId: string
  title: string
  description: string
  state: WorkItemState
  severity: "critical" | "major" | "minor" | "trivial"
  assignedTo: string | null
  priority: number
  createdAt: string
  updatedAt: string
  resolvedAt: string | null
}

export interface AzurePipeline {
  id: string
  projectId: string
  name: string
  description: string
  stages: AzureStage[]
  createdAt: string
  updatedAt: string
}

export interface AzurePipelineRun {
  id: string
  pipelineId: string
  projectId: string
  runNumber: number
  status: PipelineStatus
  triggeredBy: string
  branch: string
  commitSha: string
  stages: string[]
  startedAt: string
  completedAt: string | null
}

export interface AzureStage {
  id: string
  pipelineId: string
  name: string
  displayName: string
  jobs: AzureJob[]
  status: PipelineStatus
  startedAt: string | null
  completedAt: string | null
}

export interface AzureJob {
  id: string
  stageId: string
  name: string
  status: PipelineStatus
  startedAt: string | null
  completedAt: string | null
}

export interface AzureRepository {
  id: string
  projectId: string
  name: string
  description: string
  visibility: RepositoryVisibility
  defaultBranch: string
  branches: string[]
  archived: boolean
  createdAt: string
  updatedAt: string
}

export interface AzureBranch {
  id: string
  repositoryId: string
  name: string
  commitSha: string
  protected: boolean
  createdAt: string
}

export interface AzureCommit {
  sha: string
  repositoryId: string
  branch: string
  message: string
  author: string
  committer: string
  parents: string[]
  timestamp: string
}

export interface AzurePullRequest {
  id: string
  repositoryId: string
  title: string
  description: string
  sourceBranch: string
  targetBranch: string
  author: string
  reviewers: string[]
  status: "active" | "completed" | "abandoned"
  mergeStatus: "conflicts" | "succeeded" | "not_set"
  createdAt: string
  updatedAt: string
  closedAt: string | null
}

export interface AzureArtifact {
  id: string
  pipelineRunId: string
  name: string
  type: string
  sizeBytes: number
  retentionDays: number
  createdAt: string
}

export interface AzurePackage {
  id: string
  feedId: string
  name: string
  version: string
  description: string
  packageType: "npm" | "nuget" | "maven" | "pypi" | "generic"
  published: boolean
  createdAt: string
  updatedAt: string
}

export interface AzureFeed {
  id: string
  projectId: string
  name: string
  description: string
  packages: string[]
  upstreamSources: string[]
  createdAt: string
  updatedAt: string
}

export interface AzureTestPlan {
  id: string
  projectId: string
  name: string
  description: string
  suites: string[]
  createdAt: string
  updatedAt: string
}

export interface AzureTestSuite {
  id: string
  testPlanId: string
  name: string
  description: string
  testCases: string[]
  createdAt: string
  updatedAt: string
}

export interface AzureTestCase {
  id: string
  testSuiteId: string
  title: string
  description: string
  steps: string[]
  expectedResult: string
  status: TestStatus
  assignedTo: string | null
  createdAt: string
  updatedAt: string
}

export interface AzurePermission {
  resource: string
  access: PermissionLevel
  granted: boolean
}

export interface AzureRequest {
  id: string
  action: string
  resource: string
  body: Record<string, unknown>
  timestamp: string
}

export interface AzureResponse {
  id: string
  requestId: string
  success: boolean
  data: Record<string, unknown> | null
  errors: string[]
  timestamp: string
}

export interface AzureHealth {
  status: "healthy" | "degraded" | "unhealthy" | "unknown"
  state: string
  uptimeMs: number
  lastOperation: string | null
  lastError: string | null
}

export interface AzureMetrics {
  totalOrganizations: number
  totalProjects: number
  totalBoards: number
  totalPipelines: number
  totalRepositories: number
  totalArtifacts: number
  totalTestPlans: number
  operationsSucceeded: number
  operationsFailed: number
}