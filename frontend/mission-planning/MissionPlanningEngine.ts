import type { IEventBus, ITelemetry } from "@/platform/interfaces"
import type { CapabilityDefinition } from "@/capability-framework/types"
import type {
  PlanningRequest, PlanningResponse,
  PlanningMetrics, PlanningHealth,
} from "./types"
import { PlanningSessionManager } from "./PlanningSessionManager"
import { MissionPlanner } from "./MissionPlanner"
import { PriorityEngine } from "./PriorityEngine"
import { ResourcePlanner } from "./ResourcePlanner"
import { TimelinePlanner } from "./TimelinePlanner"
import { PortfolioPlanner } from "./PortfolioPlanner"
import { PlanningValidationEngine } from "./PlanningValidationEngine"
import { PlanningPolicyEngine } from "./PlanningPolicyEngine"
import { PlanningMetricsCollector } from "./PlanningMetricsCollector"
import { PlanningHealthManager } from "./PlanningHealthManager"
import { MissionPlanningCapability } from "./MissionPlanningCapability"

const DEFAULT_POLICIES = [
  { id: "plan.default.allow", name: "Default Allow", description: "Default allow for planning operations", category: "governance" as const, effect: "allow" as const, rules: [{ field: "action", operator: "exists" as const, value: null, message: "" }], priority: 0, enabled: true },
  { id: "plan.priority.limit", name: "Priority Limit", description: "Maximum number of critical priority plans", category: "priority" as const, effect: "deny" as const, rules: [{ field: "currentLoad", operator: "gte" as const, value: 3, message: "Maximum 3 critical priority plans allowed" }], priority: 100, enabled: true },
  { id: "plan.resource.check", name: "Resource Check", description: "Resources must be estimated before finalization", category: "resource" as const, effect: "deny" as const, rules: [{ field: "resourcesEstimated", operator: "exists" as const, value: null, message: "Resources must be estimated" }], priority: 80, enabled: true },
]

export class MissionPlanningEngine {
  private readonly systemId: string
  private readonly eventBus: IEventBus
  private readonly telemetry: ITelemetry
  private readonly capabilityDefinition: CapabilityDefinition
  private initialized: boolean = false

  constructor(
    eventBus: IEventBus,
    telemetry: ITelemetry,
  ) {
    this.systemId = `mission-planning-${Date.now()}`
    this.eventBus = eventBus
    this.telemetry = telemetry

    const capability = new MissionPlanningCapability()
    this.capabilityDefinition = capability.toCapabilityDefinition()
  }

  async initialize(): Promise<void> {
    if (this.initialized) return

    await PlanningMetricsCollector.initialize(this.systemId)
    await PlanningHealthManager.initialize(this.systemId)

    for (const policy of DEFAULT_POLICIES) {
      await PlanningPolicyEngine.registerPolicy(policy)
    }

    this.initialized = true

    await this.eventBus.publish("planning", "planning.engine.initialized", {
      systemId: this.systemId,
    })
  }

  async shutdown(): Promise<void> {
    await this.eventBus.publish("planning", "planning.engine.shutdown", {
      systemId: this.systemId,
    })
  }

  async createPlan(request: PlanningRequest): Promise<PlanningResponse> {
    const startTime = Date.now()
    this.requireInitialized()

    try {
      const session = await PlanningSessionManager.createSession(
        request.missionId, request.strategy, request.policy,
      )
      await PlanningMetricsCollector.recordSessionCreated(this.systemId)

      await this.eventBus.publish("planning", "planning.session.created", {
        systemId: this.systemId, sessionId: session.id, missionId: request.missionId,
      })

      const plan = await MissionPlanner.createMissionPlan(
        session.id, request.missionId,
        request.name ?? `Plan-${request.missionId}`,
        request.description ?? `Execution plan for mission ${request.missionId}`,
        request.strategy, request.priority,
      )
      await PlanningSessionManager.linkPlan(session.id, plan.id)
      await PlanningMetricsCollector.recordPlanCreated(this.systemId)

      await this.eventBus.publish("planning", "planning.plan.created", {
        systemId: this.systemId, sessionId: session.id, planId: plan.id,
      })

      return {
        success: true,
        session,
        plan,
        data: { planId: plan.id },
        error: null,
        durationMs: Date.now() - startTime,
        timestamp: new Date().toISOString(),
      }
    } catch (err) {
      return this.createError("PLAN_CREATION_FAILED", err instanceof Error ? err.message : String(err), startTime)
    }
  }

  async optimizePlan(request: PlanningRequest): Promise<PlanningResponse> {
    const startTime = Date.now()
    this.requireInitialized()

    try {
      const plan = request.planId
        ? await MissionPlanner.getPlan(request.planId)
        : null

      if (!plan) throw new Error("Plan not found")

      await PlanningSessionManager.updateSession(plan.sessionId, { status: "optimizing" })

      const priority = await PriorityEngine.calculatePriority(
        request.missionId, plan.sessionId, request.priority ?? plan.priority,
      )

      const timeline = await TimelinePlanner.generateTimeline(plan.id)
      const duration = await TimelinePlanner.estimateDuration(plan.id)
      plan.estimatedDurationMs = duration

      const resourceData = [
        { type: "analyst", required: Math.max(1, Math.ceil(plan.totalTasks / 5)), available: 10 },
        { type: "executor", required: Math.max(1, Math.ceil(plan.totalTasks / 3)), available: 8 },
      ]
      const resources = await ResourcePlanner.estimateResources(plan.sessionId, resourceData)
      await PlanningMetricsCollector.recordResourceEstimate(this.systemId)

      await MissionPlanner.generateExecutionSequence(plan.id)
      await PlanningSessionManager.updateSession(plan.sessionId, { status: "validating" })

      const checkpoint = await PlanningValidationEngine.validateCompleteness(plan.sessionId, plan.id)
      if (checkpoint.ready) {
        await MissionPlanner.finalizePlan(plan.id)
        await PlanningMetricsCollector.recordPlanFinalized(this.systemId)
      }

      await this.eventBus.publish("planning", "planning.plan.optimized", {
        systemId: this.systemId, sessionId: plan.sessionId, planId: plan.id,
        ready: checkpoint.ready,
      })

      const updatedPlan = await MissionPlanner.getPlan(plan.id)
      const updatedSession = await PlanningSessionManager.getSession(plan.sessionId)

      return {
        success: checkpoint.ready,
        session: updatedSession,
        plan: updatedPlan,
        data: {
          priority: priority.level,
          timeline: timeline.id,
          resources: resources.length,
          duration,
          ready: checkpoint.ready,
          checkpoint,
        },
        error: checkpoint.ready ? null : "Optimization validation failed",
        durationMs: Date.now() - startTime,
        timestamp: new Date().toISOString(),
      }
    } catch (err) {
      await PlanningHealthManager.recordOptimizationFailure(this.systemId)
      return this.createError("OPTIMIZATION_FAILED", err instanceof Error ? err.message : String(err), startTime)
    }
  }

  async validatePlan(request: PlanningRequest): Promise<PlanningResponse> {
    const startTime = Date.now()
    this.requireInitialized()

    try {
      if (!request.planId) throw new Error("planId required")
      const plan = await MissionPlanner.getPlan(request.planId)
      if (!plan) throw new Error(`Plan ${request.planId} not found`)

      const validation = await PlanningValidationEngine.validateAll(plan.sessionId, request.planId)
      const session = await PlanningSessionManager.getSession(plan.sessionId)

      return {
        success: validation.result === "pass",
        session,
        plan,
        data: { result: validation.result, reasons: validation.reasons },
        error: validation.reasons.length > 0 ? validation.reasons.join("; ") : null,
        durationMs: Date.now() - startTime,
        timestamp: new Date().toISOString(),
      }
    } catch (err) {
      return this.createError("VALIDATION_FAILED", err instanceof Error ? err.message : String(err), startTime)
    }
  }

  async estimateResources(request: PlanningRequest): Promise<PlanningResponse> {
    const startTime = Date.now()
    this.requireInitialized()

    try {
      if (!request.planId) throw new Error("planId required")
      const plan = await MissionPlanner.getPlan(request.planId)
      if (!plan) throw new Error(`Plan ${request.planId} not found`)

      const resourceData = [
        { type: "analyst", required: Math.max(1, Math.ceil(plan.totalTasks / 5)), available: 10 },
        { type: "executor", required: Math.max(1, Math.ceil(plan.totalTasks / 3)), available: 8 },
        { type: "validator", required: Math.max(1, Math.ceil(plan.totalTasks / 10)), available: 5 },
      ]
      const resources = await ResourcePlanner.estimateResources(plan.sessionId, resourceData)
      await PlanningMetricsCollector.recordResourceEstimate(this.systemId)

      const capacity = await ResourcePlanner.validateCapacity(plan.sessionId)

      return {
        success: capacity.sufficient,
        session: await PlanningSessionManager.getSession(plan.sessionId),
        plan,
        data: { resources, capacity },
        error: capacity.sufficient ? null : `Resource shortages: ${capacity.shortages.join("; ")}`,
        durationMs: Date.now() - startTime,
        timestamp: new Date().toISOString(),
      }
    } catch (err) {
      return this.createError("RESOURCE_ESTIMATION_FAILED", err instanceof Error ? err.message : String(err), startTime)
    }
  }

  async generateTimeline(request: PlanningRequest): Promise<PlanningResponse> {
    const startTime = Date.now()
    this.requireInitialized()

    try {
      if (!request.planId) throw new Error("planId required")
      const timeline = await TimelinePlanner.generateTimeline(request.planId)
      const plan = await MissionPlanner.getPlan(request.planId)
      const session = plan ? await PlanningSessionManager.getSession(plan.sessionId) : null

      return {
        success: true,
        session,
        plan,
        data: {
          timeline,
          totalDurationMs: timeline.totalDurationMs,
          milestones: timeline.milestones.length,
          estimatedEndAt: timeline.estimatedEndAt,
        },
        error: null,
        durationMs: Date.now() - startTime,
        timestamp: new Date().toISOString(),
      }
    } catch (err) {
      return this.createError("TIMELINE_FAILED", err instanceof Error ? err.message : String(err), startTime)
    }
  }

  async optimizePortfolio(request: PlanningRequest): Promise<PlanningResponse> {
    const startTime = Date.now()
    this.requireInitialized()

    try {
      const portfolio = await PortfolioPlanner.groupRelatedMissions(
        request.name ?? `Portfolio-${request.missionId}`,
        request.description ?? `Portfolio for mission ${request.missionId}`,
        [request.missionId],
      )

      const optimized = await PortfolioPlanner.optimizePortfolio(portfolio.id)
      await PortfolioPlanner.balancePortfolio(portfolio.id)
      const conflicts = await PortfolioPlanner.detectPortfolioConflicts(portfolio.id)

      return {
        success: true,
        session: null,
        plan: null,
        data: { portfolio: optimized, conflicts, conflictCount: conflicts.length },
        error: conflicts.length > 0 ? `${conflicts.length} portfolio conflict(s) detected` : null,
        durationMs: Date.now() - startTime,
        timestamp: new Date().toISOString(),
      }
    } catch (err) {
      return this.createError("PORTFOLIO_FAILED", err instanceof Error ? err.message : String(err), startTime)
    }
  }

  async metrics(): Promise<PlanningMetrics> {
    this.requireInitialized()
    return PlanningMetricsCollector.collect(this.systemId)
  }

  async health(): Promise<PlanningHealth> {
    this.requireInitialized()
    return PlanningHealthManager.check(this.systemId)
  }

  private createError(code: string, message: string, startTime: number): PlanningResponse {
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
      throw new Error("MissionPlanningEngine not initialized. Call initialize() first.")
    }
  }
}
