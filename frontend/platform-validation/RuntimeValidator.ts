import type { RuntimeValidationData } from "./types"

export const RuntimeValidator = {
  async validateRuntimeReadiness(runtimeReady: boolean): Promise<{ valid: boolean; errors: string[] }> {
    const errors: string[] = []
    if (!runtimeReady) errors.push("runtime is not ready")
    return { valid: runtimeReady, errors }
  },

  async validateRuntimeComposition(modules: unknown[], expected: number): Promise<{ valid: boolean; errors: string[] }> {
    const errors: string[] = []
    if (modules.length < expected) errors.push(`runtime composition incomplete: ${modules.length}/${expected} modules`)
    return { valid: errors.length === 0, errors }
  },

  async validateStartupSequence(startupSuccess: boolean): Promise<{ valid: boolean; errors: string[] }> {
    const errors: string[] = []
    if (!startupSuccess) errors.push("startup sequence did not complete")
    return { valid: startupSuccess, errors }
  },

  async validateRestart(restartSuccess: boolean): Promise<{ valid: boolean; errors: string[] }> {
    const errors: string[] = []
    if (!restartSuccess) errors.push("restart failed")
    return { valid: restartSuccess, errors }
  },

  async validateRecovery(recoverySuccess: boolean): Promise<{ valid: boolean; errors: string[] }> {
    const errors: string[] = []
    if (!recoverySuccess) errors.push("recovery failed")
    return { valid: recoverySuccess, errors }
  },

  async validateAll(
    runtimeReady: boolean,
    modules: unknown[],
    expectedModules: number,
    startupSuccess: boolean,
    restartSupported: boolean,
    recoverySupported: boolean,
  ): Promise<RuntimeValidationData> {
    const errors: string[] = []

    const readiness = await this.validateRuntimeReadiness(runtimeReady)
    if (!readiness.valid) errors.push(...readiness.errors)

    const composition = await this.validateRuntimeComposition(modules, expectedModules)
    if (!composition.valid) errors.push(...composition.errors)

    const sequence = await this.validateStartupSequence(startupSuccess)
    if (!sequence.valid) errors.push(...sequence.errors)

    return {
      runtimeReady: readiness.valid,
      compositionValid: composition.valid,
      startupSequenceValid: sequence.valid,
      restartSupported,
      recoverySupported,
      valid: errors.length === 0,
      errors,
    }
  },
}