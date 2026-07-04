import type { KernelContext } from "./types"

export const ContextManager = {
  async createContext(missionId: string, sessionId: string, correlationId: string, userIntent: string): Promise<KernelContext> {
    return {
      missionId,
      sessionId,
      correlationId,
      userIntent,
      data: { originalIntent: userIntent },
      errors: [],
      warnings: [],
      propagatedFrom: null,
      propagatedAt: null,
    }
  },

  async propagateContext(context: KernelContext, updates: Record<string, unknown>): Promise<KernelContext> {
    return {
      ...context,
      data: { ...context.data, ...updates },
      propagatedFrom: context.correlationId,
      propagatedAt: new Date().toISOString(),
    }
  },

  async mergeContext(context: KernelContext, newData: Record<string, unknown>): Promise<KernelContext> {
    return {
      ...context,
      data: { ...context.data, ...newData },
      updatedAt: new Date().toISOString(),
    } as KernelContext & { updatedAt: string }
  },

  async addError(context: KernelContext, error: string): Promise<KernelContext> {
    return {
      ...context,
      errors: [...context.errors, error],
    }
  },

  async addWarning(context: KernelContext, warning: string): Promise<KernelContext> {
    return {
      ...context,
      warnings: [...context.warnings, warning],
    }
  },

  async getContextData<T>(context: KernelContext, key: string): Promise<T | undefined> {
    return context.data[key] as T | undefined
  },
}
