import type { GovernanceAudit } from "./types"
import { generateId } from "./shared"

const audits = new Map<string, GovernanceAudit>()

export const GovernanceAuditManager = {
  async recordAudit(sessionId: string, action: string, actor: string, target: string, detail: string, metadata: Record<string, unknown> = {}): Promise<GovernanceAudit> {
    const id = generateId("gov-aud")
    const audit: GovernanceAudit = {
      id,
      sessionId,
      action,
      actor,
      target,
      detail,
      timestamp: new Date().toISOString(),
      metadata,
    }
    audits.set(id, audit)
    return audit
  },

  async buildTimeline(sessionId: string): Promise<GovernanceAudit[]> {
    return Array.from(audits.values())
      .filter((a) => a.sessionId === sessionId)
      .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
  },

  async queryAudit(filter?: { actor?: string; action?: string; target?: string; sessionId?: string }): Promise<GovernanceAudit[]> {
    let result = Array.from(audits.values())
    if (filter?.actor) result = result.filter((a) => a.actor === filter.actor)
    if (filter?.action) result = result.filter((a) => a.action === filter.action)
    if (filter?.target) result = result.filter((a) => a.target === filter.target)
    if (filter?.sessionId) result = result.filter((a) => a.sessionId === filter.sessionId)
    return result.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
  },

  async getAudit(id: string): Promise<GovernanceAudit | null> {
    return audits.get(id) ?? null
  },

  async getAuditCount(): Promise<number> {
    return audits.size
  },
}
