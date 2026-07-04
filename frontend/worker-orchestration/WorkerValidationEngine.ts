import type { WorkerValidation, WorkerDependency, WorkerCheckpoint } from "./types"
import { generateId } from "@/worker-framework/shared"
import { WorkerCoordinator } from "./WorkerCoordinator"
import { WorkerAssignmentEngine } from "./WorkerAssignmentEngine"

const validations = new Map<string, WorkerValidation>()
const dependencies = new Map<string, WorkerDependency>()
const checkpoints = new Map<string, WorkerCheckpoint>()

export const WorkerValidationEngine = {
  async createDependency(
    sessionId: string, sourceWorkerId: string, targetWorkerId: string,
    type: WorkerDependency["type"] = "hard",
  ): Promise<WorkerDependency> {
    const dep: WorkerDependency = {
      id: generateId("wo-dep"),
      sessionId,
      sourceWorkerId,
      targetWorkerId,
      type,
      resolved: false,
      createdAt: new Date().toISOString(),
      resolvedAt: null,
    }
    dependencies.set(dep.id, dep)
    return dep
  },

  async resolveDependency(depId: string): Promise<WorkerDependency> {
    const dep = dependencies.get(depId)
    if (!dep) throw new Error(`Dependency ${depId} not found`)
    dep.resolved = true
    dep.resolvedAt = new Date().toISOString()
    return dep
  },

  async getDependenciesBySession(sessionId: string): Promise<WorkerDependency[]> {
    return Array.from(dependencies.values()).filter((d) => d.sessionId === sessionId)
  },

  async resolveDependenciesForWorker(sessionId: string, workerId: string): Promise<boolean> {
    const deps = Array.from(dependencies.values()).filter(
      (d) => d.sessionId === sessionId && d.sourceWorkerId === workerId,
    )
    return deps.every((d) => d.resolved)
  },

  detectCycleDependency(sessionId: string): boolean {
    const deps = Array.from(dependencies.values()).filter((d) => d.sessionId === sessionId)
    const adj = new Map<string, string[]>()
    for (const d of deps) {
      if (!adj.has(d.sourceWorkerId)) adj.set(d.sourceWorkerId, [])
      adj.get(d.sourceWorkerId)!.push(d.targetWorkerId)
    }
    const visited = new Set<string>()
    const recStack = new Set<string>()
    const dfs = (node: string): boolean => {
      if (recStack.has(node)) return true
      if (visited.has(node)) return false
      visited.add(node)
      recStack.add(node)
      const neighbors = adj.get(node) ?? []
      for (const n of neighbors) {
        if (dfs(n)) return true
      }
      recStack.delete(node)
      return false
    }
    for (const node of adj.keys()) {
      if (dfs(node)) return true
    }
    return false
  },

  async createCheckpoint(sessionId: string, workerId: string, stage: string): Promise<WorkerCheckpoint> {
    const depsResolved = await this.resolveDependenciesForWorker(sessionId, workerId)
    const assignments = await WorkerAssignmentEngine.getAssignmentsBySession(sessionId)
    const assigned = assignments.some((a) => a.workerId === workerId && a.status === "assigned")

    const checkpoint: WorkerCheckpoint = {
      id: generateId("wo-checkpoint"),
      sessionId,
      workerId,
      stage,
      ready: depsResolved && assigned,
      dependenciesResolved: depsResolved,
      assigned,
      validated: false,
      checkedAt: new Date().toISOString(),
    }
    checkpoints.set(checkpoint.id, checkpoint)
    return checkpoint
  },

  async getCheckpointsBySession(sessionId: string): Promise<WorkerCheckpoint[]> {
    return Array.from(checkpoints.values()).filter((c) => c.sessionId === sessionId)
  },

  async validateWorker(sessionId: string, workerId: string): Promise<WorkerValidation> {
    const worker = await WorkerCoordinator.getWorker(workerId)
    const available = worker !== null
    const capabilitiesCompatible = available && worker.capabilities.length > 0
    const depsResolved = await this.resolveDependenciesForWorker(sessionId, workerId)
    const lifecycleValid = available && (worker.status === "registered" || worker.status === "running")

    const valid: WorkerValidation = {
      id: generateId("wo-validation"),
      sessionId,
      workerId,
      available,
      capabilitiesCompatible,
      synchronizationReady: depsResolved,
      lifecycleValid,
      consistent: available && capabilitiesCompatible && depsResolved && lifecycleValid,
      validatedAt: new Date().toISOString(),
    }
    validations.set(valid.id, valid)
    return valid
  },

  async getValidation(validationId: string): Promise<WorkerValidation | null> {
    return validations.get(validationId) ?? null
  },

  async clearSession(sessionId: string): Promise<void> {
    for (const [id, d] of dependencies.entries()) {
      if (d.sessionId === sessionId) dependencies.delete(id)
    }
    for (const [id, c] of checkpoints.entries()) {
      if (c.sessionId === sessionId) checkpoints.delete(id)
    }
    for (const [id, v] of validations.entries()) {
      if (v.sessionId === sessionId) validations.delete(id)
    }
  },
}
