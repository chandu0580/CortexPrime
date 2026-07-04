export interface IntentInput {
  text: string
  timestamp: string
}

export type ValidationSeverity = "error" | "warning" | "info"

export interface ValidationIssue {
  field: string
  message: string
  severity: ValidationSeverity
}

export interface ValidationResult {
  valid: boolean
  issues: ValidationIssue[]
  normalized?: string
}

export interface NormalizedIntent {
  id: string
  originalText: string
  normalizedText: string
  domain: string | null
  confidence: number
  timestamp: string
}

export type Priority = "low" | "medium" | "high" | "critical"

export type Readiness = "not_assessed" | "assessment_pending" | "assessed"

export interface MissionContext {
  businessGoal: string
  constraints: string[]
  successCriteria: string[]
  stakeholders: string[]
  priority: Priority
  businessDomain: string
}

export interface MissionAssessment {
  feasibility: number
  estimatedDuration: string
  resourceRequirements: string[]
  risks: string[]
  recommendations: string[]
  readiness: Readiness
}

export interface MissionPreview {
  title: string
  summary: string
  objectives: string[]
  expectedOutcomes: string[]
  estimatedEffort: string
  suggestedCapabilities: string[]
}

export interface MissionAnalysis {
  intentId: string
  intent: NormalizedIntent
  context: MissionContext
  assessment: MissionAssessment
  preview: MissionPreview
  timestamp: string
}
