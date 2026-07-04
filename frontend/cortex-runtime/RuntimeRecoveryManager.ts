import { type RuntimeRecovery, RuntimeState, StartupStrategy } from "./types"
import { generateId } from "./shared"

const recoveries: RuntimeRecovery[] = []
let failureCount = 0

export const RuntimeRecoveryManager = {
  async trackFailure(): Promise<void> {
    failureCount++
  },

  async getFailureCount(): Promise<number> {
    return failureCount
  },

  async determineRestartEligibility(state: RuntimeState): Promise<boolean> {
    return state === RuntimeState.FAILED || state === RuntimeState.SHUTDOWN
  },

  async recoveryReadiness(state: RuntimeState): Promise<boolean> {
    return state === RuntimeState.FAILED
  },

  async recover(fromState: RuntimeState, strategy: StartupStrategy = StartupStrategy.TOPOLOGICAL): Promise<RuntimeRecovery> {
    const attempt = recoveries.length + 1
    const recovery: RuntimeRecovery = {
      id: generateId("recovery"),
      attempt,
      fromState,
      toState: RuntimeState.PENDING,
      strategy,
      success: true,
      errors: [],
      timestamp: new Date().toISOString(),
    }
    recoveries.push(recovery)
    return recovery
  },

  async restartStrategy(): Promise<StartupStrategy> {
    if (failureCount <= 1) return StartupStrategy.TOPOLOGICAL
    return StartupStrategy.SEQUENTIAL
  },

  async rollbackSupport(): Promise<boolean> {
    return true
  },

  async getRecoveries(): Promise<RuntimeRecovery[]> {
    return [...recoveries]
  },
}