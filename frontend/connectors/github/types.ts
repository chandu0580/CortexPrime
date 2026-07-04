export type RepositoryVisibility = "public" | "private" | "internal"

export type PullRequestState = "open" | "closed" | "merged" | "draft"

export type IssueState = "open" | "closed" | "reopened" | "triage"

export type WorkflowStatus = "queued" | "in_progress" | "completed" | "failed" | "cancelled" | "skipped"

export type ReviewState = "approved" | "changes_requested" | "commented" | "dismissed" | "pending"

export interface GitHubRepository {
  id: string
  owner: string
  name: string
  fullName: string
  description: string
  visibility: RepositoryVisibility
  defaultBranch: string
  topics: string[]
  archived: boolean
  forked: boolean
  createdAt: string
  updatedAt: string
}

export interface GitHubBranch {
  id: string
  repositoryId: string
  name: string
  commitSha: string
  protected: boolean
  protectionRules: string[]
  createdAt: string
}

export interface GitHubCommit {
  sha: string
  repositoryId: string
  branch: string
  message: string
  author: string
  committer: string
  parents: string[]
  timestamp: string
}

export interface GitHubIssue {
  id: string
  repositoryId: string
  number: number
  title: string
  body: string
  state: IssueState
  author: string
  assignees: string[]
  labels: GitHubLabel[]
  milestone: GitHubMilestone | null
  comments: number
  locked: boolean
  createdAt: string
  updatedAt: string
  closedAt: string | null
}

export interface GitHubIssueComment {
  id: string
  issueId: string
  author: string
  body: string
  createdAt: string
  updatedAt: string
}

export interface GitHubLabel {
  id: string
  repositoryId: string
  name: string
  color: string
  description: string
}

export interface GitHubMilestone {
  id: string
  repositoryId: string
  number: number
  title: string
  description: string
  state: IssueState
  dueOn: string | null
  closedAt: string | null
  createdAt: string
  updatedAt: string
}

export interface GitHubPullRequest {
  id: string
  repositoryId: string
  number: number
  title: string
  body: string
  state: PullRequestState
  author: string
  headBranch: string
  baseBranch: string
  headSha: string
  baseSha: string
  assignees: string[]
  reviewers: string[]
  labels: GitHubLabel[]
  milestone: GitHubMilestone | null
  draft: boolean
  mergeable: boolean
  merged: boolean
  mergedBy: string | null
  comments: number
  reviewComments: number
  additions: number
  deletions: number
  createdAt: string
  updatedAt: string
  mergedAt: string | null
  closedAt: string | null
}

export interface GitHubReview {
  id: string
  pullRequestId: string
  author: string
  state: ReviewState
  body: string
  commitSha: string
  submittedAt: string
}

export interface GitHubCheckRun {
  id: string
  repositoryId: string
  name: string
  headSha: string
  status: WorkflowStatus
  conclusion: string | null
  startedAt: string
  completedAt: string | null
}

export interface GitHubWorkflow {
  id: string
  repositoryId: string
  name: string
  path: string
  state: "active" | "disabled" | "deleted"
  createdAt: string
  updatedAt: string
}

export interface GitHubActionRun {
  id: string
  workflowId: string
  repositoryId: string
  runNumber: number
  status: WorkflowStatus
  conclusion: string | null
  headBranch: string
  headSha: string
  triggeredBy: string
  startedAt: string
  completedAt: string | null
}

export interface GitHubRelease {
  id: string
  repositoryId: string
  tagName: string
  targetCommitish: string
  name: string
  body: string
  draft: boolean
  prerelease: boolean
  published: boolean
  author: string
  createdAt: string
  publishedAt: string | null
}

export interface GitHubTag {
  id: string
  repositoryId: string
  name: string
  commitSha: string
  message: string
  createdAt: string
}

export interface GitHubDiscussion {
  id: string
  repositoryId: string
  number: number
  title: string
  body: string
  author: string
  category: string
  locked: boolean
  answerChosen: boolean
  comments: number
  createdAt: string
  updatedAt: string
}

export interface GitHubProject {
  id: string
  repositoryId: string
  name: string
  body: string
  state: "open" | "closed"
  columns: GitHubColumn[]
  createdAt: string
  updatedAt: string
}

export interface GitHubColumn {
  id: string
  projectId: string
  name: string
  cards: GitHubCard[]
  createdAt: string
}

export interface GitHubCard {
  id: string
  columnId: string
  contentId: string | null
  contentType: string | null
  note: string | null
  position: number
  archived: boolean
  createdAt: string
}

export interface GitHubOrganization {
  id: string
  login: string
  name: string
  description: string
  avatarUrl: string
  members: GitHubMember[]
  createdAt: string
}

export interface GitHubMember {
  id: string
  login: string
  role: "admin" | "member" | "outside"
  permissions: GitHubPermission[]
  addedAt: string
}

export interface GitHubPermission {
  resource: string
  access: "read" | "write" | "admin" | "none"
  granted: boolean
}

export interface GitHubRequest {
  id: string
  method: string
  path: string
  body: Record<string, unknown>
  timestamp: string
}

export interface GitHubResponse {
  id: string
  requestId: string
  statusCode: number
  success: boolean
  data: Record<string, unknown> | null
  errors: string[]
  timestamp: string
}

export interface GitHubHealth {
  status: "healthy" | "degraded" | "unhealthy" | "unknown"
  state: string
  uptimeMs: number
  lastOperation: string | null
  lastError: string | null
}

export interface GitHubMetrics {
  totalRepositories: number
  totalIssues: number
  totalPullRequests: number
  totalWorkflows: number
  totalReleases: number
  totalDiscussions: number
  activeProjects: number
  operationsSucceeded: number
  operationsFailed: number
}
