import type { ExecutionWorker, WorkerCapability } from "@/runtime-core/types"

export type CapabilityStatus = "available" | "limited" | "unavailable" | "deprecated"

export type MatchPrecision = "exact" | "partial" | "cross_train" | "none"

export type ConstraintType = "time_window" | "concurrency" | "isolation" | "priority" | "location" | "security"

export type ResolutionStatus = "resolved" | "partial" | "unresolved"

export interface CapabilityDescriptor {
  id: string
  name: string
  version: string
  capability: WorkerCapability
  features: string[]
  constraints: CapabilityConstraint[]
  maxConcurrency: number
  estimatedSetupTime: string
  estimatedTeardownTime: string
  dependencies: string[]
  metadata: Record<string, string>
}

export interface CapabilityRequirement {
  taskId: string
  requiredCapability: WorkerCapability
  requiredFeatures: string[]
  minVersion: string
  priority: number
  maxConcurrency: number
  timeout: string
  constraints: CapabilityConstraint[]
}

export interface CapabilityMatch {
  descriptorId: string
  workerId: string
  precision: MatchPrecision
  matchedFeatures: string[]
  unmatchedFeatures: string[]
  versionCompatible: boolean
  versionMatch: "exact" | "major" | "minor" | "incompatible"
}

export interface CapabilityScore {
  candidateId: string
  workerId: string
  matchScore: number
  availabilityScore: number
  healthScore: number
  loadScore: number
  priorityScore: number
  totalScore: number
  breakdown: string
}

export interface CapabilityCandidate {
  id: string
  worker: ExecutionWorker
  descriptor: CapabilityDescriptor
  match: CapabilityMatch
  score: CapabilityScore
  available: boolean
  rank: number
}

export interface CapabilityResolution {
  id: string
  requirement: CapabilityRequirement
  candidates: CapabilityCandidate[]
  selectedCandidate: CapabilityCandidate | null
  status: ResolutionStatus
  reasoning: string
}

export interface CapabilityConstraint {
  id: string
  type: ConstraintType
  name: string
  value: string
  description: string
}

export interface CapabilityPolicy {
  id: string
  name: string
  description: string
  rules: CapabilityPolicyRule[]
}

export interface CapabilityPolicyRule {
  id: string
  condition: string
  action: "allow" | "deny" | "warn" | "require_additional"
  details: string
}

export interface CapabilityAvailability {
  workerId: string
  descriptorId: string
  status: CapabilityStatus
  currentLoad: number
  maxLoad: number
  healthy: boolean
  lastHeartbeat: string | null
  estimatedAvailableAt: string | null
}

export interface CapabilityRoutingReport {
  id: string
  requirement: CapabilityRequirement
  resolutions: CapabilityResolution[]
  totalCandidates: number
  totalAvailable: number
  totalUnavailable: number
  bestCandidate: CapabilityCandidate | null
  summary: string
  timestamp: string
}
