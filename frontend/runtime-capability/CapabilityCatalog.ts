import type { CapabilityDescriptor } from "./types"
import type { WorkerCapability } from "@/runtime-core/types"
import { generateId } from "./shared"

const catalog = new Map<string, CapabilityDescriptor>()

export const CapabilityCatalog = {
  async registerCapability(descriptor: Omit<CapabilityDescriptor, "id">): Promise<CapabilityDescriptor> {
    const entry: CapabilityDescriptor = { id: generateId("cap"), ...descriptor }
    catalog.set(entry.id, entry)
    return entry
  },

  async getCapability(id: string): Promise<CapabilityDescriptor | null> {
    return catalog.get(id) ?? null
  },

  async findCapabilities(capability: WorkerCapability): Promise<CapabilityDescriptor[]> {
    return Array.from(catalog.values()).filter((c) => c.capability === capability)
  },

  async findCapabilityByFeature(feature: string): Promise<CapabilityDescriptor[]> {
    return Array.from(catalog.values()).filter((c) =>
      c.features.some((f) => f.toLowerCase().includes(feature.toLowerCase())),
    )
  },

  async getAllCapabilities(): Promise<CapabilityDescriptor[]> {
    return Array.from(catalog.values())
  },

  async getCapabilityCount(): Promise<number> {
    return catalog.size
  },
}
