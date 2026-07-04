import type { RuntimeManifest as RuntimeManifestType, RuntimeModuleRecord } from "./types"
import { generateId } from "./shared"

const platformModules: RuntimeModuleRecord[] = [
  { id: "platform-composition",   name: "Platform Composition",   version: "1.0.0", package: "platform-composition",   dependencies: [],                          required: true },
  { id: "platform-bootstrap",     name: "Platform Bootstrap",     version: "1.0.0", package: "platform-bootstrap",     dependencies: ["platform-composition"],     required: true },
  { id: "runtime-composition",    name: "Runtime Composition",    version: "1.0.0", package: "runtime-composition",    dependencies: ["platform-bootstrap"],      required: true },
  { id: "kernel",                 name: "Kernel",                 version: "1.0.0", package: "kernel",                 dependencies: ["runtime-composition"],     required: true },
  { id: "runtime-core",           name: "Runtime Core",           version: "1.0.0", package: "runtime-core",           dependencies: ["kernel"],                  required: true },
  { id: "worker-framework",       name: "Worker Framework",       version: "1.0.0", package: "worker-framework",       dependencies: ["runtime-core"],            required: true },
  { id: "capability-framework",   name: "Capability Framework",   version: "1.0.0", package: "capability-framework",   dependencies: ["runtime-core"],            required: true },
  { id: "worker-pipeline",        name: "Worker Pipeline",        version: "1.0.0", package: "worker-pipeline",        dependencies: ["worker-framework"],        required: true },
  { id: "connector-framework",    name: "Connector Framework",    version: "1.0.0", package: "connector-framework",    dependencies: ["runtime-core"],            required: true },
  { id: "event-bus",              name: "Event Bus",              version: "1.0.0", package: "event-bus",              dependencies: ["runtime-core"],            required: true },
  { id: "mission-engines",        name: "Mission Engines",        version: "1.0.0", package: "mission-engines",        dependencies: ["capability-framework"],    required: false },
  { id: "cognitive-services",     name: "Cognitive Services",     version: "1.0.0", package: "cognitive-services",     dependencies: ["capability-framework"],    required: false },
  { id: "enterprise-services",    name: "Enterprise Services",    version: "1.0.0", package: "enterprise-services",    dependencies: ["connector-framework"],     required: false },
  { id: "connectors",             name: "Connectors",             version: "1.0.0", package: "connectors",             dependencies: ["connector-framework"],     required: false },
  { id: "observability",          name: "Observability",          version: "1.0.0", package: "observability",          dependencies: ["event-bus"],               required: false },
  { id: "governance",             name: "Governance",             version: "1.0.0", package: "governance",             dependencies: ["event-bus"],               required: false },
  { id: "analytics",              name: "Analytics",              version: "1.0.0", package: "analytics",              dependencies: ["event-bus"],               required: false },
]

let manifestData: RuntimeManifestType | null = null

export const RuntimeManifest = {
  async load(): Promise<RuntimeManifestType> {
    if (manifestData) return manifestData
    manifestData = {
      id: generateId("manifest"),
      modules: platformModules,
      version: "1.0.0",
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    }
    return manifestData
  },

  async getManifest(): Promise<RuntimeManifestType | null> {
    return manifestData
  },

  async getModule(moduleId: string): Promise<RuntimeModuleRecord | null> {
    const manifest = await this.load()
    return manifest.modules.find((m) => m.id === moduleId) ?? null
  },

  async listModules(): Promise<RuntimeModuleRecord[]> {
    const manifest = await this.load()
    return [...manifest.modules]
  },

  async listRequiredModules(): Promise<RuntimeModuleRecord[]> {
    const manifest = await this.load()
    return manifest.modules.filter((m) => m.required)
  },
}