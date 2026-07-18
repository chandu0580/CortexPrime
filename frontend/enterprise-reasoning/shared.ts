import type { DecisionCategory, EnterpriseDecision } from "./types"

import { generateId } from '../lib/utils/id';
export { generateId }

export function buildDecisionBase(category: DecisionCategory, targetId: string, targetLabel: string): Omit<EnterpriseDecision, "explanation" | "evidence" | "assumptions" | "alternatives" | "confidence"> {
  return {
    id: generateId(`dec-${category}`),
    category,
    targetId,
    targetLabel,
    timestamp: new Date().toISOString(),
  }
}
