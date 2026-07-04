import type { DependencyValidation } from "./types"
import { generateId } from "./shared"

export const DependencyValidator = {
  async validateMissingModules(allModuleIds: string[], allDependencyIds: string[]): Promise<{ missing: string[]; valid: boolean }> {
    const moduleSet = new Set(allModuleIds)
    const missing = allDependencyIds.filter((d) => !moduleSet.has(d))
    return { missing, valid: missing.length === 0 }
  },

  async validateCircularDependencies(cycles: string[][]): Promise<{ cycles: string[][]; valid: boolean }> {
    return { cycles, valid: cycles.length === 0 }
  },

  async validateDependencyOrder(sorted: string[], adjacency: Map<string, string[]>): Promise<{ valid: boolean; invalid: string[] }> {
    const positions = new Map<string, number>()
    sorted.forEach((id, i) => positions.set(id, i))
    const invalid: string[] = []
    for (const [id, deps] of adjacency) {
      const pos = positions.get(id) ?? -1
      for (const dep of deps) {
        const depPos = positions.get(dep) ?? -1
        if (depPos > pos) invalid.push(`${id} depends on ${dep} but appears before it`)
      }
    }
    return { valid: invalid.length === 0, invalid }
  },

  async validateDuplicateRegistrations(ids: string[]): Promise<{ duplicates: string[]; valid: boolean }> {
    const seen = new Set<string>()
    const duplicates: string[] = []
    for (const id of ids) {
      if (seen.has(id)) duplicates.push(id)
      seen.add(id)
    }
    return { duplicates, valid: duplicates.length === 0 }
  },

  async validateAll(deps: { moduleId: string; dependsOn: string[] }[], cycles: string[][]): Promise<DependencyValidation> {
    const allModuleIds = deps.map((d) => d.moduleId)
    const allDepIds = deps.flatMap((d) => d.dependsOn)
    const errors: string[] = []

    const missingResult = await this.validateMissingModules(allModuleIds, allDepIds)
    if (!missingResult.valid) errors.push(`missing modules: ${missingResult.missing.join(", ")}`)

    const cycleResult = await this.validateCircularDependencies(cycles)
    if (!cycleResult.valid) errors.push(`${cycles.length} circular dependencies found`)

    const adjacency = new Map<string, string[]>()
    deps.forEach((d) => adjacency.set(d.moduleId, d.dependsOn))
    const orderResult = await this.validateDependencyOrder(allModuleIds, adjacency)
    if (!orderResult.valid) errors.push(...orderResult.invalid)

    const dupResult = await this.validateDuplicateRegistrations(allModuleIds)
    if (!dupResult.valid) errors.push(`duplicate registrations: ${dupResult.duplicates.join(", ")}`)

    const unresolved = deps.filter((d) => !d.dependsOn.every((dep) => allModuleIds.includes(dep)))

    return {
      totalDependencies: allDepIds.length,
      resolved: deps.length - unresolved.length,
      unresolved: unresolved.length,
      cyclesFound: cycles.length,
      valid: errors.length === 0,
      errors,
    }
  },
}