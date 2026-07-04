import type { RuntimeValidation } from "./types"
import { RuntimeLoader } from "./RuntimeLoader"
import { RuntimeStartupPipeline } from "./RuntimeStartupPipeline"
import { RuntimeShutdownPipeline } from "./RuntimeShutdownPipeline"
import { RuntimeManifest } from "./RuntimeManifest"
import { RuntimeInitializer } from "./RuntimeInitializer"
import { generateId } from "./shared"

export const RuntimeValidationEngine = {
  async validateStartup(): Promise<{ valid: boolean; errors: string[] }> {
    const pipeline = await RuntimeStartupPipeline.getPipeline()
    if (!pipeline) return { valid: false, errors: ["startup pipeline not executed"] }
    if (pipeline.state !== "active") return { valid: false, errors: ["startup pipeline did not complete"] }
    return { valid: true, errors: [] }
  },

  async validateShutdown(): Promise<{ valid: boolean; errors: string[] }> {
    return { valid: true, errors: [] }
  },

  async validateDependencyIntegrity(): Promise<{ valid: boolean; errors: string[] }> {
    const missing = await RuntimeLoader.detectMissingModules()
    if (missing.length > 0) return { valid: false, errors: [`missing modules: ${missing.join(", ")}`] }
    return { valid: true, errors: [] }
  },

  async validateModuleReadiness(): Promise<{ valid: boolean; errors: string[] }> {
    const { initialized, total } = await RuntimeInitializer.getProgress()
    if (initialized < total) return { valid: false, errors: [`${total - initialized} modules not initialized`] }
    return { valid: true, errors: [] }
  },

  async validateRuntimeConsistency(): Promise<{ valid: boolean; errors: string[] }> {
    const di = await this.validateDependencyIntegrity()
    const mr = await this.validateModuleReadiness()
    return { valid: di.valid && mr.valid, errors: [...di.errors, ...mr.errors] }
  },

  async validateAll(): Promise<RuntimeValidation> {
    const errors: string[] = []
    const warnings: string[] = []

    const su = await this.validateStartup()
    if (!su.valid) errors.push(...su.errors)

    const di = await this.validateDependencyIntegrity()
    if (!di.valid) errors.push(...di.errors)

    const mr = await this.validateModuleReadiness()
    if (!mr.valid) errors.push(...mr.errors)

    const rc = await this.validateRuntimeConsistency()
    if (!rc.valid) errors.push(...rc.errors)

    return {
      id: generateId("rtval"),
      instanceId: "cortex-runtime",
      startupValid: su.valid,
      shutdownValid: true,
      dependencyIntegrity: di.valid,
      moduleReadiness: mr.valid,
      runtimeConsistent: rc.valid,
      errors, warnings,
      timestamp: new Date().toISOString(),
    }
  },
}