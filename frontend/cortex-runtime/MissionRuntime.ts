import type { IEventBus, ITelemetry } from "@/platform/interfaces"
import type { RedisConfig } from "@/cognitive-memory/types"
import type { Neo4jConfig } from "@/knowledge-graph/types"
import type { ProviderConfig } from "@/enterprise-reasoning/types"
import type { PlanningStrategy, PlanningPriority } from "@/mission-planning/types"
import { MissionPlanningEngine } from "@/mission-planning/MissionPlanningEngine"
import { MissionExecutionEngine } from "@/mission-execution/MissionExecutionEngine"
import { CognitiveOrchestrator } from "@/cognitive-orchestrator/CognitiveOrchestrator"
import { WorkerOrchestrator } from "@/worker-orchestration/WorkerOrchestrator"
import { CognitiveMemory } from "@/cognitive-memory/CognitiveMemory"
import { KnowledgeGraph } from "@/knowledge-graph/KnowledgeGraph"
import { ConnectorRegistry } from "@/connector-framework/ConnectorRegistry"
import { ReasoningRuntime } from "@/enterprise-reasoning/reasoning-runtime"
import { ReasoningContextBuilder } from "@/enterprise-reasoning/context-builder"
import { generateId } from "./shared"

export interface MissionRuntimeConfig {
  redis?: RedisConfig
  neo4j?: Neo4jConfig
  eventBus: IEventBus
  telemetry: ITelemetry
  reasoning?: {
    providers: ProviderConfig[]
    defaultProvider?: string
    maxRetries?: number
    retryDelayMs?: number
    streamingEnabled?: boolean
  }
}

export interface MissionRuntimeState {
  id: string
  initialized: boolean
  planningEngine: MissionPlanningEngine | null
  executionEngine: MissionExecutionEngine | null
  cognitiveOrchestrator: CognitiveOrchestrator | null
  workerOrchestrator: WorkerOrchestrator | null
  cognitiveMemory: CognitiveMemory | null
  knowledgeGraph: KnowledgeGraph | null
  connectors: Map<string, unknown>
  reasoningRuntime: boolean
  startedAt: string | null
  lastHealthCheck: string | null
}

export interface MissionRuntimeHealth {
  healthy: boolean
  components: {
    planning: boolean
    execution: boolean
    cognitiveOrchestrator: boolean
    workerOrchestrator: boolean
    cognitiveMemory: boolean
    knowledgeGraph: boolean
    connectors: boolean
    reasoning: boolean
  }
  timestamp: string
}

export interface MissionRuntimeMetrics {
  missionsStarted: number
  missionsCompleted: number
  missionsFailed: number
  averagePlanningDurationMs: number
  averageExecutionDurationMs: number
  activeSessions: number
  lastMissionStartedAt: string | null
  lastMissionCompletedAt: string | null
  totalReasoningCalls: number
  totalReasoningTokens: number
  totalReasoningCost: number
  reasoningErrors: number
}

export class MissionRuntime {
  private state: MissionRuntimeState
  private readonly config: MissionRuntimeConfig
  private metrics: MissionRuntimeMetrics

  constructor(config: MissionRuntimeConfig) {
    this.config = config
    this.state = {
      id: generateId("mission-runtime"),
      initialized: false,
      planningEngine: null,
      executionEngine: null,
      cognitiveOrchestrator: null,
      workerOrchestrator: null,
      cognitiveMemory: null,
      knowledgeGraph: null,
      connectors: new Map(),
      reasoningRuntime: false,
      startedAt: null,
      lastHealthCheck: null,
    }
    this.metrics = {
      missionsStarted: 0,
      missionsCompleted: 0,
      missionsFailed: 0,
      averagePlanningDurationMs: 0,
      averageExecutionDurationMs: 0,
      activeSessions: 0,
      lastMissionStartedAt: null,
      lastMissionCompletedAt: null,
      totalReasoningCalls: 0,
      totalReasoningTokens: 0,
      totalReasoningCost: 0,
      reasoningErrors: 0,
    }
  }

  async initialize(): Promise<void> {
    if (this.state.initialized) return

    const startTime = Date.now()

    try {
      // Initialize planning engine
      this.state.planningEngine = new MissionPlanningEngine(
        this.config.eventBus,
        this.config.telemetry,
      )
      await this.state.planningEngine.initialize()

      // Initialize execution engine
      this.state.executionEngine = new MissionExecutionEngine(
        this.config.eventBus,
        this.config.telemetry,
      )
      await this.state.executionEngine.initialize()

      // Initialize cognitive orchestrator
      this.state.cognitiveOrchestrator = new CognitiveOrchestrator(
        this.config.eventBus,
        this.config.telemetry,
      )
      await this.state.cognitiveOrchestrator.initialize()

      // Initialize worker orchestrator
      this.state.workerOrchestrator = new WorkerOrchestrator(
        this.config.eventBus,
        this.config.telemetry,
      )
      await this.state.workerOrchestrator.initialize()

      // Initialize cognitive memory with Redis
      if (this.config.redis) {
        this.state.cognitiveMemory = new CognitiveMemory(
          this.config.eventBus,
          this.config.telemetry,
          undefined,
          undefined,
          this.config.redis,
        )
        await this.state.cognitiveMemory.initialize()
      }

      // Initialize knowledge graph with Neo4j
      if (this.config.neo4j) {
        this.state.knowledgeGraph = new KnowledgeGraph(
          this.config.eventBus,
          this.config.telemetry,
          undefined,
          undefined,
          this.config.neo4j,
        )
        await this.state.knowledgeGraph.initialize()
      }

      // Initialize reasoning runtime if providers are configured
      if (this.config.reasoning?.providers && this.config.reasoning.providers.length > 0) {
        await ReasoningRuntime.initialize(
          {
            providers: this.config.reasoning.providers,
            maxRetries: this.config.reasoning.maxRetries ?? 3,
            retryDelayMs: this.config.reasoning.retryDelayMs ?? 1000,
            streamingEnabled: this.config.reasoning.streamingEnabled ?? false,
          },
          this.config.eventBus,
          this.config.telemetry,
        )

        // Wire CognitiveMemory and KnowledgeGraph into context builder
        if (this.state.cognitiveMemory) {
          await ReasoningContextBuilder.setCognitiveMemory(this.state.cognitiveMemory)
        }
        if (this.state.knowledgeGraph) {
          await ReasoningContextBuilder.setKnowledgeGraph(this.state.knowledgeGraph)
        }

        this.state.reasoningRuntime = true
      }

      this.state.initialized = true
      this.state.startedAt = new Date().toISOString()

      await this.config.eventBus.publish("mission-runtime", "mission-runtime.initialized", {
        runtimeId: this.state.id,
        durationMs: Date.now() - startTime,
      })

      await this.config.telemetry.recordEvent("mission-runtime.initialized", {
        runtimeId: this.state.id,
        durationMs: Date.now() - startTime,
      })
    } catch (error) {
      await this.config.eventBus.publish("mission-runtime", "mission-runtime.initialization-failed", {
        runtimeId: this.state.id,
        error: error instanceof Error ? error.message : String(error),
      })
      throw error
    }
  }

  async shutdown(): Promise<void> {
    if (!this.state.initialized) return

    const startTime = Date.now()

    try {
      // Shutdown in reverse order
      if (this.state.reasoningRuntime) {
        await ReasoningRuntime.shutdown()
      }

      if (this.state.knowledgeGraph) {
        await this.state.knowledgeGraph.shutdown()
      }

      if (this.state.cognitiveMemory) {
        await this.state.cognitiveMemory.shutdown()
      }

      if (this.state.workerOrchestrator) {
        await this.state.workerOrchestrator.shutdown()
      }

      if (this.state.cognitiveOrchestrator) {
        await this.state.cognitiveOrchestrator.shutdown()
      }

      if (this.state.executionEngine) {
        await this.state.executionEngine.shutdown()
      }

      if (this.state.planningEngine) {
        await this.state.planningEngine.shutdown()
      }

      this.state.initialized = false

      await this.config.eventBus.publish("mission-runtime", "mission-runtime.shutdown", {
        runtimeId: this.state.id,
        durationMs: Date.now() - startTime,
      })

      await this.config.telemetry.recordEvent("mission-runtime.shutdown", {
        runtimeId: this.state.id,
        durationMs: Date.now() - startTime,
      })
    } catch (error) {
      await this.config.eventBus.publish("mission-runtime", "mission-runtime.shutdown-failed", {
        runtimeId: this.state.id,
        error: error instanceof Error ? error.message : String(error),
      })
      throw error
    }
  }

  async startMission(missionId: string, options: {
    name?: string
    description?: string
    strategy?: string
    priority?: number
  } = {}): Promise<{
    success: boolean
    missionId: string
    planningSessionId: string | null
    executionSessionId: string | null
    error: string | null
  }> {
    this.requireInitialized()
    const startTime = Date.now()

    try {
      // Step 1: Create planning session
      const planningResult = await this.state.planningEngine!.createPlan({
        id: generateId("plan-request"),
        type: "create_plan",
        missionId,
        name: options.name,
        description: options.description,
        strategy: options.strategy as any,
        priority: options.priority as any,
      })

      if (!planningResult.success) {
        throw new Error(`Planning failed: ${planningResult.error}`)
      }

      // Step 2: Optimize plan
      const optimizationResult = await this.state.planningEngine!.optimizePlan({
        id: generateId("optimize-request"),
        type: "optimize",
        missionId,
        planId: planningResult.plan?.id,
      })

      if (!optimizationResult.success) {
        throw new Error(`Optimization failed: ${optimizationResult.error}`)
      }

      // Step 3: Execute mission
      const executionResult = await this.state.executionEngine!.executeMission({
        id: generateId("exec-request"),
        type: "execute",
        missionId,
        strategy: options.strategy as any,
      })

      if (!executionResult.success) {
        throw new Error(`Execution failed: ${executionResult.error}`)
      }

      // Step 4: Orchestrate cognitively
      const cognitiveResult = await this.state.cognitiveOrchestrator!.orchestrate({
        id: generateId("cognitive-request"),
        type: "orchestrate",
        context: {
          missionId,
          planningSessionId: planningResult.session?.id,
          executionSessionId: executionResult.session?.id,
        },
      })

      // Step 5: Orchestrate workers
      const workerResult = await this.state.workerOrchestrator!.process({
        id: generateId("worker-request"),
        type: "orchestrate",
        missionId,
        workerIds: [],
        workerType: "executor",
        capabilities: ["mission-execution"],
        task: `Execute mission ${missionId}`,
      })

      // Step 6: Persist to memory and knowledge graph
      if (this.state.cognitiveMemory) {
        await this.state.cognitiveMemory.storeMissionContext(missionId, {
          planningSessionId: planningResult.session?.id,
          executionSessionId: executionResult.session?.id,
          cognitiveSessionId: cognitiveResult.session?.id,
          workerSessionId: workerResult.session?.id,
          startedAt: new Date().toISOString(),
        })
      }

      if (this.state.knowledgeGraph) {
        await this.state.knowledgeGraph.createMissionEntity(missionId, {
          name: options.name || `Mission-${missionId}`,
          description: options.description,
          status: "in_progress",
          startedAt: new Date().toISOString(),
        })
      }

      // Step 7: LLM Reasoning — generate mission plan and worker decisions
      if (this.state.reasoningRuntime) {
        try {
          const llmPlan = await ReasoningRuntime.planMission(
            missionId,
            missionId,
            options.description || options.name || `Mission ${missionId}`,
            (options.priority !== undefined
              ? options.priority <= 1 ? "low" : options.priority <= 3 ? "medium" : options.priority <= 5 ? "high" : "critical"
              : "medium") as "low" | "medium" | "high" | "critical",
            {
        strategy: options.strategy as any,
              planningSessionId: planningResult.session?.id,
              executionSessionId: executionResult.session?.id,
            },
          )

          // Store LLM plan in memory
          if (this.state.cognitiveMemory) {
            await this.state.cognitiveMemory.storeWorking(
              `mission-${missionId}`,
              `mission:${missionId}:llm-plan`,
              llmPlan as unknown as Record<string, unknown>,
              86400000,
              "high",
              "global",
              ["mission", "llm-plan"],
              { missionId, type: "llm-mission-plan" },
            )
          }

          // Generate worker decisions via LLM
          const workerDecision = await ReasoningRuntime.decideWorkerAction(
            missionId,
            missionId,
            `Execute ${llmPlan.title || missionId}`,
            "high",
            {
              phases: llmPlan.phases?.length ?? 0,
              keyResults: llmPlan.keyResults,
              risks: llmPlan.risks,
            },
          )

          // Store worker decision in memory
          if (this.state.cognitiveMemory) {
            await this.state.cognitiveMemory.storeWorking(
              `mission-${missionId}`,
              `mission:${missionId}:worker-decision`,
              workerDecision as unknown as Record<string, unknown>,
              86400000,
              "high",
              "global",
              ["mission", "worker-decision"],
              { missionId, type: "llm-worker-decision" },
            )
          }

          this.metrics.totalReasoningCalls++
          await this.config.telemetry.recordEvent("mission-runtime.reasoning-completed", {
            runtimeId: this.state.id,
            missionId,
            planTitle: llmPlan.title,
            phasesCount: llmPlan.phases?.length ?? 0,
          })
        } catch (reasoningError) {
          this.metrics.reasoningErrors++
          await this.config.telemetry.recordEvent("mission-runtime.reasoning-failed", {
            runtimeId: this.state.id,
            missionId,
            error: reasoningError instanceof Error ? reasoningError.message : String(reasoningError),
          })
          // Continue mission execution even if reasoning fails
        }
      }

      this.metrics.missionsStarted++
      this.metrics.lastMissionStartedAt = new Date().toISOString()
      this.metrics.activeSessions++

      await this.config.eventBus.publish("mission-runtime", "mission-runtime.mission-started", {
        runtimeId: this.state.id,
        missionId,
        planningSessionId: planningResult.session?.id,
        executionSessionId: executionResult.session?.id,
      })

      await this.config.telemetry.recordEvent("mission-runtime.mission-started", {
        runtimeId: this.state.id,
        missionId,
        durationMs: Date.now() - startTime,
      })

      return {
        success: true,
        missionId,
        planningSessionId: planningResult.session?.id || null,
        executionSessionId: executionResult.session?.id || null,
        error: null,
      }
    } catch (error) {
      this.metrics.missionsFailed++

      await this.config.eventBus.publish("mission-runtime", "mission-runtime.mission-failed", {
        runtimeId: this.state.id,
        missionId,
        error: error instanceof Error ? error.message : String(error),
      })

      await this.config.telemetry.recordEvent("mission-runtime.mission-failed", {
        runtimeId: this.state.id,
        missionId,
        error: error instanceof Error ? error.message : String(error),
      })

      return {
        success: false,
        missionId,
        planningSessionId: null,
        executionSessionId: null,
        error: error instanceof Error ? error.message : String(error),
      }
    }
  }

  async completeMission(missionId: string, success: boolean): Promise<void> {
    this.requireInitialized()

    if (success) {
      this.metrics.missionsCompleted++
    } else {
      this.metrics.missionsFailed++
    }

    this.metrics.lastMissionCompletedAt = new Date().toISOString()
    this.metrics.activeSessions = Math.max(0, this.metrics.activeSessions - 1)

    // Update knowledge graph
    if (this.state.knowledgeGraph) {
      await this.state.knowledgeGraph.updateMissionEntity(missionId, {
        status: success ? "completed" : "failed",
        completedAt: new Date().toISOString(),
      })
    }

    await this.config.eventBus.publish("mission-runtime", "mission-runtime.mission-completed", {
      runtimeId: this.state.id,
      missionId,
      success,
    })

    await this.config.telemetry.recordEvent("mission-runtime.mission-completed", {
      runtimeId: this.state.id,
      missionId,
      success,
    })
  }

  async getHealth(): Promise<MissionRuntimeHealth> {
    const components = {
      planning: await this.checkComponentHealth(this.state.planningEngine),
      execution: await this.checkComponentHealth(this.state.executionEngine),
      cognitiveOrchestrator: await this.checkComponentHealth(this.state.cognitiveOrchestrator),
      workerOrchestrator: await this.checkComponentHealth(this.state.workerOrchestrator),
      cognitiveMemory: await this.checkMemoryHealth(),
      knowledgeGraph: await this.checkGraphHealth(),
      connectors: await this.checkConnectorsHealth(),
      reasoning: this.state.reasoningRuntime ? ReasoningRuntime.isInitialized() : true,
    }

    const healthy = Object.values(components).every(Boolean)

    this.state.lastHealthCheck = new Date().toISOString()

    return {
      healthy,
      components,
      timestamp: new Date().toISOString(),
    }
  }

  async getMetrics(): Promise<MissionRuntimeMetrics> {
    return { ...this.metrics }
  }

  async getState(): Promise<MissionRuntimeState> {
    return { ...this.state }
  }

  async registerConnector(connectorId: string, connector: unknown): Promise<void> {
    this.requireInitialized()
    
    this.state.connectors.set(connectorId, connector)
    
    await this.config.eventBus.publish("mission-runtime", "mission-runtime.connector-registered", {
      runtimeId: this.state.id,
      connectorId,
    })
    
    await this.config.telemetry.recordEvent("mission-runtime.connector-registered", {
      runtimeId: this.state.id,
      connectorId,
    })
  }

  async getConnector(connectorId: string): Promise<unknown | null> {
    this.requireInitialized()
    return this.state.connectors.get(connectorId) || null
  }

  async getConnectors(): Promise<Map<string, unknown>> {
    this.requireInitialized()
    return new Map(this.state.connectors)
  }

  private requireInitialized(): void {
    if (!this.state.initialized) {
      throw new Error("MissionRuntime not initialized. Call initialize() first.")
    }
  }

  private async checkComponentHealth(engine: unknown): Promise<boolean> {
    if (!engine) return false

    try {
      const healthEngine = engine as { health(): Promise<unknown> }
      await healthEngine.health()
      return true
    } catch {
      return false
    }
  }

  private async checkMemoryHealth(): Promise<boolean> {
    if (!this.state.cognitiveMemory) return false

    try {
      const health = await this.state.cognitiveMemory.health()
      return health.status === "healthy"
    } catch {
      return false
    }
  }

  private async checkGraphHealth(): Promise<boolean> {
    if (!this.state.knowledgeGraph) return false

    try {
      const health = await this.state.knowledgeGraph.health()
      return health.status === "healthy"
    } catch {
      return false
    }
  }

  private async checkConnectorsHealth(): Promise<boolean> {
    if (this.state.connectors.size === 0) return true

    try {
      // Check if connector registry is healthy
      const registrationCount = await ConnectorRegistry.registrationCount()
      return registrationCount >= 0
    } catch {
      return false
    }
  }
}
