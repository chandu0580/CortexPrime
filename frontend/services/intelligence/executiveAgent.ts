import { api } from "@/services/api"

export interface AgentNotification {
  id: string
  type: "mission_completed" | "mission_blocked" | "approval_required" | "infrastructure_degraded" | "security_alert" | "connector_failure" | "cost_anomaly" | "recommendation"
  severity: "info" | "warning" | "critical"
  title: string
  description: string
  timestamp: string
  action?: string
  actionHref?: string
  read: boolean
}

export interface AgentSuggestion {
  id: string
  type: "next_best_action" | "mission" | "infrastructure" | "security" | "cost" | "approval"
  priority: "critical" | "high" | "medium" | "low"
  title: string
  description: string
  action: string
  actionHref?: string
  confidence: number
}

export interface MissionPreparation {
  id: string
  name: string
  description: string
  requiredWorkers: string[]
  requiredConnectors: string[]
  riskLevel: string
  expectedOutcome: string
  approvalRequired: boolean
  estimatedDuration: string
}

export interface TimelineEntry {
  id: string
  type: "mission" | "decision" | "approval" | "recommendation" | "alert" | "system"
  title: string
  description: string
  timestamp: string
  category: "today" | "yesterday" | "last_week"
}

export interface ConversationContext {
  missions: { id: string; name: string; status: string }[]
  approvals: { id: string; mission: string; status: string }[]
  recommendations: AgentSuggestion[]
  timeline: TimelineEntry[]
  health: Record<string, string>
}

export interface ExecutiveAgentState {
  notifications: AgentNotification[]
  suggestions: AgentSuggestion[]
  missionPreparations: MissionPreparation[]
  timeline: TimelineEntry[]
  conversationContext: ConversationContext | null
  lastMonitoredAt: string | null
  monitoring: boolean
}

export class ExecutiveAgentService {
  private state: ExecutiveAgentState = {
    notifications: [],
    suggestions: [],
    missionPreparations: [],
    timeline: [],
    conversationContext: null,
    lastMonitoredAt: null,
    monitoring: false,
  }

  private monitorInterval: ReturnType<typeof setInterval> | null = null
  private listeners: Array<(state: ExecutiveAgentState) => void> = []
  private idCounter = 0
  private previousSnapshot: Record<string, unknown> = {}

  private nextId(prefix: string) {
    this.idCounter++
    return `${prefix}_${this.idCounter}`
  }

  private ts() {
    return new Date().toISOString()
  }

  subscribe(listener: (state: ExecutiveAgentState) => void) {
    this.listeners.push(listener)
    return () => { this.listeners = this.listeners.filter((l) => l !== listener) }
  }

  private notify() {
    this.listeners.forEach((l) => l({ ...this.state }))
  }

  async startMonitoring() {
    if (this.state.monitoring) return
    this.state.monitoring = true

    // initial load
    await this.monitorCycle()
    this.monitorInterval = setInterval(() => this.monitorCycle(), 15000)
  }

  stopMonitoring() {
    this.state.monitoring = false
    if (this.monitorInterval) {
      clearInterval(this.monitorInterval)
      this.monitorInterval = null
    }
  }

  private async monitorCycle() {
    try {
      const [snapRes, analRes] = await Promise.allSettled([
        api.get<Record<string, unknown>>("/api/executive/snapshot"),
        api.get<Record<string, unknown>>("/api/executive/analytics"),
      ])
      const snap = snapRes.status === "fulfilled" ? snapRes.value : {}
      const anal = analRes.status === "fulfilled" ? analRes.value : {}

      this.analyzeSnapshot(snap, anal)
      this.state.lastMonitoredAt = this.ts()
      this.notify()
    } catch {
      // silent
    }
  }

  private analyzeSnapshot(snap: Record<string, unknown>, anal: Record<string, unknown>) {
    const missions = (snap.missions as Record<string, number>) || {}
    const infra = (snap.infrastructure as Record<string, string>) || {}
    const approvals = (snap.approvalQueue as Record<string, number>) || {}

    // --- Infrastructure degradation ---
    Object.entries(infra).forEach(([name, status]) => {
      if (status !== "connected" && status !== "checking") {
        const key = `infra_${name}` as const
        const exists = this.state.notifications.some((n) => n.id === key)
        if (!exists) {
          this.state.notifications.unshift({
            id: key, type: "infrastructure_degraded", severity: "warning",
            title: `${name.charAt(0).toUpperCase() + name.slice(1)} degraded`,
            description: `Status: ${status}. May affect mission execution.`,
            timestamp: this.ts(), action: "View infrastructure", actionHref: "/executive-platform/observability", read: false,
          })
        }
      }
    })

    // --- Pending approvals ---
    const pendingApprovals = approvals.pending || 0
    if (pendingApprovals > 0) {
      const key = `approvals_${pendingApprovals}` as const
      const exists = this.state.notifications.some((n) => n.id === key)
      if (!exists) {
        this.state.notifications.unshift({
          id: key, type: "approval_required", severity: pendingApprovals > 5 ? "critical" : "warning",
          title: `${pendingApprovals} pending approval(s)`,
          description: "Approvals may be blocking mission execution.",
          timestamp: this.ts(), action: "Review approvals", actionHref: "/executive-platform/approvals", read: false,
        })
      }
    }

    // --- Mission completions ---
    const completed = missions.completed || 0
    const prevCompleted = (this.previousSnapshot.missions as Record<string, number>)?.completed || 0
    if (completed > prevCompleted) {
      this.state.notifications.unshift({
        id: this.nextId("mission_done"), type: "mission_completed", severity: "info",
        title: "Mission completed",
        description: `Total completions: ${completed}`,
        timestamp: this.ts(), read: false,
      })
      this.state.timeline.unshift({
        id: this.nextId("tl"), type: "mission", title: "Mission completed",
        description: `Total completions reached ${completed}`, timestamp: this.ts(), category: "today",
      })
    }

    // --- Failed missions ---
    const failed = missions.failed || 0
    const prevFailed = (this.previousSnapshot.missions as Record<string, number>)?.failed || 0
    if (failed > prevFailed) {
      this.state.notifications.unshift({
        id: this.nextId("mission_fail"), type: "mission_blocked", severity: "critical",
        title: "Mission failed",
        description: `Total failures: ${failed}`,
        timestamp: this.ts(), read: false,
      })
    }

    // --- Recommendations as suggestions ---
    const rawRecs = (snap.recommendations as string[]) || []
    rawRecs.slice(0, 5).forEach((text, i) => {
      const id = `sug_${i}_${Date.now()}`
      const exists = this.state.suggestions.some((s) => s.title === text.slice(0, 60))
      if (!exists) {
        this.state.suggestions.unshift({
          id, type: "mission", priority: text.toLowerCase().includes("critical") ? "critical" : "high",
          title: text.slice(0, 80), description: text, action: text,
          confidence: 0.85,
        })
      }
    })

    // --- Build timeline from snapshot ---
    if (snap.updated_at || snap.lastRefresh) {
      this.state.timeline.unshift({
        id: this.nextId("tl_sys"), type: "system", title: "System snapshot updated",
        description: "Executive intelligence refreshed", timestamp: this.ts(), category: "today",
      })
    }

    // --- Mission preparations ---
    if (this.state.missionPreparations.length === 0) {
      this.state.missionPreparations = [
        {
          id: "prep_software_release", name: "Software Release", description: "Plan and coordinate a production release",
          requiredWorkers: ["browser"], requiredConnectors: ["rabbitmq", "redis", "neo4j"],
          riskLevel: "high", expectedOutcome: "Release plan with rollback", approvalRequired: true,
          estimatedDuration: "~2 minutes",
        },
        {
          id: "prep_incident_response", name: "Incident Response", description: "Respond to a production incident",
          requiredWorkers: ["browser"], requiredConnectors: ["rabbitmq", "redis", "neo4j"],
          riskLevel: "high", expectedOutcome: "Root cause analysis + remediation", approvalRequired: true,
          estimatedDuration: "~3 minutes",
        },
        {
          id: "prep_executive_research", name: "Executive Research", description: "Deep research on a strategic topic",
          requiredWorkers: ["browser"], requiredConnectors: ["redis", "neo4j"],
          riskLevel: "low", expectedOutcome: "Executive briefing with recommendations", approvalRequired: false,
          estimatedDuration: "~1 minute",
        },
      ]
    }

    // --- Build conversation context ---
    this.state.conversationContext = {
      missions: Object.entries(missions).map(([k, v]) => ({ id: k, name: k, status: k === "active" ? "running" : "completed" })),
      approvals: [{ id: "pending", mission: `Approvals (${pendingApprovals})`, status: pendingApprovals > 0 ? "pending" : "none" }],
      recommendations: this.state.suggestions.slice(0, 3),
      timeline: this.state.timeline.slice(0, 5),
      health: infra as Record<string, string>,
    }

    this.previousSnapshot = snap
    this.trimState()
  }

  private trimState() {
    if (this.state.notifications.length > 50) this.state.notifications = this.state.notifications.slice(0, 50)
    if (this.state.suggestions.length > 20) this.state.suggestions = this.state.suggestions.slice(0, 20)
    if (this.state.timeline.length > 100) this.state.timeline = this.state.timeline.slice(0, 100)
  }

  markRead(notificationId: string) {
    const n = this.state.notifications.find((n) => n.id === notificationId)
    if (n) n.read = true
    this.notify()
  }

  dismissNotification(notificationId: string) {
    this.state.notifications = this.state.notifications.filter((n) => n.id !== notificationId)
    this.notify()
  }

  dismissSuggestion(suggestionId: string) {
    this.state.suggestions = this.state.suggestions.filter((s) => s.id !== suggestionId)
    this.notify()
  }

  getNotifications() { return this.state.notifications }
  getSuggestions() { return this.state.suggestions }
  getTimeline() { return this.state.timeline }
  getMissionPreparations() { return this.state.missionPreparations }
  getConversationContext() { return this.state.conversationContext }
  getState() { return { ...this.state } }
}

export const executiveAgent = new ExecutiveAgentService()