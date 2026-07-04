import type { ApplicationService } from "./types"
import { generateId } from "./shared"

const services = new Map<string, ApplicationService>()

export const DependencyContainer = {
  async register(name: string, instance: unknown, singleton: boolean = true): Promise<ApplicationService> {
    const service: ApplicationService = { id: generateId("svc"), name, instance, singleton }
    services.set(name, service)
    return service
  },

  async resolve<T>(name: string): Promise<T | null> {
    const service = services.get(name)
    return (service?.instance as T) ?? null
  },

  async replace(name: string, instance: unknown): Promise<ApplicationService | null> {
    const existing = services.get(name)
    if (!existing) return null
    const updated: ApplicationService = { ...existing, instance }
    services.set(name, updated)
    return updated
  },

  async remove(name: string): Promise<boolean> {
    return services.delete(name)
  },

  async listServices(): Promise<ApplicationService[]> {
    return Array.from(services.values())
  },

  async clear(): Promise<void> {
    services.clear()
  },
}