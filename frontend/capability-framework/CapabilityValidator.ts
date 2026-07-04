import type { CapabilityDefinition, CapabilityValidationResult } from "./types"
import { CapabilityRegistry } from "./CapabilityRegistry"

export const CapabilityValidator = {
  async validate(capabilityId: string): Promise<CapabilityValidationResult> {
    const definition = await CapabilityRegistry.get(capabilityId)
    if (!definition) {
      return {
        valid: false,
        capabilityId,
        errors: [{ code: "NOT_FOUND", message: `Capability ${capabilityId} is not registered`, path: "id", severity: "error" }],
        warnings: [],
        stageValidation: {},
        dependencyValidation: {},
        policyValidation: {},
      }
    }

    const errors: CapabilityValidationResult["errors"] = []
    const warnings: CapabilityValidationResult["warnings"] = []
    const stageValidation: Record<string, boolean> = {}
    const dependencyValidation: Record<string, boolean> = {}
    const policyValidation: Record<string, boolean> = {}

    this.validateDescriptor(definition, errors, warnings)
    this.validateStages(definition, errors, warnings, stageValidation)
    this.validateRequirements(definition, errors, warnings)
    this.validateConstraints(definition, errors, warnings)
    this.validateDependencies(definition, errors, warnings, dependencyValidation)
    this.validatePolicies(definition, errors, warnings, policyValidation)
    this.validateConfiguration(definition, errors, warnings)

    return {
      valid: errors.length === 0,
      capabilityId,
      errors,
      warnings,
      stageValidation,
      dependencyValidation,
      policyValidation,
    }
  },

  async validateAll(): Promise<CapabilityValidationResult[]> {
    const definitions = await CapabilityRegistry.list()
    return Promise.all(definitions.map((d) => this.validate(d.id)))
  },

  validateDescriptor(
    definition: CapabilityDefinition,
    errors: CapabilityValidationResult["errors"],
    warnings: CapabilityValidationResult["warnings"],
  ): void {
    const d = definition.descriptor
    if (!d.id) errors.push({ code: "MISSING_ID", message: "Capability descriptor ID is required", path: "descriptor.id", severity: "error" })
    if (!d.name) errors.push({ code: "MISSING_NAME", message: "Capability name is required", path: "descriptor.name", severity: "error" })
    if (!d.type) errors.push({ code: "MISSING_TYPE", message: "Capability type is required", path: "descriptor.type", severity: "error" })
    if (!d.version) errors.push({ code: "MISSING_VERSION", message: "Capability version is required", path: "descriptor.version", severity: "error" })

    if (d.id && d.id !== definition.id) {
      warnings.push({ code: "ID_MISMATCH", message: `Capability ID "${definition.id}" differs from descriptor ID "${d.id}"`, path: "id" })
    }
  },

  validateStages(
    definition: CapabilityDefinition,
    errors: CapabilityValidationResult["errors"],
    warnings: CapabilityValidationResult["warnings"],
    stageValidation: Record<string, boolean>,
  ): void {
    const seen = new Set<string>()

    for (const stage of definition.stages) {
      const stageErrors: string[] = []
      if (!stage.id) stageErrors.push("Stage ID is required")
      if (!stage.name) stageErrors.push("Stage name is required")
      if (stage.order < 0) stageErrors.push("Stage order must be non-negative")
      if (stage.timeoutMs <= 0) stageErrors.push("Stage timeout must be greater than 0")

      if (seen.has(stage.id)) {
        stageErrors.push(`Duplicate stage ID: ${stage.id}`)
      }
      seen.add(stage.id)

      if (stageErrors.length > 0) {
        stageValidation[stage.id] = false
        for (const msg of stageErrors) {
          errors.push({ code: "STAGE_INVALID", message: `Stage "${stage.name ?? stage.id}": ${msg}`, path: `stages.${stage.id}`, severity: "error" })
        }
      } else {
        stageValidation[stage.id] = true
      }
    }

    if (definition.stages.length === 0) {
      warnings.push({ code: "NO_STAGES", message: "Capability has no stages defined", path: "stages" })
    }

    const orders = definition.stages.map((s) => s.order)
    if (new Set(orders).size !== orders.length) {
      warnings.push({ code: "DUPLICATE_ORDER", message: "Multiple stages share the same order value", path: "stages" })
    }
  },

  validateRequirements(
    definition: CapabilityDefinition,
    errors: CapabilityValidationResult["errors"],
    warnings: CapabilityValidationResult["warnings"],
  ): void {
    for (const req of definition.requirements) {
      if (!req.id) errors.push({ code: "REQUIREMENT_INVALID", message: "Requirement ID is required", path: `requirements.${req.id}`, severity: "error" })
      if (!req.key) errors.push({ code: "REQUIREMENT_INVALID", message: `Requirement "${req.id}": key is required`, path: `requirements.${req.id}`, severity: "error" })
      if (!req.value) warnings.push({ code: "REQUIREMENT_EMPTY", message: `Requirement "${req.id}" has no value`, path: `requirements.${req.id}` })
    }
  },

  validateConstraints(
    definition: CapabilityDefinition,
    errors: CapabilityValidationResult["errors"],
    warnings: CapabilityValidationResult["warnings"],
  ): void {
    for (const constraint of definition.constraints) {
      if (!constraint.id) errors.push({ code: "CONSTRAINT_INVALID", message: "Constraint ID is required", path: "constraints", severity: "error" })
      if (!constraint.key) errors.push({ code: "CONSTRAINT_INVALID", message: `Constraint "${constraint.id}": key is required`, path: `constraints.${constraint.id}`, severity: "error" })
      if (constraint.value === undefined || constraint.value === null) {
        warnings.push({ code: "CONSTRAINT_EMPTY", message: `Constraint "${constraint.id}" has no value`, path: `constraints.${constraint.id}` })
      }
    }
  },

  validateDependencies(
    definition: CapabilityDefinition,
    errors: CapabilityValidationResult["errors"],
    warnings: CapabilityValidationResult["warnings"],
    dependencyValidation: Record<string, boolean>,
  ): void {
    for (const dep of definition.dependencies) {
      const depErrors: string[] = []
      if (!dep.id) depErrors.push("Dependency ID is required")
      if (!dep.capabilityId) depErrors.push("Dependency capabilityId is required")
      if (!dep.name) depErrors.push("Dependency name is required")

      if (depErrors.length > 0) {
        dependencyValidation[dep.id] = false
        for (const msg of depErrors) {
          errors.push({ code: "DEPENDENCY_INVALID", message: `Dependency "${dep.name ?? dep.id}": ${msg}`, path: `dependencies.${dep.id}`, severity: "error" })
        }
      } else {
        dependencyValidation[dep.id] = true
      }
    }

    if (definition.dependencies.length > 0) {
      const ids = definition.dependencies.map((d) => d.capabilityId)
      if (new Set(ids).size !== ids.length) {
        warnings.push({ code: "DUPLICATE_DEPENDENCY", message: "Multiple dependencies reference the same capability", path: "dependencies" })
      }
    }
  },

  validatePolicies(
    definition: CapabilityDefinition,
    errors: CapabilityValidationResult["errors"],
    warnings: CapabilityValidationResult["warnings"],
    policyValidation: Record<string, boolean>,
  ): void {
    for (const policy of definition.policies) {
      const policyErrors: string[] = []
      if (!policy.id) policyErrors.push("Policy ID is required")
      if (!policy.name) policyErrors.push("Policy name is required")
      if (!policy.resource) policyErrors.push("Policy resource is required")

      if (policyErrors.length > 0) {
        policyValidation[policy.id] = false
        for (const msg of policyErrors) {
          errors.push({ code: "POLICY_INVALID", message: `Policy "${policy.name ?? policy.id}": ${msg}`, path: `policies.${policy.id}`, severity: "error" })
        }
      } else {
        policyValidation[policy.id] = true
      }
    }
  },

  validateConfiguration(
    definition: CapabilityDefinition,
    errors: CapabilityValidationResult["errors"],
    warnings: CapabilityValidationResult["warnings"],
  ): void {
    const config = definition.configuration
    if (!config.settings) warnings.push({ code: "MISSING_SETTINGS", message: "Capability configuration has no settings", path: "configuration.settings" })
    if (!config.defaults) warnings.push({ code: "MISSING_DEFAULTS", message: "Capability configuration has no defaults", path: "configuration.defaults" })
    if (!config.features) warnings.push({ code: "MISSING_FEATURES", message: "Capability configuration has no features", path: "configuration.features" })
  },
}
