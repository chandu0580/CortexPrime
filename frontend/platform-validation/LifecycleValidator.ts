import type { LifecycleValidation } from "./types"

export const LifecycleValidator = {
  async validateModuleTransitions(modules: { id: string; state: string }[]): Promise<{ validTransitions: number; invalidTransitions: number; errors: string[] }> {
    const validStates = ["pending", "initializing", "active", "paused", "shutdown", "failed"]
    const errors: string[] = []
    let validTransitions = 0
    let invalidTransitions = 0

    for (const mod of modules) {
      if (validStates.includes(mod.state)) validTransitions++
      else {
        invalidTransitions++
        errors.push(`module ${mod.id} has invalid state: ${mod.state}`)
      }
    }
    return { validTransitions, invalidTransitions, errors }
  },

  async validateAll(modules: { id: string; state: string }[]): Promise<LifecycleValidation> {
    const result = await this.validateModuleTransitions(modules)
    return {
      moduleCount: modules.length,
      validTransitions: result.validTransitions,
      invalidTransitions: result.invalidTransitions,
      valid: result.errors.length === 0,
      errors: result.errors,
    }
  },
}