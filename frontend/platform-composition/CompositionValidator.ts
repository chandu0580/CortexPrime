import type { CompositionValidation, ValidationSeverity } from "./types"
import { CompositionDependencyResolver } from "./CompositionDependencyResolver"
import { CompositionLifecycle } from "./CompositionLifecycle"
import { CompositionContextManager } from "./CompositionContext"
import { generateId } from "./shared"

export const CompositionValidator = {
  async validateDependencies(): Promise<{ valid: boolean; errors: string[] }> {
    const errors: string[] = []
    const { missing, cycles } = await CompositionDependencyResolver.resolveDependencies()
    if (missing.length > 0) errors.push(`missing dependencies: ${missing.join(", ")}`)
    if (cycles.length > 0) errors.push(`circular dependencies: ${JSON.stringify(cycles)}`)
    return { valid: errors.length === 0, errors }
  },

  async validateLifecycle(): Promise<{ valid: boolean; errors: string[] }> {
    const errors: string[] = []
    const transitions = await CompositionLifecycle.getTransitions()
    if (transitions.length === 0) errors.push("no lifecycle transitions recorded")
    return { valid: errors.length === 0, errors }
  },

  async validateContext(): Promise<{ valid: boolean; errors: string[] }> {
    const errors: string[] = []
    const contexts = await CompositionContextManager.getContextsByComposition("platform")
    if (contexts.length === 0) errors.push("no composition contexts found")
    return { valid: errors.length === 0, errors }
  },

  async validateHealth(): Promise<{ valid: boolean; errors: string[] }> {
    const { valid, errors: depErrors } = await this.validateDependencies()
    const { valid: lcValid, errors: lcErrors } = await this.validateLifecycle()
    const allErrors = [...depErrors, ...lcErrors]
    return { valid: valid && lcValid, errors: allErrors }
  },

  async validateMetrics(): Promise<{ valid: boolean; errors: string[] }> {
    return { valid: true, errors: [] }
  },

  async validateAll(): Promise<CompositionValidation> {
    const errors: string[] = []
    const warnings: string[] = []

    const depResult = await this.validateDependencies()
    if (!depResult.valid) errors.push(...depResult.errors)

    const lcResult = await this.validateLifecycle()
    if (!lcResult.valid) errors.push(...lcResult.errors)

    const ctxResult = await this.validateContext()
    if (!ctxResult.valid) warnings.push(...ctxResult.errors)

    const healthResult = await this.validateHealth()
    if (!healthResult.valid) errors.push(...healthResult.errors)

    return {
      id: generateId("validation"),
      compositionId: "platform",
      dependenciesValid: depResult.valid,
      lifecycleValid: lcResult.valid,
      contextValid: ctxResult.valid,
      healthValid: healthResult.valid,
      metricsValid: true,
      errors,
      warnings,
      timestamp: new Date().toISOString(),
    }
  },
}