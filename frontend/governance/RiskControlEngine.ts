import type { RiskAssessment, RiskLevel } from "./types"
import { generateId } from "./shared"

const assessments = new Map<string, RiskAssessment>()

const riskWeights: Record<string, number> = {
  data_exposure: 0.9,
  resource_exhaustion: 0.7,
  privilege_escalation: 0.95,
  policy_violation: 0.6,
  unauthorized_access: 0.85,
  data_corruption: 0.8,
  service_disruption: 0.75,
  compliance_breach: 0.9,
}

export const RiskControlEngine = {
  async assessRisk(sessionId: string, factors: string[], details: Record<string, unknown> = {}): Promise<RiskAssessment> {
    let score = 0
    const matchedFactors: string[] = []

    for (const factor of factors) {
      const weight = riskWeights[factor] ?? 0.3
      score += weight
      matchedFactors.push(factor)
    }

    score = Math.min(score / factors.length, 1)
    const level = RiskControlEngine.classifyRisk(score)

    const assessment: RiskAssessment = {
      id: generateId("risk"),
      sessionId,
      level,
      score,
      factors: matchedFactors,
      mitigations: [],
      assessedAt: new Date().toISOString(),
      details,
    }

    assessments.set(assessment.id, assessment)
    return assessment
  },

  classifyRisk(score: number): RiskLevel {
    if (score >= 0.8) return "critical"
    if (score >= 0.6) return "high"
    if (score >= 0.3) return "medium"
    return "low"
  },

  async classifyRiskLevel(sessionId: string, score: number): Promise<RiskAssessment> {
    const level = RiskControlEngine.classifyRisk(score)
    const assessment: RiskAssessment = {
      id: generateId("risk"),
      sessionId,
      level,
      score,
      factors: [],
      mitigations: [],
      assessedAt: new Date().toISOString(),
      details: {},
    }
    assessments.set(assessment.id, assessment)
    return assessment
  },

  async mitigateRisk(assessmentId: string, mitigation: string): Promise<RiskAssessment> {
    const assessment = assessments.get(assessmentId)
    if (!assessment) throw new Error(`Risk assessment not found: ${assessmentId}`)
    const updated: RiskAssessment = {
      ...assessment,
      mitigations: [...assessment.mitigations, mitigation],
    }
    assessments.set(assessmentId, updated)
    return updated
  },

  async escalateRisk(assessmentId: string, reason: string): Promise<RiskAssessment> {
    const assessment = assessments.get(assessmentId)
    if (!assessment) throw new Error(`Risk assessment not found: ${assessmentId}`)
    const escalatedLevel = assessment.level === "critical" ? "critical" : assessment.level === "high" ? "critical" : assessment.level === "medium" ? "high" : "medium"
    const updated: RiskAssessment = {
      ...assessment,
      level: escalatedLevel,
      score: Math.min(assessment.score + 0.15, 1),
      details: { ...assessment.details, escalationReason: reason },
    }
    assessments.set(assessmentId, updated)
    return updated
  },

  async getAssessment(assessmentId: string): Promise<RiskAssessment | null> {
    return assessments.get(assessmentId) ?? null
  },

  async listAssessments(sessionId?: string): Promise<RiskAssessment[]> {
    let result = Array.from(assessments.values())
    if (sessionId) result = result.filter((a) => a.sessionId === sessionId)
    return result.sort((a, b) => new Date(b.assessedAt).getTime() - new Date(a.assessedAt).getTime())
  },

  async assessmentCount(): Promise<number> {
    return assessments.size
  },
}
