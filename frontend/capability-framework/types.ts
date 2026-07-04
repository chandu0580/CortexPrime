import type { PlatformError } from "@/platform/contracts"

export type CapabilityStatus = "active" | "inactive" | "deprecated" | "retired"

export type RequirementType = "hardware" | "software" | "permission" | "capability" | "environment"

export type ConstraintType = "rate_limit" | "concurrency" | "time_window" | "resource" | "scope"

export type DependencyType = "hard" | "soft" | "optional"

export type PolicyEffect = "allow" | "deny" | "audit"

export type CapabilityStageType = "setup" | "execute" | "cleanup" | "validate" | "transform" | "output"

export interface CapabilityDescriptor {
  id: string
  name: string
  type: string
  version: string
  description: string
  category: string
  tags: string[]
  icon: string
  provider: string
  status: CapabilityStatus
  createdAt: string
  updatedAt: string
}

export interface CapabilityStage {
  id: string
  name: string
  description: string
  type: CapabilityStageType
  order: number
  timeoutMs: number
  maxRetries: number
  inputKeys: string[]
  outputKeys: string[]
  required: boolean
  tags: string[]
}

export interface CapabilityRequirement {
  id: string
  type: RequirementType
  key: string
  value: string
  description: string
  optional: boolean
  validationHint: string
}

export interface CapabilityConstraint {
  id: string
  type: ConstraintType
  key: string
  value: number | string | string[]
  description: string
  operator: "eq" | "neq" | "lt" | "lte" | "gt" | "gte" | "in" | "not_in"
  severity: "error" | "warning"
}

export interface CapabilityPolicy {
  id: string
  name: string
  description: string
  effect: PolicyEffect
  resource: string
  actions: string[]
  conditions: Record<string, unknown>
  priority: number
  enabled: boolean
}

export interface CapabilityConfiguration {
  settings: Record<string, unknown>
  defaults: Record<string, unknown>
  overrides: Record<string, unknown>
  environment: Record<string, string>
  features: Record<string, boolean>
  timeouts: Record<string, number>
  limits: Record<string, number>
}

export interface CapabilityDependency {
  id: string
  capabilityId: string
  name: string
  version: string
  type: DependencyType
  optional: boolean
  description: string
  requiredFeatures: string[]
}

export interface CapabilityMetadata {
  displayName: string
  description: string
  category: string
  tags: string[]
  provider: string
  homepage: string
  documentation: string
  license: string
  maintainers: string[]
  changelog: string[]
}

export interface CapabilityValidationResult {
  valid: boolean
  capabilityId: string
  errors: Array<{
    code: string
    message: string
    path: string
    severity: "error" | "warning"
  }>
  warnings: Array<{
    code: string
    message: string
    path: string
  }>
  stageValidation: Record<string, boolean>
  dependencyValidation: Record<string, boolean>
  policyValidation: Record<string, boolean>
}

export interface CapabilityDefinition {
  id: string
  descriptor: CapabilityDescriptor
  stages: CapabilityStage[]
  requirements: CapabilityRequirement[]
  constraints: CapabilityConstraint[]
  policies: CapabilityPolicy[]
  configuration: CapabilityConfiguration
  dependencies: CapabilityDependency[]
  metadata: CapabilityMetadata
  createdAt: string
  updatedAt: string
}
