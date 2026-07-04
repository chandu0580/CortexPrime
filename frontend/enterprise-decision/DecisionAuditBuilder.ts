import type { AuditEvent, DecisionAudit } from "./types"
import { generateId } from "./shared"

export const DecisionAuditBuilder = {
  async buildAudit(decisionId: string, events: AuditEvent[]): Promise<DecisionAudit> {
    const sorted = [...events].sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())

    return {
      id: generateId("audit"),
      decisionId,
      events: sorted,
      trail: sorted.map((e) => `[${e.timestamp}] ${e.actor}: ${e.action} — ${e.details}`).join("\n"),
    }
  },
}
