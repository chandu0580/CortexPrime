import type { TaskQueue, ExecutionTask } from "./types"
import { generateId } from "./shared"

const queues = new Map<string, TaskQueue>()

export const TaskQueueManager = {
  async createQueue(name: string, sessionId: string, capacity: number = 100): Promise<TaskQueue> {
    const queue: TaskQueue = {
      id: generateId("queue"),
      name,
      sessionId,
      tasks: [],
      capacity,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    }
    queues.set(queue.id, queue)
    return queue
  },

  async getQueue(queueId: string): Promise<TaskQueue | null> {
    return queues.get(queueId) ?? null
  },

  async enqueue(queueId: string, task: ExecutionTask): Promise<TaskQueue> {
    const queue = queues.get(queueId)
    if (!queue) throw new Error(`Queue not found: ${queueId}`)
    if (queue.tasks.length >= queue.capacity) throw new Error(`Queue ${queueId} at capacity (${queue.capacity})`)

    const updated: TaskQueue = {
      ...queue,
      tasks: [...queue.tasks, task],
      updatedAt: new Date().toISOString(),
    }
    queues.set(queueId, updated)
    return updated
  },

  async dequeue(queueId: string): Promise<{ task: ExecutionTask; queue: TaskQueue } | null> {
    const queue = queues.get(queueId)
    if (!queue) throw new Error(`Queue not found: ${queueId}`)
    if (queue.tasks.length === 0) return null

    const sorted = [...queue.tasks].sort((a, b) => b.priority - a.priority)
    const task = sorted[0]
    const remaining = queue.tasks.filter((t) => t.id !== task.id)

    const updated: TaskQueue = {
      ...queue,
      tasks: remaining,
      updatedAt: new Date().toISOString(),
    }
    queues.set(queueId, updated)
    return { task, queue: updated }
  },

  async peek(queueId: string): Promise<ExecutionTask | null> {
    const queue = queues.get(queueId)
    if (!queue || queue.tasks.length === 0) return null
    const sorted = [...queue.tasks].sort((a, b) => b.priority - a.priority)
    return sorted[0]
  },

  async removeTask(queueId: string, taskId: string): Promise<TaskQueue> {
    const queue = queues.get(queueId)
    if (!queue) throw new Error(`Queue not found: ${queueId}`)
    const updated: TaskQueue = {
      ...queue,
      tasks: queue.tasks.filter((t) => t.id !== taskId),
      updatedAt: new Date().toISOString(),
    }
    queues.set(queueId, updated)
    return updated
  },

  async getQueueDepth(queueId: string): Promise<number> {
    const queue = queues.get(queueId)
    return queue?.tasks.length ?? 0
  },

  async getSessionQueues(sessionId: string): Promise<TaskQueue[]> {
    return Array.from(queues.values()).filter((q) => q.sessionId === sessionId)
  },

  async getAllQueues(): Promise<TaskQueue[]> {
    return Array.from(queues.values())
  },
}
