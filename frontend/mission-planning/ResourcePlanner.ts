import type { PlanningResource, PlanningConstraint } from "./types"
import { generateId } from "@/worker-framework/shared"

const resources = new Map<string, PlanningResource>()
const constraints = new Map<string, PlanningConstraint>()

export const ResourcePlanner = {
  async estimateResources(sessionId: string, workerTypes: { type: string; required: number; available: number }[]): Promise<PlanningResource[]> {
    const estimated: PlanningResource[] = workerTypes.map((wt) => {
      const resource: PlanningResource = {
        id: generateId("plan-resource"),
        sessionId,
        workerType: wt.type,
        requiredCount: wt.required,
        availableCount: wt.available,
        estimatedLoad: wt.required > 0 ? Math.round((wt.required / Math.max(wt.available, 1)) * 100) : 0,
        reserved: false,
        estimatedAt: new Date().toISOString(),
      }
      resources.set(resource.id, resource)
      return resource
    })
    return estimated
  },

  async getResource(resourceId: string): Promise<PlanningResource | null> {
    return resources.get(resourceId) ?? null
  },

  async getResourcesBySession(sessionId: string): Promise<PlanningResource[]> {
    return Array.from(resources.values()).filter((r) => r.sessionId === sessionId)
  },

  async reserveResources(sessionId: string): Promise<PlanningResource[]> {
    const sessionResources = await this.getResourcesBySession(sessionId)
    for (const r of sessionResources) {
      r.reserved = true
    }
    return sessionResources
  },

  async optimizeResourceUsage(sessionId: string): Promise<{ optimized: PlanningResource[]; constraints: PlanningConstraint[] }> {
    const sessionResources = await this.getResourcesBySession(sessionId)
    const newConstraints: PlanningConstraint[] = []

    for (const r of sessionResources) {
      if (r.estimatedLoad > 100) {
        r.requiredCount = r.availableCount
        r.estimatedLoad = 100
        const constraint: PlanningConstraint = {
          id: generateId("plan-constraint"),
          sessionId,
          type: "resource",
          description: `Resource shortage for ${r.workerType}: required ${r.requiredCount}, available ${r.availableCount}`,
          severity: "blocking",
          active: true,
        }
        constraints.set(constraint.id, constraint)
        newConstraints.push(constraint)
      }
      if (r.estimatedLoad > 80) {
        const constraint: PlanningConstraint = {
          id: generateId("plan-constraint"),
          sessionId,
          type: "capacity",
          description: `High load for ${r.workerType}: ${r.estimatedLoad}%`,
          severity: "warning",
          active: true,
        }
        constraints.set(constraint.id, constraint)
        newConstraints.push(constraint)
      }
    }

    return { optimized: sessionResources, constraints: newConstraints }
  },

  async validateCapacity(sessionId: string): Promise<{ sufficient: boolean; shortages: string[] }> {
    const sessionResources = await this.getResourcesBySession(sessionId)
    const shortages: string[] = []

    for (const r of sessionResources) {
      if (r.requiredCount > r.availableCount) {
        shortages.push(`${r.workerType}: need ${r.requiredCount}, have ${r.availableCount}`)
      }
    }

    return { sufficient: shortages.length === 0, shortages }
  },

  async registerConstraint(sessionId: string, type: PlanningConstraint["type"], description: string, severity: PlanningConstraint["severity"]): Promise<PlanningConstraint> {
    const constraint: PlanningConstraint = {
      id: generateId("plan-constraint"),
      sessionId,
      type,
      description,
      severity,
      active: true,
    }
    constraints.set(constraint.id, constraint)
    return constraint
  },

  async getConstraintsBySession(sessionId: string): Promise<PlanningConstraint[]> {
    return Array.from(constraints.values()).filter((c) => c.sessionId === sessionId && c.active)
  },

  async clearSession(sessionId: string): Promise<void> {
    for (const [id, r] of resources.entries()) {
      if (r.sessionId === sessionId) resources.delete(id)
    }
    for (const [id, c] of constraints.entries()) {
      if (c.sessionId === sessionId) constraints.delete(id)
    }
  },
}
