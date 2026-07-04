import type { CompositionHealthData } from "./types"
import { CompositionRegistry } from "./CompositionRegistry"
import { CompositionLifecycle } from "./CompositionLifecycle"
import { CompositionDependencyResolver } from "./CompositionDependencyResolver"

export const CompositionHealth = {
  async check(): Promise<CompositionHealthData> {
    const modules = await CompositionRegistry.listModules()
    const transitions = await CompositionLifecycle.getTransitions()
    const { missing, cycles } = await CompositionDependencyResolver.resolveDependencies()

    const dependenciesHealthy = missing.length === 0 && cycles.length === 0
    const lifecycleHealthy = transitions.length > 0
    const platformReady = dependenciesHealthy && lifecycleHealthy
    const recoveryReady = platformReady

    const lastTransition = transitions.length > 0 ? transitions[transitions.length - 1].timestamp : null
    const lastError = transitions.filter((t) => t.reason.includes("failed")).pop()?.timestamp ?? null

    return {
      platformReady,
      dependenciesHealthy,
      lifecycleHealthy,
      recoveryReady,
      activeNodeCount: modules.length,
      totalNodeCount: modules.length,
      lastTransition,
      lastError,
    }
  },
}