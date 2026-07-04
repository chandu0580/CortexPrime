import type { ExecutionTask, TaskQueue, TaskBatch, TaskDependency, TaskAssignment, TaskCheckpoint, TaskResult, TaskMetrics, TaskState } from "./types"
import { TaskQueueManager } from "./TaskQueueManager"
import { TaskLifecycle } from "./TaskLifecycle"
import { TaskDependencyResolver } from "./TaskDependencyResolver"
import { TaskBatchManager } from "./TaskBatchManager"
import { TaskPriorityEngine } from "./TaskPriorityEngine"
import { TaskAssignmentManager } from "./TaskAssignmentManager"
import { TaskCheckpointManager } from "./TaskCheckpointManager"
import { TaskMetricsCollector } from "./TaskMetricsCollector"
import { generateId } from "./shared"

export const taskExecutionEngine = {
  async createTask(
    sessionId: string,
    name: string,
    description: string,
    priority: number = 5,
    maxRetries: number = 0,
    timeout: string = "300000ms",
    metadata: Record<string, string> = {},
  ): Promise<ExecutionTask> {
    const task: ExecutionTask = {
      id: generateId("task"),
      sessionId,
      batchId: null,
      name,
      description,
      state: "CREATED",
      priority,
      workerId: null,
      dependencies: [],
      checkpoints: [],
      result: null,
      retryCount: 0,
      maxRetries,
      createdAt: new Date().toISOString(),
      startedAt: null,
      completedAt: null,
      timeout,
      metadata,
    }

    await TaskPriorityEngine.assignPriority(task)
    return task
  },

  async enqueueTask(task: ExecutionTask, queueId: string): Promise<TaskQueue> {
    const transitioned = await TaskLifecycle.transition(task, "QUEUED")
    const queue = await TaskQueueManager.enqueue(queueId, { ...task, state: transitioned.state })
    return queue
  },

  async dequeueTask(queueId: string): Promise<ExecutionTask | null> {
    const result = await TaskQueueManager.dequeue(queueId)
    if (!result) return null

    const transitioned = await TaskLifecycle.transition(result.task, "READY")
    return { ...result.task, state: transitioned.state }
  },

  async assignTask(taskId: string, workerId: string, sessionId: string): Promise<{ task: ExecutionTask; assignment: TaskAssignment }> {
    const task = await TaskLifecycle.transition(
      { id: taskId, state: "READY" } as ExecutionTask,
      "ASSIGNED",
    )

    const assignment = await TaskAssignmentManager.assign(workerId, taskId, sessionId)
    return { task, assignment }
  },

  async completeTask(taskId: string, result: TaskResult): Promise<ExecutionTask> {
    const task = { id: taskId, state: "RUNNING" } as ExecutionTask
    const transitioned = await TaskLifecycle.transition(task, "COMPLETED")
    return { ...transitioned, result }
  },

  async cancelTask(task: ExecutionTask): Promise<ExecutionTask> {
    const transitioned = await TaskLifecycle.transition(task, "CANCELLED")
    await TaskAssignmentManager.revokeSessionAssignments(task.sessionId)
    return transitioned
  },

  async retryTask(task: ExecutionTask): Promise<ExecutionTask> {
    if (task.retryCount >= task.maxRetries) {
      throw new Error(`Task ${task.id} has exhausted retries (${task.retryCount}/${task.maxRetries})`)
    }
    return {
      ...task,
      state: "QUEUED",
      retryCount: task.retryCount + 1,
      workerId: null,
      startedAt: null,
      completedAt: null,
    }
  },

  async splitTask(originalTask: ExecutionTask, subtaskNames: string[]): Promise<{
    parentTask: ExecutionTask
    subtasks: ExecutionTask[]
  }> {
    const parentTask = { ...originalTask, metadata: { ...originalTask.metadata, split: "true" } }

    const subtasks: ExecutionTask[] = subtaskNames.map((name, i) => ({
      id: generateId("task"),
      sessionId: originalTask.sessionId,
      batchId: originalTask.batchId,
      name,
      description: `Subtask of ${originalTask.name}`,
      state: "CREATED" as TaskState,
      priority: originalTask.priority,
      workerId: null,
      dependencies: i > 0
        ? [{ id: generateId("dep"), taskId: "", dependsOnTaskId: subtasks[i - 1].id, type: "hard" as const, satisfied: false, details: `Sequential subtask dependency` }]
        : [],
      checkpoints: [],
      result: null,
      retryCount: 0,
      maxRetries: originalTask.maxRetries,
      createdAt: new Date().toISOString(),
      startedAt: null,
      completedAt: null,
      timeout: originalTask.timeout,
      metadata: { ...originalTask.metadata, parentTaskId: originalTask.id },
    }))

    return { parentTask, subtasks }
  },

  async mergeTasks(tasks: ExecutionTask[]): Promise<ExecutionTask> {
    const first = tasks[0]
    const merged: ExecutionTask = {
      id: generateId("task"),
      sessionId: first.sessionId,
      batchId: first.batchId,
      name: `Merged: ${tasks.map((t) => t.name).join(", ")}`,
      description: `Merged from ${tasks.length} tasks`,
      state: "CREATED",
      priority: Math.max(...tasks.map((t) => t.priority)),
      workerId: null,
      dependencies: [],
      checkpoints: [],
      result: null,
      retryCount: 0,
      maxRetries: Math.max(...tasks.map((t) => t.maxRetries)),
      createdAt: new Date().toISOString(),
      startedAt: null,
      completedAt: null,
      timeout: tasks.reduce((longest, t) => {
        const tMs = parseTimeout(t.timeout)
        const lMs = parseTimeout(longest)
        return tMs > lMs ? t.timeout : longest
      }, "300000ms"),
      metadata: { mergedTaskIds: tasks.map((t) => t.id).join(",") },
    }
    return merged
  },

  async checkpointTask(taskId: string, name: string, description: string, order: number): Promise<TaskCheckpoint> {
    return TaskCheckpointManager.createCheckpoint(taskId, name, description, order)
  },

  async addDependency(taskId: string, dependsOnTaskId: string, type: "hard" | "soft" | "signal" = "hard"): Promise<TaskDependency> {
    return TaskDependencyResolver.addDependency(taskId, dependsOnTaskId, type)
  },

  async collectMetrics(): Promise<TaskMetrics> {
    const queues = await TaskQueueManager.getAllQueues()
    const allTasks = queues.flatMap((q) => q.tasks)
    return TaskMetricsCollector.collectMetrics(allTasks)
  },
}

function parseTimeout(timeout: string): number {
  const match = timeout.match(/^(\d+)(ms|s|m|h)$/)
  if (!match) return 300000
  const value = parseInt(match[1], 10)
  switch (match[2]) {
    case "ms": return value
    case "s": return value * 1000
    case "m": return value * 60000
    case "h": return value * 3600000
    default: return 300000
  }
}
