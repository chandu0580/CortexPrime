import { BootstrapState, BootstrapValidation, BootstrapMetricsData, BootstrapHealthData } from "./types"
import { BootstrapRegistry } from "./BootstrapRegistry"
import { BootstrapSequence } from "./BootstrapSequence"
import { BootstrapDependencyResolver } from "./BootstrapDependencyResolver"
import { BootstrapLifecycle } from "./BootstrapLifecycle"
import { BootstrapContext } from "./BootstrapContext"
import { BootstrapValidator } from "./BootstrapValidator"
import { BootstrapMetrics } from "./BootstrapMetrics"
import { BootstrapHealth } from "./BootstrapHealth"
import { cortexEventBus } from "@/event-bus/cortexEventBus"

export class PlatformBootstrapEngine {
  private operationCount = 0

  registry(): typeof BootstrapRegistry { return BootstrapRegistry }
  sequence(): typeof BootstrapSequence { return BootstrapSequence }
  resolver(): typeof BootstrapDependencyResolver { return BootstrapDependencyResolver }
  lifecycle(): typeof BootstrapLifecycle { return BootstrapLifecycle }
  context(): typeof BootstrapContext { return BootstrapContext }
  validator(): typeof BootstrapValidator { return BootstrapValidator }
  metrics(): typeof BootstrapMetrics { return BootstrapMetrics }
  health(): typeof BootstrapHealth { return BootstrapHealth }

  async bootstrap(): Promise<BootstrapState> {
    this.operationCount++
    await BootstrapMetrics.recordStart()
    await BootstrapHealth.setState(BootstrapState.INITIALIZING)

    const init = await BootstrapLifecycle.initialize(BootstrapState.PENDING)
    if (!init) return BootstrapState.FAILED
    await BootstrapHealth.setState(BootstrapState.INITIALIZING)

    const seq = await BootstrapSequence.buildSequence()
    await BootstrapLifecycle.bootstrap(BootstrapState.INITIALIZING)
    await BootstrapHealth.setState(BootstrapState.BOOTSTRAPPING)

    for (const stage of seq.stages) {
      await BootstrapSequence.updateStageStatus(stage.type, BootstrapState.INITIALIZING)
      for (const moduleId of stage.modules) {
        await BootstrapRegistry.updateModuleStatus(moduleId, BootstrapState.INITIALIZING)
        await BootstrapRegistry.updateModuleStatus(moduleId, BootstrapState.ACTIVE)
      }
      await BootstrapSequence.updateStageStatus(stage.type, BootstrapState.ACTIVE)
    }

    await BootstrapLifecycle.activate(BootstrapState.BOOTSTRAPPING)
    await BootstrapHealth.setState(BootstrapState.ACTIVE)
    await this.publish("bootstrap.completed", { status: BootstrapState.ACTIVE })
    return BootstrapState.ACTIVE
  }

  async shutdown(): Promise<BootstrapState> {
    this.operationCount++
    await BootstrapLifecycle.shutdown(BootstrapState.ACTIVE)
    await BootstrapHealth.setState(BootstrapState.SHUTDOWN)
    await BootstrapSequence.rollback()
    await this.publish("bootstrap.shutdown", { status: BootstrapState.SHUTDOWN })
    return BootstrapState.SHUTDOWN
  }

  async restart(): Promise<BootstrapState> {
    this.operationCount++
    await BootstrapMetrics.recordRestart()
    await BootstrapLifecycle.restart(await BootstrapHealth.check().then((h) => h.currentState))
    await BootstrapRegistry.clear()
    await BootstrapHealth.setState(BootstrapState.PENDING)
    await this.publish("bootstrap.restart", { status: BootstrapState.PENDING })
    return this.bootstrap()
  }

  async validate(): Promise<BootstrapValidation> {
    this.operationCount++
    return BootstrapValidator.validateAll()
  }

  async getMetrics(): Promise<BootstrapMetricsData> {
    return BootstrapMetrics.collect()
  }

  async getHealth(): Promise<BootstrapHealthData> {
    return BootstrapHealth.check()
  }

  private async publish(event: string, data: Record<string, unknown>): Promise<void> {
    await cortexEventBus.publish("platform", "bootstrap", `platform.bootstrap.${event}`, "PlatformBootstrapEngine", data)
  }
}
