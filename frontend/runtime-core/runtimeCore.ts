import type { MissionSession } from "@/cortex-kernel/types"
import type {
  ExecutionSession,
  ExecutionWorker,
  ExecutionTask,
  ExecutionCheckpoint,
  ExecutionHeartbeat,
  ExecutionState,
  WorkerCapability,
  FailureRecord,
  RetryPolicy,
  WorkerAssignment,
  RuntimeEvent,
  RuntimeMetrics,
} from "./types"
import { ExecutionSessionManager } from "./ExecutionSessionManager"
import { WorkerRegistry } from "./WorkerRegistry"
import { WorkerScheduler } from "./WorkerScheduler"
import { ExecutionLifecycle } from "./ExecutionLifecycle"
import { HeartbeatManager } from "./HeartbeatManager"
import { FailureRecovery } from "./FailureRecovery"
import { RetryCoordinator } from "./RetryCoordinator"
import { RuntimeTelemetry } from "./RuntimeTelemetry"
import { generateId } from "./shared"

export const runtimeCore = {
  async createExecutionSession(kernelSession: MissionSession): Promise<ExecutionSession> {
    const session = await ExecutionSessionManager.createSession(kernelSession)
    await RuntimeTelemetry.emitEvent(session.id, "session", "session.created", `Execution session created from kernel session: ${kernelSession.id}`)
    return session
  },

  async registerWorker(
    name: string,
    version: string,
    capability: WorkerCapability,
    metadata: Record<string, string> = {},
  ): Promise<ExecutionWorker> {
    const worker = await WorkerRegistry.registerWorker(name, version, capability, metadata)
    await RuntimeTelemetry.emitEvent("system", "worker", "worker.registered", `Worker ${name} v${version} registered for capability: ${capability}`)
    return worker
  },

  async assignWorker(sessionId: string, capability: WorkerCapability, taskId: string): Promise<{
    session: ExecutionSession
    worker: ExecutionWorker
    assignment: WorkerAssignment
  }> {
    const session = await ExecutionSessionManager.getSession(sessionId)
    if (!session) throw new Error(`Execution session not found: ${sessionId}`)

    const result = await WorkerScheduler.assignWorker(session, capability, taskId)
    await ExecutionSessionManager.updateSession(sessionId, {
      state: result.session.state,
      workerId: result.session.workerId,
      worker: result.session.worker,
      assignment: result.session.assignment,
    })
    await RuntimeTelemetry.emitEvent(sessionId, "assignment", "worker.assigned", `Worker ${result.worker.name} assigned to task ${taskId}`)
    return result
  },

  async startExecution(sessionId: string): Promise<ExecutionSession> {
    const session = await ExecutionSessionManager.getSession(sessionId)
    if (!session) throw new Error(`Execution session not found: ${sessionId}`)

    const updated = await ExecutionLifecycle.transition(session, "RUNNING")
    await ExecutionSessionManager.updateSession(sessionId, { state: updated.state, updatedAt: updated.updatedAt })
    await RuntimeTelemetry.emitEvent(sessionId, "lifecycle", "execution.started", "Execution started")
    return updated
  },

  async pauseExecution(sessionId: string): Promise<ExecutionSession> {
    const session = await ExecutionSessionManager.getSession(sessionId)
    if (!session) throw new Error(`Execution session not found: ${sessionId}`)

    const updated = await ExecutionLifecycle.transition(session, "PAUSED")
    await ExecutionSessionManager.updateSession(sessionId, { state: updated.state, updatedAt: updated.updatedAt })
    await RuntimeTelemetry.emitEvent(sessionId, "lifecycle", "execution.paused", "Execution paused")
    return updated
  },

  async resumeExecution(sessionId: string): Promise<ExecutionSession> {
    const session = await ExecutionSessionManager.getSession(sessionId)
    if (!session) throw new Error(`Execution session not found: ${sessionId}`)

    const updated = await ExecutionLifecycle.transition(session, "RESUMED")
    await ExecutionSessionManager.updateSession(sessionId, { state: updated.state, updatedAt: updated.updatedAt })
    await RuntimeTelemetry.emitEvent(sessionId, "lifecycle", "execution.resumed", "Execution resumed")
    return updated
  },

  async cancelExecution(sessionId: string): Promise<ExecutionSession> {
    const session = await ExecutionSessionManager.getSession(sessionId)
    if (!session) throw new Error(`Execution session not found: ${sessionId}`)

    const updated = await ExecutionLifecycle.transition(session, "CANCELLED")
    await ExecutionSessionManager.updateSession(sessionId, { state: updated.state, completedAt: updated.completedAt })
    await WorkerScheduler.revokeAssignment(sessionId)
    await RuntimeTelemetry.emitEvent(sessionId, "lifecycle", "execution.cancelled", "Execution cancelled")
    return updated
  },

  async recordCheckpoint(
    sessionId: string,
    taskId: string,
    name: string,
    description: string,
    order: number,
  ): Promise<ExecutionSession> {
    const session = await ExecutionSessionManager.getSession(sessionId)
    if (!session) throw new Error(`Execution session not found: ${sessionId}`)

    const checkpoint: ExecutionCheckpoint = {
      id: generateId("cp"),
      taskId,
      name,
      description,
      order,
      reached: true,
      reachedAt: new Date().toISOString(),
      metadata: null,
    }

    const updated = await ExecutionSessionManager.addCheckpoint(sessionId, checkpoint)
    await RuntimeTelemetry.emitEvent(sessionId, "checkpoint", "checkpoint.reached", `Checkpoint reached: ${name}`, { taskId, checkpointId: checkpoint.id })
    return updated
  },

  async recordHeartbeat(
    workerId: string,
    sessionId: string,
    taskId: string,
    status: "alive" | "degraded" | "stuck" = "alive",
  ): Promise<ExecutionHeartbeat> {
    const heartbeat = await HeartbeatManager.recordHeartbeat(workerId, sessionId, taskId, status)
    return heartbeat
  },

  async retryExecution(sessionId: string, taskId: string): Promise<{
    session: ExecutionSession
    policy: RetryPolicy
    canRetry: boolean
  }> {
    const session = await ExecutionSessionManager.getSession(sessionId)
    if (!session) throw new Error(`Execution session not found: ${sessionId}`)

    const task = session.tasks.find((t) => t.id === taskId)
    if (!task) throw new Error(`Task not found: ${taskId}`)

    let policy = await RetryCoordinator.getPolicy(taskId)
    if (!policy) {
      policy = await RetryCoordinator.createPolicy(taskId, task.maxRetries)
    }

    const canRetry = await RetryCoordinator.canRetry(policy, "temporary_failure")
    if (canRetry) {
      const updatedPolicy = await RetryCoordinator.executeRetry(policy)
      const lifecycleUpdated = await ExecutionLifecycle.transition(session, "READY")
      await ExecutionSessionManager.updateSession(sessionId, { state: lifecycleUpdated.state })

      await RuntimeTelemetry.emitEvent(sessionId, "retry", "execution.retrying",
        `Retry ${updatedPolicy.retryCount}/${updatedPolicy.maxRetries} for task ${taskId}`,
      )

      return { session: lifecycleUpdated, policy: updatedPolicy, canRetry: true }
    }

    return { session, policy, canRetry: false }
  },

  async recoverExecution(sessionId: string, taskId: string): Promise<{
    session: ExecutionSession
    failure: FailureRecord
    recovered: boolean
    action: string
  }> {
    const session = await ExecutionSessionManager.getSession(sessionId)
    if (!session) throw new Error(`Execution session not found: ${sessionId}`)

    const task = session.tasks.find((t) => t.id === taskId)
    if (!task) throw new Error(`Task not found: ${taskId}`)

    const failure = await FailureRecovery.recordFailure(
      taskId,
      sessionId,
      session.workerId,
      "Execution failure during recovery attempt",
      "execution_error",
    )

    const result = await FailureRecovery.attemptRecovery(session, task, failure)

    if (result.recovered) {
      await FailureRecovery.markRetried(failure.id)
      await FailureRecovery.markRecovered(failure.id)
    }

    const lifecycleUpdated = await ExecutionLifecycle.transition(session, result.newState)
    await ExecutionSessionManager.updateSession(sessionId, { state: lifecycleUpdated.state })

    await RuntimeTelemetry.emitEvent(sessionId, "recovery", `execution.${result.recovered ? "recovered" : "failed"}`,
      result.action, { taskId, failureId: failure.id })

    return { session: lifecycleUpdated, failure, recovered: result.recovered, action: result.action }
  },

  async emitRuntimeEvent(
    sessionId: string,
    type: string,
    name: string,
    details: string,
    metadata?: Record<string, string>,
  ): Promise<RuntimeEvent> {
    return RuntimeTelemetry.emitEvent(sessionId, type, name, details, metadata ?? null)
  },

  async closeExecution(sessionId: string, finalState: "COMPLETED" | "FAILED" | "CANCELLED"): Promise<ExecutionSession> {
    const session = await ExecutionSessionManager.getSession(sessionId)
    if (!session) throw new Error(`Execution session not found: ${sessionId}`)

    const closed = await ExecutionSessionManager.closeSession(sessionId, finalState)
    await WorkerScheduler.releaseWorker(sessionId, finalState === "COMPLETED")
    await RuntimeTelemetry.emitEvent(sessionId, "session", `session.${finalState.toLowerCase()}`, `Execution session closed: ${finalState}`)

    return closed
  },

  async getMetrics(): Promise<RuntimeMetrics> {
    const sessionCounts = await ExecutionSessionManager.sessionCount()
    const workerCounts = await WorkerRegistry.getWorkerCounts()
    const totalHeartbeats = await HeartbeatManager.getHeartbeatCount()
    const allSessions = Array.from(
      (await ExecutionSessionManager.getActiveSessions()).values(),
    )
    const tasksRunning = allSessions.reduce(
      (sum, s) => sum + s.tasks.filter((t) => t.state === "running" || t.state === "assigned").length,
      0,
    )
    const tasksCompleted = allSessions.reduce(
      (sum, s) => sum + s.tasks.filter((t) => t.state === "completed").length,
      0,
    )
    const tasksFailed = allSessions.reduce(
      (sum, s) => sum + s.tasks.filter((t) => t.state === "failed").length,
      0,
    )

    return RuntimeTelemetry.getMetrics(
      sessionCounts.active,
      sessionCounts.total,
      workerCounts.busy,
      workerCounts.idle,
      workerCounts.total,
      tasksCompleted,
      tasksFailed,
      tasksRunning,
      totalHeartbeats,
    )
  },
}
