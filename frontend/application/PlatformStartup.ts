import type { ApplicationStartupResult, ApplicationState, ApplicationModule } from "./types"
import { ConfigurationLoader } from "./ConfigurationLoader"
import { EnvironmentManager } from "./EnvironmentManager"
import { ServiceContainer } from "./ServiceContainer"
import { ModuleComposer } from "./ModuleComposer"
import { FeatureFlagManager } from "./FeatureFlagManager"
import { ApplicationRegistry } from "./ApplicationRegistry"
import { cortexEventBus } from "@/event-bus/cortexEventBus"

export const PlatformStartup = {
  async start(environment: string = "development"): Promise<ApplicationStartupResult> {
    const stages: string[] = []
    const errors: string[] = []
    const startTime = Date.now()

    await cortexEventBus.publish("application", "startup", "application.starting", "PlatformStartup", { environment })

    stages.push("loadConfiguration")
    await ConfigurationLoader.load(environment)

    stages.push("resolveEnvironment")
    const env = await EnvironmentManager.resolve(environment)

    stages.push("registerServices")
    await ApplicationRegistry.registerAll()
    await ServiceContainer.registerAll()

    stages.push("loadFeatures")
    const config = await ConfigurationLoader.getConfig()
    if (config) await FeatureFlagManager.loadFromConfig(config.features)

    stages.push("composeModules")
    const modules = await ModuleComposer.compose()

    stages.push("initializePlatform")
    const platform = await ServiceContainer.getPlatform()
    if (platform) {
      await platform.assemble()
    }

    stages.push("startRuntime")
    const runtime = await ServiceContainer.getRuntime()
    if (runtime) {
      const result = await runtime.start()
      if (!result.success) errors.push(...result.errors)
    }

    stages.push("runValidation")
    const validation = await ServiceContainer.getValidation()
    if (validation) {
      await validation.validate()
    }

    stages.push("healthCheck")

    await cortexEventBus.publish("application", "startup", "application.started", "PlatformStartup", {
      environment: env.type,
      stagesCompleted: stages.length,
      errors: errors.length,
    })

    return {
      success: errors.length === 0,
      state: errors.length === 0 ? "active" as ApplicationState : "failed" as ApplicationState,
      durationMs: Date.now() - startTime,
      stagesCompleted: stages,
      errors,
    }
  },
}