import type { TaskCheckpoint } from "./types"
import { generateId } from "./shared"

const checkpoints = new Map<string, TaskCheckpoint>()

export const TaskCheckpointManager = {
  async createCheckpoint(
    taskId: string,
    name: string,
    description: string,
    order: number,
    metadata: Record<string, string> | null = null,
  ): Promise<TaskCheckpoint> {
    const checkpoint: TaskCheckpoint = {
      id: generateId("cp"),
      taskId,
      name,
      description,
      order,
      reached: false,
      reachedAt: null,
      metadata,
    }
    checkpoints.set(checkpoint.id, checkpoint)
    return checkpoint
  },

  async markReached(checkpointId: string): Promise<TaskCheckpoint> {
    const cp = checkpoints.get(checkpointId)
    if (!cp) throw new Error(`Checkpoint not found: ${checkpointId}`)
    const updated: TaskCheckpoint = {
      ...cp,
      reached: true,
      reachedAt: new Date().toISOString(),
    }
    checkpoints.set(checkpointId, updated)
    return updated
  },

  async getCheckpoint(checkpointId: string): Promise<TaskCheckpoint | null> {
    return checkpoints.get(checkpointId) ?? null
  },

  async getTaskCheckpoints(taskId: string): Promise<TaskCheckpoint[]> {
    return Array.from(checkpoints.values())
      .filter((c) => c.taskId === taskId)
      .sort((a, b) => a.order - b.order)
  },

  async getReachedCheckpoints(taskId: string): Promise<TaskCheckpoint[]> {
    const all = await TaskCheckpointManager.getTaskCheckpoints(taskId)
    return all.filter((c) => c.reached)
  },

  async getProgress(taskId: string): Promise<{ completed: number; total: number; percent: number }> {
    const all = await TaskCheckpointManager.getTaskCheckpoints(taskId)
    const completed = all.filter((c) => c.reached).length
    return {
      completed,
      total: all.length,
      percent: all.length > 0 ? (completed / all.length) * 100 : 0,
    }
  },

  async getTotalCheckpointCount(): Promise<number> {
    return checkpoints.size
  },
}
