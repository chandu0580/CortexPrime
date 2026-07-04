import type { IEventBus, ITelemetry } from "@/platform/interfaces"
import type { CapabilityDefinition } from "@/capability-framework/types"
import type {
  CognitiveSession, CognitiveContext, CognitivePipelineExecution, CognitivePipelineDefinition,
  CognitiveRequest, CognitiveResponse, CognitiveMetrics, CognitiveHealth,
  CognitiveStage,
} from "./types"
import { CognitiveSessionManager } from "./CognitiveSessionManager"
import { CognitiveContextManager } from "./CognitiveContextManager"
import { CognitivePipeline } from "./CognitivePipeline"
import { WorkerCoordinationEngine } from "./WorkerCoordinationEngine"
import { CognitiveRoutingEngine } from "./CognitiveRoutingEngine"
import { CognitiveStateManager } from "./CognitiveStateManager"
import { CognitivePolicyEngine, type CognitivePolicy } from "./CognitivePolicyEngine"
import { CognitiveMetricsCollector } from "./CognitiveMetricsCollector"
import { CognitiveHealthManager } from "./CognitiveHealthManager"
import { CognitiveCapability } from "./CognitiveCapability"

const DEFAULT_POLICIES: CognitivePolicy[] = [
  { id: "cog.default.allow", name: "Default Allow", description: "Default allow for orchestration operations", category: "general", effect: "allow", rules: [{ field: "action", operator: "exists", value: null, message: "" }], priority: 0, enabled: true },
  { id: "cog.workers.required", name: "Workers Required", description: "At least one worker must be available for coordination", category: "availability", effect: "deny", rules: [{ field: "requiredWorkers", operator: "gte", value: 1, message: "At least one worker required for coordination" }], priority: 100, enabled: true },
  { id: "cog.memory.minimum", name: "Minimum Memory", description: "At least one memory entry required for context build", category: "memory", effect: "deny", rules: [{ field: "entryCount", operator: "gte", value: 1, message: "At least one memory entry required for context build" }], priority: 80, enabled: true },
]

export class CognitiveOrchestrator {
  private readonly systemId: string
  private readonly eventBus: IEventBus
  private readonly telemetry: ITelemetry
  private readonly capabilityDefinition: CapabilityDefinition
  private initialized: boolean = false

  constructor(
    eventBus: IEventBus,
    telemetry: ITelemetry,
  ) {
    this.systemId = `cognitive-orchestrator-${Date.now()}`
    this.eventBus = eventBus
    this.telemetry = telemetry

    const capability = new CognitiveCapability()
    this.capabilityDefinition = capability.toCapabilityDefinition()
  }

  async initialize(): Promise<void> {
    if (this.initialized) return

    await CognitiveMetricsCollector.initialize(this.systemId)
    await CognitiveHealthManager.initialize(this.systemId)

    for (const policy of DEFAULT_POLICIES) {
      await CognitivePolicyEngine.registerPolicy(policy)
    }

    this.initialized = true

    await this.eventBus.publish("cognition", "cognition.orchestrator.initialized", {
      systemId: this.systemId,
    })
  }

  async shutdown(): Promise<void> {
    await this.eventBus.publish("cognition", "cognition.orchestrator.shutdown", {
      systemId: this.systemId,
    })
  }

  async orchestrate(request: CognitiveRequest): Promise<CognitiveResponse> {
    const startTime = Date.now()
    this.requireInitialized()

    try {
      if (request.type !== "orchestrate") {
        return this.createError("INVALID_REQUEST", `CognitiveOrchestrator cannot handle request type: ${request.type}`, startTime)
      }

      const pipelineDef = await this.ensurePipeline(request)
      const context = await CognitiveContextManager.createContext("pending", request)
      const session = await CognitiveSessionManager.createSession(
        request.id, pipelineDef.id, context.id, pipelineDef.stages,
      )

      await CognitiveMetricsCollector.recordSessionCreated(this.systemId)

      await CognitiveSessionManager.updateSession(session.id, { status: "active" })
      context.sessionId = session.id
      await CognitiveContextManager.updateContext(context.id, "sessionId", session.id)

      await this.eventBus.publish("cognition", "cognition.session.started", {
        systemId: this.systemId, sessionId: session.id, pipelineId: pipelineDef.id,
      })

      const execution = await CognitivePipeline.startExecution(pipelineDef.id, session.id)

      await this.executeStages(session, context, execution, pipelineDef)

      const completedSession = await CognitiveSessionManager.getSession(session.id)
      await CognitiveMetricsCollector.recordSessionCompleted(this.systemId)

      await this.eventBus.publish("cognition", "cognition.session.completed", {
        systemId: this.systemId, sessionId: session.id, durationMs: Date.now() - startTime,
      })

      return {
        success: true,
        session: completedSession,
        data: { contextId: context.id, executionId: execution.id },
        error: null,
        durationMs: Date.now() - startTime,
        timestamp: new Date().toISOString(),
      }
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : String(err)
      await CognitiveMetricsCollector.recordSessionFailed(this.systemId)

      await this.eventBus.publish("cognition", "cognition.session.failed", {
        systemId: this.systemId, error: errorMsg,
      })

      return this.createError("ORCHESTRATION_FAILED", errorMsg, startTime)
    }
  }

  async coordinate(request: CognitiveRequest): Promise<CognitiveResponse> {
    const startTime = Date.now()
    this.requireInitialized()

    try {
      if (request.type !== "coordinate") {
        return this.createError("INVALID_REQUEST", `CognitiveOrchestrator cannot handle request type: ${request.type}`, startTime)
      }

      const session = await CognitiveSessionManager.getSession(request.sessionId ?? "")
      if (!session) throw new Error(`Session ${request.sessionId} not found`)

      const workers = await WorkerCoordinationEngine.getAvailableWorkers()
      const assignments = await WorkerCoordinationEngine.broadcast(
        session.id, "coordinate", request.context ?? {},
      )

      return {
        success: true,
        session,
        data: { assignments: assignments.map((a) => a.id), workerCount: workers.length },
        error: null,
        durationMs: Date.now() - startTime,
        timestamp: new Date().toISOString(),
      }
    } catch (err) {
      return this.createError("COORDINATION_FAILED", err instanceof Error ? err.message : String(err), startTime)
    }
  }

  async validate(sessionId?: string): Promise<CognitiveResponse> {
    const startTime = Date.now()
    this.requireInitialized()

    try {
      const sessions = sessionId
        ? [await CognitiveSessionManager.getSession(sessionId)].filter(Boolean)
        : await CognitiveSessionManager.getAll()

      const issues: string[] = []
      for (const s of sessions) {
        if (!s) continue
        if (s.status === "active" && s.stages.every((st) => st.status === "completed")) {
          issues.push(`Session ${s.id} is active with all stages completed`)
        }
        if (s.status === "failed" && !s.error) {
          issues.push(`Session ${s.id} is failed with no error message`)
        }
      }

      return {
        success: issues.length === 0,
        session: null,
        data: { validated: sessions.length, issues },
        error: issues.length > 0 ? issues.join("; ") : null,
        durationMs: Date.now() - startTime,
        timestamp: new Date().toISOString(),
      }
    } catch (err) {
      return this.createError("VALIDATION_FAILED", err instanceof Error ? err.message : String(err), startTime)
    }
  }

  async snapshot(sessionId: string): Promise<CognitiveResponse> {
    const startTime = Date.now()
    this.requireInitialized()

    try {
      const context = await CognitiveContextManager.getContextBySession(sessionId)
      const snap = await CognitiveStateManager.snapshot(sessionId, context)

      return {
        success: true,
        session: await CognitiveSessionManager.getSession(sessionId),
        data: { snapshotId: snap.id, capturedAt: snap.capturedAt },
        error: null,
        durationMs: Date.now() - startTime,
        timestamp: new Date().toISOString(),
      }
    } catch (err) {
      return this.createError("SNAPSHOT_FAILED", err instanceof Error ? err.message : String(err), startTime)
    }
  }

  async metrics(): Promise<CognitiveMetrics> {
    this.requireInitialized()
    return CognitiveMetricsCollector.collect(this.systemId)
  }

  async health(): Promise<CognitiveHealth> {
    this.requireInitialized()
    return CognitiveHealthManager.check(this.systemId)
  }

  private async executeStages(
    session: CognitiveSession,
    context: CognitiveContext,
    execution: CognitivePipelineExecution,
    pipelineDef: CognitivePipelineDefinition,
  ): Promise<void> {
    for (let i = 0; i < execution.stages.length; i++) {
      const stageDef = execution.stages[i]
      if (!stageDef) continue

      await CognitivePipeline.markStageStarted(execution.id, stageDef.order)
      await CognitiveSessionManager.updateCurrentStage(session.id, stageDef.name)

      await this.eventBus.publish("cognition", "cognition.stage.started", {
        systemId: this.systemId, sessionId: session.id, stage: stageDef.name,
      })

      try {
        await this.executeStage(stageDef.name, session, context, execution)

        await CognitivePipeline.markStageCompleted(execution.id, stageDef.order)

        const completedStage = (await CognitivePipeline.getExecution(execution.id))?.stages.find((s) => s.order === stageDef.order)
        if (completedStage?.durationMs !== null) {
          await CognitiveMetricsCollector.recordStageCompleted(this.systemId, stageDef.name, completedStage!.durationMs ?? 0)
        }

        await this.eventBus.publish("cognition", "cognition.stage.completed", {
          systemId: this.systemId, sessionId: session.id, stage: stageDef.name,
        })

        const route = await CognitiveRoutingEngine.determineRoute(
          session, execution, "completed",
        )
        await CognitiveRoutingEngine.recordDecision(session.id, stageDef.name, "proceed", "Stage completed successfully", route)
        await CognitiveMetricsCollector.recordRoutingDecision(this.systemId)

        if (route.type === "terminate") break
        if (route.type === "skip") {
          await CognitivePipeline.markStageCompleted(execution.id, stageDef.order)
          await CognitiveMetricsCollector.recordRoutingDecision(this.systemId)
          continue
        }
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : String(err)

        const route = await CognitiveRoutingEngine.determineRoute(
          session, execution, "failed", errorMsg,
        )
        await CognitiveRoutingEngine.recordDecision(session.id, stageDef.name, "retry", errorMsg, route)
        await CognitiveMetricsCollector.recordRoutingDecision(this.systemId)

        if (route.type === "retry" && stageDef.retryCount < pipelineDef.maxRetries) {
          await CognitivePipeline.markStageFailed(execution.id, stageDef.order, errorMsg)
          await CognitiveMetricsCollector.recordRetry(this.systemId)
          await CognitiveMetricsCollector.recordStageFailed(this.systemId)
          await CognitiveHealthManager.recordFailedStage(this.systemId)
          i--
          continue
        }

        await CognitivePipeline.markStageFailed(execution.id, stageDef.order, errorMsg)
        await CognitivePipeline.failExecution(execution.id)
        await CognitiveSessionManager.failSession(session.id, errorMsg)
        await CognitiveMetricsCollector.recordStageFailed(this.systemId)
        await CognitiveHealthManager.recordFailedStage(this.systemId)

        await this.eventBus.publish("cognition", "cognition.stage.failed", {
          systemId: this.systemId, sessionId: session.id, stage: stageDef.name, error: errorMsg,
        })

        throw err
      }
    }

    await CognitivePipeline.completeExecution(execution.id)
    await CognitiveSessionManager.closeSession(session.id)
  }

  private async executeStage(
    stage: CognitiveStage,
    session: CognitiveSession,
    context: CognitiveContext,
    execution: CognitivePipelineExecution,
  ): Promise<void> {
    switch (stage) {
      case "intake":
        break

      case "context_build": {
        const ctxResult = await CognitivePolicyEngine.evaluateContext(session, context)
        if (!ctxResult.allowed) {
          throw new Error(`Context policy denied: ${ctxResult.reasons.join(", ")}`)
        }
        break
      }

      case "memory_retrieval": {
        const memResult = await CognitivePolicyEngine.evaluateMemory(context.memoryEntries.length, [])
        if (!memResult.allowed) {
          throw new Error(`Memory policy denied: ${memResult.reasons.join(", ")}`)
        }
        break
      }

      case "knowledge_resolution": {
        const graphResult = await CognitivePolicyEngine.evaluateGraph(context.knowledgeEntities.length, 0)
        if (!graphResult.allowed) {
          throw new Error(`Graph policy denied: ${graphResult.reasons.join(", ")}`)
        }
        break
      }

      case "worker_coordination": {
        const availResult = await CognitivePolicyEngine.evaluateAvailability([])
        if (!availResult.allowed) {
          throw new Error(`Worker availability policy denied: ${availResult.reasons.join(", ")}`)
        }
        break
      }

      case "world_state_update": {
        const stateResult = await CognitivePolicyEngine.evaluateState(context.worldStateKeys.length, 0)
        if (!stateResult.allowed) {
          throw new Error(`State policy denied: ${stateResult.reasons.join(", ")}`)
        }
        break
      }

      case "validation": {
        const errors: string[] = []
        if (context.memoryEntries.length === 0) errors.push("No memory entries retrieved")
        if (execution.stages.some((s) => s.status === "failed")) errors.push("Some stages failed")
        if (errors.length > 0) throw new Error(`Validation failed: ${errors.join("; ")}`)
        break
      }

      case "completion":
        break
    }
  }

  private async ensurePipeline(request: CognitiveRequest): Promise<CognitivePipelineDefinition> {
    if (request.pipelineId) {
      const existing = await CognitivePipeline.getDefinition(request.pipelineId)
      if (existing) return existing
    }

    return CognitivePipeline.createDefinition(
      `Pipeline-${request.id}`,
      request.stages,
      request.strategy,
      request.routingPolicy,
    )
  }

  private createError(code: string, message: string, startTime: number): CognitiveResponse {
    return {
      success: false,
      session: null,
      data: null,
      error: `[${code}] ${message}`,
      durationMs: Date.now() - startTime,
      timestamp: new Date().toISOString(),
    }
  }

  private requireInitialized(): void {
    if (!this.initialized) {
      throw new Error("CognitiveOrchestrator not initialized. Call initialize() first.")
    }
  }
}
