import { type RuntimeHealthData, RuntimeState, RuntimeStatus } from "./types"
import { RuntimeManifest } from "./RuntimeManifest"
import { RuntimeInitializer } from "./RuntimeInitializer"
import { RuntimeLoader } from "./RuntimeLoader"
import { RuntimeRecoveryManager } from "./RuntimeRecoveryManager"

export const RuntimeHealthManager = {
  async check(currentState: RuntimeState): Promise<RuntimeHealthData> {
    const modules = await RuntimeManifest.listModules()
    const missing = await RuntimeLoader.detectMissingModules()
    const { initialized } = await RuntimeInitializer.getProgress()
    const canRecover = await RuntimeRecoveryManager.recoveryReadiness(currentState)

    const dependencyHealthy = missing.length === 0
    const healthyModules = initialized
    const platformReady = currentState === RuntimeState.ACTIVE && dependencyHealthy
    const recoveryReady = canRecover

    let currentStatus: RuntimeStatus
    if (currentState === RuntimeState.ACTIVE) currentStatus = RuntimeStatus.HEALTHY
    else if (currentState === RuntimeState.FAILED) currentStatus = RuntimeStatus.UNHEALTHY
    else if (currentState === RuntimeState.SHUTDOWN) currentStatus = RuntimeStatus.UNKNOWN
    else currentStatus = RuntimeStatus.STARTING

    return {
      platformReady,
      startupHealthy: currentState === RuntimeState.ACTIVE,
      shutdownHealthy: currentState === RuntimeState.SHUTDOWN,
      dependencyHealthy,
      recoveryReady,
      currentState,
      currentStatus,
      lastError: missing.length > 0 ? `missing modules: ${missing.join(", ")}` : null,
      healthyModules,
      totalModules: modules.length,
    }
  },
}