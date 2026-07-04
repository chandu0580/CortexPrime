import type { AssemblyContext } from "./types"
import { PlatformRegistry } from "./PlatformRegistry"
import { ModuleLoader } from "./ModuleLoader"
import { DependencyAssembler } from "./DependencyAssembler"
import { RuntimeAssembler } from "./RuntimeAssembler"
import { PlatformHealth } from "./PlatformHealth"
import { PlatformMetrics } from "./PlatformMetrics"
import { cortexEventBus } from "@/event-bus/cortexEventBus"

export class PlatformValidator {
  async validateMissingModules(): Promise<{ valid: boolean; missing: string[] }> {
    const modules = await PlatformRegistry.listModules()
    const allDeps = new Set(modules.flatMap((m) => m.dependencies))
    const allModuleIds = new Set(modules.map((m) => m.id))
    const missing: string[] = []
    for (const dep of allDeps) if (!allModuleIds.has(dep)) missing.push(dep)
    return { valid: missing.length === 0, missing }
  }

  async validateDependencyGraph(): Promise<{ valid: boolean; errors: string[] }> {
    return DependencyAssembler.validateAll()
  }

  async validateCircularReferences(): Promise<{ valid: boolean; cycles: string[][] }> {
    const cycles = await DependencyAssembler.detectCycles()
    return { valid: cycles.length === 0, cycles }
  }

  async validateRegistrationCompleteness(): Promise<{ valid: boolean; unregistered: string[] }> {
    return { valid: true, unregistered: [] }
  }

  async validateRuntimeComposition(): Promise<{ valid: boolean; errors: string[] }> {
    const modules = await PlatformRegistry.listModules()
    const loadedCount = modules.filter((m) => m.loaded).length
    if (loadedCount < modules.length) return { valid: false, errors: [`${modules.length - loadedCount} modules not loaded`] }
    return { valid: true, errors: [] }
  }

  async validateStartupReadiness(): Promise<{ valid: boolean; errors: string[] }> {
    const missing = await this.validateMissingModules()
    const graph = await this.validateDependencyGraph()
    const cycles = await this.validateCircularReferences()
    const errors = [...missing.missing.map((m) => `missing module: ${m}`), ...graph.errors]
    if (!cycles.valid) errors.push(`circular references: ${JSON.stringify(cycles.cycles)}`)
    return { valid: errors.length === 0, errors }
  }

  async validateAll(): Promise<{ valid: boolean; errors: string[]; warnings: string[] }> {
    const errors: string[] = []
    const warnings: string[] = []
    const missing = await this.validateMissingModules()
    if (!missing.valid) errors.push(...missing.missing.map((m) => `missing module: ${m}`))
    const graph = await this.validateDependencyGraph()
    if (!graph.valid) errors.push(...graph.errors)
    const cycles = await this.validateCircularReferences()
    if (!cycles.valid) errors.push(`circular references: ${JSON.stringify(cycles.cycles)}`)
    return { valid: errors.length === 0, errors, warnings }
  }
}