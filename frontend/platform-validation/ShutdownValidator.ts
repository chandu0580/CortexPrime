import type { ValidationResult, ValidationStatus, ValidationSeverity } from "./types"
import { generateId } from "./shared"

export const ShutdownValidator = {
  async validateShutdownOrder(modules: string[], reverseModules: string[]): Promise<ValidationResult> {
    const errors: string[] = []
    const expectedReverse = [...modules].reverse()
    for (let i = 0; i < Math.min(expectedReverse.length, reverseModules.length); i++) {
      if (expectedReverse[i] !== reverseModules[i]) errors.push(`shutdown order mismatch at position ${i}`)
    }
    return {
      id: generateId("val"),
      name: "Shutdown Order",
      status: errors.length === 0 ? "passed" as ValidationStatus : "failed" as ValidationStatus,
      severity: "high" as ValidationSeverity,
      errors,
      durationMs: 0,
    }
  },

  async validateResourceRelease(deactivated: number, total: number): Promise<ValidationResult> {
    const errors: string[] = []
    if (deactivated < total) errors.push(`${total - deactivated} modules not deactivated`)
    return {
      id: generateId("val"),
      name: "Resource Release",
      status: errors.length === 0 ? "passed" as ValidationStatus : "failed" as ValidationStatus,
      severity: "high" as ValidationSeverity,
      errors,
      durationMs: 0,
    }
  },

  async validateShutdownCompletion(errors: string[]): Promise<ValidationResult> {
    return {
      id: generateId("val"),
      name: "Shutdown Completion",
      status: errors.length === 0 ? "passed" as ValidationStatus : "failed" as ValidationStatus,
      severity: "critical" as ValidationSeverity,
      errors,
      durationMs: 0,
    }
  },
}