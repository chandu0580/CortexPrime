import { RuntimeCompositionState, type RuntimeValidation, type RuntimeMetricsData, type RuntimeHealthData } from "./types"
import { RuntimeRegistry } from "./RuntimeRegistry"
import { RuntimeCompositionGraph } from "./RuntimeCompositionGraph"
import { RuntimeDependencyResolver } from "./RuntimeDependencyResolver"
import { RuntimeLifecycle } from "./RuntimeLifecycle"
import { RuntimeContextManager } from "./RuntimeContextManager"
import { RuntimeCoordinator } from "./RuntimeCoordinator"
import { RuntimeValidator } from "./RuntimeValidator"
import { RuntimeMetrics } from "./RuntimeMetrics"
import { RuntimeHealth } from "./RuntimeHealth"
import { cortexEventBus } from "@/event-bus/cortexEventBus"

export class RuntimeCompositionEngine {
  private operationCount = 0

  registry(): typeof RuntimeRegistry { return RuntimeRegistry }
  graph(): typeof RuntimeCompositionGraph { return RuntimeCompositionGraph }
  resolver(): typeof RuntimeDependencyResolver { return RuntimeDependencyResolver }
  lifecycle(): typeof RuntimeLifecycle { return RuntimeLifecycle }
  context(): typeof RuntimeContextManager { return RuntimeContextManager }
  coordinator(): typeof RuntimeCoordinator { return RuntimeCoordinator }
  validator(): typeof RuntimeValidator { return RuntimeValidator }
  metrics(): typeof RuntimeMetrics { return RuntimeMetrics }
  health(): typeof RuntimeHealth { return RuntimeHealth }

  async compose(): Promise<void> {
    this.operationCount++
    await RuntimeCoordinator.compose()
    await this.publish("composition.composed", {})
  }

  async initialize(): Promise<RuntimeCompositionState> {
    this.operationCount++
    await RuntimeMetrics.recordStart()
    const state = await RuntimeCoordinator.initialize()
    await this.publish("composition.initialized", { state })
    return state
  }

  async shutdown(): Promise<RuntimeCompositionState> {
    this.operationCount++
    await RuntimeMetrics.recordShutdown()
    const state = await RuntimeCoordinator.shutdown()
    await this.publish("composition.shutdown", { state })
    return state
  }

  async restart(): Promise<RuntimeCompositionState> {
    this.operationCount++
    await RuntimeMetrics.recordRestart()
    await RuntimeLifecycle.restart(await RuntimeCoordinator.getState())
    await RuntimeRegistry.clear()
    await this.publish("composition.restart", {})
    return this.initialize()
  }

  async validate(): Promise<RuntimeValidation> {
    this.operationCount++
    return RuntimeValidator.validateAll()
  }

  async getMetrics(): Promise<RuntimeMetricsData> {
    return RuntimeMetrics.collect()
  }

  async getHealth(): Promise<RuntimeHealthData> {
    return RuntimeHealth.check()
  }

  private async publish(event: string, data: Record<string, unknown>): Promise<void> {
    await cortexEventBus.publish("runtime", "composition", `runtime.${event}`, "RuntimeCompositionEngine", data)
  }
}
