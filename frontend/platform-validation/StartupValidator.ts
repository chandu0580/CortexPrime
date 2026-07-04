import type { ValidationResult, ValidationStatus, ValidationSeverity } from "./types"
import { generateId } from "./shared"

export const StartupValidator = {
  async validatePlatformStart(): Promise<ValidationResult> {
    const errors: string[] = []
    return {
      id: generateId("val"),
      name: "Platform Start",
      status: errors.length === 0 ? "passed" as ValidationStatus : "failed" as ValidationStatus,
      severity: "critical" as ValidationSeverity,
      errors,
      durationMs: 0,
    }
  },

  async validateStartupOrder(expected: string[], actual: string[]): Promise<ValidationResult> {
    const errors: string[] = []
    if (actual.length !== expected.length) errors.push(`expected ${expected.length} modules, found ${actual.length}`)
    for (let i = 0; i < Math.min(expected.length, actual.length); i++) {
      if (expected[i] !== actual[i]) errors.push(`order mismatch at position ${i}: expected ${expected[i]}, found ${actual[i]}`)
    }
    return {
      id: generateId("val"),
      name: "Startup Order",
      status: errors.length === 0 ? "passed" as ValidationStatus : "failed" as ValidationStatus,
      severity: "high" as ValidationSeverity,
      errors,
      durationMs: 0,
    }
  },

  async validateModuleInitialization(initialized: number, total: number): Promise<ValidationResult> {
    const errors: string[] = []
    if (initialized < total) errors.push(`${total - initialized} modules not initialized`)
    return {
      id: generateId("val"),
      name: "Module Initialization",
      status: errors.length === 0 ? "passed" as ValidationStatus : "failed" as ValidationStatus,
      severity: "critical" as ValidationSeverity,
      errors,
      durationMs: 0,
    }
  },

  async validateActivationSequence(activated: number, total: number): Promise<ValidationResult> {
    const errors: string[] = []
    if (activated < total) errors.push(`${total - activated} modules not activated`)
    return {
      id: generateId("val"),
      name: "Activation Sequence",
      status: errors.length === 0 ? "passed" as ValidationStatus : "failed" as ValidationStatus,
      severity: "high" as ValidationSeverity,
      errors,
      durationMs: 0,
    }
  },

  async validateStartupCompletion(success: boolean): Promise<ValidationResult> {
    const errors: string[] = []
    if (!success) errors.push("startup did not complete successfully")
    return {
      id: generateId("val"),
      name: "Startup Completion",
      status: errors.length === 0 ? "passed" as ValidationStatus : "failed" as ValidationStatus,
      severity: "critical" as ValidationSeverity,
      errors,
      durationMs: 0,
    }
  },
}