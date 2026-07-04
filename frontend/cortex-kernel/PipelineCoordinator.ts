import type { MissionSession, PipelineStage, PipelineTransition, PipelineExecution, MissionState } from "./types"
import { EngineRegistry } from "./EngineRegistry"
import { ContextManager } from "./ContextManager"
import { StateMachine } from "./StateMachine"
import { CorrelationManager } from "./CorrelationManager"
import { KernelTelemetry } from "./KernelTelemetry"
import { generateId } from "./shared"

const executions = new Map<string, PipelineExecution>()

export const PipelineCoordinator = {
  async initializeExecution(session: MissionSession): Promise<PipelineExecution> {
    const stages = EngineRegistry.getStageOrder()
    const execution: PipelineExecution = {
      id: generateId("exec"),
      sessionId: session.id,
      stages,
      currentStage: stages[0],
      transitions: [],
      startedAt: new Date().toISOString(),
      completedAt: null,
      status: "running",
      error: null,
    }
    executions.set(session.id, execution)
    return execution
  },

  async getExecution(sessionId: string): Promise<PipelineExecution | null> {
    return executions.get(sessionId) ?? null
  },

  async advancePipeline(
    session: MissionSession,
    currentState: MissionState,
    engineOutput: Record<string, unknown>,
  ): Promise<{ session: MissionSession; transition: PipelineTransition; execution: PipelineExecution }> {
    const execution = executions.get(session.id)
    if (!execution) throw new Error(`No execution found for session: ${session.id}`)

    const nextStage = await StateMachine.getNextStage(session.pipelineStage)
    if (!nextStage) {
      const finalized: PipelineExecution = {
        ...execution,
        status: "completed",
        completedAt: new Date().toISOString(),
      }
      executions.set(session.id, finalized)
      throw new Error(`No next stage from ${session.pipelineStage} — pipeline complete`)
    }

    const nextState = await StateMachine.getStateForStage(nextStage)

    const canTransition = await StateMachine.canTransition(currentState, nextState)
    if (!canTransition) {
      throw new Error(`Cannot transition from state ${currentState} to ${nextState}`)
    }

    const updatedContext = await ContextManager.propagateContext(session.context, {
      [`${nextStage}_output`]: engineOutput,
      previousStage: session.pipelineStage,
    })

    const transition: PipelineTransition = {
      id: generateId("transition"),
      sessionId: session.id,
      fromStage: session.pipelineStage,
      toStage: nextStage,
      timestamp: new Date().toISOString(),
      triggeredBy: "PipelineCoordinator",
    }

    const updatedSession: MissionSession = {
      ...session,
      state: nextState,
      pipelineStage: nextStage,
      context: updatedContext,
      updatedAt: new Date().toISOString(),
    }

    const updatedExecution: PipelineExecution = {
      ...execution,
      currentStage: nextStage,
      transitions: [...execution.transitions, transition],
    }
    executions.set(session.id, updatedExecution)

    return { session: updatedSession, transition, execution: updatedExecution }
  },

  async failPipeline(sessionId: string, error: string): Promise<void> {
    const execution = executions.get(sessionId)
    if (execution) {
      executions.set(sessionId, {
        ...execution,
        status: "failed",
        completedAt: new Date().toISOString(),
        error,
      })
    }
  },

  async completePipeline(sessionId: string): Promise<void> {
    const execution = executions.get(sessionId)
    if (execution) {
      executions.set(sessionId, {
        ...execution,
        status: "completed",
        completedAt: new Date().toISOString(),
      })
    }
  },
}
