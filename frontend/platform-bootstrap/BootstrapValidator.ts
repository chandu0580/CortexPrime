import type { BootstrapValidation } from "./types"
import { BootstrapDependencyResolver } from "./BootstrapDependencyResolver"
import { BootstrapLifecycle } from "./BootstrapLifecycle"
import { BootstrapSequence } from "./BootstrapSequence"
import { generateId } from "./shared"

export const BootstrapValidator = {
  async validateStartupOrder(): Promise<{ valid: boolean; errors: string[] }> {
    const sequence = await BootstrapSequence.getSequence()
    if (!sequence) return { valid: false, errors: ["no startup sequence defined"] }
    if (sequence.stages.length === 0) return { valid: false, errors: ["startup sequence has no stages"] }
    return { valid: true, errors: [] }
  },

  async validateDependencies(): Promise<{ valid: boolean; errors: string[] }> {
    const errors: string[] = []
    const { missing, cycles } = await BootstrapDependencyResolver.resolveDependencies()
    if (missing.length > 0) errors.push(`missing bootstrap modules: ${missing.join(", ")}`)
    if (cycles.length > 0) errors.push(`circular dependencies: ${JSON.stringify(cycles)}`)
    return { valid: errors.length === 0, errors }
  },

  async validateLifecycle(): Promise<{ valid: boolean; errors: string[] }> {
    const transitions = await BootstrapLifecycle.getTransitions()
    if (transitions.length === 0) return { valid: false, errors: ["no lifecycle transitions recorded"] }
    return { valid: true, errors: [] }
  },

  async validateReadiness(): Promise<{ valid: boolean; errors: string[] }> {
    const depResult = await this.validateDependencies()
    const orderResult = await this.validateStartupOrder()
    return { valid: depResult.valid && orderResult.valid, errors: [...depResult.errors, ...orderResult.errors] }
  },

  async validateHealth(): Promise<{ valid: boolean; errors: string[] }> {
    return this.validateReadiness()
  },

  async validateAll(): Promise<BootstrapValidation> {
    const errors: string[] = []
    const warnings: string[] = []

    const orderResult = await this.validateStartupOrder()
    if (!orderResult.valid) errors.push(...orderResult.errors)

    const depResult = await this.validateDependencies()
    if (!depResult.valid) errors.push(...depResult.errors)

    const lcResult = await this.validateLifecycle()
    if (!lcResult.valid) warnings.push(...lcResult.errors)

    const readinessResult = await this.validateReadiness()
    if (!readinessResult.valid) errors.push(...readinessResult.errors)

    const healthResult = await this.validateHealth()
    if (!healthResult.valid) errors.push(...healthResult.errors)

    return {
      id: generateId("bval"),
      sessionId: "bootstrap",
      startupOrderValid: orderResult.valid,
      dependenciesValid: depResult.valid,
      lifecycleValid: lcResult.valid,
      readinessValid: readinessResult.valid,
      healthValid: healthResult.valid,
      errors,
      warnings,
      timestamp: new Date().toISOString(),
    }
  },
}