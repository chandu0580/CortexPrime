import type { WorkerTransition, WorkerLifecycleState } from "./types"
import { generateId } from "@/worker-framework/shared"
import { WorkerCoordinator } from "./WorkerCoordinator"

const transitions = new Map<string, WorkerTransition>()

const VALID_TRANSITIONS: Record<WorkerLifecycleState, WorkerLifecycleState[]> = {
  registered: ["starting"],
  starting: ["running", "failed"],
  running: ["pausing", "stopping", "failed"],
  pausing: ["paused", "failed"],
  paused: ["resuming", "stopping"],
  resuming: ["running", "failed"],
  stopping: ["stopped", "failed"],
  stopped: ["restarting", "registered"],
  restarting: ["starting", "failed"],
  failed: ["restarting"],
}

export const WorkerLifecycleManager = {
  async startWorker(workerId: string): Promise<WorkerTransition> {
    const worker = await WorkerCoordinator.getWorker(workerId)
    if (!worker) throw new Error(`Worker ${workerId} not found`)
    return this.transition(workerId, worker.status, "starting", "Start worker")
  },

  async pauseWorker(workerId: string): Promise<WorkerTransition> {
    const worker = await WorkerCoordinator.getWorker(workerId)
    if (!worker) throw new Error(`Worker ${workerId} not found`)
    return this.transition(workerId, worker.status, "pausing", "Pause worker")
  },

  async resumeWorker(workerId: string): Promise<WorkerTransition> {
    const worker = await WorkerCoordinator.getWorker(workerId)
    if (!worker) throw new Error(`Worker ${workerId} not found`)
    return this.transition(workerId, worker.status, "resuming", "Resume worker")
  },

  async stopWorker(workerId: string): Promise<WorkerTransition> {
    const worker = await WorkerCoordinator.getWorker(workerId)
    if (!worker) throw new Error(`Worker ${workerId} not found`)
    return this.transition(workerId, worker.status, "stopping", "Stop worker")
  },

  async restartWorker(workerId: string): Promise<WorkerTransition> {
    const worker = await WorkerCoordinator.getWorker(workerId)
    if (!worker) throw new Error(`Worker ${workerId} not found`)
    return this.transition(workerId, worker.status, "restarting", "Restart worker")
  },

  async transition(workerId: string, fromState: WorkerLifecycleState, toState: WorkerLifecycleState, reason: string): Promise<WorkerTransition> {
    const allowed = VALID_TRANSITIONS[fromState]
    if (!allowed || !allowed.includes(toState)) {
      throw new Error(`Invalid lifecycle transition: ${fromState} -> ${toState}`)
    }

    const transition: WorkerTransition = {
      id: generateId("wo-transition"),
      sessionId: "",
      workerId,
      fromState,
      toState,
      reason,
      timestamp: new Date().toISOString(),
    }
    transitions.set(transition.id, transition)
    return transition
  },

  async getTransition(transitionId: string): Promise<WorkerTransition | null> {
    return transitions.get(transitionId) ?? null
  },

  async getTransitionsByWorker(workerId: string): Promise<WorkerTransition[]> {
    return Array.from(transitions.values()).filter((t) => t.workerId === workerId)
  },

  isValidTransition(fromState: WorkerLifecycleState, toState: WorkerLifecycleState): boolean {
    const allowed = VALID_TRANSITIONS[fromState]
    return allowed !== undefined && allowed.includes(toState)
  },
}
