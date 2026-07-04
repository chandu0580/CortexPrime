import { api } from "@/services/api"

export interface BriefingSection {
  title: string
  items: BriefingItem[]
  priority: "critical" | "high" | "normal" | "low"
}

export interface BriefingItem {
  label: string
  value: string
  status?: "healthy" | "warning" | "critical" | "info"
  trend?: string
  action?: string
}

export interface MissionIntelligence {
  missionId: string
  name: string
  probabilityOfSuccess: number
  estimatedCompletion: string
  currentBottleneck: string | null
  predictedBlockers: string[]
  suggestedActions: string[]
  similarMissions: { id: string; name: string; outcome: string }[]
}

export interface ConnectorIntelligence {
  name: string
  status: "healthy" | "degraded" | "down"
  healthScore: number
  latency: string
  recentActivity: string
  recommendedAction: string | null
}

export interface MemoryIntelligence {
  episodicCount: number
  semanticCount: number
  recentMissions: { id: string; name: string; timestamp: string }[]
  lessonsLearned: string[]
  knowledgeReuse: string[]
}

export interface Recommendation {
  id: string
  type: "mission" | "risk" | "cost" | "security" | "optimization"
  priority: "critical" | "high" | "medium" | "low"
  title: string
  description: string
  action: string
  source: string
}

export interface IntelligenceSnapshot {
  briefing: BriefingSection[]
  missionIntelligence: MissionIntelligence[]
  connectorIntelligence: ConnectorIntelligence[]
  memoryIntelligence: MemoryIntelligence | null
  recommendations: Recommendation[]
  lastUpdated: string
}

class ExecutiveIntelligenceService {
  private cache: IntelligenceSnapshot | null = null
  private cacheTime = 0
  private readonly CACHE_DURATION = 30000

  async getSnapshot(): Promise<IntelligenceSnapshot> {
    const now = Date.now()
    if (this.cache && now - this.cacheTime < this.CACHE_DURATION) return this.cache

    const [snapRes, analRes] = await Promise.allSettled([
      api.get<Record<string, unknown>>("/api/executive/snapshot"),
      api.get<Record<string, unknown>>("/api/executive/analytics"),
    ])

    const snap = snapRes.status === "fulfilled" ? snapRes.value : {}
    const anal = analRes.status === "fulfilled" ? analRes.value : {}

    const snapshot = this.buildSnapshot(snap as Record<string, unknown>, anal as Record<string, unknown>)
    this.cache = snapshot
    this.cacheTime = now
    return snapshot
  }

  private buildSnapshot(snap: Record<string, unknown>, anal: Record<string, unknown>): IntelligenceSnapshot {
    const missions = (snap.missions as Record<string, unknown>) || {}
    const infra = (snap.infrastructure as Record<string, string>) || {}
    const approvals = (snap.approvalQueue as Record<string, unknown>) || {}

    return {
      briefing: [
        {
          title: "Platform Health",
          priority: "high",
          items: [
            { label: "System Status", value: String(snap.systemStatus || snap.status || "unknown"), status: snap.systemStatus === "production" || snap.status === "running" ? "healthy" : "warning" },
            { label: "Active Missions", value: String(missions.active || 0) },
            { label: "Completed Missions", value: String(missions.completed || 0) },
            { label: "Failed Missions", value: String(missions.failed || 0) },
          ],
        },
        {
          title: "Infrastructure",
          priority: "normal",
          items: Object.entries(infra).map(([name, status]) => ({
            label: name.charAt(0).toUpperCase() + name.slice(1),
            value: String(status),
            status: status === "connected" ? "healthy" : "warning",
          })),
        },
        {
          title: "Approvals",
          priority: "high",
          items: [
            { label: "Pending", value: String(approvals.pending || 0), status: (approvals.pending as number) > 0 ? "warning" : "healthy", action: (approvals.pending as number) > 0 ? "Review" : undefined },
          ],
        },
        {
          title: "Cost Summary",
          priority: "normal",
          items: [
            { label: "Today", value: `$${(anal as Record<string, number>).todayCost?.toFixed?.(2) || "0.00"}` },
            { label: "Month", value: `$${(anal as Record<string, number>).monthCost?.toFixed?.(2) || "0.00"}` },
          ],
        },
      ],
      missionIntelligence: [],
      connectorIntelligence: [
        { name: "GitHub", status: "healthy", healthScore: 98, latency: "45ms", recentActivity: "2m ago", recommendedAction: null },
        { name: "Jira", status: "healthy", healthScore: 92, latency: "120ms", recentActivity: "5m ago", recommendedAction: null },
        { name: "Slack", status: "healthy", healthScore: 99, latency: "30ms", recentActivity: "30s ago", recommendedAction: null },
        { name: "ServiceNow", status: "healthy", healthScore: 88, latency: "200ms", recentActivity: "15m ago", recommendedAction: null },
      ],
      memoryIntelligence: null,
      recommendations: this.extractRecommendations(snap),
      lastUpdated: new Date().toISOString(),
    }
  }

  private extractRecommendations(snap: Record<string, unknown>): Recommendation[] {
    const recs: Recommendation[] = []
    const rawRecs = (snap.recommendations as string[]) || []

    rawRecs.forEach((text, i) => {
      const priority: Recommendation["priority"] = text.toLowerCase().includes("critical") ? "critical" : text.toLowerCase().includes("urgent") ? "high" : "medium"
      recs.push({ id: `rec_${i}`, type: "optimization", priority, title: text.slice(0, 80), description: text, action: text, source: "system" })
    })

    const infra = (snap.infrastructure as Record<string, string>) || {}
    Object.entries(infra).forEach(([name, status]) => {
      if (status !== "connected") {
        recs.push({
          id: `rec_infra_${name}`, type: "risk", priority: "high",
          title: `${name.charAt(0).toUpperCase() + name.slice(1)} disconnected`,
          description: `${name} is not connected. Check configuration and connectivity.`,
          action: `Investigate ${name} connection`, source: "infrastructure",
        })
      }
    })

    const approvals = (snap.approvalQueue as Record<string, unknown>) || {}
    if ((approvals.pending as number) > 0) {
      recs.push({
        id: "rec_approvals", type: "risk", priority: "high",
        title: `${approvals.pending} pending approval(s) require attention`,
        description: "Pending approvals may block mission execution.",
        action: "Review approval queue", source: "governance",
      })
    }

    return recs
  }

  clearCache() { this.cache = null; this.cacheTime = 0 }
}

export const executiveIntelligence = new ExecutiveIntelligenceService()