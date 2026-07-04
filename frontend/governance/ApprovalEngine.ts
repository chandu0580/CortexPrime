import type { ApprovalRequest, ApprovalDecision, ApprovalState } from "./types"
import { generateId } from "./shared"

const requests = new Map<string, ApprovalRequest>()
const decisions = new Map<string, ApprovalDecision>()

export const ApprovalEngine = {
  async requestApproval(sessionId: string, action: string, requestedBy: string, reason: string, metadata: Record<string, unknown> = {}): Promise<ApprovalRequest> {
    const id = generateId("apr")
    const request: ApprovalRequest = {
      id,
      sessionId,
      action,
      requestedBy,
      reason,
      state: "pending",
      approver: null,
      decidedAt: null,
      createdAt: new Date().toISOString(),
      metadata,
    }
    requests.set(id, request)
    return request
  },

  async approve(requestId: string, approver: string, reason: string = "Approved"): Promise<{ request: ApprovalRequest; decision: ApprovalDecision }> {
    const request = requests.get(requestId)
    if (!request) throw new Error(`Approval request not found: ${requestId}`)
    if (request.state !== "pending") throw new Error(`Approval request ${requestId} is already ${request.state}`)

    const decision: ApprovalDecision = {
      id: generateId("apd"),
      requestId,
      approver,
      state: "approved",
      reason,
      timestamp: new Date().toISOString(),
    }

    const updated: ApprovalRequest = {
      ...request,
      state: "approved",
      approver,
      decidedAt: new Date().toISOString(),
    }

    requests.set(requestId, updated)
    decisions.set(decision.id, decision)
    return { request: updated, decision }
  },

  async reject(requestId: string, approver: string, reason: string): Promise<{ request: ApprovalRequest; decision: ApprovalDecision }> {
    const request = requests.get(requestId)
    if (!request) throw new Error(`Approval request not found: ${requestId}`)
    if (request.state !== "pending") throw new Error(`Approval request ${requestId} is already ${request.state}`)

    const decision: ApprovalDecision = {
      id: generateId("apd"),
      requestId,
      approver,
      state: "rejected",
      reason,
      timestamp: new Date().toISOString(),
    }

    const updated: ApprovalRequest = {
      ...request,
      state: "rejected",
      approver,
      decidedAt: new Date().toISOString(),
    }

    requests.set(requestId, updated)
    decisions.set(decision.id, decision)
    return { request: updated, decision }
  },

  async revoke(requestId: string, approver: string, reason: string): Promise<{ request: ApprovalRequest; decision: ApprovalDecision }> {
    const request = requests.get(requestId)
    if (!request) throw new Error(`Approval request not found: ${requestId}`)

    const decision: ApprovalDecision = {
      id: generateId("apd"),
      requestId,
      approver,
      state: "revoked",
      reason,
      timestamp: new Date().toISOString(),
    }

    const updated: ApprovalRequest = {
      ...request,
      state: "revoked",
      approver,
      decidedAt: new Date().toISOString(),
    }

    requests.set(requestId, updated)
    decisions.set(decision.id, decision)
    return { request: updated, decision }
  },

  async getRequest(requestId: string): Promise<ApprovalRequest | null> {
    return requests.get(requestId) ?? null
  },

  async listRequests(sessionId?: string, state?: ApprovalState): Promise<ApprovalRequest[]> {
    let result = Array.from(requests.values())
    if (sessionId) result = result.filter((r) => r.sessionId === sessionId)
    if (state) result = result.filter((r) => r.state === state)
    return result.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
  },

  async getDecisions(requestId: string): Promise<ApprovalDecision[]> {
    return Array.from(decisions.values()).filter((d) => d.requestId === requestId)
  },

  async requestCount(): Promise<number> {
    return requests.size
  },
}
