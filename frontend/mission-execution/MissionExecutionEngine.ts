import type { IEventBus, ITelemetry } from "@/platform/interfaces"
import type { CapabilityDefinition } from "@/capability-framework/types"
import type {
  ExecutionPlan, ExecutionRequest, ExecutionResponse,
  ExecutionMetrics, ExecutionHealth,
  DistributedTask,
} from "./types"
import { ExecutionSessionManager } from "./ExecutionSessionManager"
import { MissionDecompositionEngine } from "./MissionDecompositionEngine"
import { ExecutionPlanBuilder } from "./ExecutionPlanBuilder"
import { TaskDistributionEngine } from "./TaskDistributionEngine"
import { ExecutionStateManager } from "./ExecutionStateManager"
import { ExecutionValidationEngine } from "./ExecutionValidationEngine"
import { ExecutionPolicyEngine, type ExecutionPolicy } from "./ExecutionPolicyEngine"
import { ExecutionMetricsCollector } from "./ExecutionMetricsCollector"
import { ExecutionHealthManager } from "./ExecutionHealthManager"
import { MissionExecutionCapability } from "./MissionExecutionCapability"

const DEFAULT_POLICIES: ExecutionPolicy[] = [
  { id: "exec.default.allow", name: "Default Allow", description: "Default allow for execution operations", category: "general", effect: "allow", rules: [{ field: "action", operator: "exists", value: null, message: "" }], priority: 0, enabled: true },
  { id: "exec.concurrency.limit", name: "Concurrency Limit", description: "Maximum concurrent execution sessions", category: "concurrency", effect: "deny", rules: [{ field: "currentCount", operator: "gte", value: 10, message: "Maximum 10 concurrent execution sessions" }], priority: 100, enabled: true },
  { id: "exec.assignment.minimum", name: "Minimum Workers", description: "At least one worker required for task distribution", category: "assignment", effect: "deny", rules: [{ field: "workerCount", operator: "gte", value: 1, message: "At least one worker required" }], priority: 80, enabled: true },
]

export class MissionExecutionEngine {
  private readonly systemId: string
  private readonly eventBus: IEventBus
  private readonly telemetry: ITelemetry
  private readonly capabilityDefinition: CapabilityDefinition
  private initialized: boolean = false

  constructor(
    eventBus: IEventBus,
    telemetry: ITelemetry,
  ) {
    this.systemId = `mission-execution-${Date.now()}`
    this.eventBus = eventBus
    this.telemetry = telemetry

    const capability = new MissionExecutionCapability()
    this.capabilityDefinition = capability.toCapabilityDefinition()
  }

  async initialize(): Promise<void> {
    if (this.initialized) return

    await ExecutionMetricsCollector.initialize(this.systemId)
    await ExecutionHealthManager.initialize(this.systemId)

    for (const policy of DEFAULT_POLICIES) {
      await ExecutionPolicyEngine.registerPolicy(policy)
    }

    this.initialized = true

    await this.eventBus.publish("execution", "execution.engine.initialized", {
      systemId: this.systemId,
    })
  }

  async shutdown(): Promise<void> {
    await this.eventBus.publish("execution", "execution.engine.shutdown", {
      systemId: this.systemId,
    })
  }

  async executeMission(request: ExecutionRequest): Promise<ExecutionResponse> {
    const startTime = Date.now()
    this.requireInitialized()

    try {
      if (request.type !== "execute") {
        return this.createError("INVALID_REQUEST", `Cannot handle request type: ${request.type}`, startTime)
      }

      const session = await ExecutionSessionManager.createSession(request.missionId)
      await ExecutionMetricsCollector.recordSessionCreated(this.systemId)

      await this.eventBus.publish("execution", "execution.session.created", {
        systemId: this.systemId, sessionId: session.id, missionId: request.missionId,
      })

      await ExecutionSessionManager.updateStatus(session.id, "planning")

      const plan = await ExecutionPlanBuilder.createPlan(
        session.id, request.missionId, request.strategy, request.assignmentPolicy,
      )
      await ExecutionSessionManager.linkPlan(session.id, plan.id)
      await MissionDecompositionEngine.assignExecutionOrder(plan.id)
      const optimizedPlan = await ExecutionPlanBuilder.optimizePlan(plan.id)
      const finalizedPlan = await ExecutionPlanBuilder.finalizePlan(optimizedPlan.id)

      await ExecutionSessionManager.updateStage(session.id, "distribution")
      await ExecutionSessionManager.updateStatus(session.id, "distributing")

      const allTasks = this.collectTasksFromPlan(finalizedPlan)
      await TaskDistributionEngine.distributeTasks(allTasks, finalizedPlan.distributionStrategy)
      await ExecutionMetricsCollector.recordTasksDistributed(this.systemId, allTasks.length)

      await ExecutionSessionManager.updateStage(session.id, "dependency_check")
      await ExecutionSessionManager.updateStage(session.id, "validation")

      const checkpoint = await ExecutionValidationEngine.validateReadiness(session.id, finalizedPlan.id, "validation")
      if (checkpoint.ready) {
        await ExecutionMetricsCollector.recordValidationPass(this.systemId)
      } else {
        await ExecutionMetricsCollector.recordValidationFailure(this.systemId)
      }

      await ExecutionSessionManager.updateStage(session.id, "execution")
      await ExecutionSessionManager.updateStatus(session.id, "executing")

      await this.eventBus.publish("execution", "execution.session.ready", {
        systemId: this.systemId, sessionId: session.id, planId: finalizedPlan.id,
        taskCount: allTasks.length, ready: checkpoint.ready,
      })

      const updatedSession = await ExecutionSessionManager.getSession(session.id)

      return {
        success: true,
        session: updatedSession,
        plan: finalizedPlan,
        data: { taskCount: allTasks.length, ready: checkpoint.ready, checkpoint },
        error: null,
        durationMs: Date.now() - startTime,
        timestamp: new Date().toISOString(),
      }
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : String(err)
      await ExecutionMetricsCollector.recordSessionFailed(this.systemId)

      await this.eventBus.publish("execution", "execution.session.failed", {
        systemId: this.systemId, error: errorMsg,
      })

      return this.createError("EXECUTION_FAILED", errorMsg, startTime)
    }
  }

  async buildPlan(request: ExecutionRequest): Promise<ExecutionResponse> {
    const startTime = Date.now()
    this.requireInitialized()

    try {
      const session = await ExecutionSessionManager.getSession(request.sessionId ?? "")
      const plan = await ExecutionPlanBuilder.createPlan(
        request.sessionId ?? session?.id ?? "",
        request.missionId,
        request.strategy,
        request.assignmentPolicy,
      )
      const optimized = await ExecutionPlanBuilder.optimizePlan(plan.id)
      const finalized = await ExecutionPlanBuilder.finalizePlan(optimized.id)

      return {
        success: true,
        session: session,
        plan: finalized,
        data: { planId: finalized.id, phases: finalized.phases.length, tasks: finalized.totalTasks },
        error: null,
        durationMs: Date.now() - startTime,
        timestamp: new Date().toISOString(),
      }
    } catch (err) {
      return this.createError("PLAN_FAILED", err instanceof Error ? err.message : String(err), startTime)
    }
  }

  async distribute(request: ExecutionRequest): Promise<ExecutionResponse> {
    const startTime = Date.now()
    this.requireInitialized()

    try {
      const session = await ExecutionSessionManager.getSession(request.sessionId ?? "")
      if (!session) throw new Error(`Session ${request.sessionId} not found`)

      const plan = session.planId ? await MissionDecompositionEngine.getPlan(session.planId) : null
      if (!plan) throw new Error("No plan found for session")

      const allTasks = this.collectTasksFromPlan(plan)
      const assignments = await TaskDistributionEngine.distributeTasks(allTasks, plan.distributionStrategy)
      await ExecutionMetricsCollector.recordTasksDistributed(this.systemId, allTasks.length)

      return {
        success: true,
        session,
        plan,
        data: { assignments: assignments.length, tasks: allTasks.length },
        error: null,
        durationMs: Date.now() - startTime,
        timestamp: new Date().toISOString(),
      }
    } catch (err) {
      return this.createError("DISTRIBUTION_FAILED", err instanceof Error ? err.message : String(err), startTime)
    }
  }

  async validate(sessionId?: string): Promise<ExecutionResponse> {
    const startTime = Date.now()
    this.requireInitialized()

    try {
      if (!sessionId) {
        const sessions = await ExecutionSessionManager.getAll()
        return {
          success: true,
          session: null,
          plan: null,
          data: { sessionCount: sessions.length, sessions: sessions.map((s) => ({ id: s.id, status: s.status })) },
          error: null,
          durationMs: Date.now() - startTime,
          timestamp: new Date().toISOString(),
        }
      }

      const session = await ExecutionSessionManager.getSession(sessionId)
      if (!session) throw new Error(`Session ${sessionId} not found`)
      if (!session.planId) throw new Error("No plan for session")

      const checkpoint = await ExecutionValidationEngine.validateReadiness(sessionId, session.planId, session.currentStage)
      if (checkpoint.ready) {
        await ExecutionMetricsCollector.recordValidationPass(this.systemId)
      } else {
        await ExecutionMetricsCollector.recordValidationFailure(this.systemId)
      }

      return {
        success: checkpoint.ready,
        session,
        plan: await MissionDecompositionEngine.getPlan(session.planId),
        data: { checkpoint, ready: checkpoint.ready },
        error: checkpoint.ready ? null : "Validation checks not all passed",
        durationMs: Date.now() - startTime,
        timestamp: new Date().toISOString(),
      }
    } catch (err) {
      return this.createError("VALIDATION_FAILED", err instanceof Error ? err.message : String(err), startTime)
    }
  }

  async snapshot(sessionId: string): Promise<ExecutionResponse> {
    const startTime = Date.now()
    this.requireInitialized()

    try {
      const snap = await ExecutionStateManager.snapshot(sessionId)

      return {
        success: true,
        session: await ExecutionSessionManager.getSession(sessionId),
        plan: null,
        data: { snapshotId: snap.id, capturedAt: snap.capturedAt, status: snap.status },
        error: null,
        durationMs: Date.now() - startTime,
        timestamp: new Date().toISOString(),
      }
    } catch (err) {
      return this.createError("SNAPSHOT_FAILED", err instanceof Error ? err.message : String(err), startTime)
    }
  }

  async metrics(): Promise<ExecutionMetrics> {
    this.requireInitialized()
    return ExecutionMetricsCollector.collect(this.systemId)
  }

  async health(): Promise<ExecutionHealth> {
    this.requireInitialized()
    return ExecutionHealthManager.check(this.systemId)
  }

  private collectTasksFromPlan(plan: ExecutionPlan): DistributedTask[] {
    const tasks: DistributedTask[] = []
    for (const phase of plan.phases) {
      for (const stage of phase.stages) {
        tasks.push({
          id: `${plan.id}-task-${phase.order}-${stage.order}`,
          groupId: `${plan.id}-group-${phase.id}`,
          name: `Stage ${stage.name}`,
          description: `Execute ${stage.name} from phase ${phase.name}`,
          workerType: "orchestrator",
          requiredCapabilities: [stage.name],
          payload: { stage: stage.name, phase: phase.name, order: stage.order },
          priority: phase.order,
          dependencies: [],
          status: "pending",
          assignedWorkerId: null,
          createdAt: new Date().toISOString(),
          completedAt: null,
        })
      }
    }
    return tasks
  }

  private createError(code: string, message: string, startTime: number): ExecutionResponse {
    return {
      success: false,
      session: null,
      plan: null,
      data: null,
      error: `[${code}] ${message}`,
      durationMs: Date.now() - startTime,
      timestamp: new Date().toISOString(),
    }
  }

  private requireInitialized(): void {
    if (!this.initialized) {
      throw new Error("MissionExecutionEngine not initialized. Call initialize() first.")
    }
  }
}
