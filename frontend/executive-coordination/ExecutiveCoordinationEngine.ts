import type { CoordinationSession, CoordinationPlan, CoordinationStage, CoordinationTask, WorkerCandidate, WorkerSelection, WorkerDelegation, CoordinationDecision, CoordinationConflict, ConflictResolution, SynchronizationBarrier, CoordinationCheckpoint, CoordinationMetrics, CoordinationHealth, CoordinationSnapshot, CoordinationTransition, ExecutiveCoordinationCapabilityDefinition, ValidationResult, HealthSnapshot } from "./types"
import type { CoordinationState, CoordinationStrategy, DelegationPolicy, SynchronizationMode, CoordinationResult } from "./types"
import { CoordinationSessionManager } from "./CoordinationSessionManager"
import { WorkerSelectionEngine } from "./WorkerSelectionEngine"
import { CoordinationPlanner } from "./CoordinationPlanner"
import { DelegationEngine } from "./DelegationEngine"
import { SynchronizationEngine } from "./SynchronizationEngine"
import { CoordinationDecisionEngine } from "./CoordinationDecisionEngine"
import { CoordinationPolicyEngine } from "./CoordinationPolicyEngine"
import { CoordinationValidationEngine } from "./CoordinationValidationEngine"
import { CoordinationMetricsCollector } from "./CoordinationMetricsCollector"
import { CoordinationHealthManager } from "./CoordinationHealthManager"
import { ExecutiveCoordinationCapability } from "./ExecutiveCoordinationCapability"
import { cortexEventBus } from "@/event-bus/cortexEventBus"

export const ExecutiveCoordinationEngine = {
  async coordinate(sessionId: string, action: string, data: Record<string, unknown> = {}): Promise<Record<string, unknown>> {
    switch (action) {
      case "create_session": {
        const { missionId, name, strategy, metadata } = data as unknown as { missionId: string; name: string; strategy?: CoordinationStrategy; metadata?: Record<string, unknown> }
        const session = await CoordinationSessionManager.createSession(missionId, name, strategy, metadata)
        await cortexEventBus.publish("coordination", "analytics", "coordination.session.created", "ExecutiveCoordinationEngine", {
          sessionId: session.id,
          missionId,
          name,
        }, "low", session.id)
        return { session }
      }
      case "create_plan": {
        const { planName, strategy } = data as unknown as { planName: string; strategy?: CoordinationStrategy }
        const plan = await CoordinationPlanner.createPlan(sessionId, planName, strategy)
        await cortexEventBus.publish("coordination", "analytics", "coordination.plan.created", "ExecutiveCoordinationEngine", {
          planId: plan.id,
          sessionId,
          name: planName,
        }, "low", sessionId)
        return { plan }
      }
      case "build_stages": {
        const { planId, stageNames } = data as unknown as { planId: string; stageNames: string[] }
        const stages = await CoordinationPlanner.buildStages(planId, stageNames)
        return { stages }
      }
      default:
        throw new Error(`Unknown coordination action: ${action}`)
    }
  },

  async delegate(sessionId: string, taskId: string, workerId: string, policy?: DelegationPolicy): Promise<WorkerDelegation> {
    const delegation = await DelegationEngine.delegateTask(sessionId, taskId, workerId, policy)

    await cortexEventBus.publish("coordination", "analytics", "coordination.delegation.created", "ExecutiveCoordinationEngine", {
      delegationId: delegation.id,
      sessionId,
      taskId,
      workerId,
      policy: policy ?? "capability_based",
    }, "low", sessionId)

    return delegation
  },

  async selectWorker(candidates: WorkerCandidate[], requiredCapabilities: string[]): Promise<{ selection: WorkerSelection; worker: WorkerCandidate | null }> {
    return WorkerSelectionEngine.chooseWorker(candidates, requiredCapabilities)
  },

  async synchronize(sessionId: string, action: string, data: Record<string, unknown> = {}): Promise<SynchronizationBarrier> {
    switch (action) {
      case "create": {
        const { name, mode, requiredWorkers } = data as unknown as { name: string; mode: SynchronizationMode; requiredWorkers: string[] }
        const barrier = await SynchronizationEngine.createBarrier(sessionId, name, mode, requiredWorkers)
        await cortexEventBus.publish("coordination", "analytics", "coordination.barrier.created", "ExecutiveCoordinationEngine", {
          barrierId: barrier.id,
          sessionId,
          name,
          mode,
          requiredWorkers: requiredWorkers.length,
        }, "low", sessionId)
        return barrier
      }
      case "arrive": {
        const { barrierId, workerId } = data as unknown as { barrierId: string; workerId: string }
        return SynchronizationEngine.synchronizeWorkers(barrierId, workerId)
      }
      case "release": {
        const { barrierId } = data as unknown as { barrierId: string }
        return SynchronizationEngine.releaseBarrier(barrierId)
      }
      default:
        throw new Error(`Unknown sync action: ${action}`)
    }
  },

  async decide(sessionId: string, action: string, data: Record<string, unknown> = {}): Promise<CoordinationDecision> {
    switch (action) {
      case "evaluate": {
        const { reason } = data as unknown as { reason: string }
        return CoordinationDecisionEngine.evaluateExecution(sessionId, reason)
      }
      case "resolve_conflict": {
        const { type, description, involvedWorkers, involvedTasks, resolution, resolvedBy } = data as unknown as {
          type: "resource" | "dependency" | "priority" | "state"
          description: string
          involvedWorkers: string[]
          involvedTasks: string[]
          resolution: string
          resolvedBy: string
        }
        const result = await CoordinationDecisionEngine.resolveConflict(sessionId, type, description, involvedWorkers, involvedTasks, resolution, resolvedBy)
        await cortexEventBus.publish("coordination", "analytics", "coordination.conflict.resolved", "ExecutiveCoordinationEngine", {
          conflictId: result.conflict.id,
          sessionId,
          type,
        }, "high", sessionId)
        return { id: result.resolution.id, sessionId, type: "execute", reason: result.resolution.resolution, timestamp: result.resolution.resolvedAt, decidedBy: result.resolution.resolvedBy } as CoordinationDecision
      }
      case "next_action": {
        const { completed, total, failedCount } = data as unknown as { completed: number; total: number; failedCount: number }
        return CoordinationDecisionEngine.determineNextAction(sessionId, completed, total, failedCount)
      }
      case "escalate": {
        const { reason } = data as unknown as { reason: string }
        return CoordinationDecisionEngine.escalateDecision(sessionId, reason)
      }
      default:
        throw new Error(`Unknown decide action: ${action}`)
    }
  },

  async validate(type: string, data: Record<string, unknown>): Promise<ValidationResult> {
    let result: ValidationResult

    switch (type) {
      case "execution_ordering": {
        const stages = data as unknown as CoordinationStage[]
        result = await CoordinationValidationEngine.validateExecutionOrdering(stages)
        break
      }
      case "worker_assignments": {
        const { tasks, delegations } = data as unknown as { tasks: CoordinationTask[]; delegations: WorkerDelegation[] }
        result = await CoordinationValidationEngine.validateWorkerAssignments(tasks, delegations)
        break
      }
      case "dependency_satisfaction": {
        const tasks = data as unknown as CoordinationTask[]
        result = await CoordinationValidationEngine.validateDependencySatisfaction(tasks)
        break
      }
      case "sync_integrity": {
        const barriers = data as unknown as SynchronizationBarrier[]
        result = await CoordinationValidationEngine.validateSynchronizationIntegrity(barriers)
        break
      }
      case "coordination_completeness": {
        const plans = data as unknown as CoordinationPlan[]
        result = await CoordinationValidationEngine.validateCoordinationCompleteness(plans)
        break
      }
      default:
        throw new Error(`Unknown validation type: ${type}`)
    }

    await cortexEventBus.publish("coordination", "analytics", `coordination.validate.${type}`, "ExecutiveCoordinationEngine", {
      validationId: result.id,
      passed: result.passed,
      errors: result.errors.length,
    }, result.passed ? "low" : "high", "coordination")

    return result
  },

  async metrics(): Promise<CoordinationMetrics> {
    return CoordinationMetricsCollector.collectAll()
  },

  async health(): Promise<CoordinationHealth> {
    return CoordinationHealthManager.getHealth()
  },

  async getSession(sessionId: string): Promise<CoordinationSession | null> {
    return CoordinationSessionManager.getSession(sessionId)
  },

  async closeSession(sessionId: string): Promise<CoordinationSession> {
    const session = await CoordinationSessionManager.closeSession(sessionId)
    await cortexEventBus.publish("coordination", "analytics", "coordination.session.closed", "ExecutiveCoordinationEngine", {
      sessionId,
    }, "low", sessionId)
    return session
  },

  async completeTask(planId: string, taskId: string, result: CoordinationResult): Promise<CoordinationTask> {
    return CoordinationPlanner.completeTask(planId, taskId, result)
  },

  async getCapabilities(): Promise<ExecutiveCoordinationCapabilityDefinition[]> {
    return ExecutiveCoordinationCapability.list()
  },

  async isCapabilityEnabled(name: string): Promise<boolean> {
    return ExecutiveCoordinationCapability.isEnabled(name)
  },

  async snapshot(component: string, metrics: Record<string, number>, details?: string): Promise<HealthSnapshot> {
    return CoordinationHealthManager.snapshot(component, metrics, details)
  },
}
