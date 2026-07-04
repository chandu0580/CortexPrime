import { RuntimeCompositionState } from "./types"
import { RuntimeRegistry } from "./RuntimeRegistry"
import { RuntimeCompositionGraph } from "./RuntimeCompositionGraph"
import { RuntimeLifecycle } from "./RuntimeLifecycle"
import { RuntimeDependencyResolver } from "./RuntimeDependencyResolver"

let currentState: RuntimeCompositionState = RuntimeCompositionState.PENDING

export const RuntimeCoordinator = {
  async compose(): Promise<RuntimeCompositionState> {
    const { missing, cycles } = await RuntimeDependencyResolver.resolveDependencies()
    if (missing.length > 0) throw new Error(`missing runtime modules: ${missing.join(", ")}`)
    if (cycles.length > 0) throw new Error(`circular dependencies: ${JSON.stringify(cycles)}`)
    return RuntimeCompositionState.PENDING
  },

  async initialize(): Promise<RuntimeCompositionState> {
    const order = await RuntimeCompositionGraph.getExecutionOrder()
    const modules = await RuntimeRegistry.listModules()

    const init = await RuntimeLifecycle.initialize(currentState)
    if (!init) return currentState
    currentState = RuntimeCompositionState.INITIALIZING

    for (const moduleId of order) {
      const mod = modules.find((m) => m.id === moduleId)
      if (mod) {
        await RuntimeRegistry.updateModuleState(moduleId, RuntimeCompositionState.INITIALIZING)
        await RuntimeRegistry.updateModuleState(moduleId, RuntimeCompositionState.ACTIVE)
      }
    }

    const active = await RuntimeLifecycle.activate(RuntimeCompositionState.INITIALIZING)
    if (active) currentState = RuntimeCompositionState.ACTIVE
    return currentState
  },

  async activate(): Promise<RuntimeCompositionState> {
    const active = await RuntimeLifecycle.activate(currentState)
    if (active) currentState = RuntimeCompositionState.ACTIVE
    return currentState
  },

  async shutdown(): Promise<RuntimeCompositionState> {
    const order = await RuntimeCompositionGraph.getExecutionOrder()
    const modules = await RuntimeRegistry.listModules()

    const sd = await RuntimeLifecycle.shutdown(currentState)
    if (!sd) return currentState
    currentState = RuntimeCompositionState.SHUTDOWN

    for (const moduleId of order.reverse()) {
      await RuntimeRegistry.updateModuleState(moduleId, RuntimeCompositionState.SHUTDOWN)
    }
    return currentState
  },

  async pause(): Promise<RuntimeCompositionState> {
    const p = await RuntimeLifecycle.pause(currentState)
    if (p) currentState = RuntimeCompositionState.PAUSED
    return currentState
  },

  async resume(): Promise<RuntimeCompositionState> {
    const r = await RuntimeLifecycle.resume(currentState)
    if (r) currentState = RuntimeCompositionState.ACTIVE
    return currentState
  },

  async getState(): Promise<RuntimeCompositionState> {
    return currentState
  },
}
