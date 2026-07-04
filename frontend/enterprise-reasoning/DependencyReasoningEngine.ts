import type { MissionIntelligenceReport } from "@/mission-intelligence/types"
import type { EnterpriseDecision } from "./types"
import { buildDecisionBase } from "./shared"

export const DependencyReasoningEngine = {
  async analyzeDependencies(report: MissionIntelligenceReport): Promise<EnterpriseDecision[]> {
    const plan = report.plan
    const decisions: EnterpriseDecision[] = []

    for (let i = 1; i < plan.phases.length; i++) {
      const prev = plan.phases[i - 1]
      const curr = plan.phases[i]

      const steps = [
        {
          id: `dep-step-${prev.id}-${curr.id}-1`,
          order: 1,
          description: "Identify phase ordering dependency",
          input: `Phase ${prev.order}: ${prev.name} → Phase ${curr.order}: ${curr.name}`,
          output: `${curr.name} depends on ${prev.name} completion`,
          confidence: { level: "high" as const, score: 0.95, rationale: "Sequential phase ordering is standard for structured delivery" },
        },
        {
          id: `dep-step-${prev.id}-${curr.id}-2`,
          order: 2,
          description: "Validate dependency necessity",
          input: `${prev.tasks.length} tasks in ${prev.name}, ${curr.tasks.length} tasks in ${curr.name}`,
          output: `Phase ${curr.name} requires outputs from Phase ${prev.name} before execution can begin`,
          confidence: { level: "high" as const, score: 0.9, rationale: "Planning phase output is prerequisite for execution" },
        },
      ]

      const decision: EnterpriseDecision = {
        ...buildDecisionBase("dependency", `${prev.id}→${curr.id}`, `${prev.name} → ${curr.name}`),
        explanation: {
          summary: `${curr.name} phase depends on ${prev.name} phase. This is a required sequential dependency.`,
          detailed: `Phase "${curr.name}" (order ${curr.order}) depends on completion of phase "${prev.name}" (order ${prev.order}). This dependency exists because: ${curr.description.toLowerCase()}. The preceding phase (${prev.name}) produces ${prev.tasks.length} deliverables that are required inputs for ${curr.name}.`,
          trace: { id: `trace-dep-${prev.id}-${curr.id}-${Date.now()}`, steps, conclusion: `${curr.name} phase correctly depends on ${prev.name} phase completion`, confidence: { level: "high", score: 0.92, rationale: "Standard sequential dependency pattern" } },
        },
        evidence: [
          { id: `ev-dep-${prev.id}-${curr.id}-1`, source: "Mission Plan", content: `Phase ${prev.order}: ${prev.name} → Phase ${curr.order}: ${curr.name}`, relevance: "Phase order defined in mission plan", confidence: { level: "high", score: 0.95, rationale: "Phase ordering is explicit in plan" } },
          { id: `ev-dep-${prev.id}-${curr.id}-2`, source: "Phase Definitions", content: `Prev: ${prev.description}. Curr: ${curr.description}`, relevance: "Phase descriptions confirm dependency rationale", confidence: { level: "high", score: 0.88, rationale: "Phase descriptions clarify input-output relationship" } },
        ],
        assumptions: [
          { id: `ass-dep-${prev.id}-${curr.id}-1`, statement: `All ${prev.name} phase tasks will be completed before ${curr.name} begins`, impact: "Incomplete prior phase would block downstream execution", confidence: "high" },
          { id: `ass-dep-${prev.id}-${curr.id}-2`, statement: "Phase outputs are clearly defined and handoff is well-managed", impact: "Poor handoff quality would reduce downstream effectiveness", confidence: "medium" },
        ],
        alternatives: [
          {
            id: `alt-dep-${prev.id}-${curr.id}-1`,
            title: "Parallel Phase Execution",
            description: `Begin ${curr.name} before ${prev.name} is fully complete`,
            pros: ["Reduces overall timeline", "Earlier risk detection", "Increases team utilization"],
            cons: ["Higher coordination complexity", "Rework risk if prior phase changes", "Requires partial dependency management"],
            rationale: `Not recommended because ${curr.description.toLowerCase()}. Early execution would risk rework.`,
            confidence: { level: "low", score: 0.35, rationale: "Parallel execution introduces unacceptable rework risk" },
          },
        ],
        confidence: { level: "high", score: 0.92, rationale: "Sequential phase dependency is well-justified by delivery lifecycle requirements" },
      }

      decisions.push(decision)
    }

    const taskDeps = plan.dependencies.filter((d) => d.type === "sequential")
    for (const dep of taskDeps.slice(0, 3)) {
      const sourceTask = plan.tasks.find((t) => t.id === dep.sourceId)
      const targetTask = plan.tasks.find((t) => t.id === dep.targetId)
      if (!sourceTask || !targetTask) continue

      const decision: EnterpriseDecision = {
        ...buildDecisionBase("dependency", `${sourceTask.id}→${targetTask.id}`, `${sourceTask.name} → ${targetTask.name}`),
        explanation: {
          summary: `${targetTask.name} depends on ${sourceTask.name}. This ensures proper execution ordering.`,
          detailed: `Task "${targetTask.name}" depends on completion of "${sourceTask.name}" because: ${dep.description}. This sequential dependency ensures that ${sourceTask.name.toLowerCase()} produces required outputs before ${targetTask.name.toLowerCase()} begins.`,
          trace: { id: `trace-dep-${dep.id}-${Date.now()}`, steps: [
            { id: `dep-tstep-${dep.id}-1`, order: 1, description: "Evaluate task dependency", input: `Source: ${sourceTask.name}, Target: ${targetTask.name}`, output: `Sequential dependency confirmed`, confidence: { level: "high", score: 0.85, rationale: "Task ordering based on logical execution flow" } },
          ], conclusion: `Dependency between ${sourceTask.name} and ${targetTask.name} is valid and necessary`, confidence: { level: "high", score: 0.85, rationale: "Task-level dependencies follow execution logic" } },
        },
        evidence: [
          { id: `ev-dep-${dep.id}-1`, source: "Mission Plan", content: dep.description, relevance: "Dependency rationale from plan", confidence: { level: "high", score: 0.85, rationale: "Dependency is explicitly defined in plan" } },
        ],
        assumptions: [
          { id: `ass-dep-${dep.id}-1`, statement: `${sourceTask.name} will complete within estimated effort: ${sourceTask.estimatedEffort}`, impact: "Delay in source task cascades to dependent tasks", confidence: "medium" },
        ],
        alternatives: [],
        confidence: { level: "high", score: 0.85, rationale: "Task dependency is logically necessary for correct execution ordering" },
      }

      decisions.push(decision)
    }

    return decisions
  },
}
