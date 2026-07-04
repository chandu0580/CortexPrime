import type { WorkerConfiguration } from "./types"

const configs = new Map<string, WorkerConfiguration>()

const DEFAULTS: WorkerConfiguration = {
  maxConcurrentTasks: 1,
  heartbeatIntervalMs: 15000,
  healthCheckIntervalMs: 30000,
  taskTimeoutMs: 300000,
  autoRecovery: true,
  maxRetries: 3,
  settings: {},
}

export const WorkerConfigurationManager = {
  async initialize(workerId: string, overrides: Partial<WorkerConfiguration> = {}): Promise<WorkerConfiguration> {
    const config: WorkerConfiguration = { ...DEFAULTS, ...overrides }
    configs.set(workerId, config)
    return config
  },

  async getConfig(workerId: string): Promise<WorkerConfiguration | null> {
    return configs.get(workerId) ?? null
  },

  async update(workerId: string, updates: Partial<WorkerConfiguration>): Promise<WorkerConfiguration> {
    const existing = configs.get(workerId)
    if (!existing) throw new Error(`No configuration for worker: ${workerId}`)
    const updated: WorkerConfiguration = { ...existing, ...updates }
    configs.set(workerId, updated)
    return updated
  },

  async getDefaults(): Promise<WorkerConfiguration> {
    return { ...DEFAULTS }
  },

  async reset(workerId: string): Promise<WorkerConfiguration> {
    configs.set(workerId, { ...DEFAULTS })
    return configs.get(workerId)!
  },
}
