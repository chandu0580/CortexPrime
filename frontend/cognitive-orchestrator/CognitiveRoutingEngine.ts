import type { CognitiveRoute, CognitiveDecision, CognitiveStage, CognitiveStatus, CognitiveSession, CognitivePipelineExecution } from "./types"
import { generateId } from "@/worker-framework/shared"

const decisions = new Map<string, CognitiveDecision>()

const STAGE_ORDER: Record<CognitiveStage, number> = {
  intake: 1,
  context_build: 2,
  memory_retrieval: 3,
  knowledge_resolution: 4,
  worker_coordination: 5,
  world_state_update: 6,
  validation: 7,
  completion: 8,
}

export const CognitiveRoutingEngine = {
  async determineRoute(
    session: CognitiveSession,
    execution: CognitivePipelineExecution,
    stageStatus: CognitiveStatus,
    error?: string | null,
  ): Promise<CognitiveRoute> {
    const currentStage = execution.stages[execution.currentStageIndex]
    if (!currentStage) {
      return { type: "terminate", currentStage: "completion", nextStage: null, conditions: ["No more stages"] }
    }

    if (currentStage.retryCount >= 3) {
      return { type: "terminate", currentStage: currentStage.name, nextStage: null, conditions: ["Max retries exceeded"] }
    }

    if (stageStatus === "failed") {
      if (error === "skip") {
        return { type: "skip", currentStage: currentStage.name, nextStage: this.getNextStage(currentStage.name), conditions: [error] }
      }
      return { type: "retry", currentStage: currentStage.name, nextStage: currentStage.name, conditions: [error ?? "Stage failed"] }
    }

    if (stageStatus === "completed") {
      const nextStage = this.getNextStage(currentStage.name)
      if (!nextStage) {
        return { type: "terminate", currentStage: currentStage.name, nextStage: null, conditions: ["Pipeline complete"] }
      }
      return { type: "forward", currentStage: currentStage.name, nextStage, conditions: [] }
    }

    return { type: "forward", currentStage: currentStage.name, nextStage: currentStage.name, conditions: ["No decision yet"] }
  },

  async nextStage(session: CognitiveSession, execution: CognitivePipelineExecution): Promise<CognitiveStage | null> {
    const currentStage = execution.stages[execution.currentStageIndex]
    if (!currentStage) return null
    return this.getNextStage(currentStage.name)
  },

  async skipStage(session: CognitiveSession, execution: CognitivePipelineExecution, stageName: CognitiveStage): Promise<CognitiveStage | null> {
    const stageOrder = STAGE_ORDER[stageName]
    const entries = Object.entries(STAGE_ORDER)
    for (const entry of entries) {
      if (entry[1] > stageOrder) return entry[0] as CognitiveStage
    }
    return null
  },

  async retryStage(execution: CognitivePipelineExecution): Promise<CognitiveStage> {
    const currentStage = execution.stages[execution.currentStageIndex]
    return currentStage?.name ?? "intake"
  },

  async terminate(): Promise<CognitiveStage> {
    return "completion"
  },

  async recordDecision(
    sessionId: string,
    stage: CognitiveStage,
    action: CognitiveDecision["action"],
    reason: string,
    route: CognitiveRoute | null,
  ): Promise<CognitiveDecision> {
    const decision: CognitiveDecision = {
      id: generateId("cog-decision"),
      sessionId,
      stage,
      action,
      reason,
      route,
      timestamp: new Date().toISOString(),
    }
    decisions.set(decision.id, decision)
    return decision
  },

  async getDecisionsBySession(sessionId: string): Promise<CognitiveDecision[]> {
    return Array.from(decisions.values()).filter((d) => d.sessionId === sessionId)
  },

  async getRouteSummary(sessionId: string): Promise<{ total: number; skips: number; retries: number; terminations: number; proceeds: number }> {
    const sessionDecisions = await this.getDecisionsBySession(sessionId)
    return {
      total: sessionDecisions.length,
      skips: sessionDecisions.filter((d) => d.action === "skip").length,
      retries: sessionDecisions.filter((d) => d.action === "retry").length,
      terminations: sessionDecisions.filter((d) => d.action === "terminate").length,
      proceeds: sessionDecisions.filter((d) => d.action === "proceed").length,
    }
  },

  getNextStage(currentStage: CognitiveStage): CognitiveStage | null {
    const currentOrder = STAGE_ORDER[currentStage]
    const entries = Object.entries(STAGE_ORDER)
    for (const entry of entries) {
      if (entry[1] === currentOrder + 1) return entry[0] as CognitiveStage
    }
    return null
  },
}
