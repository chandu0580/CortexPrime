import type { ApplicationDiagnostic, ApplicationState } from "./types"
import { ServiceContainer } from "./ServiceContainer"

export const PlatformDiagnostics = {
  async diagnostics(): Promise<ApplicationDiagnostic> {
    const runtime = await ServiceContainer.getRuntime()
    const platform = await ServiceContainer.getPlatform()
    const validation = await ServiceContainer.getValidation()

    const runtimeHealth = runtime ? await runtime.getHealth() : null
    const runtimeMetrics = runtime ? await runtime.getMetrics() : null
    const platformHealth = platform ? await platform.getHealth() : null
    const validationReport = validation ? await validation.report() : null

    return {
      platformStatus: platformHealth?.platformReady ? "ready" : "not_ready",
      runtimeStatus: runtimeHealth?.startupHealthy ? "ready" : "not_ready",
      workerStatus: "registered",
      connectorStatus: "registered",
      missionStatus: "configured",
      health: { runtime: runtimeHealth, platform: platformHealth } as Record<string, unknown>,
      metrics: (runtimeMetrics ?? {}) as unknown as Record<string, unknown>,
      validation: (validationReport ?? {}) as unknown as Record<string, unknown>,
    }
  },
}