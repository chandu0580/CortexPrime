import type { PlatformError } from "../contracts"

export type ErrorCategory = "validation" | "authorization" | "execution" | "timeout" | "resource" | "internal" | "external"

export interface ErrorContext {
  sessionId: string
  module: string
  operation: string
  timestamp: string
  details: Record<string, unknown>
}

export interface ErrorRecovery {
  retryable: boolean
  retryDelayMs: number | null
  fallbackAction: string | null
  requiresIntervention: boolean
}

export type ErrorSeverity = PlatformError["severity"]
