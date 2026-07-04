import type { WorkerDescriptor, WorkerRegistration, WorkerState } from "./types"

const registrations = new Map<string, WorkerRegistration>()

export const WorkerRegistry = {
  async register(descriptor: WorkerDescriptor): Promise<WorkerRegistration> {
    const registration: WorkerRegistration = {
      workerId: descriptor.id,
      descriptor,
      state: "REGISTERED",
      registeredAt: new Date().toISOString(),
      lastSeenAt: new Date().toISOString(),
      healthy: true,
    }
    registrations.set(descriptor.id, registration)
    return registration
  },

  async unregister(workerId: string): Promise<void> {
    registrations.delete(workerId)
  },

  async getRegistration(workerId: string): Promise<WorkerRegistration | null> {
    return registrations.get(workerId) ?? null
  },

  async updateState(workerId: string, state: WorkerState): Promise<WorkerRegistration> {
    const reg = registrations.get(workerId)
    if (!reg) throw new Error(`Worker not registered: ${workerId}`)
    const updated: WorkerRegistration = { ...reg, state, lastSeenAt: new Date().toISOString() }
    registrations.set(workerId, updated)
    return updated
  },

  async markHealthy(workerId: string, healthy: boolean): Promise<WorkerRegistration> {
    const reg = registrations.get(workerId)
    if (!reg) throw new Error(`Worker not registered: ${workerId}`)
    const updated: WorkerRegistration = { ...reg, healthy, lastSeenAt: new Date().toISOString() }
    registrations.set(workerId, updated)
    return updated
  },

  async findByCapability(capabilityType: string): Promise<WorkerRegistration[]> {
    return Array.from(registrations.values()).filter((r) =>
      r.descriptor.capabilities.some((c) => c.type === capabilityType || c.name === capabilityType),
    )
  },

  async findByType(type: string): Promise<WorkerRegistration[]> {
    return Array.from(registrations.values()).filter((r) => r.descriptor.type === type)
  },

  async getHealthyWorkers(): Promise<WorkerRegistration[]> {
    return Array.from(registrations.values()).filter((r) => r.healthy)
  },

  async getAllRegistrations(): Promise<WorkerRegistration[]> {
    return Array.from(registrations.values())
  },

  async registrationCount(): Promise<number> {
    return registrations.size
  },
}
