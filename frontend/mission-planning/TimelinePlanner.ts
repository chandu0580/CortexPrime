import type { PlanningTimeline, PlanningPhaseTimeline, PlanningMilestone, PlanningPhase } from "./types"
import { generateId } from "@/worker-framework/shared"
import { MissionPlanner } from "./MissionPlanner"

export const TimelinePlanner = {
  async generateTimeline(planId: string): Promise<PlanningTimeline> {
    const plan = await MissionPlanner.getPlan(planId)
    if (!plan) throw new Error(`MissionPlan ${planId} not found`)

    const now = new Date()
    const phases = plan.phases
    let currentOffset = 0
    const phaseTimelines: PlanningPhaseTimeline[] = []
    const milestones: PlanningMilestone[] = []

    for (const phase of phases) {
      const duration = phase.estimatedDurationMs
      phaseTimelines.push({
        phaseId: phase.id,
        phaseName: phase.name,
        order: phase.order,
        startOffsetMs: currentOffset,
        durationMs: duration,
        parallel: false,
      })

      milestones.push({
        id: generateId("plan-milestone"),
        name: `${phase.name} Complete`,
        description: `Completion of ${phase.name}`,
        phaseId: phase.id,
        offsetMs: currentOffset + duration,
        criteria: [`All tasks in ${phase.name} completed`],
      })

      currentOffset += duration
    }

    const estimatedStartAt = now.toISOString()
    const estimatedEndAt = new Date(now.getTime() + currentOffset).toISOString()

    const timeline: PlanningTimeline = {
      id: generateId("plan-timeline"),
      sessionId: plan.sessionId,
      planId,
      phases: phaseTimelines,
      totalDurationMs: currentOffset,
      milestones,
      estimatedStartAt,
      estimatedEndAt,
      createdAt: now.toISOString(),
    }
    return timeline
  },

  async estimateDuration(planId: string): Promise<number> {
    const plan = await MissionPlanner.getPlan(planId)
    if (!plan) throw new Error(`MissionPlan ${planId} not found`)

    const baseDuration = plan.phases.reduce((sum, p) => sum + p.estimatedDurationMs, 0)
    const taskOverhead = plan.totalTasks * 5000
    const dependencyOverhead = plan.phases.reduce((sum, p) => sum + p.tasks.filter((t) => t.dependencies.length > 0).length, 0) * 10000

    return baseDuration + taskOverhead + dependencyOverhead
  },

  async reorderTimeline(planId: string, phaseOrder: string[]): Promise<PlanningTimeline> {
    const plan = await MissionPlanner.getPlan(planId)
    if (!plan) throw new Error(`MissionPlan ${planId} not found`)

    const phaseMap = new Map(plan.phases.map((p) => [p.id, p]))
    const reordered = phaseOrder.map((id) => phaseMap.get(id)).filter((p): p is PlanningPhase => p !== undefined)

    if (reordered.length > 0) {
      reordered.forEach((p, i) => { p.order = i + 1 })
      plan.phases = reordered
      plan.updatedAt = new Date().toISOString()
    }

    return this.generateTimeline(planId)
  },

  async calculateMilestones(planId: string): Promise<PlanningMilestone[]> {
    const timeline = await this.generateTimeline(planId)
    return timeline.milestones
  },
}
