import type { LLMResponse, PromptType, MissionPlan, WorkerDecision, ConnectorAction, BrowserAction, VoiceResponse, RecoveryDecision } from "./types"

interface ValidationResult {
  valid: boolean
  parsed: Record<string, unknown> | null
  errors: string[]
}

function tryParseJson(content: string): Record<string, unknown> | null {
  const jsonMatch = content.match(/```(?:json)?\s*(\{[\s\S]*?\})\s*```/)
  if (jsonMatch) {
    try { return JSON.parse(jsonMatch[1]) as Record<string, unknown> } catch { return null }
  }

  const braceStart = content.indexOf("{")
  if (braceStart >= 0) {
    try { return JSON.parse(content.slice(braceStart)) as Record<string, unknown> } catch { }
  }

  try { return JSON.parse(content) as Record<string, unknown> } catch { return null }
}

function validateRequiredFields(obj: Record<string, unknown>, required: string[]): string[] {
  const errors: string[] = []
  for (const field of required) {
    if (obj[field] === undefined || obj[field] === null) {
      errors.push(`Missing required field: ${field}`)
    }
  }
  return errors
}

export const ReasoningResponseValidator = {
  async validate(response: LLMResponse, type: PromptType): Promise<ValidationResult> {
    const errors: string[] = []

    if (!response.content) {
      return { valid: false, parsed: null, errors: ["Empty response content"] }
    }

    const parsed = tryParseJson(response.content)

    if (!parsed) {
      errors.push("Response is not valid JSON")
      return { valid: false, parsed: null, errors }
    }

    const schemaErrors = this.validateSchema(parsed, type)
    errors.push(...schemaErrors)

    return {
      valid: errors.length === 0,
      parsed,
      errors,
    }
  },

  validateSchema(obj: Record<string, unknown>, type: PromptType): string[] {
    switch (type) {
      case "mission_planning":
        return validateRequiredFields(obj, ["title", "objective", "phases", "keyResults", "estimatedDuration", "priority"])
      case "executive_reasoning":
        return validateRequiredFields(obj, ["recommendation", "reasoning", "confidence"])
      case "research":
        return validateRequiredFields(obj, ["summary", "findings"])
      case "browser_automation":
        return validateRequiredFields(obj, ["action", "target"])
      case "connector_action":
        return validateRequiredFields(obj, ["connectorId", "action", "endpoint", "method"])
      case "incident_response":
        return validateRequiredFields(obj, ["assessment", "severity", "recoveryStrategy"])
      case "engineering_operations":
        return validateRequiredFields(obj, ["operation", "target", "parameters"])
      default:
        return []
    }
  },

  async validateMissionPlan(parsed: Record<string, unknown>): Promise<MissionPlan | null> {
    const errors = validateRequiredFields(parsed, ["title", "objective", "phases", "keyResults", "estimatedDuration", "priority"])
    if (errors.length > 0) return null
    return parsed as unknown as MissionPlan
  },

  async validateWorkerDecision(parsed: Record<string, unknown>): Promise<WorkerDecision | null> {
    const errors = validateRequiredFields(parsed, ["workerId", "action", "target"])
    if (errors.length > 0) return null
    return parsed as unknown as WorkerDecision
  },

  async validateConnectorAction(parsed: Record<string, unknown>): Promise<ConnectorAction | null> {
    const errors = validateRequiredFields(parsed, ["connectorId", "action", "endpoint", "method"])
    if (errors.length > 0) return null
    return parsed as unknown as ConnectorAction
  },

  async validateBrowserAction(parsed: Record<string, unknown>): Promise<BrowserAction | null> {
    const errors = validateRequiredFields(parsed, ["action", "target"])
    if (errors.length > 0) return null
    return parsed as unknown as BrowserAction
  },

  async validateVoiceResponse(parsed: Record<string, unknown>): Promise<VoiceResponse | null> {
    const errors = validateRequiredFields(parsed, ["text", "tone"])
    if (errors.length > 0) return null
    return parsed as unknown as VoiceResponse
  },

  async validateRecoveryDecision(parsed: Record<string, unknown>): Promise<RecoveryDecision | null> {
    const errors = validateRequiredFields(parsed, ["sessionId", "failureType", "recoveryStrategy"])
    if (errors.length > 0) return null
    return parsed as unknown as RecoveryDecision
  },
}

export const ReasoningAuditor = {
  entries: new Map<string, Array<{
    id: string
    sessionId: string
    provider: string
    model: string
    promptHash: string
    promptPreview: string
    responseHash: string
    responsePreview: string
    tokensUsed: { prompt: number; completion: number; total: number }
    latencyMs: number
    success: boolean
    error: string | null
    validated: boolean
    schemaType: string | null
    timestamp: string
  }>>(),

  async record(entry: {
    id: string
    sessionId: string
    provider: string
    model: string
    promptHash: string
    promptPreview: string
    responseHash: string
    responsePreview: string
    tokensUsed: { prompt: number; completion: number; total: number }
    latencyMs: number
    success: boolean
    error: string | null
    validated: boolean
    schemaType: string | null
  }): Promise<void> {
    const auditEntry = {
      ...entry,
      timestamp: new Date().toISOString(),
    }

    const sessionEntries = this.entries.get(entry.sessionId) ?? []
    sessionEntries.push(auditEntry)
    this.entries.set(entry.sessionId, sessionEntries)
  },

  async getSessionAudit(sessionId: string): Promise<typeof this.entries extends Map<string, infer V> ? V : never> {
    return (this.entries.get(sessionId) ?? []) as never
  },

  async getAllAudit(): Promise<Array<{ sessionId: string; count: number }>> {
    return Array.from(this.entries.entries()).map(([sessionId, entries]) => ({
      sessionId,
      count: entries.length,
    }))
  },

  async getStats(): Promise<{ totalInteractions: number; totalValidated: number; totalFailed: number; totalTokens: number }> {
    let totalInteractions = 0
    let totalValidated = 0
    let totalFailed = 0
    let totalTokens = 0

    for (const [, entries] of this.entries) {
      for (const e of entries) {
        totalInteractions++
        if (e.validated) totalValidated++
        if (!e.success) totalFailed++
        totalTokens += e.tokensUsed.total
      }
    }

    return { totalInteractions, totalValidated, totalFailed, totalTokens }
  },
}
