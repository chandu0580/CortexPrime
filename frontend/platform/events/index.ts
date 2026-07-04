import type { PlatformError } from "../contracts"

export type EventChannelType = "broadcast" | "direct" | "workqueue"

export type EventDeliveryGuarantee = "at-most-once" | "at-least-once" | "exactly-once"

export interface EventSubscriptionFilter {
  types: string[] | null
  sources: string[] | null
  priorityMin: number | null
}

export interface EventBusConfig {
  maxHistorySize: number
  defaultChannelType: EventChannelType
  deliveryGuarantee: EventDeliveryGuarantee
  enableRetry: boolean
}

export interface EventBusHealth {
  totalPublished: number
  totalDelivered: number
  totalFailed: number
  activeSubscriptions: number
  healthy: boolean
  lastError: PlatformError | null
}
