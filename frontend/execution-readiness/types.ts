import type { MissionExecutionGraph, CapabilityAssignment } from "@/mission-orchestrator/types"

export type ReadinessStatus = "READY" | "WAITING" | "BLOCKED" | "REQUIRES_REVIEW" | "REQUIRES_INTERVENTION"

export type ReadinessCheckType =
  | "dependency"
  | "capability"
  | "policy"
  | "authorization"
  | "prerequisite"

export type ReadinessResult = "pass" | "fail" | "warning" | "info"

export interface ReadinessCheck {
  id: string
  type: ReadinessCheckType
  name: string
  description: string
  result: ReadinessResult
  details: string
  sourceId: string | null
  timestamp: string
}

export interface ReadinessPolicy {
  id: string
  name: string
  category: string
  evaluation: ReadinessResult
  details: string
}

export interface ExecutionApproval {
  required: boolean
  level: "none" | "team" | "management" | "executive"
  granted: boolean
  approvedBy: string | null
  approvedAt: string | null
  conditions: string[]
  waiverGranted: boolean
}

export interface ExecutionBlocker {
  id: string
  checkId: string
  reason: string
  severity: "critical" | "major" | "minor"
  autoResolvable: boolean
  resolutionHint: string
}

export interface ExecutionDependency {
  id: string
  sourceNodeId: string
  targetNodeId: string
  dependencyType: "hard" | "soft" | "informational"
  satisfied: boolean
  details: string
}

export interface ExecutionAuthorization {
  requiredLevel: "none" | "team" | "management" | "executive"
  currentLevel: "none" | "team" | "management" | "executive"
  authorized: boolean
  grantedBy: string | null
  grantedAt: string | null
  expiresAt: string | null
}

export interface ExecutionWindow {
  id: string
  openAt: string | null
  closeAt: string | null
  duration: string
  recurring: boolean
  schedule: string | null
  withinWindow: boolean
}

export interface ExecutionPrerequisite {
  id: string
  name: string
  description: string
  targetId: string
  met: boolean
  details: string
}

export interface ExecutionReadinessReport {
  id: string
  overallStatus: ReadinessStatus
  checks: ReadinessCheck[]
  policies: ReadinessPolicy[]
  approval: ExecutionApproval
  blockers: ExecutionBlocker[]
  dependencies: ExecutionDependency[]
  authorization: ExecutionAuthorization
  window: ExecutionWindow
  prerequisites: ExecutionPrerequisite[]
  passingChecks: number
  totalChecks: number
  summary: string
  timestamp: string
}
