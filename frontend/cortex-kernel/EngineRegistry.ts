import type { EngineDescriptor, EngineRegistration, EngineStatus, EngineInvocation, PipelineStage, MissionSession } from "./types"
import { generateId } from "./shared"

const registry = new Map<string, EngineRegistration>()

type EngineHandler = (session: MissionSession) => Promise<Record<string, unknown>>

const handlers = new Map<string, EngineHandler>()

const pipelineOrder: PipelineStage[] = [
  "user_intent",
  "mission_session",
  "mission_intelligence",
  "enterprise_reasoning",
  "enterprise_decision",
  "mission_orchestrator",
  "execution_readiness",
  "runtime",
]

export const EngineRegistry = {
  async registerEngine(descriptor: EngineDescriptor, handler: EngineHandler): Promise<void> {
    const registration: EngineRegistration = {
      descriptor,
      status: "registered",
      registeredAt: new Date().toISOString(),
      lastHeartbeat: null,
      invocations: 0,
    }
    registry.set(descriptor.id, registration)
    handlers.set(descriptor.id, handler)
  },

  async getEngine(engineId: string): Promise<EngineRegistration | null> {
    return registry.get(engineId) ?? null
  },

  async getHandler(engineId: string): Promise<EngineHandler | undefined> {
    return handlers.get(engineId)
  },

  async getEnginesByStage(stage: PipelineStage): Promise<EngineRegistration[]> {
    return Array.from(registry.values()).filter(
      (e) => e.descriptor.pipelineStage === stage && e.status !== "disabled",
    )
  },

  async discoverEngines(capability: string): Promise<EngineRegistration[]> {
    return Array.from(registry.values()).filter((e) => {
      const desc = e.descriptor
      return (
        desc.name.toLowerCase().includes(capability.toLowerCase()) ||
        desc.description.toLowerCase().includes(capability.toLowerCase()) ||
        desc.inputTypes.some((t) => t.toLowerCase().includes(capability.toLowerCase())) ||
        desc.outputTypes.some((t) => t.toLowerCase().includes(capability.toLowerCase()))
      )
    })
  },

  async recordInvocation(engineId: string): Promise<void> {
    const engine = registry.get(engineId)
    if (engine) {
      registry.set(engineId, {
        ...engine,
        invocations: engine.invocations + 1,
        lastHeartbeat: new Date().toISOString(),
        status: "active",
      })
    }
  },

  async setEngineStatus(engineId: string, status: EngineStatus): Promise<void> {
    const engine = registry.get(engineId)
    if (engine) {
      registry.set(engineId, { ...engine, status })
    }
  },

  async createInvocationRecord(
    engineId: string,
    sessionId: string,
    stage: PipelineStage,
    input: Record<string, unknown>,
  ): Promise<EngineInvocation> {
    return {
      id: generateId("invocation"),
      engineId,
      sessionId,
      stage,
      input,
      output: {},
      startedAt: new Date().toISOString(),
      completedAt: null,
      duration: null,
      status: "running",
      error: null,
    }
  },

  async completeInvocation(
    invocation: EngineInvocation,
    output: Record<string, unknown>,
    duration: number,
  ): Promise<EngineInvocation> {
    return {
      ...invocation,
      output,
      completedAt: new Date().toISOString(),
      duration,
      status: "completed",
    }
  },

  async failInvocation(
    invocation: EngineInvocation,
    error: string,
    duration: number,
  ): Promise<EngineInvocation> {
    return {
      ...invocation,
      completedAt: new Date().toISOString(),
      duration,
      status: "failed",
      error,
    }
  },

  async getEngineCount(): Promise<number> {
    return registry.size
  },

  getStageOrder(): PipelineStage[] {
    return [...pipelineOrder]
  },
}
