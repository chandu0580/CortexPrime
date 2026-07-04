import type { Evidence, EvidenceCategory, EvidenceConfidence, EvidenceRelationship, EvidenceRelationshipType } from "./types"
import { generateId } from "@/worker-framework/shared"

const evidenceMap = new Map<string, Evidence>()

const CONFIDENCE_WEIGHTS: Record<EvidenceConfidence, number> = {
  high: 0.9,
  medium: 0.65,
  low: 0.35,
  unverified: 0.1,
}

export const EvidenceManager = {
  async registerEvidence(
    sessionId: string,
    sourceId: string,
    category: EvidenceCategory,
    content: string,
    confidence: EvidenceConfidence = "unverified",
    metadata?: Record<string, string>,
  ): Promise<Evidence> {
    const evidence: Evidence = {
      id: generateId("intel-evidence"),
      sessionId,
      sourceId,
      category,
      confidence,
      confidenceScore: CONFIDENCE_WEIGHTS[confidence],
      content,
      metadata: metadata ?? {},
      relationships: [],
      validated: false,
      validationErrors: [],
      duplicateOf: null,
      createdAt: new Date().toISOString(),
    }
    evidenceMap.set(evidence.id, evidence)
    return evidence
  },

  async getEvidence(evidenceId: string): Promise<Evidence | null> {
    return evidenceMap.get(evidenceId) ?? null
  },

  async validateEvidence(evidenceId: string): Promise<{ valid: boolean; reasons: string[] }> {
    const evidence = evidenceMap.get(evidenceId)
    if (!evidence) throw new Error(`Evidence ${evidenceId} not found`)

    const reasons: string[] = []
    let valid = true

    if (!evidence.content || evidence.content.trim().length === 0) {
      reasons.push("Evidence content is empty")
      valid = false
    }
    if (evidence.content.length < 10) {
      reasons.push("Evidence content is too short (minimum 10 characters)")
      valid = false
    }
    if (evidence.sourceId.trim().length === 0) {
      reasons.push("Evidence source ID is required")
      valid = false
    }

    evidence.validated = valid
    evidence.validationErrors = reasons
    return { valid, reasons }
  },

  async categorizeEvidence(evidenceId: string, category: EvidenceCategory): Promise<void> {
    const evidence = evidenceMap.get(evidenceId)
    if (!evidence) throw new Error(`Evidence ${evidenceId} not found`)
    evidence.category = category
  },

  async deduplicate(sessionId: string): Promise<string[]> {
    const sessionEvidence = Array.from(evidenceMap.values()).filter((e) => e.sessionId === sessionId)
    const removed: string[] = []

    for (let i = 0; i < sessionEvidence.length; i++) {
      if (removed.includes(sessionEvidence[i].id)) continue
      for (let j = i + 1; j < sessionEvidence.length; j++) {
        if (removed.includes(sessionEvidence[j].id)) continue
        if (this.isDuplicate(sessionEvidence[i], sessionEvidence[j])) {
          evidenceMap.get(sessionEvidence[j].id)!.duplicateOf = sessionEvidence[i].id
          removed.push(sessionEvidence[j].id)
        }
      }
    }

    return removed
  },

  isDuplicate(a: Evidence, b: Evidence): boolean {
    const normalize = (s: string) => s.toLowerCase().replace(/\s+/g, " ").trim()
    const aContent = normalize(a.content)
    const bContent = normalize(b.content)

    if (aContent === bContent) return true

    if (a.sourceId === b.sourceId && a.category === b.category) {
      const aWords = new Set(aContent.split(" "))
      const bWords = bContent.split(" ")
      const overlap = bWords.filter((w) => aWords.has(w)).length
      const similarity = overlap / Math.max(bWords.length, 1)
      return similarity > 0.85
    }

    return false
  },

  async scoreConfidence(evidenceId: string): Promise<number> {
    const evidence = evidenceMap.get(evidenceId)
    if (!evidence) throw new Error(`Evidence ${evidenceId} not found`)

    let score = CONFIDENCE_WEIGHTS[evidence.confidence]

    if (evidence.validated) score += 0.1
    if (evidence.relationships.length > 0) score += 0.05 * Math.min(evidence.relationships.length, 3)
    if (evidence.duplicateOf === null) score += 0.05
    if (evidence.content.length > 100) score += 0.05
    if (evidence.content.length > 500) score += 0.05

    score = Math.min(score, 1.0)
    return Math.round(score * 100) / 100
  },

  async addRelationship(
    sourceId: string,
    targetId: string,
    type: EvidenceRelationshipType,
    description: string,
  ): Promise<void> {
    const source = evidenceMap.get(sourceId)
    if (!source) throw new Error(`Source evidence ${sourceId} not found`)
    const target = evidenceMap.get(targetId)
    if (!target) throw new Error(`Target evidence ${targetId} not found`)

    const relationship: EvidenceRelationship = {
      sourceId,
      targetId,
      type,
      description,
      createdAt: new Date().toISOString(),
    }
    source.relationships.push(relationship)
    target.relationships.push({ ...relationship, sourceId: targetId, targetId: sourceId })
  },

  async getEvidenceBySession(sessionId: string): Promise<Evidence[]> {
    return Array.from(evidenceMap.values())
      .filter((e) => e.sessionId === sessionId)
      .sort((a, b) => new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime())
  },

  async getEvidenceByCategory(sessionId: string, category: EvidenceCategory): Promise<Evidence[]> {
    return Array.from(evidenceMap.values())
      .filter((e) => e.sessionId === sessionId && e.category === category)
      .sort((a, b) => new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime())
  },

  async getEvidenceByConfidence(sessionId: string, minScore: number): Promise<Evidence[]> {
    return Array.from(evidenceMap.values())
      .filter((e) => e.sessionId === sessionId && e.confidenceScore >= minScore)
      .sort((a, b) => b.confidenceScore - a.confidenceScore)
  },

  async getValidatedCount(sessionId: string): Promise<number> {
    return Array.from(evidenceMap.values()).filter((e) => e.sessionId === sessionId && e.validated).length
  },

  async countByCategory(sessionId: string): Promise<Record<EvidenceCategory, number>> {
    const counts: Record<string, number> = {}
    for (const e of evidenceMap.values()) {
      if (e.sessionId === sessionId) {
        counts[e.category] = (counts[e.category] ?? 0) + 1
      }
    }
    return counts as Record<EvidenceCategory, number>
  },

  async clearSession(sessionId: string): Promise<void> {
    for (const [id, evidence] of evidenceMap.entries()) {
      if (evidence.sessionId === sessionId) {
        evidenceMap.delete(id)
      }
    }
  },
}
