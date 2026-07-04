import type { AuditRecord, AuditEvent, AuditSeverity } from "./types"
import { generateId } from "./shared"

const audits = new Map<string, AuditRecord>()
const auditEvents = new Map<string, AuditEvent>()

export const AuditManager = {
  async recordAudit(
    action: string,
    actor: string,
    target: string,
    severity: AuditSeverity,
    source: string,
    details: string = "",
    metadata: Record<string, unknown> = {},
  ): Promise<{ record: AuditRecord; event: AuditEvent }> {
    const id = generateId("audit")
    const eventId = generateId("audit-ev")

    const record: AuditRecord = {
      id,
      eventId,
      action,
      actor,
      target,
      severity,
      source,
      timestamp: new Date().toISOString(),
      details,
      metadata,
    }

    const event: AuditEvent = {
      id: eventId,
      auditId: id,
      type: `audit.${action}`,
      timestamp: new Date().toISOString(),
      data: { action, actor, target, severity, source, details, metadata },
      source,
    }

    audits.set(id, record)
    auditEvents.set(eventId, event)
    return { record, event }
  },

  async queryAudit(filter?: { actor?: string; severity?: AuditSeverity; action?: string; source?: string }): Promise<AuditRecord[]> {
    let result = Array.from(audits.values())
    if (filter?.actor) result = result.filter((a) => a.actor === filter.actor)
    if (filter?.severity) result = result.filter((a) => a.severity === filter.severity)
    if (filter?.action) result = result.filter((a) => a.action === filter.action)
    if (filter?.source) result = result.filter((a) => a.source === filter.source)
    return result.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
  },

  async buildTimeline(filter?: { actor?: string; severity?: AuditSeverity }): Promise<AuditRecord[]> {
    const records = await AuditManager.queryAudit(filter)
    return records.sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
  },

  async getAudit(id: string): Promise<AuditRecord | null> {
    return audits.get(id) ?? null
  },

  async getAuditCount(): Promise<number> {
    return audits.size
  },
}
