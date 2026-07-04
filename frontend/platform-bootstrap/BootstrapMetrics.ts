import { BootstrapState } from "./types"
import type { BootstrapMetricsData } from "./types"
import { BootstrapRegistry } from "./BootstrapRegistry"
import { BootstrapSequence } from "./BootstrapSequence"
import { BootstrapLifecycle } from "./BootstrapLifecycle"

let startTime = 0
let restartCount = 0

export const BootstrapMetrics = {
  async collect(): Promise<BootstrapMetricsData> {
    const modules = await BootstrapRegistry.listModules()
    const sequence = await BootstrapSequence.getSequence()
    const transitions = await BootstrapLifecycle.getTransitions()

    const completedStages = sequence ? sequence.stages.filter((s) => s.status === BootstrapState.ACTIVE).length : 0
    const failedStages = sequence ? sequence.stages.filter((s) => s.status === BootstrapState.FAILED).length : 0
    const totalStages = sequence ? sequence.stages.length : 0
    const startupDurationMs = startTime > 0 ? Date.now() - startTime : 0
    const activeModules = modules.filter((m) => m.status === BootstrapState.ACTIVE).length
    const startupCoverage = modules.length > 0 ? Math.round((activeModules / modules.length) * 100) : 0

    return {
      startupDurationMs,
      totalStages,
      completedStages,
      failedStages,
      restartCount,
      startupCoverage,
      totalModules: modules.length,
      activeModules,
    }
  },

  async recordStart(): Promise<void> {
    startTime = Date.now()
  },

  async recordRestart(): Promise<void> {
    restartCount++
  },
}