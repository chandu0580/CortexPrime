export enum TeamVisibility {
  PUBLIC = "public",
  PRIVATE = "private",
  ORG_WIDE = "org_wide",
}

export enum ChannelType {
  STANDARD = "standard",
  PRIVATE = "private",
  SHARED = "shared",
}

export enum PresenceStatus {
  AVAILABLE = "available",
  BUSY = "busy",
  DO_NOT_DISTURB = "do_not_disturb",
  AWAY = "away",
  OFFLINE = "offline",
  IN_A_MEETING = "in_a_meeting",
  IN_A_CALL = "in_a_call",
}

export enum MeetingStatus {
  SCHEDULED = "scheduled",
  ACTIVE = "active",
  ENDED = "ended",
  CANCELLED = "cancelled",
}

export enum WorkflowStatus {
  DRAFT = "draft",
  ACTIVE = "active",
  PAUSED = "paused",
  COMPLETED = "completed",
  FAILED = "failed",
}

export interface TeamsOrganization {
  id: string
  name: string
  displayName: string
  description: string
  tenantId: string
  teams: string[]
  archived: boolean
  createdAt: string
  updatedAt: string
}

export interface Team {
  id: string
  organizationId: string
  displayName: string
  description: string
  visibility: TeamVisibility
  members: TeamMember[]
  channels: string[]
  archived: boolean
  createdAt: string
  updatedAt: string
}

export interface TeamMember {
  id: string
  teamId: string
  userId: string
  displayName: string
  email: string
  role: "owner" | "member" | "guest"
  joinedAt: string
}

export interface TeamChannel {
  id: string
  teamId: string
  displayName: string
  description: string
  type: ChannelType
  members: string[]
  pinnedMessages: string[]
  archived: boolean
  createdAt: string
  updatedAt: string
}

export interface TeamMessage {
  id: string
  channelId: string
  userId: string
  displayName: string
  subject: string
  body: string
  messageType: "message" | "system" | "notification"
  parentMessageId: string | null
  mentions: TeamMention[]
  attachments: TeamAttachment[]
  pinned: boolean
  edited: boolean
  editedAt: string | null
  createdAt: string
  updatedAt: string
}

export interface TeamMention {
  id: string
  mentionedUserId: string
  mentionedDisplayName: string
  type: "user" | "team" | "channel" | "tag"
}

export interface TeamAttachment {
  id: string
  name: string
  contentType: string
  sizeBytes: number
  url: string
}

export interface TeamThread {
  id: string
  channelId: string
  parentMessageId: string
  replies: TeamReply[]
  replyCount: number
  createdAt: string
  updatedAt: string
}

export interface TeamReply {
  id: string
  threadId: string
  userId: string
  displayName: string
  body: string
  mentions: TeamMention[]
  attachments: TeamAttachment[]
  edited: boolean
  editedAt: string | null
  createdAt: string
  updatedAt: string
}

export interface TeamMeeting {
  id: string
  teamId: string
  channelId: string
  organizerId: string
  subject: string
  description: string
  status: MeetingStatus
  startTime: string
  endTime: string | null
  participants: MeetingParticipant[]
  recording: MeetingRecording | null
  joinUrl: string
  createdAt: string
  updatedAt: string
}

export interface MeetingParticipant {
  id: string
  meetingId: string
  userId: string
  displayName: string
  email: string
  role: "organizer" | "presenter" | "attendee"
  joinedAt: string | null
  leftAt: string | null
}

export interface MeetingRecording {
  id: string
  meetingId: string
  url: string
  durationSeconds: number
  createdBy: string
  createdAt: string
}

export interface Presence {
  id: string
  userId: string
  status: PresenceStatus
  activity: string
  lastSeenAt: string | null
  updatedAt: string
}

export interface TeamsNotification {
  id: string
  organizationId: string
  teamId: string
  channelId: string
  userId: string
  title: string
  body: string
  priority: "low" | "normal" | "high" | "urgent"
  delivered: boolean
  readAt: string | null
  createdAt: string
}

export interface Workflow {
  id: string
  organizationId: string
  name: string
  description: string
  steps: WorkflowStep[]
  status: WorkflowStatus
  createdAt: string
  updatedAt: string
}

export interface WorkflowStep {
  id: string
  workflowId: string
  name: string
  type: string
  config: Record<string, unknown>
  position: number
}

export interface TeamsPermission {
  resource: string
  access: "read" | "write" | "admin" | "none"
  granted: boolean
}

export interface TeamsRequest {
  id: string
  action: string
  resource: string
  body: Record<string, unknown>
  timestamp: string
}

export interface TeamsResponse {
  id: string
  requestId: string
  success: boolean
  data: Record<string, unknown> | null
  errors: string[]
  timestamp: string
}

export interface TeamsHealth {
  status: "healthy" | "degraded" | "unhealthy" | "unknown"
  state: string
  uptimeMs: number
  lastOperation: string | null
  lastError: string | null
}

export interface TeamsMetrics {
  totalOrganizations: number
  totalTeams: number
  totalChannels: number
  totalMessages: number
  totalMeetings: number
  totalNotifications: number
  totalWorkflows: number
  operationsSucceeded: number
  operationsFailed: number
}