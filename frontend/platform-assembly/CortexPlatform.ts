import { type AssemblyStatus, type AssemblyContext, type AssemblyHealth, type AssemblyMetrics, AssemblyState } from "./types"
import { PlatformRegistry } from "./PlatformRegistry"
import { ModuleLoader } from "./ModuleLoader"
import { DependencyAssembler } from "./DependencyAssembler"
import { RuntimeAssembler } from "./RuntimeAssembler"
import { PlatformValidator } from "./PlatformValidator"
import { PlatformHealth } from "./PlatformHealth"
import { PlatformMetrics } from "./PlatformMetrics"
import { CortexRuntime } from "@/cortex-runtime/CortexRuntime"
import { cortexEventBus } from "@/event-bus/cortexEventBus"

export class CortexPlatform {
  private operationCount = 0
  private state: AssemblyState = AssemblyState.PENDING
  private runtime: CortexRuntime = new CortexRuntime()

  registry(): typeof PlatformRegistry { return PlatformRegistry }
  moduleLoader(): typeof ModuleLoader { return ModuleLoader }
  dependencyAssembler(): typeof DependencyAssembler { return DependencyAssembler }
  runtimeAssembler(): typeof RuntimeAssembler { return RuntimeAssembler }
  validator(): PlatformValidator { return new PlatformValidator() }
  platformHealth(): typeof PlatformHealth { return PlatformHealth }
  platformMetrics(): typeof PlatformMetrics { return PlatformMetrics }
  cortexRuntime(): CortexRuntime { return this.runtime }

  async assemble(): Promise<AssemblyContext> {
    this.operationCount++
    this.state = AssemblyState.ASSEMBLING
    await PlatformMetrics.recordAssemblyStart()
    await PlatformRegistry.registerAll()
    await ModuleLoader.loadAll()
    await DependencyAssembler.assemble()
    const ctx = await RuntimeAssembler.assemble()
    this.state = AssemblyState.ASSEMBLED
    await RuntimeAssembler.updateState(AssemblyState.ASSEMBLED, "unknown" as AssemblyStatus)
    await this.publish("assembled", { moduleCount: ctx.modules.length })
    return ctx
  }

  async start(): Promise<AssemblyState> {
    this.operationCount++
    await this.publish("starting", {})

    const validator = new PlatformValidator()
    const validation = await validator.validateAll()
    if (!validation.valid) {
      this.state = AssemblyState.FAILED
      await this.publish("start.failed", { errors: validation.errors })
      return this.state
    }

    if (this.state === AssemblyState.PENDING) await this.assemble()
    this.state = AssemblyState.INITIALIZING

    const runtimeResult = await this.runtime.start()
    this.state = runtimeResult.success ? AssemblyState.ACTIVE : AssemblyState.FAILED

    const modules = await PlatformRegistry.listModules()
    for (const mod of modules) {
      await PlatformRegistry.updateModule(mod.id, { initialized: runtimeResult.success })
    }

    if (this.state === AssemblyState.ACTIVE) {
      await RuntimeAssembler.updateState(AssemblyState.ACTIVE, "healthy" as AssemblyStatus)
    }

    await this.publish("started", { success: runtimeResult.success, state: this.state })
    return this.state
  }

  async initialize(): Promise<AssemblyState> {
    return this.start()
  }

  async shutdown(): Promise<AssemblyState> {
    this.operationCount++
    await this.runtime.shutdown()
    this.state = AssemblyState.SHUTDOWN
    await RuntimeAssembler.updateState(AssemblyState.SHUTDOWN, "unknown" as AssemblyStatus)
    await this.publish("shutdown", {})
    return this.state
  }

  async restart(): Promise<AssemblyState> {
    this.operationCount++
    await this.publish("restarting", {})
    await this.runtime.shutdown()
    this.state = AssemblyState.PENDING
    return this.start()
  }

  async recover(): Promise<AssemblyState> {
    this.operationCount++
    await this.publish("recovering", {})
    const result = await this.runtime.recover()
    this.state = result.success ? AssemblyState.ACTIVE : AssemblyState.FAILED
    await this.publish("recovered", { success: result.success, state: this.state })
    return this.state
  }

  async validate(): Promise<{ valid: boolean; errors: string[]; warnings: string[] }> {
    this.operationCount++
    const validator = new PlatformValidator()
    return validator.validateAll()
  }

  async getHealth(): Promise<AssemblyHealth> {
    return PlatformHealth.check()
  }

  async getMetrics(): Promise<AssemblyMetrics> {
    return PlatformMetrics.collect()
  }

  async runtimeTree(): Promise<{ foundation: string[]; kernel: string[]; runtime: string[]; workers: string[]; mission: string[]; enterprise: string[]; connectors: string[] }> {
    return RuntimeAssembler.getRuntimeTree()
  }

  private async publish(event: string, data: Record<string, unknown>): Promise<void> {
    await cortexEventBus.publish("platform", "assembly", `platform.assembly.${event}`, "CortexPlatform", data)
  }
}