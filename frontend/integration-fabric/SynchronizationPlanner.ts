import type { SynchronizationPlan, SynchronizationJob, SynchronizationState, IntegrationResult } from "./types"
import { generateId } from "./shared"

const plans = new Map<string, SynchronizationPlan>()

export const SynchronizationPlanner = {
  async createPlan(
    connectorId: string,
    name: string,
    sourceEndpointId: string,
    targetEndpointId: string,
    schedule: string = "manual",
    metadata: Record<string, unknown> = {},
  ): Promise<SynchronizationPlan> {
    const id = generateId("sync")
    const now = new Date().toISOString()
    const plan: SynchronizationPlan = {
      id,
      connectorId,
      name,
      sourceEndpointId,
      targetEndpointId,
      schedule,
      state: "planned",
      jobs: [],
      createdAt: now,
      updatedAt: now,
      metadata,
    }
    plans.set(id, plan)
    return plan
  },

  async scheduleSynchronization(planId: string, actions: string[]): Promise<SynchronizationPlan> {
    const plan = plans.get(planId)
    if (!plan) throw new Error(`Synchronization plan not found: ${planId}`)
    const jobs: SynchronizationJob[] = actions.map((action, index) => ({
      id: generateId("sync-job"),
      planId,
      sequence: index + 1,
      action,
      state: "planned",
      startedAt: null,
      completedAt: null,
      result: null,
      details: "",
    }))
    const updated: SynchronizationPlan = {
      ...plan,
      jobs: [...plan.jobs, ...jobs],
      state: "planned",
      updatedAt: new Date().toISOString(),
    }
    plans.set(planId, updated)
    return updated
  },

  async startJob(planId: string, jobId: string): Promise<SynchronizationJob> {
    const plan = plans.get(planId)
    if (!plan) throw new Error(`Synchronization plan not found: ${planId}`)
    const jobIndex = plan.jobs.findIndex((j) => j.id === jobId)
    if (jobIndex === -1) throw new Error(`Job not found: ${jobId}`)
    const job = plan.jobs[jobIndex]
    const updatedJob: SynchronizationJob = { ...job, state: "in_progress", startedAt: new Date().toISOString() }
    const jobs = [...plan.jobs]
    jobs[jobIndex] = updatedJob
    const updated: SynchronizationPlan = { ...plan, state: "in_progress", jobs, updatedAt: new Date().toISOString() }
    plans.set(planId, updated)
    return updatedJob
  },

  async completeJob(planId: string, jobId: string, result: IntegrationResult, details: string = ""): Promise<SynchronizationJob> {
    const plan = plans.get(planId)
    if (!plan) throw new Error(`Synchronization plan not found: ${planId}`)
    const jobIndex = plan.jobs.findIndex((j) => j.id === jobId)
    if (jobIndex === -1) throw new Error(`Job not found: ${jobId}`)
    const job = plan.jobs[jobIndex]
    const updatedJob: SynchronizationJob = {
      ...job,
      state: result === "failure" ? "failed" : "completed",
      completedAt: new Date().toISOString(),
      result,
      details,
    }
    const jobs = [...plan.jobs]
    jobs[jobIndex] = updatedJob
    const allDone = jobs.every((j) => j.state === "completed" || j.state === "failed")
    const updated: SynchronizationPlan = {
      ...plan,
      jobs,
      state: allDone ? (jobs.some((j) => j.state === "failed") ? "failed" : "completed") : "in_progress",
      updatedAt: new Date().toISOString(),
    }
    plans.set(planId, updated)
    return updatedJob
  },

  async validateSynchronization(planId: string): Promise<{ valid: boolean; errors: string[] }> {
    const plan = plans.get(planId)
    if (!plan) return { valid: false, errors: ["Synchronization plan not found"] }
    const errors: string[] = []
    if (!plan.sourceEndpointId) errors.push("Missing source endpoint")
    if (!plan.targetEndpointId) errors.push("Missing target endpoint")
    if (!plan.name) errors.push("Missing plan name")
    return { valid: errors.length === 0, errors }
  },

  async optimizeSynchronization(planId: string): Promise<SynchronizationPlan> {
    const plan = plans.get(planId)
    if (!plan) throw new Error(`Synchronization plan not found: ${planId}`)
    const sorted = [...plan.jobs].sort((a, b) => a.sequence - b.sequence)
    const updated: SynchronizationPlan = { ...plan, jobs: sorted, updatedAt: new Date().toISOString() }
    plans.set(planId, updated)
    return updated
  },

  async getPlan(planId: string): Promise<SynchronizationPlan | null> {
    return plans.get(planId) ?? null
  },

  async listPlans(connectorId?: string): Promise<SynchronizationPlan[]> {
    let result = Array.from(plans.values())
    if (connectorId) result = result.filter((p) => p.connectorId === connectorId)
    return result.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
  },
}
