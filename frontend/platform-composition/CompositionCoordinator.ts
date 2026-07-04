import { CompositionState } from "./types"
import type { CompositionNode, CompositionEdge } from "./types"
import { CompositionRegistry } from "./CompositionRegistry"
import { CompositionGraph } from "./CompositionGraph"
import { CompositionLifecycle } from "./CompositionLifecycle"
import { CompositionDependencyResolver } from "./CompositionDependencyResolver"
import { CompositionContextManager } from "./CompositionContext"
import { generateId } from "./shared"

const state: { current: CompositionState } = { current: CompositionState.INITIALIZED }

export const CompositionCoordinator = {
  async compose(): Promise<{ nodes: CompositionNode[]; edges: CompositionEdge[] }> {
    const graph = await CompositionGraph.buildGraph()
    const { missing, cycles } = await CompositionDependencyResolver.resolveDependencies()
    if (missing.length > 0) throw new Error(`missing dependencies: ${missing.join(", ")}`)
    if (cycles.length > 0) throw new Error(`circular dependencies detected: ${JSON.stringify(cycles)}`)
    return graph
  },

  async initialize(): Promise<CompositionState> {
    const loadOrder = await CompositionDependencyResolver.getLoadOrder()
    const modules = await CompositionRegistry.listModules()
    for (const moduleId of loadOrder) {
      const module = modules.find((m) => m.moduleId === moduleId)
      if (module) {
        await CompositionLifecycle.initialize(state.current)
      }
    }
    state.current = CompositionState.ACTIVE
    return state.current
  },

  async activate(): Promise<CompositionState> {
    const loadOrder = await CompositionDependencyResolver.getLoadOrder()
    for (const moduleId of loadOrder) {
      await CompositionLifecycle.activate(state.current)
    }
    state.current = CompositionState.ACTIVE
    return state.current
  },

  async shutdown(): Promise<CompositionState> {
    const loadOrder = await CompositionDependencyResolver.getLoadOrder()
    for (const moduleId of loadOrder.reverse()) {
      await CompositionLifecycle.shutdown(state.current)
    }
    state.current = CompositionState.SHUTDOWN
    return state.current
  },

  async pause(): Promise<CompositionState> {
    const transition = await CompositionLifecycle.pause(state.current)
    if (transition) state.current = CompositionState.PAUSED
    return state.current
  },

  async resume(): Promise<CompositionState> {
    const transition = await CompositionLifecycle.resume(state.current)
    if (transition) state.current = CompositionState.ACTIVE
    return state.current
  },

  async getState(): Promise<CompositionState> {
    return state.current
  },
}
