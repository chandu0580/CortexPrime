import type { MissionState, PipelineStage } from "./types"

const stateTransitions: Record<MissionState, MissionState[]> = {
  created: ["initializing"],
  initializing: ["intaking"],
  intaking: ["analyzing", "failed"],
  analyzing: ["reasoning", "failed"],
  reasoning: ["deciding", "failed"],
  deciding: ["orchestrating", "failed"],
  orchestrating: ["validating", "failed"],
  validating: ["ready_for_runtime", "failed"],
  ready_for_runtime: ["completed", "failed"],
  completed: [],
  failed: ["initializing"],
  cancelled: [],
}

const stageProgression: PipelineStage[] = [
  "user_intent",
  "mission_session",
  "mission_intelligence",
  "enterprise_reasoning",
  "enterprise_decision",
  "mission_orchestrator",
  "execution_readiness",
  "runtime",
]

export const StateMachine = {
  async canTransition(from: MissionState, to: MissionState): Promise<boolean> {
    const allowed = stateTransitions[from]
    return allowed?.includes(to) ?? false
  },

  async transition(currentState: MissionState, targetState: MissionState): Promise<MissionState> {
    const allowed = stateTransitions[currentState]
    if (!allowed?.includes(targetState)) {
      throw new Error(`Invalid state transition: ${currentState} → ${targetState}`)
    }
    return targetState
  },

  async getValidTransitions(state: MissionState): Promise<MissionState[]> {
    return stateTransitions[state] ?? []
  },

  async getStageFromState(state: MissionState): Promise<PipelineStage> {
    const map: Record<MissionState, PipelineStage> = {
      created: "user_intent",
      initializing: "mission_session",
      intaking: "mission_session",
      analyzing: "mission_intelligence",
      reasoning: "enterprise_reasoning",
      deciding: "enterprise_decision",
      orchestrating: "mission_orchestrator",
      validating: "execution_readiness",
      ready_for_runtime: "runtime",
      completed: "runtime",
      failed: "mission_session",
      cancelled: "mission_session",
    }
    return map[state]
  },

  async getNextStage(currentStage: PipelineStage): Promise<PipelineStage | null> {
    const idx = stageProgression.indexOf(currentStage)
    if (idx === -1 || idx >= stageProgression.length - 1) return null
    return stageProgression[idx + 1]
  },

  async getPreviousStage(currentStage: PipelineStage): Promise<PipelineStage | null> {
    const idx = stageProgression.indexOf(currentStage)
    if (idx <= 0) return null
    return stageProgression[idx - 1]
  },

  async getStateForStage(stage: PipelineStage): Promise<MissionState> {
    const map: Record<PipelineStage, MissionState> = {
      user_intent: "intaking",
      mission_session: "analyzing",
      mission_intelligence: "analyzing",
      enterprise_reasoning: "reasoning",
      enterprise_decision: "deciding",
      mission_orchestrator: "orchestrating",
      execution_readiness: "validating",
      runtime: "ready_for_runtime",
    }
    return map[stage]
  },

  async isTerminalState(state: MissionState): Promise<boolean> {
    return state === "completed" || state === "failed" || state === "cancelled"
  },
}
