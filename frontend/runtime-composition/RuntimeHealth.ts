import { type RuntimeHealthData, RuntimeCompositionState } from "./types"
import { RuntimeRegistry } from "./RuntimeRegistry"
import { RuntimeDependencyResolver } from "./RuntimeDependencyResolver"
import { RuntimeCoordinator } from "./RuntimeCoordinator"

export const RuntimeHealth = {
  async check(): Promise<RuntimeHealthData> {
    const modules = await RuntimeRegistry.listModules()
    const { missing, cycles } = await RuntimeDependencyResolver.resolveDependencies()
    const currentState = await RuntimeCoordinator.getState()

    const dependencyHealth = missing.length === 0 && cycles.length === 0
    const healthyModules = modules.filter((m) => m.state === RuntimeCompositionState.ACTIVE).length
    const runtimeReady = modules.length > 0 && dependencyHealth && currentState === RuntimeCompositionState.ACTIVE
    const recoveryReady = currentState === RuntimeCompositionState.FAILED

    return {
      runtimeReady,
      dependencyHealth,
      lifecycleHealth: currentState !== RuntimeCompositionState.PENDING && currentState !== RuntimeCompositionState.FAILED,
      recoveryReady,
      currentState,
      lastError: cycles.length > 0 ? `cycles found: ${JSON.stringify(cycles)}` : missing.length > 0 ? `missing: ${missing.join(", ")}` : null,
      healthyModules,
      totalModules: modules.length,
    }
  },
}
