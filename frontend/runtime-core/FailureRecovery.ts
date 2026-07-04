import type { ExecutionSession, FailureRecord, ExecutionState, ExecutionTask } from "./types"
import { HeartbeatManager } from "./HeartbeatManager"
import { generateId } from "./shared"

const failures = new Map<string, FailureRecord>()

export const FailureRecovery = {
  async recordFailure(
    taskId: string,
    sessionId: string,
    workerId: string | null,
    error: string,
    errorType: string,
  ): Promise<FailureRecord> {
    const record: FailureRecord = {
      id: generateId("failure"),
      taskId,
      sessionId,
      workerId,
      error,
      errorType,
      occurredAt: new Date().toISOString(),
      recovered: false,
      recoveredAt: null,
      retryAttempted: false,
      retryCount: 0,
    }
    failures.set(record.id, record)
    return record
  },

  async getFailure(failureId: string): Promise<FailureRecord | null> {
    return failures.get(failureId) ?? null
  },

  async getSessionFailures(sessionId: string): Promise<FailureRecord[]> {
    return Array.from(failures.values()).filter((f) => f.sessionId === sessionId)
  },

  async getTaskFailures(taskId: string): Promise<FailureRecord[]> {
    return Array.from(failures.values()).filter((f) => f.taskId === taskId)
  },

  async markRecovered(failureId: string): Promise<FailureRecord> {
    const record = failures.get(failureId)
    if (!record) throw new Error(`Failure not found: ${failureId}`)
    const updated: FailureRecord = {
      ...record,
      recovered: true,
      recoveredAt: new Date().toISOString(),
    }
    failures.set(failureId, updated)
    return updated
  },

  async markRetried(failureId: string): Promise<FailureRecord> {
    const record = failures.get(failureId)
    if (!record) throw new Error(`Failure not found: ${failureId}`)
    const updated: FailureRecord = {
      ...record,
      retryAttempted: true,
      retryCount: record.retryCount + 1,
    }
    failures.set(failureId, updated)
    return updated
  },

  async attemptRecovery(
    session: ExecutionSession,
    task: ExecutionTask,
    failure: FailureRecord,
  ): Promise<{ recovered: boolean; newState: ExecutionState; action: string }> {
    const health = await HeartbeatManager.checkSessionHealth(session.id)

    if (health.stuck) {
      return {
        recovered: false,
        newState: "FAILED",
        action: "Worker appears stuck — cannot auto-recover",
      }
    }

    if (health.degraded) {
      return {
        recovered: false,
        newState: "PAUSED",
        action: "Worker degraded — pausing execution for manual review",
      }
    }

    if (task.retryCount < task.maxRetries) {
      return {
        recovered: true,
        newState: "READY",
        action: `Retrying task (attempt ${task.retryCount + 1}/${task.maxRetries})`,
      }
    }

    return {
      recovered: false,
      newState: "FAILED",
      action: "Max retries exceeded — execution failed",
    }
  },

  async getFailureCount(): Promise<number> {
    return failures.size
  },
}
