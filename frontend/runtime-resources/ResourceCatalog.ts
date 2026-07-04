import type { ResourceDescriptor, ResourceType } from "./types"
import { generateId } from "./shared"

const descriptors = new Map<string, ResourceDescriptor>()

export const ResourceCatalog = {
  async registerResource(
    name: string,
    resourceType: ResourceType,
    unit: string,
    description: string,
    metadata: Record<string, string> = {},
  ): Promise<ResourceDescriptor> {
    const descriptor: ResourceDescriptor = {
      id: generateId("resource"),
      name,
      resourceType,
      unit,
      description,
      metadata,
    }
    descriptors.set(descriptor.id, descriptor)
    return descriptor
  },

  async getDescriptor(id: string): Promise<ResourceDescriptor | null> {
    return descriptors.get(id) ?? null
  },

  async findDescriptors(type: ResourceType): Promise<ResourceDescriptor[]> {
    return Array.from(descriptors.values()).filter((d) => d.resourceType === type)
  },

  async getAllDescriptors(): Promise<ResourceDescriptor[]> {
    return Array.from(descriptors.values())
  },

  async getDescriptorCount(): Promise<number> {
    return descriptors.size
  },
}
