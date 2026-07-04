import type { PlanningPortfolio, PortfolioConflict, MissionPlan, PlanningPriority } from "./types"
import { generateId } from "@/worker-framework/shared"
import { MissionPlanner } from "./MissionPlanner"

const portfolios = new Map<string, PlanningPortfolio>()

export const PortfolioPlanner = {
  async groupRelatedMissions(name: string, description: string, missionIds: string[]): Promise<PlanningPortfolio> {
    const plans: MissionPlan[] = []
    for (const mid of missionIds) {
      const sessionPlans = await MissionPlanner.getAllPlans()
      const found = sessionPlans.find((p) => p.missionId === mid)
      if (found) plans.push(found)
    }

    const totalEffortMs = plans.reduce((sum, p) => sum + p.estimatedDurationMs, 0)

    const portfolio: PlanningPortfolio = {
      id: generateId("plan-portfolio"),
      name,
      description,
      missionIds,
      plans,
      totalEffortMs,
      priority: "medium",
      conflicts: [],
      optimized: false,
      createdAt: new Date().toISOString(),
    }
    portfolios.set(portfolio.id, portfolio)
    return portfolio
  },

  async getPortfolio(portfolioId: string): Promise<PlanningPortfolio | null> {
    return portfolios.get(portfolioId) ?? null
  },

  async getAllPortfolios(): Promise<PlanningPortfolio[]> {
    return Array.from(portfolios.values())
  },

  async optimizePortfolio(portfolioId: string): Promise<PlanningPortfolio> {
    const portfolio = await this.getPortfolio(portfolioId)
    if (!portfolio) throw new Error(`Portfolio ${portfolioId} not found`)

    portfolio.plans.sort((a, b) => {
      const order: Record<PlanningPriority, number> = { critical: 5, high: 4, medium: 3, low: 2, backlog: 1 }
      return (order[b.priority] ?? 0) - (order[a.priority] ?? 0)
    })

    portfolio.totalEffortMs = portfolio.plans.reduce((sum, p) => sum + p.estimatedDurationMs, 0)
    portfolio.optimized = true
    return portfolio
  },

  async balancePortfolio(portfolioId: string): Promise<PlanningPortfolio> {
    const portfolio = await this.getPortfolio(portfolioId)
    if (!portfolio) throw new Error(`Portfolio ${portfolioId} not found`)

    const counts: Record<string, number> = {}
    for (const plan of portfolio.plans) {
      const key = plan.priority
      counts[key] = (counts[key] ?? 0) + 1
    }

    const total = portfolio.plans.length
    const criticalPct = ((counts.critical ?? 0) / Math.max(total, 1)) * 100

    if (criticalPct > 50) {
      portfolio.conflicts.push({
        id: generateId("portfolio-conflict"),
        type: "priority",
        description: `Critical missions exceed 50% of portfolio (${Math.round(criticalPct)}%)`,
        sourceMissionId: portfolio.missionIds[0] ?? "",
        targetMissionId: portfolio.missionIds[portfolio.missionIds.length - 1] ?? "",
        severity: "high",
      })
    }

    return portfolio
  },

  async detectPortfolioConflicts(portfolioId: string): Promise<PortfolioConflict[]> {
    const portfolio = await this.getPortfolio(portfolioId)
    if (!portfolio) throw new Error(`Portfolio ${portfolioId} not found`)

    const conflicts: PortfolioConflict[] = []
    const resourceMap = new Map<string, string[]>()

    for (const plan of portfolio.plans) {
      for (const phase of plan.phases) {
        for (const task of phase.tasks) {
          for (const cap of task.requiredCapabilities) {
            if (!resourceMap.has(cap)) resourceMap.set(cap, [])
            resourceMap.get(cap)!.push(plan.missionId)
          }
        }
      }
    }

    for (const [cap, missions] of resourceMap) {
      if (missions.length > 1) {
        const uniqueMissions = [...new Set(missions)]
        if (uniqueMissions.length > 1) {
          conflicts.push({
            id: generateId("portfolio-conflict"),
            type: "resource",
            description: `Resource conflict for capability '${cap}' across ${uniqueMissions.length} missions`,
            sourceMissionId: uniqueMissions[0],
            targetMissionId: uniqueMissions[uniqueMissions.length - 1],
            severity: "medium",
          })
        }
      }
    }

    portfolio.conflicts = conflicts
    return conflicts
  },

  async count(): Promise<number> {
    return portfolios.size
  },
}
