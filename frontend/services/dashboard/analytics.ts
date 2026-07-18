export interface AnalyticsDashboardResponse {
  kpiCards: KPICardDTO[]
  performanceSeries: PerformancePointDTO[]
  topAgents: AgentActivityDTO[]
  actionTypes: ActionTypeDTO[]
  successRateOverTime: SuccessRatePointDTO[]
  keyInsights: InsightDTO[]
  activityHeatmap: number[][]
  heatmapHours: string[]
  summary: SummaryItemDTO[]
  mission: MissionAnalyticsDTO
  connector: ConnectorAnalyticsDTO
  agent: AgentAnalyticsDTO
  workflow: WorkflowAnalyticsDTO
  executive: ExecutiveAnalyticsDTO
  cost: CostAnalyticsDTO
  infrastructure: InfrastructureAnalyticsDTO
  governance: GovernanceAnalyticsDTO
}

export interface KPICardDTO {
  title: string
  value: string
  change: string
  isPositive: boolean
  vsText: string
  sparkline: number[]
  color: string
  icon: string
}

export interface PerformancePointDTO {
  date: string
  sessions: number
  actions: number
  successRate: number
}

export interface AgentActivityDTO {
  name: string
  actions: number
  change: string
  isPositive: boolean
  color: string
}

export interface ActionTypeDTO {
  type: string
  actions: number
  percentage: number
  color: string
}

export interface SuccessRatePointDTO {
  date: string
  rate: number
}

export interface InsightDTO {
  type: string
  title: string
  text: string
}

export interface SummaryItemDTO {
  label: string
  value: string
  change: string | null
  isPositive: boolean
}

export interface MissionAnalyticsDTO {
  activeExecutions: number
  completedExecutions: number
  failedExecutions: number
  totalExecutions: number
  successRate: number
  averageLatencyMs: number
  dailySeries: { date: string; missions: number; agent_events: number }[]
}

export interface ConnectorAnalyticsDTO {
  totalOperations: number
  byConnector: { name: string; count: number }[]
  activeConnectors: number
}

export interface AgentAnalyticsDTO {
  totalAgents: number
  activeAgents: number
  topAgents: AgentActivityDTO[]
  agentNames: string[]
}

export interface WorkflowAnalyticsDTO {
  pendingApprovals: number
  activeWorkflows: number
  completedWorkflows: number
  blockRate: number
}

export interface ExecutiveAnalyticsDTO {
  dailyTrend: { date: string; missions: number }[]
  totals: Record<string, number>
  confidenceScore: number
  hallucinationScore: number
}

export interface CostAnalyticsDTO {
  todaySpend: number
  monthSpend: number
  topMissions: { mission_id: string; cost: number }[]
  byProvider: { provider: string; total_cost: number }[]
  dailyTrend: { date: string; total_cost: number }[]
}

export interface InfrastructureAnalyticsDTO {
  activeExecutions: number
  activeAgents: number
  totalAgents: number
  uptimeHours: string
  totalTokens: number
  averageLatencyMs: number
  eventsLastHour: number
}

export interface GovernanceAnalyticsDTO {
  pendingApprovals: number
  blockedActions: number
  approvedActions: number
  totalEvents: number
  complianceRate: number
  blockRate: number
}

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

export async function fetchAnalyticsDashboard(): Promise<AnalyticsDashboardResponse> {
  const res = await fetch(`${BASE}/api/analytics/dashboard`, { credentials: "include" })
  if (!res.ok) {
    throw new Error(`Analytics dashboard fetch failed: ${res.status} ${res.statusText}`)
  }
  return res.json()
}
