import type { ExecutionLifecycle, ExecutionStage, StageTransitionMap } from "./types"
import { generateId } from "./shared"

const defaultTransitions: StageTransitionMap = {
  initialized: ["queued"],
  queued: ["preparing"],
  preparing: ["executing", "failed"],
  executing: ["validating", "failed"],
  validating: ["completed", "failed", "recovering"],
  completed: [],
  failed: ["recovering", "rolled_back"],
  recovering: ["executing", "failed", "rolled_back"],
  rolled_back: ["initialized"],
}

export const LifecycleCoordinator = {
  async coordinateLifecycle(): Promise<ExecutionLifecycle> {
    return {
      id: generateId("lifecycle"),
      currentStage: "initialized",
      availableTransitions: defaultTransitions,
      transitionHistory: [],
    }
  },
}
