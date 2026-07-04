export enum ChannelType {
  PUBLIC = "public",
  PRIVATE = "private",
  DIRECT_MESSAGE = "direct_message",
  MULTIPARTY_DM = "multiparty_dm",
}

export enum MessageType {
  STANDARD = "standard",
  THREAD_REPLY = "thread_reply",
  EPHEMERAL = "ephemeral",
  SYSTEM = "system",
}

export enum NotificationPriority {
  LOW = "low",
  NORMAL = "normal",
  HIGH = "high",
  URGENT = "urgent",
}

export enum WorkflowStatus {
  DRAFT = "draft",
  ACTIVE = "active",
  PAUSED = "paused",
  COMPLETED = "completed",
  FAILED = "failed",
}

export enum UserPresence {
  ONLINE = "online",
  AWAY = "away",
  OFFLINE = "offline",
  DO_NOT_DISTURB = "do_not_disturb",
}

export interface SlackWorkspace {
  id: string
  name: string
  domain: string
  description: string
  channels: string[]
  users: string[]
  userGroups: string[]
  archived: boolean
  createdAt: string
  updatedAt: string
}

export interface SlackChannel {
  id: string
  workspaceId: string
  name: string
  topic: string
  purpose: string
  type: ChannelType
  members: string[]
  pinnedMessages: string[]
  archived: boolean
  createdAt: string
  updatedAt: string
}

export interface SlackMessage {
  id: string
  channelId: string
  userId: string
  text: string
  type: MessageType
  threadId: string | null
  mentions: SlackMention[]
  attachments: SlackAttachment[]
  reactions: SlackReaction[]
  pinned: boolean
  edited: boolean
  editedAt: string | null
  createdAt: string
  updatedAt: string
}

export interface SlackThread {
  id: string
  channelId: string
  parentMessageId: string
  replies: SlackReply[]
  replyCount: number
  closed: boolean
  createdAt: string
  updatedAt: string
}

export interface SlackReply {
  id: string
  threadId: string
  userId: string
  text: string
  mentions: SlackMention[]
  attachments: SlackAttachment[]
  reactions: SlackReaction[]
  createdAt: string
  updatedAt: string
}

export interface SlackUser {
  id: string
  workspaceId: string
  name: string
  displayName: string
  email: string
  presence: UserPresence
  isAdmin: boolean
  isBot: boolean
  timezone: string
  avatarUrl: string
  createdAt: string
  updatedAt: string
}

export interface SlackUserGroup {
  id: string
  workspaceId: string
  name: string
  handle: string
  description: string
  members: string[]
  createdAt: string
  updatedAt: string
}

export interface SlackNotification {
  id: string
  workspaceId: string
  channelId: string
  userId: string
  title: string
  body: string
  priority: NotificationPriority
  delivered: boolean
  readAt: string | null
  createdAt: string
}

export interface SlackReaction {
  id: string
  emoji: string
  userIds: string[]
  count: number
}

export interface SlackWorkflow {
  id: string
  workspaceId: string
  name: string
  description: string
  steps: SlackWorkflowStep[]
  status: WorkflowStatus
  createdAt: string
  updatedAt: string
}

export interface SlackWorkflowStep {
  id: string
  workflowId: string
  name: string
  type: string
  config: Record<string, unknown>
  position: number
}

export interface SlackMention {
  id: string
  userId: string
  type: "user" | "channel" | "here" | "everyone"
  startIndex: number
  endIndex: number
}

export interface SlackAttachment {
  id: string
  title: string
  text: string
  color: string
  imageUrl: string
  thumbUrl: string
  fields: Record<string, string>[]
  actions: SlackAttachmentAction[]
}

export interface SlackAttachmentAction {
  id: string
  name: string
  text: string
  type: "button" | "select" | "overflow"
  url: string
  value: string
  style: "default" | "primary" | "danger"
}

export interface SlackPermission {
  resource: string
  access: "read" | "write" | "admin" | "none"
  granted: boolean
}

export interface SlackRequest {
  id: string
  action: string
  resource: string
  body: Record<string, unknown>
  timestamp: string
}

export interface SlackResponse {
  id: string
  requestId: string
  success: boolean
  data: Record<string, unknown> | null
  errors: string[]
  timestamp: string
}

export interface SlackHealth {
  status: "healthy" | "degraded" | "unhealthy" | "unknown"
  state: string
  uptimeMs: number
  lastOperation: string | null
  lastError: string | null
}

export interface SlackMetrics {
  totalWorkspaces: number
  totalChannels: number
  totalMessages: number
  totalThreads: number
  totalUsers: number
  totalNotifications: number
  totalWorkflows: number
  operationsSucceeded: number
  operationsFailed: number
}