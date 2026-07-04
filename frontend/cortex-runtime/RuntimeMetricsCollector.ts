import type { RuntimeMetricsData, RuntimeState } from "./types"
import { RuntimeManifest } from "./RuntimeManifest"
import { RuntimeInitializer } from "./RuntimeInitializer"
import { RuntimeRecoveryManager } from "./RuntimeRecoveryManager"

let startTime = 0
let shutdownStartTime = 0
let restartCount = 0

export const RuntimeMetricsCollector = {
  async collect(currentState: RuntimeState): Promise<RuntimeMetricsData> {
    const modules = await RuntimeManifest.listModules()
    const { initialized, total } = await RuntimeInitializer.getProgress()
    const failures = await RuntimeRecoveryManager.getFailureCount()
    const recoveries = await RuntimeRecoveryManager.getRecoveries()
    const uptimeMs = startTime > 0 ? Date.now() - startTime : 0
    const startupDurationMs = startTime > 0 ? Date.now() - startTime : 0
    const shutdownDurationMs = shutdownStartTime > 0 ? Date.now() - shutdownStartTime : 0
    const moduleCoverage = total > 0 ? Math.round((initialized / total) * 100) : 0

    return {
      startupDurationMs,
      shutdownDurationMs,
      restartCount,
      failureCount: failures,
      recoveryCount: recoveries.length,
      totalModules: modules.length,
      activeModules: initialized,
      moduleCoverage,
      totalTransitions: 0,
      uptimeMs,
    }
  },

  async recordStart(): Promise<void> { startTime = Date.now() },
  async recordShutdown(): Promise<void> { shutdownStartTime = Date.now() },
  async recordRestart(): Promise<void> { restartCount++ },
}