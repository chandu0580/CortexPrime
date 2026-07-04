import { ApplicationState, ApplicationStatus, type ApplicationStartupResult, type ApplicationShutdownResult, type ApplicationDiagnostic, type ApplicationMetrics, type ApplicationHealth, type ApplicationConfiguration, type ApplicationEnvironment } from "./types"
import { ServiceContainer } from "./ServiceContainer"
import { PlatformStartup } from "./PlatformStartup"
import { PlatformShutdown } from "./PlatformShutdown"
import { PlatformDiagnostics } from "./PlatformDiagnostics"
import { ConfigurationLoader } from "./ConfigurationLoader"
import { EnvironmentManager } from "./EnvironmentManager"
import { FeatureFlagManager } from "./FeatureFlagManager"
import { DependencyContainer } from "./DependencyContainer"
import { ModuleComposer } from "./ModuleComposer"
import { ApplicationRegistry } from "./ApplicationRegistry"
import { cortexEventBus } from "@/event-bus/cortexEventBus"
import { generateId } from "./shared"

let applicationState: ApplicationState = ApplicationState.PENDING
let startTime = 0

export class CortexPrimeApplication {
  private operationCount = 0

  registry(): typeof ApplicationRegistry { return ApplicationRegistry }
  configLoader(): typeof ConfigurationLoader { return ConfigurationLoader }
  environment(): typeof EnvironmentManager { return EnvironmentManager }
  features(): typeof FeatureFlagManager { return FeatureFlagManager }
  container(): typeof DependencyContainer { return DependencyContainer }
  services(): typeof ServiceContainer { return ServiceContainer }
  composer(): typeof ModuleComposer { return ModuleComposer }
  startup(): typeof PlatformStartup { return PlatformStartup }
  shutdownHandler(): typeof PlatformShutdown { return PlatformShutdown }
  diagnostics(): typeof PlatformDiagnostics { return PlatformDiagnostics }

  async initialize(environment: string = "development"): Promise<void> {
    this.operationCount++
    applicationState = ApplicationState.INITIALIZING
    startTime = Date.now()

    await ConfigurationLoader.load(environment)
    await EnvironmentManager.resolve(environment)
    await ApplicationRegistry.registerAll()
    await ServiceContainer.registerAll()

    const config = await ConfigurationLoader.getConfig()
    if (config) await FeatureFlagManager.loadFromConfig(config.features)

    await cortexEventBus.publish("application", "lifecycle", "application.initialized", "CortexPrimeApplication", { environment })
    applicationState = ApplicationState.PENDING
  }

  async start(): Promise<ApplicationStartupResult> {
    this.operationCount++

    if (applicationState === ApplicationState.PENDING || applicationState === ApplicationState.INITIALIZING) {
      const env = await EnvironmentManager.getEnvironment()
      await this.initialize(env?.type ?? "development")
    }

    applicationState = ApplicationState.STARTING
    await cortexEventBus.publish("application", "lifecycle", "application.starting", "CortexPrimeApplication", {})

    const result = await PlatformStartup.start()
    applicationState = result.success ? ApplicationState.ACTIVE : ApplicationState.FAILED

    await cortexEventBus.publish("application", "lifecycle", "application.started", "CortexPrimeApplication", {
      success: result.success,
      durationMs: result.durationMs,
    })
    return result
  }

  async shutdown(): Promise<ApplicationShutdownResult> {
    this.operationCount++
    applicationState = ApplicationState.STOPPING
    await cortexEventBus.publish("application", "lifecycle", "application.stopping", "CortexPrimeApplication", {})

    const result = await PlatformShutdown.shutdown()
    applicationState = ApplicationState.SHUTDOWN

    await cortexEventBus.publish("application", "lifecycle", "application.shutdown", "CortexPrimeApplication", {
      success: result.success,
      durationMs: result.durationMs,
    })
    return result
  }

  async restart(): Promise<ApplicationStartupResult> {
    this.operationCount++
    await cortexEventBus.publish("application", "lifecycle", "application.restarting", "CortexPrimeApplication", {})
    await this.shutdown()
    applicationState = ApplicationState.PENDING
    return this.start()
  }

  async getDiagnostics(): Promise<ApplicationDiagnostic> {
    return PlatformDiagnostics.diagnostics()
  }

  async getHealth(): Promise<ApplicationHealth> {
    const platform = await ServiceContainer.getPlatform()
    const health = platform ? await platform.getHealth() : null
    const uptimeMs = startTime > 0 ? Date.now() - startTime : 0

    return {
      state: applicationState,
      status: applicationState === ApplicationState.ACTIVE ? ApplicationStatus.HEALTHY : applicationState === ApplicationState.FAILED ? ApplicationStatus.UNHEALTHY : ApplicationStatus.UNKNOWN,
      modulesHealthy: health?.activeModules ?? 0,
      totalModules: health?.totalModules ?? 0,
      lastError: health?.lastError ?? null,
      uptimeMs,
    }
  }

  async getMetrics(): Promise<ApplicationMetrics> {
    const platform = await ServiceContainer.getPlatform()
    const metrics = platform ? await platform.getMetrics() : null
    const features = await FeatureFlagManager.listFeatures()
    const services = await DependencyContainer.listServices()
    const modules = await ApplicationRegistry.listModules()
    const uptimeMs = startTime > 0 ? Date.now() - startTime : 0

    return {
      startupDurationMs: metrics?.assemblyDurationMs ?? 0,
      shutdownDurationMs: 0,
      modulesRegistered: modules.length,
      servicesRegistered: services.length,
      featuresEnabled: features.filter((f) => f.state === "enabled").length,
      uptimeMs,
    }
  }

  async getConfiguration(): Promise<ApplicationConfiguration | null> {
    return ConfigurationLoader.getConfig()
  }

  async getEnvironment(): Promise<ApplicationEnvironment | null> {
    return EnvironmentManager.getEnvironment()
  }
}