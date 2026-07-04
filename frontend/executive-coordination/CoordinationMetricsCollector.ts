import type { CoordinationMetrics } from "./types"
import { CoordinationSessionManager } from "./CoordinationSessionManager"
import { CoordinationPlanner } from "./CoordinationPlanner"
import { DelegationEngine } from "./DelegationEngine"
import { SynchronizationEngine } from "./SynchronizationEngine"
import { CoordinationDecisionEngine } from "./CoordinationDecisionEngine"
import { WorkerSelectionEngine } from "./WorkerSelectionEngine"

export const CoordinationMetricsCollector = {
  async collectAll(): Promise<CoordinationMetrics> {
    const sessions = await CoordinationSessionManager.listSessions()
    const plans = await CoordinationPlanner.listPlans()
    const delegations = await DelegationEngine.listDelegations()
    const barriers = await SynchronizationEngine.listBarriers()
    const conflicts = await CoordinationDecisionEngine.getConflicts()
    const selections = await WorkerSelectionEngine.getSelections()
    const decisions = await CoordinationDecisionEngine.listDecisions()

    return {
      totalSessions: sessions.length,
      activeSessions: sessions.filter((s) => s.state === "active").length,
      totalPlans: plans.length,
      totalDelegations: delegations.length,
      totalSynchronizations: barriers.length,
      totalConflicts: conflicts.length,
      totalWorkerSelections: selections.length,
      totalDecisions: decisions.length,
    }
  },

  async collectSessions(): Promise<{ total: number; active: number }> {
    const sessions = await CoordinationSessionManager.listSessions()
    return { total: sessions.length, active: sessions.filter((s) => s.state === "active").length }
  },

  async collectPlans(): Promise<number> {
    const plans = await CoordinationPlanner.listPlans()
    return plans.length
  },

  async collectDelegations(): Promise<number> {
    const delegations = await DelegationEngine.listDelegations()
    return delegations.length
  },

  async collectConflicts(): Promise<number> {
    const conflicts = await CoordinationDecisionEngine.getConflicts()
    return conflicts.length
  },
}
