import type { WorkerRegistration } from "./types"
import { WorkerRegistry } from "./WorkerRegistry"

export const WorkerDiscovery = {
  async discoverByCapability(capabilityType: string): Promise<WorkerRegistration[]> {
    return WorkerRegistry.findByCapability(capabilityType)
  },

  async discoverByType(type: string): Promise<WorkerRegistration[]> {
    return WorkerRegistry.findByType(type)
  },

  async discoverAvailable(capabilityType: string): Promise<WorkerRegistration[]> {
    const all = await WorkerRegistry.findByCapability(capabilityType)
    const healthy = await WorkerRegistry.getHealthyWorkers()
    const healthyIds = new Set(healthy.map((h) => h.workerId))
    return all.filter((r) => healthyIds.has(r.workerId))
  },

  async discoverAll(): Promise<WorkerRegistration[]> {
    return WorkerRegistry.getAllRegistrations()
  },
}
