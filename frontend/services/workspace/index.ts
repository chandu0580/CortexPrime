import { runtimeService } from "@/services/runtime"
import { api } from "@/services/api"
import { fetchDashboardHealth } from "@/services/dashboard/health"
import { fetchDashboardOverview } from "@/services/dashboard/overview"

export interface WorkspaceExecutiveData {
  activeMissions: number
  completedMissions: number
  failedMissions: number
  totalMissions: number
  activeAgents: number
  queueDepth: number
  safetyScore: number
  systemStatus: string
  autonomyScore: number
  currentMission: {
    goal: string
    stage: string
    progress: number
    activeAgent: string | null
    elapsedSecs: number
    health: string
  } | null
  healthMatrix: { label: string; status: string; score: number }[]
  agents: { id: string; status: string; lastAction: string }[]
  timestamp: string
}

export interface WorkspaceMissionData {
  activeMissions: { execution_id: string; goal: string; status: string; startedAt: string | null; assignedAgent?: string }[]
  completedMissions: { execution_id: string; goal: string; status: string; startedAt: string | null; completedAt: string | null }[]
  missionCount: number
  completedCount: number
  failedCount: number
}

export interface WorkspacePortfolioData {
  activeMissions: number
  completedMissions: number
  failedMissions: number
  activeAgents: number
  totalCompleted: number
  totalFailed: number
  successRate: number
  queueDepth: number
}

export interface WorkspaceIntelligenceData {
  recentMissions: { execution_id: string; goal: string; status: string }[]
  activeCount: number
  totalCount: number
  successRate: number
}

function safeParseInt(val: unknown): number {
  if (typeof val === "number") return val
  if (typeof val === "string") {
    const n = Number(val)
    return Number.isFinite(n) ? n : 0
  }
  return 0
}

export async function fetchWorkspaceExecutive(): Promise<WorkspaceExecutiveData> {
  const [snapshotRes, telemetry, health] = await Promise.allSettled([
    api.get<Record<string, unknown>>("/api/executive/snapshot"),
    api.get<Record<string, unknown>>("/api/telemetry/runtime"),
    fetchDashboardHealth(),
  ])

  const snapshot = snapshotRes.status === "fulfilled" ? snapshotRes.value : null
  const runtime = telemetry.status === "fulfilled" ? telemetry.value : null
  const dashHealth = health.status === "fulfilled" ? health.value : null

  const currentMissionRaw = snapshot?.current_mission as Record<string, unknown> | null | undefined

  return {
    activeMissions: safeParseInt(snapshot?.active_missions ?? runtime?.active_executions ?? 0),
    completedMissions: safeParseInt(runtime?.total_completed ?? 0),
    failedMissions: safeParseInt(runtime?.total_failed ?? 0),
    totalMissions: safeParseInt(snapshot?.active_missions ?? 0) + safeParseInt(runtime?.total_completed ?? 0) + safeParseInt(runtime?.total_failed ?? 0),
    activeAgents: safeParseInt(snapshot?.active_agents ?? runtime?.active_agents ?? 0),
    queueDepth: safeParseInt(runtime?.queue_depth ?? 0),
    safetyScore: safeParseInt(snapshot?.safety_score),
    systemStatus: String(snapshot?.system_status ?? runtime?.status ?? "unknown"),
    autonomyScore: safeParseInt((snapshot?.autonomy_overall as number | undefined) ?? 0),
    currentMission: currentMissionRaw
      ? {
          goal: String(currentMissionRaw.goal ?? ""),
          stage: String(currentMissionRaw.stage ?? "idle"),
          progress: safeParseInt(currentMissionRaw.progress),
          activeAgent: currentMissionRaw.active_agent ? String(currentMissionRaw.active_agent) : null,
          elapsedSecs: safeParseInt(currentMissionRaw.elapsed_secs),
          health: String(currentMissionRaw.health ?? "unknown"),
        }
      : null,
    healthMatrix: Array.isArray(snapshot?.health_matrix)
      ? (snapshot!.health_matrix as { label: string; status: string; score: number }[])
      : dashHealth?.services?.map((s) => ({ label: s.label, status: s.status, score: s.status === "healthy" ? 100 : 50 })) ?? [],
    agents: Array.isArray(snapshot?.agents)
      ? (snapshot!.agents as { id: string; status: string; lastAction: string }[])
      : [],
    timestamp: String(snapshot?.timestamp ?? new Date().toISOString()),
  }
}

export async function fetchWorkspaceMission(): Promise<WorkspaceMissionData> {
  const [activeRes, completedRes] = await Promise.allSettled([
    runtimeService.getActiveMissions(),
    runtimeService.getCompletedMissions(),
  ])

  const activeBody = activeRes.status === "fulfilled" ? (activeRes.value as Record<string, unknown>) : null
  const completedBody = completedRes.status === "fulfilled" ? (completedRes.value as Record<string, unknown>) : null

  const activeMissions: WorkspaceMissionData["activeMissions"] = []
  const completedMissions: WorkspaceMissionData["completedMissions"] = []
  let missionCount = 0
  let completedCount = 0
  let failedCount = 0

  const activeEntries = activeBody?.active_missions as Record<string, unknown> | undefined
  if (activeEntries && typeof activeEntries === "object" && !Array.isArray(activeEntries)) {
    for (const [execId, entry] of Object.entries(activeEntries)) {
      if (!entry || typeof entry !== "object") continue
      const e = entry as Record<string, unknown>
      activeMissions.push({
        execution_id: execId,
        goal: String(e.goal ?? execId),
        status: String(e.status ?? "running"),
        startedAt: typeof e.started_at === "string" ? e.started_at : null,
        assignedAgent: Array.isArray(e.agentsInvolved) && (e.agentsInvolved as string[]).length > 0
          ? (e.agentsInvolved as string[])[0]
          : undefined,
      })
    }
    missionCount = activeMissions.length
  }

  const completedList = completedBody?.completed_missions as Record<string, unknown>[] | undefined
  if (Array.isArray(completedList)) {
    for (const entry of completedList) {
      const execId = String(entry.execution_id ?? entry.id ?? `completed-${Math.random().toString(36).slice(2, 8)}`)
      const status = String(entry.status ?? "completed")
      completedMissions.push({
        execution_id: execId,
        goal: String(entry.goal ?? execId),
        status,
        startedAt: typeof entry.started_at === "string" ? entry.started_at : null,
        completedAt: typeof entry.completed_at === "string" ? entry.completed_at : null,
      })
      if (status === "completed") completedCount++
      else if (status === "failed") failedCount++
    }
  }

  return { activeMissions, completedMissions, missionCount, completedCount, failedCount }
}

export async function fetchWorkspacePortfolio(): Promise<WorkspacePortfolioData> {
  const telemetry = await api.get<Record<string, unknown>>("/api/telemetry/runtime").catch(() => null)
  const tc = safeParseInt(telemetry?.total_completed ?? 0)
  const tf = safeParseInt(telemetry?.total_failed ?? 0)

  return {
    activeMissions: safeParseInt(telemetry?.active_executions ?? 0),
    completedMissions: tc,
    failedMissions: tf,
    activeAgents: safeParseInt(telemetry?.active_agents ?? 0),
    totalCompleted: tc,
    totalFailed: tf,
    successRate: tc + tf > 0 ? Math.round((tc / (tc + tf)) * 100) : 100,
    queueDepth: safeParseInt(telemetry?.queue_depth ?? 0),
  }
}

export async function fetchWorkspaceIntelligence(): Promise<WorkspaceIntelligenceData> {
  const [activeRes, completedRes] = await Promise.allSettled([
    runtimeService.getActiveMissions(),
    runtimeService.getCompletedMissions(),
  ])

  const recentMissions: { execution_id: string; goal: string; status: string }[] = []
  let activeCount = 0
  let totalCount = 0
  let successCount = 0

  const activeBody = activeRes.status === "fulfilled" ? (activeRes.value as Record<string, unknown>) : null
  const activeEntries = activeBody?.active_missions as Record<string, unknown> | undefined
  if (activeEntries && typeof activeEntries === "object" && !Array.isArray(activeEntries)) {
    for (const [execId, entry] of Object.entries(activeEntries)) {
      if (!entry || typeof entry !== "object") continue
      const e = entry as Record<string, unknown>
      recentMissions.push({
        execution_id: execId,
        goal: String(e.goal ?? execId),
        status: String(e.status ?? "running"),
      })
    }
    activeCount = recentMissions.length
    totalCount = recentMissions.length
  }

  const completedBody = completedRes.status === "fulfilled" ? (completedRes.value as Record<string, unknown>) : null
  const completedList = completedBody?.completed_missions as Record<string, unknown>[] | undefined
  if (Array.isArray(completedList)) {
    for (const entry of completedList) {
      recentMissions.push({
        execution_id: String(entry.execution_id ?? entry.id ?? ""),
        goal: String(entry.goal ?? ""),
        status: String(entry.status ?? "completed"),
      })
      if (String(entry.status ?? "completed") === "completed") successCount++
    }
    totalCount += completedList.length
  }

  recentMissions.sort((a, b) => a.execution_id.localeCompare(b.execution_id)).reverse()

  return {
    recentMissions: recentMissions.slice(0, 10),
    activeCount,
    totalCount,
    successRate: totalCount > 0 ? Math.round((successCount / totalCount) * 100) : 100,
  }
}
