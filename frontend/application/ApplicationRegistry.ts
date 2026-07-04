import type { ApplicationModule } from "./types"
import { generateId } from "./shared"

const moduleDefinitions: Omit<ApplicationModule, "registered">[] = [
  { id: "platform-assembly",     name: "Platform Assembly",          package: "platform-assembly",      dependencies: [] },
  { id: "platform-bootstrap",    name: "Platform Bootstrap",         package: "platform-bootstrap",     dependencies: ["platform-assembly"] },
  { id: "platform-composition",  name: "Platform Composition",       package: "platform-composition",   dependencies: ["platform-bootstrap"] },
  { id: "runtime-composition",   name: "Runtime Composition",        package: "runtime-composition",    dependencies: ["platform-composition"] },
  { id: "cortex-runtime",        name: "Cortex Runtime",             package: "cortex-runtime",         dependencies: ["runtime-composition"] },
  { id: "kernel",                name: "Kernel",                     package: "cortex-kernel",          dependencies: ["cortex-runtime"] },
  { id: "runtime-core",          name: "Runtime Core",               package: "runtime-core",           dependencies: ["kernel"] },
  { id: "worker-framework",      name: "Worker Framework",           package: "worker-framework",       dependencies: ["runtime-core"] },
  { id: "capability-framework",  name: "Capability Framework",       package: "capability-framework",   dependencies: ["runtime-core"] },
  { id: "connector-framework",   name: "Connector Framework",        package: "connector-framework",    dependencies: ["capability-framework"] },
  { id: "mission-engines",       name: "Mission Engines",            package: "mission-orchestrator",   dependencies: ["capability-framework"] },
  { id: "cognitive-services",    name: "Cognitive Services",         package: "cognitive-orchestrator", dependencies: ["capability-framework"] },
  { id: "enterprise-services",   name: "Enterprise Services",        package: "enterprise-reasoning",   dependencies: ["cognitive-services"] },
  { id: "validation",            name: "Platform Validation",        package: "platform-validation",    dependencies: ["cortex-runtime"] },
  { id: "observability",         name: "Observability",              package: "observability",          dependencies: ["runtime-core"] },
  { id: "governance",            name: "Governance",                 package: "governance",             dependencies: ["runtime-core"] },
  { id: "analytics",             name: "Analytics",                  package: "analytics",              dependencies: ["observability"] },
  { id: "connectors",            name: "Connectors",                 package: "connectors",             dependencies: ["connector-framework"] },
  { id: "platform-validation",   name: "Platform Validation Suite",  package: "platform-validation",    dependencies: ["platform-assembly"] },
]

const modules = new Map<string, ApplicationModule>()

export const ApplicationRegistry = {
  async registerAll(): Promise<ApplicationModule[]> {
    modules.clear()
    const records: ApplicationModule[] = moduleDefinitions.map((def) => ({ ...def, registered: false }))
    for (const rec of records) { modules.set(rec.id, rec) }
    return records
  },

  async getModule(moduleId: string): Promise<ApplicationModule | null> {
    return modules.get(moduleId) ?? null
  },

  async listModules(): Promise<ApplicationModule[]> {
    return Array.from(modules.values())
  },

  async markRegistered(moduleId: string): Promise<void> {
    const mod = modules.get(moduleId)
    if (mod) modules.set(moduleId, { ...mod, registered: true })
  },
}