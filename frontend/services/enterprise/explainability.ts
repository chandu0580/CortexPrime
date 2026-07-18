import axios from "axios"
import { apiUrl } from "@/lib/constants"

export interface ExplainableMission {
  execution_id: string
  template_name: string
  objective: string
  status: string
  started_at: string
  completed_at: string
  has_explainability: boolean
}

export interface MissionSummary {
  mission_objective: string
  template_name: string
  status: string
  started_at: string
  completed_at: string
  total_steps: number
  total_decisions: number
  total_recoveries: number
  total_approvals: number
  total_artifacts: number
  total_outcomes: number
  overall_confidence: number
  risk_level: string
}

export interface TimelineEntry {
  type: string
  source: string
  timestamp: string
  event_type: string
  agent: string
  status: string
  message: string
  phase: string
}

export interface ReasoningStep {
  step: number
  event_type: string
  decision: string
  agent: string
  timestamp: string
  rationale: string
}

export interface EvidenceItem {
  source: string
  event_type: string
  content: string
  url?: string
  timestamp: string
}

export interface Alternative {
  type: string
  count: number
  description: string
  status: string
}

export interface PolicyEvaluation {
  policy: string
  risk_level: string
  outcome: string
  reason: string
  timestamp: string
}

export interface VerificationResult {
  verified: boolean
  method: string
  evidence_data: string
  timestamp: string
}

export interface ConfidenceAnalysis {
  overall: number
  components: Record<string, number>
  weights: Record<string, number>
  base_score: number
}

export interface ConnectorCall {
  connector: string
  operation: string
  status: string
  description: string
  timestamp: string
}

export interface LearningContext {
  lessons_applied: { content: string; confidence: number }[]
  patterns_available: { signature: string; count: number }[]
  recovery_strategies: { type: string; count: number }[]
}

export interface MissionExplanation {
  execution_id: string
  summary: MissionSummary
  timeline: TimelineEntry[]
  reasoning: ReasoningStep[]
  evidence: EvidenceItem[]
  alternatives: { total_alternatives: number; alternatives: Alternative[]; note: string }
  policies: { total_evaluated: number; policies: PolicyEvaluation[] }
  verification: { total_checks: number; passed: number; failed: number; results: VerificationResult[] }
  confidence: ConfidenceAnalysis
  connector_calls: ConnectorCall[]
  learning_context: LearningContext
  sources: Record<string, number>
  generated_at: string
}

export interface ExplainabilityDashboard {
  total_missions: number
  completed_missions: number
  failed_missions: number
  running_missions: number
  avg_events_per_mission: number
  explainable_missions: number
  generated_at: string
}

export const enterpriseExplainabilityApi = {
  listMissions: async (limit = 50): Promise<{ missions: ExplainableMission[]; total: number }> => {
    const res = await axios.get(`${apiUrl}/api/explainability/missions`, { params: { limit } })
    return res.data
  },

  getMissionExplanation: async (executionId: string): Promise<MissionExplanation> => {
    const res = await axios.get(`${apiUrl}/api/explainability/missions/${executionId}`)
    return res.data
  },

  getTimeline: async (executionId: string): Promise<{ execution_id: string; timeline: TimelineEntry[]; total_entries: number }> => {
    const res = await axios.get(`${apiUrl}/api/explainability/missions/${executionId}/timeline`)
    return res.data
  },

  getReasoning: async (executionId: string): Promise<{ execution_id: string; reasoning: ReasoningStep[] }> => {
    const res = await axios.get(`${apiUrl}/api/explainability/missions/${executionId}/reasoning`)
    return res.data
  },

  getEvidence: async (executionId: string): Promise<{ execution_id: string; evidence: EvidenceItem[] }> => {
    const res = await axios.get(`${apiUrl}/api/explainability/missions/${executionId}/evidence`)
    return res.data
  },

  getAlternatives: async (executionId: string): Promise<{ execution_id: string; alternatives: { alternatives: Alternative[] } }> => {
    const res = await axios.get(`${apiUrl}/api/explainability/missions/${executionId}/alternatives`)
    return res.data
  },

  getPolicies: async (executionId: string): Promise<{ execution_id: string; policies: { policies: PolicyEvaluation[] } }> => {
    const res = await axios.get(`${apiUrl}/api/explainability/missions/${executionId}/policies`)
    return res.data
  },

  getVerification: async (executionId: string): Promise<{ execution_id: string; verification: { results: VerificationResult[] } }> => {
    const res = await axios.get(`${apiUrl}/api/explainability/missions/${executionId}/verification`)
    return res.data
  },

  getConfidence: async (executionId: string): Promise<{ execution_id: string; confidence: ConfidenceAnalysis }> => {
    const res = await axios.get(`${apiUrl}/api/explainability/missions/${executionId}/confidence`)
    return res.data
  },

  getDashboard: async (): Promise<ExplainabilityDashboard> => {
    const res = await axios.get(`${apiUrl}/api/explainability/dashboard`)
    return res.data
  },
}
