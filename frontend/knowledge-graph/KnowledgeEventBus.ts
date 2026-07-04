import type { IEventBus } from "@/platform/interfaces"

export type KnowledgeEventType =
  | "knowledge.graph.initialized"
  | "knowledge.graph.shutdown"
  | "knowledge.entity.registered"
  | "knowledge.entity.updated"
  | "knowledge.entity.removed"
  | "knowledge.relationship.created"
  | "knowledge.relationship.removed"
  | "knowledge.traversal.completed"
  | "knowledge.inference.completed"
  | "knowledge.validation.completed"
  | "knowledge.validation.issues"

export interface KnowledgeEvent {
  type: KnowledgeEventType
  timestamp: string
  payload: Record<string, unknown>
}

export type KnowledgeEventCallback = (event: KnowledgeEvent) => void

export const KnowledgeEventBus = {
  async publish(eventBus: IEventBus, type: KnowledgeEventType, payload: Record<string, unknown>): Promise<void> {
    const event: KnowledgeEvent = {
      type,
      timestamp: new Date().toISOString(),
      payload,
    }

    await eventBus.publish("knowledge", type, payload)
    return event as unknown as Promise<void>
  },
}
