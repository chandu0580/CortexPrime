import type { TaskBatch, ExecutionTask, BatchStatus } from "./types"
import { generateId } from "./shared"

const batches = new Map<string, TaskBatch>()

export const TaskBatchManager = {
  async createBatch(
    sessionId: string,
    name: string,
    description: string,
    tasks: ExecutionTask[] = [],
  ): Promise<TaskBatch> {
    const batch: TaskBatch = {
      id: generateId("batch"),
      sessionId,
      name,
      description,
      tasks,
      status: "preparing",
      totalTasks: tasks.length,
      completedTasks: 0,
      failedTasks: 0,
      createdAt: new Date().toISOString(),
      completedAt: null,
    }
    batches.set(batch.id, batch)
    return batch
  },

  async getBatch(batchId: string): Promise<TaskBatch | null> {
    return batches.get(batchId) ?? null
  },

  async addTaskToBatch(batchId: string, task: ExecutionTask): Promise<TaskBatch> {
    const batch = batches.get(batchId)
    if (!batch) throw new Error(`Batch not found: ${batchId}`)
    const updated: TaskBatch = {
      ...batch,
      tasks: [...batch.tasks, task],
      totalTasks: batch.totalTasks + 1,
    }
    batches.set(batchId, updated)
    return updated
  },

  async evaluateBatch(batchId: string): Promise<TaskBatch> {
    const batch = batches.get(batchId)
    if (!batch) throw new Error(`Batch not found: ${batchId}`)

    const completed = batch.tasks.filter((t) => t.state === "COMPLETED").length
    const failed = batch.tasks.filter((t) => t.state === "FAILED").length
    const cancelled = batch.tasks.filter((t) => t.state === "CANCELLED").length
    const active = batch.tasks.filter((t) => !["COMPLETED", "FAILED", "CANCELLED"].includes(t.state)).length

    let status: BatchStatus
    if (active === 0 && failed === 0 && cancelled === 0) {
      status = "completed"
    } else if (active === 0 && failed > 0 && completed === 0) {
      status = "failed"
    } else if (active === 0 && failed > 0) {
      status = "partial"
    } else if (active > 0) {
      status = "running"
    } else {
      status = "preparing"
    }

    const updated: TaskBatch = {
      ...batch,
      status,
      completedTasks: completed,
      failedTasks: failed + cancelled,
      completedAt: active === 0 ? new Date().toISOString() : batch.completedAt,
    }
    batches.set(batchId, updated)
    return updated
  },

  async getSessionBatches(sessionId: string): Promise<TaskBatch[]> {
    return Array.from(batches.values()).filter((b) => b.sessionId === sessionId)
  },

  async getAllBatches(): Promise<TaskBatch[]> {
    return Array.from(batches.values())
  },
}
