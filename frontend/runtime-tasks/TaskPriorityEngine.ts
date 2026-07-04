import type { ExecutionTask, TaskPriority } from "./types"
import { generateId } from "./shared"

const priorities = new Map<string, TaskPriority>()

export const TaskPriorityEngine = {
  async assignPriority(task: ExecutionTask, dependencyCount: number = 0): Promise<TaskPriority> {
    const basePriority = task.priority
    const factors: string[] = []

    let adjustment = 0

    if (task.maxRetries > 0) {
      adjustment += 1
      factors.push("+1: retryable")
    }

    if (dependencyCount > 0) {
      adjustment += Math.min(dependencyCount, 3)
      factors.push(`+${Math.min(dependencyCount, 3)}: ${dependencyCount} dependents`)
    }

    if (task.timeout) {
      const timeoutMs = parseTimeout(task.timeout)
      if (timeoutMs < 60000) {
        adjustment += 2
        factors.push("+2: short timeout")
      }
    }

    const priority: TaskPriority = {
      taskId: task.id,
      basePriority,
      adjustedPriority: Math.max(0, Math.min(100, basePriority + adjustment)),
      factors,
    }
    priorities.set(task.id, priority)
    return priority
  },

  async getPriority(taskId: string): Promise<TaskPriority | null> {
    return priorities.get(taskId) ?? null
  },

  async calculateAdjusted(task: ExecutionTask, dependents: ExecutionTask[]): Promise<number> {
    const p = await TaskPriorityEngine.assignPriority(task, dependents.length)
    return p.adjustedPriority
  },

  async sortByPriority(tasks: ExecutionTask[]): Promise<ExecutionTask[]> {
    return [...tasks].sort((a, b) => {
      const pa = priorities.get(a.id)?.adjustedPriority ?? a.priority
      const pb = priorities.get(b.id)?.adjustedPriority ?? b.priority
      return pb - pa
    })
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
