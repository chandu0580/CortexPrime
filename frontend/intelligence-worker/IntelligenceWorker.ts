import type { PlatformContext, PlatformCapability } from "@/platform/contracts"
import type { IKernel, IEventBus, ITelemetry, IExecutionResult } from "@/platform/interfaces"
import type { WorkerConfiguration } from "@/worker-framework/types"
import type { CapabilityDefinition } from "@/capability-framework/types"
import { AbstractWorker } from "@/worker-framework/AbstractWorker"
import type { CognitiveMemory } from "@/cognitive-memory/CognitiveMemory"
import type { WorldState } from "@/world-state/WorldState"
import type { KnowledgeGraph } from "@/knowledge-graph/KnowledgeGraph"
import type { EntityCategory, RelationshipType } from "@/knowledge-graph/types"
import type { IntelligenceTaskPayload, IntelligenceMetrics, IntelligenceWorkerConfig } from "./types"
import { IntelligenceSessionManager } from "./IntelligenceSessionManager"
import { IntelligenceActivityManager } from "./IntelligenceActivityManager"
import { IntelligencePlanningEngine } from "./IntelligencePlanningEngine"
import { EvidenceManager } from "./EvidenceManager"
import { InsightManager } from "./InsightManager"
import { RecommendationManager } from "./RecommendationManager"
import { IntelligencePipeline } from "./IntelligencePipeline"
import { IntelligencePolicyEngine } from "./IntelligencePolicyEngine"
import { IntelligenceMetricsCollector } from "./IntelligenceMetricsCollector"
import { IntelligenceHealthManager, type IntelligenceHealthReport } from "./IntelligenceHealthManager"
import { IntelligenceCapability } from "./IntelligenceCapability"

const DEFAULT_INTEL_CONFIG: IntelligenceWorkerConfig = {
  maxConcurrentSessions: 5,
  sessionTimeoutMs: 300_000,
  defaultRequestType: "analysis",
  maxObjectivesPerPlan: 10,
  maxEvidencePerSession: 1000,
  minEvidenceForInsight: 2,
  minInsightsForRecommendation: 1,
  policies: [
    { id: "intel.default.allow", name: "Default Allow", description: "Default allow for intelligence actions", effect: "allow", category: "general", rules: [{ field: "action", operator: "exists", value: null, message: "" }], priority: 0, enabled: true },
    { id: "intel.evidence.minimum", name: "Minimum Evidence", description: "Minimum evidence required for insights", effect: "deny", category: "evidence", rules: [{ field: "evidence_count", operator: "gte", value: 2, message: "Minimum 2 evidence items required for insight generation" }], priority: 100, enabled: true },
    { id: "intel.confidence.threshold", name: "Confidence Threshold", description: "Minimum confidence for recommendations", effect: "audit", category: "confidence", rules: [{ field: "confidence_score", operator: "gte", value: 0.5, message: "Confidence below 0.5 threshold" }], priority: 80, enabled: true },
  ],
}

const DEFAULT_WORKER_CONFIG: WorkerConfiguration = {
  maxConcurrentTasks: 5,
  heartbeatIntervalMs: 15_000,
  healthCheckIntervalMs: 30_000,
  taskTimeoutMs: 300_000,
  autoRecovery: true,
  maxRetries: 3,
  settings: {},
}

const INTEL_CAPABILITIES: PlatformCapability[] = [
  { id: "intelligence.planning", name: "Intelligence Planning", type: "custom", version: "1.0.0", features: ["create-plan", "define-objectives", "track-progress"], enabled: true },
  { id: "intelligence.evidence", name: "Evidence Management", type: "custom", version: "1.0.0", features: ["register-evidence", "validate-evidence", "categorize-evidence", "deduplicate"], enabled: true },
  { id: "intelligence.analysis", name: "Evidence Analysis", type: "custom", version: "1.0.0", features: ["score-confidence", "detect-relationships", "analyze-evidence"], enabled: true },
  { id: "intelligence.insights", name: "Insight Generation", type: "custom", version: "1.0.0", features: ["create-insights", "group-insights", "prioritize-insights"], enabled: true },
  { id: "intelligence.recommendations", name: "Recommendation Generation", type: "custom", version: "1.0.0", features: ["generate-recommendations", "prioritize-recommendations"], enabled: true },
  { id: "intelligence.summary", name: "Summary Building", type: "custom", version: "1.0.0", features: ["build-summary", "compile-findings"], enabled: true },
]

export class IntelligenceWorker extends AbstractWorker {
  private readonly intelConfig: IntelligenceWorkerConfig
  private readonly capabilityDefinition: CapabilityDefinition
  private readonly pipeline: IntelligencePipeline
  private readonly cognitiveMemory: CognitiveMemory | null
  private readonly worldState: WorldState | null
  private readonly knowledgeGraph: KnowledgeGraph | null
  private memorySessionId: string | null = null
  private evidenceEntityIds = new Map<string, string>()

  constructor(
    kernel: IKernel,
    eventBus: IEventBus,
    telemetry: ITelemetry,
    capabilityDefinition?: CapabilityDefinition,
    intelConfig?: Partial<IntelligenceWorkerConfig>,
    cognitiveMemory?: CognitiveMemory,
    worldState?: WorldState,
    knowledgeGraph?: KnowledgeGraph,
  ) {
    const mergedConfig = { ...DEFAULT_INTEL_CONFIG, ...intelConfig }

    super(
      {
        id: `intel-worker-${Date.now()}`,
        name: "Intelligence Worker",
        type: "intelligence-worker",
        version: "1.0.0",
        description: "Enterprise intelligence worker for planning, evidence analysis, insight generation, and recommendation creation",
        capabilities: INTEL_CAPABILITIES,
        metadata: {
          defaultRequestType: mergedConfig.defaultRequestType,
          maxConcurrentSessions: String(mergedConfig.maxConcurrentSessions),
          maxObjectivesPerPlan: String(mergedConfig.maxObjectivesPerPlan),
        },
      },
      { ...DEFAULT_WORKER_CONFIG, settings: { intelConfig: mergedConfig } },
      kernel,
      eventBus,
      telemetry,
    )

    this.intelConfig = mergedConfig
    this.cognitiveMemory = cognitiveMemory ?? null
    this.worldState = worldState ?? null
    this.knowledgeGraph = knowledgeGraph ?? null

    const capability = new IntelligenceCapability(capabilityDefinition)
    this.capabilityDefinition = capability.getDefinition()

    this.pipeline = new IntelligencePipeline()
  }

  async register(): Promise<void> {
    await super.register()
    await IntelligenceMetricsCollector.initialize(this.descriptor.id)
    await IntelligenceHealthManager.initialize(this.descriptor.id)

    if (this.cognitiveMemory) {
      const memSession = await this.cognitiveMemory.createSession(this.descriptor.id, "user", this.descriptor.id)
      this.memorySessionId = memSession.id
    }

    if (this.worldState) {
      await this.worldState.create(`intel:worker:${this.descriptor.id}:status`, {
        status: "registered", workerId: this.descriptor.id,
      }, { sessionId: this.descriptor.id, actor: this.descriptor.id, scope: "global", domain: "intelligence", metadata: {} })
    }

    await this.eventBus.publish("intelligence", "intelligence.capability.registered", {
      workerId: this.descriptor.id,
      capabilityId: this.capabilityDefinition.id,
      stages: this.capabilityDefinition.stages.length,
    })

    for (const policy of this.intelConfig.policies) {
      await IntelligencePolicyEngine.registerPolicy(policy)
    }
  }

  async initialize(): Promise<void> {
    await super.initialize()
    await this.pipeline.registerPipeline()
    await this.pipeline.build()

    await this.eventBus.publish("intelligence", "intelligence.pipeline.initialized", {
      workerId: this.descriptor.id,
      pipelineId: this.pipeline.pipelineId,
    })
  }

  async start(): Promise<void> {
    await super.start()

    if (this.worldState) {
      await this.worldState.update(`intel:worker:${this.descriptor.id}:status`, {
        status: "started", workerId: this.descriptor.id,
      }, { sessionId: this.descriptor.id, actor: this.descriptor.id, scope: "global", domain: "intelligence", metadata: {} })
    }

    await this.eventBus.publish("intelligence", "intelligence.worker.started", {
      workerId: this.descriptor.id,
      capabilityId: this.capabilityDefinition.id,
    })
  }

  async execute(taskId: string, payload: Record<string, unknown>, context: PlatformContext): Promise<IExecutionResult> {
    const startTime = Date.now()
    const startedAt = new Date(startTime).toISOString()

    const taskPayload = payload as IntelligenceTaskPayload

    try {
      switch (taskPayload.type) {
        case "create_session":
          return await this.executeCreateSession(taskId, taskPayload, context, startTime, startedAt)
        case "execute_plan":
          return await this.executePlan(taskId, taskPayload, context, startTime, startedAt)
        case "process_evidence":
          return await this.executeProcessEvidence(taskId, taskPayload, context, startTime, startedAt)
        case "generate_insights":
          return await this.executeGenerateInsights(taskId, taskPayload, context, startTime, startedAt)
        case "generate_recommendations":
          return await this.executeGenerateRecommendations(taskId, taskPayload, context, startTime, startedAt)
        case "build_summary":
          return await this.executeBuildSummary(taskId, taskPayload, context, startTime, startedAt)
        case "control_session":
          return await this.executeControlSession(taskId, taskPayload, context, startTime, startedAt)
        default:
          return this.createError(startedAt, "UNKNOWN_INTEL_TASK", `Unknown intelligence task type: ${(payload as { type?: string }).type ?? "undefined"}`)
      }
    } catch (err) {
      this.tasksFailed++
      await IntelligenceHealthManager.recordFailure(this.descriptor.id)
      await IntelligenceMetricsCollector.recordError(this.descriptor.id)

      const completedAt = new Date().toISOString()
      return {
        sessionId: context.sessionId,
        success: false,
        output: { taskId },
        error: {
          code: "INTEL_TASK_FAILED",
          message: err instanceof Error ? err.message : String(err),
          module: "IntelligenceWorker",
          severity: "error",
          timestamp: completedAt,
          details: { taskId, payloadType: (payload as { type?: string }).type ?? "unknown" },
          cause: null,
        },
        startedAt,
        completedAt,
        durationMs: Date.now() - startTime,
      }
    }
  }

  private async executeCreateSession(
    taskId: string,
    taskPayload: IntelligenceTaskPayload & { type: "create_session" },
    context: PlatformContext,
    startTime: number,
    startedAt: string,
  ): Promise<IExecutionResult> {
    const activeSessions = await IntelligenceSessionManager.getActiveSessions()
    if (activeSessions.length >= this.intelConfig.maxConcurrentSessions) {
      this.tasksFailed++
      return this.createError(startedAt, "MAX_SESSIONS_EXCEEDED", `Maximum concurrent sessions (${this.intelConfig.maxConcurrentSessions}) reached`)
    }

    const session = await IntelligenceSessionManager.createSession(taskPayload.request)
    await IntelligenceHealthManager.recordSuccess(this.descriptor.id)
    await IntelligenceMetricsCollector.recordSessionCreated(this.descriptor.id)
    await IntelligenceMetricsCollector.recordActivity(this.descriptor.id)

    await IntelligenceActivityManager.recordActivity(
      session.id,
      "session_created",
      `Intelligence session created for ${taskPayload.request.type}`,
      { requestType: taskPayload.request.type, requestId: taskPayload.request.id },
    )

    if (this.cognitiveMemory && this.memorySessionId) {
      await this.cognitiveMemory.storeWorking(
        this.memorySessionId,
        `intel:session:${session.id}`,
        { request: taskPayload.request, sessionId: session.id },
        undefined, "high", "user", [`intel:${this.descriptor.id}`],
        { sessionId: session.id, requestType: taskPayload.request.type, taskId },
      )
    }

    if (this.worldState) {
      await this.worldState.create(`intel:session:${session.id}:state`, "created", {
        sessionId: session.id, actor: this.descriptor.id, scope: "session", domain: "intelligence", metadata: { requestType: taskPayload.request.type },
      })
    }

    this.tasksCompleted++

    const completedAt = new Date().toISOString()
    return {
      sessionId: context.sessionId,
      success: true,
      output: { sessionId: session.id, session },
      error: null,
      startedAt,
      completedAt,
      durationMs: Date.now() - startTime,
    }
  }

  private async executePlan(
    taskId: string,
    taskPayload: IntelligenceTaskPayload & { type: "execute_plan" },
    context: PlatformContext,
    startTime: number,
    startedAt: string,
  ): Promise<IExecutionResult> {
    const session = await IntelligenceSessionManager.getSession(taskPayload.sessionId)
    if (!session) {
      this.tasksFailed++
      return this.createError(startedAt, "SESSION_NOT_FOUND", `Intelligence session ${taskPayload.sessionId} not found`)
    }

    await IntelligenceSessionManager.transitionState(taskPayload.sessionId, "planning")
    await IntelligenceHealthManager.recordSuccess(this.descriptor.id)

    const plan = await IntelligencePlanningEngine.createPlan(taskPayload.sessionId)
    await IntelligenceSessionManager.setPlan(taskPayload.sessionId, plan.id)
    await IntelligenceMetricsCollector.recordPlan(this.descriptor.id)

    for (const objective of taskPayload.objectives) {
      await IntelligencePlanningEngine.addObjective(plan.id, objective.description, objective.key, objective.target)
    }
    await IntelligenceMetricsCollector.recordObjective(this.descriptor.id, taskPayload.objectives.length)

    const pipelineStages = [
      { name: "Validate Request", description: "Validate the intelligence request", order: 1 },
      { name: "Build Plan", description: "Build execution plan with objectives", order: 2 },
      { name: "Collect Evidence", description: "Collect and validate evidence", order: 3 },
      { name: "Analyze Evidence", description: "Analyze evidence and score confidence", order: 4 },
      { name: "Generate Insights", description: "Generate insights from evidence", order: 5 },
      { name: "Generate Recommendations", description: "Generate recommendations from insights", order: 6 },
      { name: "Build Summary", description: "Build intelligence summary", order: 7 },
      { name: "Finalize", description: "Finalize intelligence execution", order: 8 },
    ]

    for (const stage of pipelineStages) {
      await IntelligencePlanningEngine.addStage(plan.id, stage.name, stage.description, stage.order)
    }

    await IntelligencePlanningEngine.activatePlan(plan.id)
    const progress = await IntelligencePlanningEngine.calculateProgress(plan.id)

    await IntelligenceActivityManager.recordActivity(
      taskPayload.sessionId,
      "plan_created",
      `Intelligence plan created with ${taskPayload.objectives.length} objectives`,
      { planId: plan.id, objectiveCount: String(taskPayload.objectives.length) },
    )

    const execution = await this.pipeline.startExecution(
      context.sessionId,
      context.correlationId,
      { taskId, planId: plan.id, sessionId: taskPayload.sessionId },
    )

    const advanceResult = await this.pipeline.advance(execution.id)

    await IntelligenceSessionManager.transitionState(taskPayload.sessionId, "collecting")

    this.tasksCompleted++

    const completedAt = new Date().toISOString()
    return {
      sessionId: context.sessionId,
      success: true,
      output: {
        planId: plan.id,
        sessionId: taskPayload.sessionId,
        objectivesCount: taskPayload.objectives.length,
        stagesCount: pipelineStages.length,
        progress,
        pipelineStatus: advanceResult.state,
        pipelineExecutionId: execution.id,
      },
      error: null,
      startedAt,
      completedAt,
      durationMs: Date.now() - startTime,
    }
  }

  private async executeProcessEvidence(
    taskId: string,
    taskPayload: IntelligenceTaskPayload & { type: "process_evidence" },
    context: PlatformContext,
    startTime: number,
    startedAt: string,
  ): Promise<IExecutionResult> {
    const session = await IntelligenceSessionManager.getSession(taskPayload.sessionId)
    if (!session) {
      this.tasksFailed++
      return this.createError(startedAt, "SESSION_NOT_FOUND", `Intelligence session ${taskPayload.sessionId} not found`)
    }

    await IntelligenceHealthManager.recordSuccess(this.descriptor.id)

    const evidenceIds: string[] = []
    this.evidenceEntityIds = new Map<string, string>()
    for (const item of taskPayload.evidenceItems) {
      const evidence = await EvidenceManager.registerEvidence(
        taskPayload.sessionId,
        item.sourceId,
        item.category,
        item.content,
        item.confidence,
        item.metadata,
      )
      await EvidenceManager.validateEvidence(evidence.id)
      evidenceIds.push(evidence.id)

      if (this.knowledgeGraph) {
        const kgEntity = await this.knowledgeGraph.registerEntity(
          `evidence:${evidence.id}`, evidence.category, "evidence" as EntityCategory,
          evidence.content.slice(0, 500),
          { sessionId: taskPayload.sessionId, sourceId: evidence.sourceId, confidence: String(evidence.confidenceScore) },
          [`intel:${this.descriptor.id}`, `session:${taskPayload.sessionId}`, evidence.category],
          this.descriptor.id, evidence.confidenceScore,
        )
        this.evidenceEntityIds.set(evidence.id, kgEntity.id)
      }
    }

    await IntelligenceMetricsCollector.recordEvidence(this.descriptor.id, taskPayload.evidenceItems.length)
    await IntelligenceMetricsCollector.recordActivity(this.descriptor.id)

    const duplicates = await EvidenceManager.deduplicate(taskPayload.sessionId)

    await IntelligenceActivityManager.recordActivity(
      taskPayload.sessionId,
      "evidence_added",
      `${taskPayload.evidenceItems.length} evidence items processed`,
      { count: String(taskPayload.evidenceItems.length), duplicatesFound: String(duplicates.length) },
    )

    if (this.cognitiveMemory && this.memorySessionId) {
      for (const evId of evidenceIds) {
        const evidence = await EvidenceManager.getEvidence(evId)
        if (evidence) {
          await this.cognitiveMemory.registerConcept(
            this.memorySessionId, `evidence:${evidence.id}`,
            `Evidence: ${evidence.content.slice(0, 200)}`, evidence.category,
            undefined, "medium", "user", [`intel:${this.descriptor.id}`, `session:${taskPayload.sessionId}`],
            { evidenceId: evidence.id, sessionId: taskPayload.sessionId, sourceId: evidence.sourceId },
          )
        }
      }
    }

    this.tasksCompleted++

    const completedAt = new Date().toISOString()
    return {
      sessionId: context.sessionId,
      success: true,
      output: {
        sessionId: taskPayload.sessionId,
        evidenceIds,
        registeredCount: evidenceIds.length,
        duplicatesRemoved: duplicates.length,
      },
      error: null,
      startedAt,
      completedAt,
      durationMs: Date.now() - startTime,
    }
  }

  private async executeGenerateInsights(
    taskId: string,
    taskPayload: IntelligenceTaskPayload & { type: "generate_insights" },
    context: PlatformContext,
    startTime: number,
    startedAt: string,
  ): Promise<IExecutionResult> {
    const session = await IntelligenceSessionManager.getSession(taskPayload.sessionId)
    if (!session) {
      this.tasksFailed++
      return this.createError(startedAt, "SESSION_NOT_FOUND", `Intelligence session ${taskPayload.sessionId} not found`)
    }

    const evidenceItems = await EvidenceManager.getEvidenceBySession(taskPayload.sessionId)
    const filteredEvidence = evidenceItems.filter((e) => taskPayload.evidenceIds.includes(e.id))

    if (filteredEvidence.length < this.intelConfig.minEvidenceForInsight) {
      this.tasksFailed++
      return this.createError(startedAt, "INSUFFICIENT_EVIDENCE", `Minimum ${this.intelConfig.minEvidenceForInsight} evidence items required for insight generation`)
    }

    await IntelligenceSessionManager.transitionState(taskPayload.sessionId, "analyzing")
    await IntelligenceHealthManager.recordSuccess(this.descriptor.id)

    const insightIds: string[] = []

    const evidenceByCategory = new Map<string, typeof filteredEvidence>()
    for (const ev of filteredEvidence) {
      const key = ev.category
      if (!evidenceByCategory.has(key)) evidenceByCategory.set(key, [])
      evidenceByCategory.get(key)!.push(ev)
    }

    for (const [category, categoryEvidence] of evidenceByCategory) {
      const avgConfidence = categoryEvidence.reduce((sum, e) => sum + e.confidenceScore, 0) / categoryEvidence.length
      let priority: "critical" | "high" | "medium" | "low" = "medium"
      if (avgConfidence >= 0.8) priority = "high"
      else if (avgConfidence >= 0.5) priority = "medium"
      else priority = "low"

      const insight = await InsightManager.createInsight(
        taskPayload.sessionId,
        categoryEvidence.map((e) => e.id),
        `Analysis of ${category} evidence`,
        `Analyzed ${categoryEvidence.length} ${category} evidence items with average confidence ${Math.round(avgConfidence * 100)}%`,
        priority,
      )
      insightIds.push(insight.id)
    }

    await IntelligenceMetricsCollector.recordInsight(this.descriptor.id, insightIds.length)
    await IntelligenceMetricsCollector.recordActivity(this.descriptor.id)

    await IntelligenceActivityManager.recordActivity(
      taskPayload.sessionId,
      "insight_generated",
      `${insightIds.length} insights generated from ${filteredEvidence.length} evidence items`,
      { evidenceCount: String(filteredEvidence.length), insightCount: String(insightIds.length) },
    )

    if (this.cognitiveMemory && this.memorySessionId) {
      for (const insId of insightIds) {
        const insight = await InsightManager.getInsight(insId)
        if (insight) {
          await this.cognitiveMemory.registerConcept(
            this.memorySessionId, `insight:${insight.id}`,
            `Insight: ${insight.title}`, "intelligence",
            undefined, insight.priority === "critical" || insight.priority === "high" ? "high" : "medium",
            "user", [`intel:${this.descriptor.id}`, `session:${taskPayload.sessionId}`],
            { insightId: insight.id, sessionId: taskPayload.sessionId, priority: insight.priority },
          )
        }
      }
    }

    if (this.knowledgeGraph) {
      for (const insId of insightIds) {
        const insight = await InsightManager.getInsight(insId)
        if (insight) {
          const entity = await this.knowledgeGraph.registerEntity(
            `insight:${insight.id}`, "insight", "intelligence" as EntityCategory,
            insight.description.slice(0, 500),
            { sessionId: taskPayload.sessionId, priority: insight.priority, confidence: String(0) },
            [`intel:${this.descriptor.id}`, `session:${taskPayload.sessionId}`],
            this.descriptor.id, 0.0, [insight.title],
          )
          for (const evId of insight.evidenceIds) {
            const targetId = this.evidenceEntityIds.get(evId)
            if (targetId) {
              await this.knowledgeGraph.createRelationship(
                entity.id, targetId, "derived_from" as RelationshipType,
                0.8, 0.9, { insightId: insight.id, evidenceId: evId },
              )
            }
          }
        }
      }
    }

    await IntelligenceSessionManager.transitionState(taskPayload.sessionId, "generating")

    this.tasksCompleted++

    const completedAt = new Date().toISOString()
    return {
      sessionId: context.sessionId,
      success: true,
      output: {
        sessionId: taskPayload.sessionId,
        insightIds,
        evidenceIds: taskPayload.evidenceIds,
        groupsCreated: evidenceByCategory.size,
      },
      error: null,
      startedAt,
      completedAt,
      durationMs: Date.now() - startTime,
    }
  }

  private async executeGenerateRecommendations(
    taskId: string,
    taskPayload: IntelligenceTaskPayload & { type: "generate_recommendations" },
    context: PlatformContext,
    startTime: number,
    startedAt: string,
  ): Promise<IExecutionResult> {
    const session = await IntelligenceSessionManager.getSession(taskPayload.sessionId)
    if (!session) {
      this.tasksFailed++
      return this.createError(startedAt, "SESSION_NOT_FOUND", `Intelligence session ${taskPayload.sessionId} not found`)
    }

    const insights = await InsightManager.getInsightsBySession(taskPayload.sessionId)
    const filteredInsights = insights.filter((i) => taskPayload.insightIds.includes(i.id))

    const evidence = await EvidenceManager.getEvidenceBySession(taskPayload.sessionId)
    const filteredEvidence = evidence.filter((e) => taskPayload.evidenceIds.includes(e.id))

    await IntelligenceHealthManager.recordSuccess(this.descriptor.id)

    const recommendations = await RecommendationManager.generateFromEvidence(
      taskPayload.sessionId,
      filteredEvidence,
      filteredInsights,
    )

    await IntelligenceMetricsCollector.recordRecommendation(this.descriptor.id, recommendations.length)
    await IntelligenceMetricsCollector.recordActivity(this.descriptor.id)

    await IntelligenceActivityManager.recordActivity(
      taskPayload.sessionId,
      "recommendation_created",
      `${recommendations.length} recommendations generated from ${filteredInsights.length} insights`,
      { insightCount: String(filteredInsights.length), recommendationCount: String(recommendations.length) },
    )

    this.tasksCompleted++

    const completedAt = new Date().toISOString()
    return {
      sessionId: context.sessionId,
      success: true,
      output: {
        sessionId: taskPayload.sessionId,
        recommendationIds: recommendations.map((r) => r.id),
        recommendations,
      },
      error: null,
      startedAt,
      completedAt,
      durationMs: Date.now() - startTime,
    }
  }

  private async executeBuildSummary(
    taskId: string,
    taskPayload: IntelligenceTaskPayload & { type: "build_summary" },
    context: PlatformContext,
    startTime: number,
    startedAt: string,
  ): Promise<IExecutionResult> {
    const session = await IntelligenceSessionManager.getSession(taskPayload.sessionId)
    if (!session) {
      this.tasksFailed++
      return this.createError(startedAt, "SESSION_NOT_FOUND", `Intelligence session ${taskPayload.sessionId} not found`)
    }

    if (!session.planId) {
      this.tasksFailed++
      return this.createError(startedAt, "NO_PLAN", "No plan found for this session, execute a plan first")
    }

    await IntelligenceSessionManager.transitionState(taskPayload.sessionId, "summarizing")
    await IntelligenceHealthManager.recordSuccess(this.descriptor.id)

    const plan = await IntelligencePlanningEngine.getPlan(session.planId)
    const allInsights = await InsightManager.getInsightsBySession(taskPayload.sessionId)
    const allRecommendations = await RecommendationManager.getRecommendationsBySession(taskPayload.sessionId)

    const summaryId = `summary-${taskPayload.sessionId}-${Date.now()}`
    await IntelligenceSessionManager.setSummary(taskPayload.sessionId, summaryId)

    await IntelligenceMetricsCollector.recordSummary(this.descriptor.id)
    await IntelligenceMetricsCollector.recordActivity(this.descriptor.id)

    const keyFindings = allInsights.map((i) => i.title)
    const insightDescriptions = allInsights.map((i) => `${i.title}: ${i.description}`)
    const recommendationTitles = allRecommendations.map((r) => `${r.title} [${r.priority}]`)

    const planDuration = plan
      ? Date.now() - new Date(plan.createdAt).getTime()
      : 0
    await IntelligenceMetricsCollector.recordPlanDuration(this.descriptor.id, planDuration)

    await IntelligenceActivityManager.recordActivity(
      taskPayload.sessionId,
      "summary_completed",
      "Intelligence summary completed",
      { insightCount: String(allInsights.length), recommendationCount: String(allRecommendations.length) },
    )

    if (this.cognitiveMemory && this.memorySessionId) {
      await this.cognitiveMemory.storeEpisode(
        this.memorySessionId, taskPayload.sessionId,
        `Intelligence summary for session ${taskPayload.sessionId}`,
        [
          ...allInsights.map((i) => ({ id: `insight-event-${i.id}`, timestamp: i.createdAt, type: "insight" as const, description: i.title, data: { priority: i.priority } })),
          ...allRecommendations.map((r) => ({ id: `rec-event-${r.id}`, timestamp: r.createdAt, type: "recommendation" as const, description: r.title, data: { priority: r.priority } })),
        ],
        planDuration,
        "high", "user", [`intel:${this.descriptor.id}`],
        { sessionId: taskPayload.sessionId, insightCount: String(allInsights.length), recommendationCount: String(allRecommendations.length) },
      )
    }

    await IntelligenceSessionManager.transitionState(taskPayload.sessionId, "completed")

    this.tasksCompleted++

    const completedAt = new Date().toISOString()
    return {
      sessionId: context.sessionId,
      success: true,
      output: {
        sessionId: taskPayload.sessionId,
        summaryId,
        title: `Intelligence Summary for Session ${taskPayload.sessionId}`,
        keyFindings,
        insights: insightDescriptions,
        recommendations: recommendationTitles,
        conclusions: [`Analysis completed with ${allInsights.length} insights and ${allRecommendations.length} recommendations`],
      },
      error: null,
      startedAt,
      completedAt,
      durationMs: Date.now() - startTime,
    }
  }

  private async executeControlSession(
    taskId: string,
    taskPayload: IntelligenceTaskPayload & { type: "control_session" },
    context: PlatformContext,
    startTime: number,
    startedAt: string,
  ): Promise<IExecutionResult> {
    const wsCtx = { sessionId: taskPayload.sessionId, actor: this.descriptor.id, scope: "session" as const, domain: "intelligence", metadata: {} }

    switch (taskPayload.action) {
      case "pause":
        await IntelligenceSessionManager.pauseSession(taskPayload.sessionId)
        await IntelligenceActivityManager.recordActivity(taskPayload.sessionId, "session_closed", "Session paused", { action: "pause" })
        if (this.worldState) {
          await this.worldState.update(`intel:session:${taskPayload.sessionId}:state`, "paused", wsCtx)
        }
        break
      case "resume":
        await IntelligenceSessionManager.resumeSession(taskPayload.sessionId)
        await IntelligenceActivityManager.recordActivity(taskPayload.sessionId, "session_closed", "Session resumed", { action: "resume" })
        if (this.worldState) {
          await this.worldState.update(`intel:session:${taskPayload.sessionId}:state`, "active", wsCtx)
        }
        break
      case "cancel":
        await IntelligenceSessionManager.closeSession(taskPayload.sessionId)
        await IntelligenceActivityManager.recordActivity(taskPayload.sessionId, "session_closed", "Session cancelled", { action: "cancel" })
        if (this.worldState) {
          await this.worldState.update(`intel:session:${taskPayload.sessionId}:state`, "cancelled", wsCtx)
        }
        break
      default:
        this.tasksFailed++
        return this.createError(startedAt, "INVALID_SESSION_ACTION", `Invalid session action: ${taskPayload.action}`)
    }

    await IntelligenceHealthManager.recordSuccess(this.descriptor.id)
    this.tasksCompleted++

    const completedAt = new Date().toISOString()
    return {
      sessionId: context.sessionId,
      success: true,
      output: {
        sessionId: taskPayload.sessionId,
        action: taskPayload.action,
      },
      error: null,
      startedAt,
      completedAt,
      durationMs: Date.now() - startTime,
    }
  }

  async getIntelMetrics(): Promise<IntelligenceMetrics> {
    const sessions = await IntelligenceSessionManager.getActiveSessions()
    return IntelligenceMetricsCollector.collect(this.descriptor.id, sessions.length)
  }

  async getIntelHealth(): Promise<IntelligenceHealthReport> {
    return IntelligenceHealthManager.check(this.descriptor.id)
  }

  getCapabilityDefinition(): CapabilityDefinition {
    return structuredClone(this.capabilityDefinition)
  }

  getIntelConfig(): IntelligenceWorkerConfig {
    return { ...this.intelConfig }
  }

  async pause(): Promise<void> {
    await super.pause()
    await this.eventBus.publish("intelligence", "intelligence.worker.paused", {
      workerId: this.descriptor.id,
    })
  }

  async resume(): Promise<void> {
    await super.resume()
    await this.eventBus.publish("intelligence", "intelligence.worker.resumed", {
      workerId: this.descriptor.id,
    })
  }

  async shutdown(): Promise<void> {
    await super.shutdown()
    await this.eventBus.publish("intelligence", "intelligence.worker.shutdown", {
      workerId: this.descriptor.id,
    })
  }

  private createError(startedAt: string, code: string, message: string): IExecutionResult {
    const completedAt = new Date().toISOString()
    return {
      sessionId: "",
      success: false,
      output: null,
      error: {
        code,
        message,
        module: "IntelligenceWorker",
        severity: "error",
        timestamp: completedAt,
        details: null,
        cause: null,
      },
      startedAt,
      completedAt,
      durationMs: 0,
    }
  }
}
