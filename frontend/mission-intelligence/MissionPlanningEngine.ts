import type { MissionAnalysis } from "@/types/intelligence"
import type { MissionPlan, MissionCapability, MissionDependency, MissionTask } from "./types"
import { MissionStrategyEngine } from "./MissionStrategyEngine"

function generateId(): string {
  return `plan-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`
}

function buildDependencies(tasks: MissionTask[]): MissionDependency[] {
  const dependencies: MissionDependency[] = []

  for (const task of tasks) {
    for (const depId of task.dependsOn) {
      dependencies.push({
        id: `dep-${generateId()}`,
        sourceId: depId,
        targetId: task.id,
        type: "sequential",
        description: `${task.name} depends on preceding task`,
      })
    }
  }

  return dependencies
}

export const MissionPlanningEngine = {
  async buildPlan(analysis: MissionAnalysis): Promise<MissionPlan> {
    const strategy = await MissionStrategyEngine.buildStrategy(analysis)
    const allTasks: MissionTask[] = []
    const capabilities: MissionCapability[] = []

    for (const phase of strategy.phases) {
      for (const task of phase.tasks) {
        allTasks.push(task)
      }
    }

    for (let i = 1; i < strategy.phases.length; i++) {
      const prevPhase = strategy.phases[i - 1]
      const currPhase = strategy.phases[i]

      for (const task of currPhase.tasks) {
        if (prevPhase.tasks.length > 0) {
          task.dependsOn.push(prevPhase.tasks[prevPhase.tasks.length - 1].id)
        }
      }
    }

    for (const cap of analysis.preview.suggestedCapabilities) {
      capabilities.push({
        id: `cap-${generateId()}`,
        name: cap,
        description: `Enterprise capability for ${cap.toLowerCase()}`,
        required: true,
        confidence: 0.8,
        alternatives: [],
      })
    }

    for (const req of analysis.assessment.resourceRequirements) {
      capabilities.push({
        id: `cap-${generateId()}`,
        name: req,
        description: `Resource capability: ${req.toLowerCase()}`,
        required: true,
        confidence: 0.7,
        alternatives: [],
      })
    }

    const dependencies = buildDependencies(allTasks)

    const plan: MissionPlan = {
      id: `plan-${generateId()}`,
      strategyId: strategy.id,
      phases: strategy.phases,
      tasks: allTasks,
      dependencies,
      capabilities,
      risks: [],
      estimatedDuration: analysis.assessment.estimatedDuration,
      resourceAllocation: {
        "Domain Expertise": 2,
        "Engineering": 3,
        "Project Management": 1,
        "Quality Assurance": 1,
      },
    }

    return plan
  },
}
