import { type CortexRuntimeInstance, RuntimeState, RuntimeStatus, type RuntimeStartupResult, type RuntimeShutdownResult, type RuntimeValidation, type RuntimeMetricsData, type RuntimeHealthData } from "./types"
import { RuntimeManifest } from "./RuntimeManifest"
import { RuntimeLoader } from "./RuntimeLoader"
import { RuntimeInitializer } from "./RuntimeInitializer"
import { RuntimeStartupPipeline } from "./RuntimeStartupPipeline"
import { RuntimeShutdownPipeline } from "./RuntimeShutdownPipeline"
import { RuntimeRecoveryManager } from "./RuntimeRecoveryManager"
import { RuntimeValidationEngine } from "./RuntimeValidationEngine"
import { RuntimeMetricsCollector } from "./RuntimeMetricsCollector"
import { RuntimeHealthManager } from "./RuntimeHealthManager"
import { generateId } from "./shared"
import { cortexEventBus } from "@/event-bus/cortexEventBus"

let instance: CortexRuntimeInstance | null = null
let currentState: RuntimeState = RuntimeState.PENDING

export class CortexRuntime {
  private operationCount = 0

  manifest(): typeof RuntimeManifest { return RuntimeManifest }
  loader(): typeof RuntimeLoader { return RuntimeLoader }
  initializer(): typeof RuntimeInitializer { return RuntimeInitializer }
  startupPipeline(): typeof RuntimeStartupPipeline { return RuntimeStartupPipeline }
  shutdownPipeline(): typeof RuntimeShutdownPipeline { return RuntimeShutdownPipeline }
  recoveryManager(): typeof RuntimeRecoveryManager { return RuntimeRecoveryManager }
  validationEngine(): typeof RuntimeValidationEngine { return RuntimeValidationEngine }
  metricsCollector(): typeof RuntimeMetricsCollector { return RuntimeMetricsCollector }
  healthManager(): typeof RuntimeHealthManager { return RuntimeHealthManager }

  async start(): Promise<RuntimeStartupResult> {
    this.operationCount++
    currentState = RuntimeState.PREFLIGHT
    await RuntimeMetricsCollector.recordStart()

    const manifest = await RuntimeManifest.load()
    instance = {
      id: instance?.id ?? generateId("cortex"),
      version: manifest.version,
      state: currentState,
      status: RuntimeStatus.STARTING,
      startedAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      uptimeMs: 0,
    }

    await this.publish("runtime.starting", { instanceId: instance.id })

    const pipeline = await RuntimeStartupPipeline.execute()
    const stagesCompleted = pipeline.stages.filter((s) => s.state === RuntimeState.ACTIVE).length
    currentState = stagesCompleted === pipeline.stages.length ? RuntimeState.ACTIVE : RuntimeState.FAILED

    instance.state = currentState
    instance.status = currentState === RuntimeState.ACTIVE ? RuntimeStatus.HEALTHY : RuntimeStatus.UNHEALTHY
    instance.updatedAt = new Date().toISOString()
    instance.uptimeMs = Date.now() - new Date(instance.startedAt!).getTime()

    await this.publish("runtime.started", { instanceId: instance.id, state: currentState })

    const errors: string[] = []
    if (currentState === RuntimeState.FAILED) errors.push("startup pipeline did not complete all stages")

    return {
      success: currentState === RuntimeState.ACTIVE,
      state: currentState,
      stagesCompleted,
      totalStages: pipeline.stages.length,
      durationMs: Date.now() - new Date(instance.startedAt!).getTime(),
      errors,
    }
  }

  async shutdown(): Promise<RuntimeShutdownResult> {
    this.operationCount++
    currentState = RuntimeState.SHUTDOWN
    await RuntimeMetricsCollector.recordShutdown()

    await this.publish("runtime.shutting", {})

    const result = await RuntimeShutdownPipeline.execute()

    instance = instance ? { ...instance, state: RuntimeState.SHUTDOWN, status: RuntimeStatus.UNKNOWN, updatedAt: new Date().toISOString() } : null

    await this.publish("runtime.shutdown", { modulesDeactivated: result.modulesDeactivated })
    return {
      success: result.errors.length === 0,
      state: RuntimeState.SHUTDOWN,
      modulesDeactivated: result.modulesDeactivated,
      durationMs: result.durationMs,
      errors: result.errors,
    }
  }

  async restart(): Promise<RuntimeStartupResult> {
    this.operationCount++
    await RuntimeMetricsCollector.recordRestart()

    await this.publish("runtime.restarting", {})

    if (instance && instance.state !== RuntimeState.SHUTDOWN) {
      await this.shutdown()
    }

    currentState = RuntimeState.PENDING
    return this.start()
  }

  async recover(): Promise<RuntimeStartupResult> {
    this.operationCount++
    if (currentState !== RuntimeState.FAILED) {
      return {
        success: false, state: currentState, stagesCompleted: 0, totalStages: 0, durationMs: 0,
        errors: ["cannot recover: runtime is not in failed state"],
      }
    }

    currentState = RuntimeState.RECOVERING
    await RuntimeRecoveryManager.trackFailure()
    const strategy = await RuntimeRecoveryManager.restartStrategy()

    await this.publish("runtime.recovering", { strategy })

    const recovery = await RuntimeRecoveryManager.recover(RuntimeState.FAILED, strategy)
    currentState = RuntimeState.PENDING

    const result = await this.start()
    recovery.success = result.success

    await this.publish("runtime.recovered", { attempt: recovery.attempt, success: result.success })
    return result
  }

  async validate(): Promise<RuntimeValidation> {
    this.operationCount++
    return RuntimeValidationEngine.validateAll()
  }

  async getMetrics(): Promise<RuntimeMetricsData> {
    return RuntimeMetricsCollector.collect(currentState)
  }

  async getHealth(): Promise<RuntimeHealthData> {
    return RuntimeHealthManager.check(currentState)
  }

  async getInstance(): Promise<CortexRuntimeInstance | null> {
    if (instance) {
      instance.uptimeMs = Date.now() - new Date(instance.startedAt!).getTime()
    }
    return instance
  }

  private async publish(event: string, data: Record<string, unknown>): Promise<void> {
    await cortexEventBus.publish("platform", "runtime", `platform.runtime.${event}`, "CortexRuntime", data)
  }
}