export type EventCategory =
  | "kernel"
  | "mission"
  | "runtime"
  | "worker"
  | "task"
  | "scheduler"
  | "resource"
  | "capability"
  | "governance"
  | "memory"
  | "analytics"
  | "learning"
  | "browser"
  | "voice"
  | "research"
  | "connector"
  | "application"
  | "reasoning"
  | "cognition"
  | "planning"
  | "execution"
  | "knowledge"
  | "intelligence"
  | "world"
  | "platform"
  | "lifecycle"
  | "telemetry"
  | "assembly"
  | "bootstrap"
  | "composition"
  | "shutdown"
  | "startup"
  | "validation"

export type EventPriority = "critical" | "high" | "normal" | "low"

export type DeliveryStatus = "pending" | "delivered" | "failed" | "filtered"

export type ChannelType = "broadcast" | "direct" | "workqueue"

export interface CortexEvent {
  id: string
  category: EventCategory
  type: string
  source: string
  data: Record<string, unknown>
  timestamp: string
}

export interface EventEnvelope {
  event: CortexEvent
  envelopeId: string
  correlationId: string
  channel: string
  priority: EventPriority
  ttl: number
  publishedAt: string
}

export interface EventChannel {
  id: string
  name: string
  category: EventCategory
  type: ChannelType
  description: string
  created_at: string
}

export interface EventSubscription {
  id: string
  channelId: string
  handlerId: string
  handlerName: string
  filter: EventFilter | null
  createdAt: string
  active: boolean
}

export interface EventHandler {
  id: string
  name: string
  description: string
  handle: (event: CortexEvent) => Promise<void>
}

export interface EventFilter {
  id: string
  categories: EventCategory[] | null
  types: string[] | null
  sources: string[] | null
  priorityMin: EventPriority | null
}

export interface EventDelivery {
  id: string
  envelopeId: string
  subscriptionId: string
  handlerId: string
  status: DeliveryStatus
  attemptedAt: string
  completedAt: string | null
  error: string | null
  durationMs: number | null
}

export interface EventHistoryEntry {
  envelope: EventEnvelope
  deliveryCount: number
  completedDeliveries: number
  failedDeliveries: number
  firstAttemptedAt: string
  lastAttemptedAt: string
}

export interface EventMetrics {
  totalPublished: number
  totalDelivered: number
  totalFailed: number
  totalFiltered: number
  activeSubscriptions: number
  activeHandlers: number
  registeredChannels: number
  historySize: number
  eventsByCategory: Record<string, number>
  averageDeliveryMs: number
}
