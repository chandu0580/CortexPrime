import type { HealthValidation } from "./types"

export const HealthValidator = {
  async validatePlatformHealth(platformHealthy: boolean): Promise<{ valid: boolean; errors: string[] }> {
    const errors: string[] = []
    if (!platformHealthy) errors.push("platform is not healthy")
    return { valid: platformHealthy, errors }
  },

  async validateRuntimeHealth(runtimeHealthy: boolean): Promise<{ valid: boolean; errors: string[] }> {
    const errors: string[] = []
    if (!runtimeHealthy) errors.push("runtime is not healthy")
    return { valid: runtimeHealthy, errors }
  },

  async validateDependencyHealth(dependencyHealthy: boolean): Promise<{ valid: boolean; errors: string[] }> {
    const errors: string[] = []
    if (!dependencyHealthy) errors.push("dependencies are not healthy")
    return { valid: dependencyHealthy, errors }
  },

  async validateAll(
    platformHealthy: boolean,
    runtimeHealthy: boolean,
    dependencyHealthy: boolean,
    modulesHealthy: number,
    totalModules: number,
  ): Promise<HealthValidation> {
    const errors: string[] = []

    const ph = await this.validatePlatformHealth(platformHealthy)
    if (!ph.valid) errors.push(...ph.errors)

    const rh = await this.validateRuntimeHealth(runtimeHealthy)
    if (!rh.valid) errors.push(...rh.errors)

    const dh = await this.validateDependencyHealth(dependencyHealthy)
    if (!dh.valid) errors.push(...dh.errors)

    return {
      platformHealthy: ph.valid,
      runtimeHealthy: rh.valid,
      dependencyHealthy: dh.valid,
      modulesHealthy,
      totalModules,
      valid: errors.length === 0,
      errors,
    }
  },
}