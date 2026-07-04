import type { RetryPolicy, ExecutionTask, ExecutionSession } from "./types"
import { generateId } from "./shared"

const retryPolicies = new Map<string, RetryPolicy>()

const DEFAULT_RETRYABLE_ERRORS = [
  "timeout",
  "connection_error",
  "worker_unavailable",
  "temporary_failure",
  "rate_limited",
]

export const RetryCoordinator = {
  async createPolicy(
    taskId: string,
    maxRetries: number = 3,
    backoffMs: number = 1000,
    backoffMultiplier: number = 2,
    maxBackoffMs: number = 60000,
    retryableErrors: string[] = DEFAULT_RETRYABLE_ERRORS,
  ): Promise<RetryPolicy> {
    const policy: RetryPolicy = {
      id: generateId("retry"),
      taskId,
      maxRetries,
      retryCount: 0,
      backoffMs,
      backoffMultiplier,
      maxBackoffMs,
      retryableErrors,
      lastRetryAt: null,
      nextRetryAt: null,
    }
    retryPolicies.set(policy.id, policy)
    return policy
  },

  async getPolicy(taskId: string): Promise<RetryPolicy | null> {
    return Array.from(retryPolicies.values()).find((p) => p.taskId === taskId) ?? null
  },

  async canRetry(policy: RetryPolicy, error: string): Promise<boolean> {
    if (policy.retryCount >= policy.maxRetries) return false
    return policy.retryableErrors.some((e) => error.toLowerCase().includes(e.toLowerCase()))
  },

  async calculateBackoff(policy: RetryPolicy): Promise<number> {
    const backoff = policy.backoffMs * Math.pow(policy.backoffMultiplier, policy.retryCount)
    return Math.min(backoff, policy.maxBackoffMs)
  },

  async executeRetry(policy: RetryPolicy): Promise<RetryPolicy> {
    const nextBackoff = await RetryCoordinator.calculateBackoff(policy)
    const updated: RetryPolicy = {
      ...policy,
      retryCount: policy.retryCount + 1,
      lastRetryAt: new Date().toISOString(),
      nextRetryAt: new Date(Date.now() + nextBackoff).toISOString(),
    }
    retryPolicies.set(policy.id, updated)
    return updated
  },

  async resetPolicy(policy: RetryPolicy): Promise<RetryPolicy> {
    const updated: RetryPolicy = {
      ...policy,
      retryCount: 0,
      lastRetryAt: null,
      nextRetryAt: null,
    }
    retryPolicies.set(policy.id, updated)
    return updated
  },

  async getPolicyCount(): Promise<number> {
    return retryPolicies.size
  },
}
