export interface ExecutiveDashboardResponse {
  reasoning: {
    sessions: ReasoningSessionDTO[]
    activeSessionId: string | null
    isReasoning: boolean
    error: string | null
  }
  simulation: {
    simulations: SimulationResultDTO[]
    activeSimulationId: string | null
    isSimulating: boolean
    error: string | null
  }
  adaptiveExecution: {
    missionId: string | null
    activeRecoveries: AdaptiveRecoveryDTO[]
    completedRecoveries: AdaptiveRecoveryDTO[]
    failedRecoveries: AdaptiveRecoveryDTO[]
    adaptiveMode: boolean
    healthScore: number
    isHealing: boolean
  }
  observation: {
    categories: ObservationCategoryDTO[]
    metrics: ObservationMetricDTO[]
    alerts: ObservationAlertDTO[]
    isObserving: boolean
    lastUpdate: string | null
  }
  decisionMemory: {
    decisions: DecisionRecordDTO[]
    isLoading: boolean
    error: string | null
  }
  runtimeMetrics: {
    activeExecutions: number
    completedExecutions: number
    failedExecutions: number
    activeAgents: number
    totalTokens: number
    avgLatency: number
    confidenceScore: number
    healthScore: number
  }
}

export interface ReasoningSessionDTO {
  id: string
  missionId: string
  goal: string
  context: string
  constraints: string[]
  dependencies: string[]
  assumptions: string[]
  expectedOutcome: string
  strategies: { name: string; description: string; confidence: number; risk: string }[]
  overallConfidence: number
  riskLevel: string
  recommendation: string
  steps: ReasoningStepDTO[]
  status: string
  startedAt: string | null
  completedAt: string | null
}

export interface ReasoningStepDTO {
  id: string
  type: string
  title: string
  description: string
  status: string
  confidence?: number
}

export interface SimulationResultDTO {
  id: string
  missionId: string
  type: string
  status: string
  scenarios: SimulationScenarioDTO[]
  startedAt: string | null
  completedAt: string | null
}

export interface SimulationScenarioDTO {
  id: string
  name: string
  description: string
  predictedOutcome: string
  confidence: number
  metrics: { label: string; value: string | number }[]
  risks: { description: string; severity: string }[]
  recommendation: string
}

export interface AdaptiveRecoveryDTO {
  id: string
  missionId: string
  stepId: string
  failureType: string
  failureMessage: string
  attemptCount: number
  maxAttempts: number
  strategy: string
  status: string
  startedAt: string | null
}

export interface ObservationCategoryDTO {
  id: string
  label: string
  metrics: ObservationMetricDTO[]
  alerts: ObservationAlertDTO[]
}

export interface ObservationMetricDTO {
  label: string
  value: string | number
  status: string
  trend: string
  timestamp: string
}

export interface ObservationAlertDTO {
  id: string
  severity: string
  source: string
  message: string
  timestamp: string
  acknowledged: boolean
}

export interface DecisionRecordDTO {
  id: string
  missionId: string
  decision: string
  rationale: string
  alternatives: { description: string; pros: string[]; cons: string[] }[]
  outcome: string
  confidence: number
  riskLevel: string
  timestamp: string
  metrics?: Record<string, number>
}

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

export async function fetchExecutiveDashboard(): Promise<ExecutiveDashboardResponse> {
  const res = await fetch(`${BASE}/api/executive/dashboard`, { credentials: "include" })
  if (!res.ok) {
    throw new Error(`Executive dashboard fetch failed: ${res.status} ${res.statusText}`)
  }
  return res.json()
}
