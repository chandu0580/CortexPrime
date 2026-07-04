import type { WorkerDelegation, DelegationPolicy } from "./types"
import { generateId } from "./shared"

const delegations = new Map<string, WorkerDelegation>()

export const DelegationEngine = {
  async delegateTask(sessionId: string, taskId: string, workerId: string, policy: DelegationPolicy = "capability_based"): Promise<WorkerDelegation> {
    const id = generateId("del")
    const delegation: WorkerDelegation = {
      id,
      sessionId,
      taskId,
      workerId,
      policy,
      status: "active",
      delegatedAt: new Date().toISOString(),
      reassignedAt: null,
      revokedAt: null,
      completedAt: null,
    }
    delegations.set(id, delegation)
    return delegation
  },

  async reassignTask(delegationId: string, newWorkerId: string): Promise<WorkerDelegation> {
    const delegation = delegations.get(delegationId)
    if (!delegation) throw new Error(`Delegation not found: ${delegationId}`)
    const updated: WorkerDelegation = {
      ...delegation,
      workerId: newWorkerId,
      status: "reassigned",
      reassignedAt: new Date().toISOString(),
    }
    delegations.set(delegationId, updated)

    const id = generateId("del")
    const newDelegation: WorkerDelegation = {
      id,
      sessionId: delegation.sessionId,
      taskId: delegation.taskId,
      workerId: newWorkerId,
      policy: delegation.policy,
      status: "active",
      delegatedAt: new Date().toISOString(),
      reassignedAt: null,
      revokedAt: null,
      completedAt: null,
    }
    delegations.set(id, newDelegation)
    return newDelegation
  },

  async revokeDelegation(delegationId: string): Promise<WorkerDelegation> {
    const delegation = delegations.get(delegationId)
    if (!delegation) throw new Error(`Delegation not found: ${delegationId}`)
    const updated: WorkerDelegation = {
      ...delegation,
      status: "revoked",
      revokedAt: new Date().toISOString(),
    }
    delegations.set(delegationId, updated)
    return updated
  },

  async completeDelegation(delegationId: string): Promise<WorkerDelegation> {
    const delegation = delegations.get(delegationId)
    if (!delegation) throw new Error(`Delegation not found: ${delegationId}`)
    const updated: WorkerDelegation = {
      ...delegation,
      status: "completed",
      completedAt: new Date().toISOString(),
    }
    delegations.set(delegationId, updated)
    return updated
  },

  async rebalanceAssignments(sessionId: string): Promise<WorkerDelegation[]> {
    const sessionDelegations = Array.from(delegations.values()).filter(
      (d) => d.sessionId === sessionId && d.status === "active",
    )
    const workerLoad = new Map<string, number>()
    for (const d of sessionDelegations) {
      workerLoad.set(d.workerId, (workerLoad.get(d.workerId) ?? 0) + 1)
    }
    return sessionDelegations
  },

  async getDelegation(id: string): Promise<WorkerDelegation | null> {
    return delegations.get(id) ?? null
  },

  async listDelegations(sessionId?: string): Promise<WorkerDelegation[]> {
    let result = Array.from(delegations.values())
    if (sessionId) result = result.filter((d) => d.sessionId === sessionId)
    return result.sort((a, b) => new Date(b.delegatedAt).getTime() - new Date(a.delegatedAt).getTime())
  },
}
