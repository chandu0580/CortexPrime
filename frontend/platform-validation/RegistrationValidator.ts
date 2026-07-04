import type { ValidationResult, ValidationStatus, ValidationSeverity } from "./types"
import { generateId } from "./shared"

export const RegistrationValidator = {
  async verifyPackageRegistration(packages: string[], expected: string[]): Promise<ValidationResult> {
    const errors: string[] = []
    const missing = expected.filter((e) => !packages.includes(e))
    if (missing.length > 0) errors.push(`missing package registrations: ${missing.join(", ")}`)
    return {
      id: generateId("val"),
      name: "Package Registration",
      status: errors.length === 0 ? "passed" as ValidationStatus : "failed" as ValidationStatus,
      severity: "critical" as ValidationSeverity,
      errors,
      durationMs: 0,
    }
  },

  async verifyCapabilityRegistration(capabilities: string[], expected: string[]): Promise<ValidationResult> {
    const errors: string[] = []
    const missing = expected.filter((e) => !capabilities.includes(e))
    if (missing.length > 0) errors.push(`missing capabilities: ${missing.join(", ")}`)
    return {
      id: generateId("val"),
      name: "Capability Registration",
      status: errors.length === 0 ? "passed" as ValidationStatus : "failed" as ValidationStatus,
      severity: "high" as ValidationSeverity,
      errors,
      durationMs: 0,
    }
  },

  async verifyWorkerRegistration(workers: string[], expected: string[]): Promise<ValidationResult> {
    const errors: string[] = []
    const missing = expected.filter((e) => !workers.includes(e))
    if (missing.length > 0) errors.push(`missing worker registrations: ${missing.join(", ")}`)
    return {
      id: generateId("val"),
      name: "Worker Registration",
      status: errors.length === 0 ? "passed" as ValidationStatus : "failed" as ValidationStatus,
      severity: "medium" as ValidationSeverity,
      errors,
      durationMs: 0,
    }
  },

  async verifyConnectorRegistration(connectors: string[], expected: string[]): Promise<ValidationResult> {
    const errors: string[] = []
    const missing = expected.filter((e) => !connectors.includes(e))
    if (missing.length > 0) errors.push(`missing connector registrations: ${missing.join(", ")}`)
    return {
      id: generateId("val"),
      name: "Connector Registration",
      status: errors.length === 0 ? "passed" as ValidationStatus : "failed" as ValidationStatus,
      severity: "medium" as ValidationSeverity,
      errors,
      durationMs: 0,
    }
  },
}