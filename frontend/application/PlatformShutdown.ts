import type { ApplicationShutdownResult, ApplicationState } from "./types"
import { ServiceContainer } from "./ServiceContainer"
import { DependencyContainer } from "./DependencyContainer"
import { cortexEventBus } from "@/event-bus/cortexEventBus"

export const PlatformShutdown = {
  async shutdown(): Promise<ApplicationShutdownResult> {
    const errors: string[] = []
    const startTime = Date.now()

    await cortexEventBus.publish("application", "shutdown", "application.shutting", "PlatformShutdown", {})

    const runtime = await ServiceContainer.getRuntime()
    if (runtime) {
      const result = await runtime.shutdown()
      if (!result.success) errors.push(...result.errors)
    }

    const platform = await ServiceContainer.getPlatform()
    if (platform) {
      await platform.shutdown()
    }

    await DependencyContainer.clear()

    await cortexEventBus.publish("application", "shutdown", "application.shutdown", "PlatformShutdown", { errors: errors.length })

    return {
      success: errors.length === 0,
      state: "shutdown" as ApplicationState,
      durationMs: Date.now() - startTime,
      errors,
    }
  },
}