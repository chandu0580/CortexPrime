import type { MissionSession, EngineDescriptor, PipelineExecution, KernelMetadata, KernelContext, EngineInvocation, TelemetryEvent, PipelineTransition } from "./types"
import { SessionManager } from "./SessionManager"
import { EngineRegistry } from "./EngineRegistry"
import { PipelineCoordinator } from "./PipelineCoordinator"
import { ContextManager } from "./ContextManager"
import { LifecycleManager } from "./LifecycleManager"
import { StateMachine } from "./StateMachine"
import { CorrelationManager } from "./CorrelationManager"
import { KernelTelemetry } from "./KernelTelemetry"

export const cortexKernel = {
  async createMissionSession(userIntent: string): Promise<{ session: MissionSession; execution: PipelineExecution }> {
    await KernelTelemetry.setKernelState("running")
    const session = await SessionManager.createSession(userIntent)
    await LifecycleManager.initializeSession(session)
    await CorrelationManager.createCorrelation(session.id)
    const execution = await PipelineCoordinator.initializeExecution(session)
    await KernelTelemetry.emitEvent(session.id, "session", "session.created", `Mission session created: ${session.id}`)
    return { session, execution }
  },

  async registerEngine(descriptor: EngineDescriptor, handler: (session: MissionSession) => Promise<Record<string, unknown>>): Promise<void> {
    await EngineRegistry.registerEngine(descriptor, handler)
    await LifecycleManager.recordEvent("engine.registered", `Engine ${descriptor.name} v${descriptor.version} registered for stage: ${descriptor.pipelineStage}`, null, {
      engineId: descriptor.id,
      name: descriptor.name,
      stage: descriptor.pipelineStage,
    })
  },

  async invokeEngine(sessionId: string, engineId: string): Promise<EngineInvocation> {
    const session = await SessionManager.getSession(sessionId)
    if (!session) throw new Error(`Session not found: ${sessionId}`)

    const handler = await EngineRegistry.getHandler(engineId)
    if (!handler) throw new Error(`No handler registered for engine: ${engineId}`)

    const engine = await EngineRegistry.getEngine(engineId)
    if (!engine) throw new Error(`Engine not registered: ${engineId}`)

    const startTime = Date.now()
    const invocation = await EngineRegistry.createInvocationRecord(
      engineId,
      sessionId,
      engine.descriptor.pipelineStage,
      { context: session.context },
    )

    try {
      const output = await handler(session)
      const duration = Date.now() - startTime
      const completed = await EngineRegistry.completeInvocation(invocation, output, duration)

      await CorrelationManager.addEngineHop(session.correlationId, engineId)
      await EngineRegistry.recordInvocation(engineId)
      await KernelTelemetry.recordInvocationTelemetry(sessionId, engine.descriptor.name, duration, true)

      return completed
    } catch (err) {
      const duration = Date.now() - startTime
      const error = err instanceof Error ? err.message : String(err)
      const failed = await EngineRegistry.failInvocation(invocation, error, duration)

      await EngineRegistry.setEngineStatus(engineId, "error")
      await KernelTelemetry.recordInvocationTelemetry(sessionId, engine.descriptor.name, duration, false)
      await KernelTelemetry.emitEvent(sessionId, "error", `engine.${engine.descriptor.name}.failed`, error)

      return failed
    }
  },

  async propagateContext(sessionId: string, updates: Record<string, unknown>): Promise<KernelContext> {
    const session = await SessionManager.getSession(sessionId)
    if (!session) throw new Error(`Session not found: ${sessionId}`)

    const updatedContext = await ContextManager.propagateContext(session.context, updates)
    await SessionManager.updateSession(sessionId, { context: updatedContext })

    return updatedContext
  },

  async advancePipeline(sessionId: string, currentState: import("./types").MissionState, engineOutput: Record<string, unknown>): Promise<{
    session: MissionSession
    transition: PipelineTransition
    execution: PipelineExecution
  }> {
    const session = await SessionManager.getSession(sessionId)
    if (!session) throw new Error(`Session not found: ${sessionId}`)

    const result = await PipelineCoordinator.advancePipeline(session, currentState, engineOutput)
    await SessionManager.updateSession(sessionId, { state: result.session.state, pipelineStage: result.session.pipelineStage })
    await LifecycleManager.transitionSession(session, session.state, result.session.state)
    await KernelTelemetry.emitEvent(sessionId, "pipeline", "pipeline.advanced", `Pipeline advanced: ${result.transition.fromStage} → ${result.transition.toStage}`)

    return result
  },

  async transitionState(sessionId: string, fromState: import("./types").MissionState, toState: import("./types").MissionState): Promise<MissionSession> {
    const session = await SessionManager.getSession(sessionId)
    if (!session) throw new Error(`Session not found: ${sessionId}`)

    const newState = await StateMachine.transition(fromState, toState)
    const updatedSession = await SessionManager.updateSession(sessionId, { state: newState })
    await LifecycleManager.transitionSession(session, fromState, toState)

    return updatedSession
  },

  async emitTelemetry(sessionId: string, type: string, name: string, details: string, durationMs?: number): Promise<TelemetryEvent> {
    return KernelTelemetry.emitEvent(sessionId, type, name, details, durationMs ?? null)
  },

  async closeMission(sessionId: string, finalState: "completed" | "failed" | "cancelled"): Promise<MissionSession> {
    const session = await SessionManager.getSession(sessionId)
    if (!session) throw new Error(`Session not found: ${sessionId}`)

    const closed = await SessionManager.closeSession(sessionId, finalState)
    await LifecycleManager.closeSession(session, finalState)
    await CorrelationManager.closeCorrelation(session.correlationId)
    await KernelTelemetry.emitEvent(sessionId, "session", `session.${finalState}`, `Mission session closed: ${finalState}`)

    if (finalState === "completed") {
      await PipelineCoordinator.completePipeline(sessionId)
    } else {
      await PipelineCoordinator.failPipeline(sessionId, `Session closed with state: ${finalState}`)
    }

    return closed
  },

  async getMetadata(): Promise<KernelMetadata> {
    const activeCount = await SessionManager.sessionCount()
    return KernelTelemetry.getMetadata(activeCount)
  },
}
