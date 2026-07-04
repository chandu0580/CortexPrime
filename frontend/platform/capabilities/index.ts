import type { PlatformCapability } from "../contracts"

export type CapabilityMatchPrecision = "exact" | "partial" | "cross_train" | "none"

export interface CapabilityMatch {
  capability: PlatformCapability
  precision: CapabilityMatchPrecision
  matchedFeatures: string[]
  unmatchedFeatures: string[]
  score: number
}

export interface CapabilityRequest {
  requiredType: string
  requiredFeatures: string[]
  minVersion: string
  priority: number
}

export interface CapabilityResolution {
  request: CapabilityRequest
  matches: CapabilityMatch[]
  selected: CapabilityMatch | null
  status: "resolved" | "partial" | "unresolved"
}
