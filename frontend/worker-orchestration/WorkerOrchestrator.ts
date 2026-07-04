import type { IEventBus, ITelemetry } from "@/platform/interfaces"
import type { WorkerRequest, WorkerResponse, WorkerSession, SynchronizationStrategy } from "./types"
import { WorkerSessionManager } from "./WorkerSessionManager"
import { WorkerCoordinator } from "./WorkerCoordinator"
import { WorkerAssignmentEngine } from "./WorkerAssignmentEngine"
import { WorkerSynchronizationEngine } from "./WorkerSynchronizationEngine"
import { WorkerLifecycleManager } from "./WorkerLifecycleManager"
import { WorkerRecoveryEngine } from "./WorkerRecoveryEngine"
import { WorkerPolicyEngine } from "./WorkerPolicyEngine"
import { WorkerValidationEngine } from "./WorkerValidationEngine"
import { WorkerMetricsCollector } from "./WorkerMetricsCollector"
import { WorkerHealthManager } from "./WorkerHealthManager"

type eventName = "worker.session.created" | "worker.session.completed" | "worker.session.failed" | "worker.execution.started" | "worker.execution.completed" | "worker.assignment.created" | "worker.synchronization.completed" | "worker.recovery.attempted" | "worker.health.changed"

export class WorkerOrchestrator {
  public readonly name = "WorkerOrchestrator"
  public readonly version = "1.0.0"
  public initialized = false

  private eventBus: IEventBus
  private telemetry: ITelemetry

  public SessionManager = WorkerSessionManager
  public Coordinator = WorkerCoordinator
  public AssignmentEngine = WorkerAssignmentEngine
  public SynchronizationEngine = WorkerSynchronizationEngine
  public LifecycleManager = WorkerLifecycleManager
  public RecoveryEngine = WorkerRecoveryEngine
  public PolicyEngine = WorkerPolicyEngine
  public ValidationEngine = WorkerValidationEngine
  public MetricsCollector = WorkerMetricsCollector
  public HealthManager = WorkerHealthManager

  constructor(eventBus: IEventBus, telemetry: ITelemetry) {
    this.eventBus = eventBus
    this.telemetry = telemetry
  }

  async initialize(): Promise<void> {
    this.initialized = true
    await this.emit("worker.health.changed", { status: "healthy", message: "WorkerOrchestrator initialized" })
    await this.telemetry.recordEvent("WorkerOrchestrator.initialized", {})
  }

  async shutdown(): Promise<void> {
    this.initialized = false
    await this.emit("worker.health.changed", { status: "stopped", message: "WorkerOrchestrator shut down" })
    await this.telemetry.recordEvent("WorkerOrchestrator.shutdown", {})
  }

  async process(request: WorkerRequest): Promise<WorkerResponse> {
    const start = Date.now()
    try {
      switch (request.type) {
        case "orchestrate":
          return await this.handleOrchestrate(request)
        case "assign":
          return await this.handleAssign(request)
        case "synchronize":
          return await this.handleSynchronize(request)
        case "validate":
          return await this.handleValidate(request)
        case "recover":
          return await this.handleRecover(request)
        case "inspect":
          return await this.handleInspect(request)
        default:
          return this.error("Unknown request type", start)
      }
    } catch (err: unknown) {
      return this.error(err instanceof Error ? err.message : String(err), start)
    }
  }

  private async handleOrchestrate(request: WorkerRequest): Promise<WorkerResponse> {
    const start = Date.now()
    if (!request.missionId) return this.error("missionId is required for orchestrate", Date.now())

    const session = await WorkerSessionManager.createSession(request.id ?? "default", request.missionId)
    await this.emit("worker.session.created", { sessionId: session.id, missionId: request.missionId })

    if (request.workerIds && request.workerIds.length > 0) {
      for (const wid of request.workerIds) {
        await WorkerSessionManager.addWorker(session.id, wid)
        const execution = await WorkerCoordinator.coordinateExecution(session.id, wid, request.id)
        await this.emit("worker.execution.started", { executionId: execution.id, workerId: wid, sessionId: session.id })

        const strategy = request.assignmentStrategy ?? "least_loaded"
        await WorkerAssignmentEngine.assignWorker(session.id, wid, request.workerType ?? "", request.id, request.task ?? "", request.capabilities ?? [], strategy)
        await this.emit("worker.assignment.created", { sessionId: session.id, workerId: wid })
      }
    }

    await WorkerSessionManager.updateSession(session.id, { status: "executing" })
    return this.success(session, { session }, start)
  }

  private async handleAssign(request: WorkerRequest): Promise<WorkerResponse> {
    if (!request.sessionId || !request.workerIds || !request.task) {
      return this.error("sessionId, workerIds, and task are required for assign", Date.now())
    }

    const assignments = []
    for (const wid of request.workerIds) {
      const assignment = await WorkerAssignmentEngine.assignWorker(
        request.sessionId, wid, request.workerType ?? "", request.id, request.task,
        request.capabilities ?? [], request.assignmentStrategy ?? "least_loaded",
      )
      assignments.push(assignment)
    }

    return this.success(null, { assignments }, Date.now())
  }

  private async handleSynchronize(request: WorkerRequest): Promise<WorkerResponse> {
    if (!request.sessionId || !request.workerIds) {
      return this.error("sessionId and workerIds are required for synchronize", Date.now())
    }

    const strategy: SynchronizationStrategy = request.strategy ?? "barrier"

    if (strategy === "barrier") {
      const barrier = await WorkerSynchronizationEngine.createBarrier(request.sessionId, "sync-barrier", request.workerIds)
      for (const wid of request.workerIds) {
        await WorkerSynchronizationEngine.waitForBarrier(barrier.id, wid)
        await this.emit("worker.synchronization.completed", { barrierId: barrier.id, workerId: wid, sessionId: request.sessionId })
      }
      return this.success(null, { barrier, released: true }, Date.now())
    }

    const sync = await WorkerSynchronizationEngine.createSynchronization(request.sessionId, "sync-group", strategy, request.workerIds.length)
    for (const wid of request.workerIds) {
      await WorkerSynchronizationEngine.synchronizeWorkers(sync.id)
      await this.emit("worker.synchronization.completed", { syncId: sync.id, workerId: wid, sessionId: request.sessionId })
    }

    return this.success(null, { synchronization: sync }, Date.now())
  }

  private async handleValidate(request: WorkerRequest): Promise<WorkerResponse> {
    if (!request.sessionId || !request.workerIds) {
      return this.error("sessionId and workerIds are required for validate", Date.now())
    }

    const validations = []
    for (const wid of request.workerIds) {
      const validation = await WorkerValidationEngine.validateWorker(request.sessionId, wid)
      validations.push(validation)
    }

    const consistent = validations.every((v) => v.consistent)
    return this.success(null, { validations, consistent }, Date.now())
  }

  private async handleRecover(request: WorkerRequest): Promise<WorkerResponse> {
    if (!request.sessionId || !request.workerIds) {
      return this.error("sessionId and workerIds are required for recover", Date.now())
    }

    const snapshot = await WorkerRecoveryEngine.captureSnapshot(request.sessionId)
    const recoveries = []

    for (const wid of request.workerIds) {
      const recovery = await WorkerRecoveryEngine.recordRecovery(request.sessionId, wid, "manual", "Manual recovery initiated", 3)
      const attempted = await WorkerRecoveryEngine.attemptRecovery(recovery.id)
      recoveries.push({ workerId: wid, recoveryId: recovery.id, recovered: attempted })
      await this.emit("worker.recovery.attempted", { recoveryId: recovery.id, workerId: wid, recovered: attempted, sessionId: request.sessionId })
    }

    return this.success(null, { snapshot, recoveries }, Date.now())
  }

  private async handleInspect(request: WorkerRequest): Promise<WorkerResponse> {
    void request
    const metrics = await WorkerMetricsCollector.collectMetrics()
    const health = await WorkerHealthManager.checkHealth()
    const workers = await WorkerCoordinator.getAllWorkers()
    const sessions = await WorkerSessionManager.getAll()
    const policies = await WorkerPolicyEngine.getAllPolicies()

    return this.success(null, { metrics, health, workers, sessions, policies }, Date.now())
  }

  private async emit(event: eventName, data: Record<string, unknown>): Promise<void> {
    await this.eventBus.publish(event, "worker-orchestration", data)
  }

  private success(session: WorkerSession | null, data: Record<string, unknown> | null, startMs: number): WorkerResponse {
    return {
      success: true,
      session,
      data,
      error: null,
      durationMs: Date.now() - startMs,
      timestamp: new Date().toISOString(),
    }
  }

  private error(message: string, startMs: number): WorkerResponse {
    return {
      success: false,
      session: null,
      data: null,
      error: message,
      durationMs: Date.now() - startMs,
      timestamp: new Date().toISOString(),
    }
  }
}
