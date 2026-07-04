import type { PlatformModuleRecord, ModuleCategory } from "./types"
import { generateId } from "./shared"

const moduleDefinitions: Omit<PlatformModuleRecord, "loaded" | "initialized">[] = [
  { id: "platform-contracts",     name: "Platform Contracts",       package: "platform-contracts",      category: "foundation" as ModuleCategory,  dependencies: [] },
  { id: "worker-framework",       name: "Worker Framework",         package: "worker-framework",        category: "foundation" as ModuleCategory,  dependencies: ["platform-contracts"] },
  { id: "worker-pipeline",        name: "Worker Pipeline",          package: "worker-pipeline",         category: "foundation" as ModuleCategory,  dependencies: ["worker-framework"] },
  { id: "capability-framework",   name: "Capability Framework",     package: "capability-framework",    category: "foundation" as ModuleCategory,  dependencies: ["platform-contracts"] },
  { id: "connector-framework",    name: "Connector Framework",      package: "connector-framework",     category: "foundation" as ModuleCategory,  dependencies: ["capability-framework"] },
  { id: "kernel",                 name: "Kernel",                   package: "cortex-kernel",           category: "kernel" as ModuleCategory,      dependencies: ["platform-contracts"] },
  { id: "runtime-core",           name: "Runtime Core",             package: "runtime-core",            category: "kernel" as ModuleCategory,      dependencies: ["kernel"] },
  { id: "runtime-composition",    name: "Runtime Composition",      package: "runtime-composition",     category: "runtime" as ModuleCategory,     dependencies: ["runtime-core"] },
  { id: "platform-composition",   name: "Platform Composition",     package: "platform-composition",    category: "runtime" as ModuleCategory,     dependencies: ["runtime-composition"] },
  { id: "platform-bootstrap",     name: "Platform Bootstrap",       package: "platform-bootstrap",      category: "runtime" as ModuleCategory,     dependencies: ["platform-composition"] },
  { id: "cortex-runtime",         name: "Cortex Runtime",           package: "cortex-runtime",          category: "runtime" as ModuleCategory,     dependencies: ["platform-bootstrap"] },
  { id: "mission-intelligence",   name: "Mission Intelligence",     package: "mission-intelligence",    category: "mission" as ModuleCategory,     dependencies: ["kernel"] },
  { id: "mission-planning",       name: "Mission Planning",         package: "mission-planning",        category: "mission" as ModuleCategory,     dependencies: ["mission-intelligence"] },
  { id: "mission-execution",      name: "Mission Execution",        package: "mission-execution",       category: "mission" as ModuleCategory,     dependencies: ["mission-planning"] },
  { id: "mission-orchestrator",   name: "Mission Orchestrator",     package: "mission-orchestrator",    category: "mission" as ModuleCategory,     dependencies: ["mission-execution"] },
  { id: "cognitive-memory",       name: "Cognitive Memory",         package: "cognitive-memory",        category: "cognitive" as ModuleCategory,   dependencies: ["kernel"] },
  { id: "knowledge-graph",        name: "Knowledge Graph",          package: "knowledge-graph",         category: "cognitive" as ModuleCategory,   dependencies: ["cognitive-memory"] },
  { id: "world-state",            name: "World State",              package: "world-state",             category: "cognitive" as ModuleCategory,   dependencies: ["knowledge-graph"] },
  { id: "cognitive-orchestrator", name: "Cognitive Orchestrator",   package: "cognitive-orchestrator",  category: "cognitive" as ModuleCategory,   dependencies: ["world-state"] },
  { id: "enterprise-reasoning",   name: "Enterprise Reasoning",     package: "enterprise-reasoning",    category: "enterprise" as ModuleCategory,  dependencies: ["cognitive-orchestrator"] },
  { id: "enterprise-decision",    name: "Enterprise Decision",      package: "enterprise-decision",     category: "enterprise" as ModuleCategory,  dependencies: ["enterprise-reasoning"] },
  { id: "execution-readiness",    name: "Execution Readiness",      package: "execution-readiness",     category: "enterprise" as ModuleCategory,  dependencies: ["enterprise-decision"] },
  { id: "executive-coordination", name: "Executive Coordination",   package: "executive-coordination",  category: "enterprise" as ModuleCategory,  dependencies: ["execution-readiness"] },
  { id: "governance",             name: "Governance",               package: "governance",              category: "enterprise" as ModuleCategory,  dependencies: ["executive-coordination"] },
  { id: "observability",          name: "Observability",            package: "observability",           category: "enterprise" as ModuleCategory,  dependencies: ["executive-coordination"] },
  { id: "analytics",              name: "Analytics",                package: "analytics",               category: "enterprise" as ModuleCategory,  dependencies: ["observability"] },
  { id: "integration-fabric",     name: "Integration Fabric",       package: "integration-fabric",      category: "integration" as ModuleCategory, dependencies: ["connector-framework"] },
  { id: "connectors",             name: "Connectors",               package: "connectors",              category: "connector" as ModuleCategory,   dependencies: ["integration-fabric"] },
  { id: "browser-worker",         name: "Browser Worker",           package: "browser-worker",          category: "worker" as ModuleCategory,      dependencies: ["worker-framework"] },
  { id: "voice-worker",           name: "Voice Worker",             package: "voice-worker",            category: "worker" as ModuleCategory,      dependencies: ["worker-framework"] },
  { id: "intelligence-worker",    name: "Intelligence Worker",      package: "intelligence-worker",     category: "worker" as ModuleCategory,      dependencies: ["worker-framework"] },
]

const modules = new Map<string, PlatformModuleRecord>()

export const PlatformRegistry = {
  async registerAll(): Promise<PlatformModuleRecord[]> {
    modules.clear()
    const records: PlatformModuleRecord[] = moduleDefinitions.map((def) => ({
      ...def,
      loaded: false,
      initialized: false,
    }))
    for (const rec of records) modules.set(rec.id, rec)
    return records
  },

  async getModule(moduleId: string): Promise<PlatformModuleRecord | null> {
    return modules.get(moduleId) ?? null
  },

  async listModules(): Promise<PlatformModuleRecord[]> {
    return Array.from(modules.values())
  },

  async listByCategory(category: ModuleCategory): Promise<PlatformModuleRecord[]> {
    return Array.from(modules.values()).filter((m) => m.category === category)
  },

  async updateModule(moduleId: string, updates: Partial<PlatformModuleRecord>): Promise<PlatformModuleRecord | null> {
    const mod = modules.get(moduleId)
    if (!mod) return null
    const updated: PlatformModuleRecord = { ...mod, ...updates }
    modules.set(moduleId, updated)
    return updated
  },

  async clear(): Promise<void> {
    modules.clear()
  },
}