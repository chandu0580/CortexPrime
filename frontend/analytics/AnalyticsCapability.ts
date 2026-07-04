import type { AnalyticsCapabilityDefinition } from "./types"
import { generateId } from "./shared"

const capabilities = new Map<string, AnalyticsCapabilityDefinition>()

const builtInCapabilities: AnalyticsCapabilityDefinition[] = [
  { id: "an-metrics", name: "analytics.metrics", description: "Metric aggregation by category, worker, and mission", version: "1.0.0", enabled: true },
  { id: "an-trends", name: "analytics.trends", description: "Trend analysis, direction detection, and window comparison", version: "1.0.0", enabled: true },
  { id: "an-kpi", name: "analytics.kpi", description: "KPI calculation, threshold evaluation, and ranking", version: "1.0.0", enabled: true },
  { id: "an-reporting", name: "analytics.reporting", description: "Executive report generation with structured sections", version: "1.0.0", enabled: true },
  { id: "an-forecasting", name: "analytics.forecasting", description: "Deterministic forecast dataset preparation", version: "1.0.0", enabled: true },
  { id: "an-validation", name: "analytics.validation", description: "Analytics validation for aggregations, KPIs, trends, reports, forecasts", version: "1.0.0", enabled: true },
]

for (const cap of builtInCapabilities) {
  capabilities.set(cap.id, cap)
}

export const AnalyticsCapability = {
  async isEnabled(name: string): Promise<boolean> {
    const cap = Array.from(capabilities.values()).find((c) => c.name === name)
    return cap?.enabled ?? false
  },

  async enable(name: string): Promise<AnalyticsCapabilityDefinition> {
    const cap = Array.from(capabilities.values()).find((c) => c.name === name)
    if (!cap) throw new Error(`Capability not found: ${name}`)
    const updated: AnalyticsCapabilityDefinition = { ...cap, enabled: true }
    capabilities.set(cap.id, updated)
    return updated
  },

  async disable(name: string): Promise<AnalyticsCapabilityDefinition> {
    const cap = Array.from(capabilities.values()).find((c) => c.name === name)
    if (!cap) throw new Error(`Capability not found: ${name}`)
    const updated: AnalyticsCapabilityDefinition = { ...cap, enabled: false }
    capabilities.set(cap.id, updated)
    return updated
  },

  async register(definition: Omit<AnalyticsCapabilityDefinition, "id">): Promise<AnalyticsCapabilityDefinition> {
    const id = generateId("cap")
    const full: AnalyticsCapabilityDefinition = { ...definition, id }
    capabilities.set(id, full)
    return full
  },

  async list(): Promise<AnalyticsCapabilityDefinition[]> {
    return Array.from(capabilities.values())
  },

  async get(name: string): Promise<AnalyticsCapabilityDefinition | null> {
    return Array.from(capabilities.values()).find((c) => c.name === name) ?? null
  },
}
