import { type BootstrapHealthData, BootstrapState } from "./types"
import { BootstrapRegistry } from "./BootstrapRegistry"
import { BootstrapSequence } from "./BootstrapSequence"
import { BootstrapDependencyResolver } from "./BootstrapDependencyResolver"

let currentState: BootstrapState = BootstrapState.PENDING

export const BootstrapHealth = {
  async check(): Promise<BootstrapHealthData> {
    const modules = await BootstrapRegistry.listModules()
    const sequence = await BootstrapSequence.getSequence()
    const { missing, cycles } = await BootstrapDependencyResolver.resolveDependencies()

    const dependencyReady = missing.length === 0 && cycles.length === 0
    const currentStageType = sequence?.stages.find((s) => s.status === BootstrapState.BOOTSTRAPPING || s.status === BootstrapState.INITIALIZING)?.type ?? null
    const currentStageLabel = currentStageType ? currentStageType.charAt(0).toUpperCase() + currentStageType.slice(1) : null
    const healthyModules = modules.filter((m) => m.status === BootstrapState.ACTIVE).length
    const startupReady = modules.length > 0 && dependencyReady
    const restartReady = currentState === BootstrapState.SHUTDOWN || currentState === BootstrapState.FAILED
    const recoveryReady = currentState === BootstrapState.FAILED

    return {
      startupReady,
      dependencyReady,
      restartReady,
      recoveryReady,
      currentState,
      currentStage: currentStageLabel,
      lastError: sequence?.stages.find((s) => s.status === BootstrapState.FAILED)?.label ?? null,
      healthyModules,
      totalModules: modules.length,
    }
  },

  async setState(state: BootstrapState): Promise<void> {
    currentState = state
  },
}