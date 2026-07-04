import type { CapabilityAvailability, CapabilityStatus, CapabilityDescriptor } from "./types"
import type { ExecutionWorker } from "@/runtime-core/types"
import { WorkerRegistry } from "@/runtime-core/WorkerRegistry"
import { generateId } from "./shared"

export const CapabilityAvailabilityManager = {
  async checkAvailability(
    descriptor: CapabilityDescriptor,
    worker: ExecutionWorker,
  ): Promise<CapabilityAvailability> {
    const registration = await WorkerRegistry.getRegistration(worker.id)
    const healthy = registration?.healthy ?? false
    const currentLoad = worker.status === "busy" ? 1 : 0
    const maxLoad = descriptor.maxConcurrency

    let status: CapabilityStatus = "available"
    let estimatedAvailableAt: string | null = null

    if (!healthy || worker.status === "offline") {
      status = "unavailable"
    } else if (worker.status === "error") {
      status = "unavailable"
    } else if (currentLoad >= maxLoad) {
      status = "limited"
      estimatedAvailableAt = new Date(Date.now() + 60000).toISOString()
    } else if (worker.status === "busy") {
      status = "limited"
      estimatedAvailableAt = new Date(Date.now() + 30000).toISOString()
    }

    return {
      workerId: worker.id,
      descriptorId: descriptor.id,
      status,
      currentLoad,
      maxLoad,
      healthy,
      lastHeartbeat: worker.lastHeartbeat,
      estimatedAvailableAt,
    }
  },

  async checkBatchAvailability(
    descriptors: CapabilityDescriptor[],
    workers: ExecutionWorker[],
  ): Promise<CapabilityAvailability[]> {
    const results: CapabilityAvailability[] = []

    for (const descriptor of descriptors) {
      for (const worker of workers) {
        if (worker.capability === descriptor.capability) {
          const availability = await CapabilityAvailabilityManager.checkAvailability(descriptor, worker)
          results.push(availability)
        }
      }
    }

    return results
  },

  async filterAvailable(
    availabilities: CapabilityAvailability[],
  ): Promise<CapabilityAvailability[]> {
    return availabilities.filter((a) => a.status === "available" || a.status === "limited")
  },

  async getAvailableAt(workerId: string): Promise<string | null> {
    const registration = await WorkerRegistry.getRegistration(workerId)
    if (!registration) return null

    if (registration.worker.status === "idle") return new Date().toISOString()
    if (registration.worker.status === "busy") {
      return new Date(Date.now() + 60000).toISOString()
    }
    return null
  },
}
