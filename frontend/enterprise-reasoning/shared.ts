import type { DecisionCategory, EnterpriseDecision } from "./types"

function generateId(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`
}

export function buildDecisionBase(category: DecisionCategory, targetId: string, targetLabel: string): Omit<EnterpriseDecision, "explanation" | "evidence" | "assumptions" | "alternatives" | "confidence"> {
  return {
    id: generateId(`dec-${category}`),
    category,
    targetId,
    targetLabel,
    timestamp: new Date().toISOString(),
  }
}
