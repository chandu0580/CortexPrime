import { RuntimeCompositionState } from "./types"
import type { RuntimeMetricsData } from "./types"
import { RuntimeRegistry } from "./RuntimeRegistry"
import { RuntimeCompositionGraph } from "./RuntimeCompositionGraph"
import { RuntimeLifecycle } from "./RuntimeLifecycle"

let startTime = 0
let shutdownStartTime = 0
let restartCount = 0

export const RuntimeMetrics = {
  async collect(): Promise<RuntimeMetricsData> {
    const modules = await RuntimeRegistry.listModules()
    const transitions = await RuntimeLifecycle.getTransitions()
    const graph = await RuntimeCompositionGraph.buildGraph()

    const activeModules = modules.filter((m) => m.state === RuntimeCompositionState.ACTIVE).length
    const dependencyCount = Array.from(graph.adjacency.values()).reduce((sum, deps) => sum + deps.length, 0)
    const startupDurationMs = startTime > 0 ? Date.now() - startTime : 0
    const sdDurationMs = shutdownStartTime > 0 ? Date.now() - shutdownStartTime : 0
    const executionCoverage = modules.length > 0 ? Math.round((activeModules / modules.length) * 100) : 0

    return {
      moduleCount: modules.length,
      activeModules,
      startupDurationMs,
      shutdownDurationMs: sdDurationMs,
      restartCount,
      executionCoverage,
      dependencyCount,
      totalTransitions: transitions.length,
    }
  },

  async recordStart(): Promise<void> { startTime = Date.now() },
  async recordShutdown(): Promise<void> { shutdownStartTime = Date.now() },
  async recordRestart(): Promise<void> { restartCount++ },
}
