import type { CompositionNode, CompositionEdge, DependencyType } from "./types"
import { generateId } from "./shared"

interface ModuleRegistration {
  moduleId: string
  moduleName: string
  moduleVersion: string
  category: string
  dependencies: string[]
}

const registeredModules = new Map<string, ModuleRegistration>()
const edges = new Map<string, CompositionEdge>()

export const CompositionRegistry = {
  async registerModule(
    moduleId: string,
    moduleName: string,
    moduleVersion: string,
    category: string,
    dependencies: string[] = [],
  ): Promise<ModuleRegistration> {
    const registration: ModuleRegistration = { moduleId, moduleName, moduleVersion, category, dependencies }
    registeredModules.set(moduleId, registration)
    return registration
  },

  async registerDependency(sourceId: string, targetId: string, type: DependencyType, required: boolean = true): Promise<CompositionEdge> {
    const id = generateId("edge")
    const edge: CompositionEdge = { id, sourceId, targetId, type, required }
    edges.set(id, edge)
    return edge
  },

  async getModule(moduleId: string): Promise<ModuleRegistration | null> {
    return registeredModules.get(moduleId) ?? null
  },

  async listModules(): Promise<ModuleRegistration[]> {
    return Array.from(registeredModules.values())
  },

  async listEdges(): Promise<CompositionEdge[]> {
    return Array.from(edges.values())
  },

  async getDependencies(moduleId: string): Promise<ModuleRegistration[]> {
    const module = registeredModules.get(moduleId)
    if (!module) return []
    return module.dependencies
      .map((depId) => registeredModules.get(depId))
      .filter((m): m is ModuleRegistration => m != null)
  },

  async getDependents(moduleId: string): Promise<ModuleRegistration[]> {
    return Array.from(registeredModules.values()).filter((m) => m.dependencies.includes(moduleId))
  },

  async clear(): Promise<void> {
    registeredModules.clear()
    edges.clear()
  },
}