import type { CompositionMetricsData } from "./types"
import { CompositionRegistry } from "./CompositionRegistry"
import { CompositionLifecycle } from "./CompositionLifecycle"
import { generateId } from "./shared"

const startTime = Date.now()
let shutdownStartTime: number | null = null

export const CompositionMetrics = {
  async collect(): Promise<CompositionMetricsData> {
    const modules = await CompositionRegistry.listModules()
    const transitions = await CompositionLifecycle.getTransitions()
    const activeModules = modules.length
    const dependencyCount = modules.reduce((sum, m) => sum + m.dependencies.length, 0)
    const startupDurationMs = Date.now() - startTime
    const shutdownDurationMs = shutdownStartTime ? Date.now() - shutdownStartTime : 0
    const totalTransitions = transitions.length
    const failedTransitions = transitions.filter((t) => t.reason.includes("failed")).length
    const compositionCoverage = modules.length > 0 ? Math.round((activeModules / modules.length) * 100) : 0

    return {
      moduleCount: modules.length,
      activeModules,
      dependencyCount,
      startupDurationMs,
      shutdownDurationMs,
      compositionCoverage,
      totalTransitions,
      failedTransitions,
    }
  },

  async recordShutdownStart(): Promise<void> {
    shutdownStartTime = Date.now()
  },
}