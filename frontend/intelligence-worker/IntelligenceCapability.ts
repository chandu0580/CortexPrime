import type { CapabilityDefinition, CapabilityStage } from "@/capability-framework/types"

export class IntelligenceCapability {
  private definition: CapabilityDefinition

  constructor(customConfig?: Partial<CapabilityDefinition>) {
    const now = new Date().toISOString()
    this.definition = {
      id: customConfig?.id ?? "intelligence.capability",
      descriptor: {
        id: customConfig?.descriptor?.id ?? "intelligence.capability",
        name: customConfig?.descriptor?.name ?? "Intelligence Capability",
        type: customConfig?.descriptor?.type ?? "custom",
        version: customConfig?.descriptor?.version ?? "1.0.0",
        description: customConfig?.descriptor?.description ?? "Enterprise intelligence operating capability for planning, evidence analysis, insight generation, and recommendation creation",
        category: customConfig?.descriptor?.category ?? "analysis",
        tags: customConfig?.descriptor?.tags ?? ["intelligence", "analysis", "planning", "insights", "recommendations"],
        icon: customConfig?.descriptor?.icon ?? "brain",
        provider: customConfig?.descriptor?.provider ?? "cortexprime",
        status: customConfig?.descriptor?.status ?? "active",
        createdAt: now,
        updatedAt: now,
      },
      stages: customConfig?.stages ?? this.createDefaultStages(),
      requirements: customConfig?.requirements ?? [
        { id: "req.intel.storage", type: "capability", key: "evidence_storage", value: "required", description: "Storage for evidence items", optional: false, validationHint: "Ensure evidence storage is available" },
        { id: "req.intel.concurrency", type: "environment", key: "analysis_concurrency", value: "4", description: "Concurrent analysis threads", optional: true, validationHint: "Set analysis concurrency level" },
      ],
      constraints: customConfig?.constraints ?? [
        { id: "con.intel.sessions", type: "concurrency", key: "max_concurrent_sessions", value: 10, description: "Maximum concurrent intelligence sessions", operator: "lte", severity: "error" },
        { id: "con.intel.evidence", type: "resource", key: "max_evidence_per_session", value: 1000, description: "Maximum evidence items per session", operator: "lte", severity: "warning" },
      ],
      policies: customConfig?.policies ?? [
        { id: "pol.intel.default", name: "Default Intelligence Allow", description: "Default allow policy for intelligence operations", effect: "allow", resource: "intelligence:*", actions: ["*"], conditions: {}, priority: 0, enabled: true },
        { id: "pol.intel.confidence", name: "Confidence Threshold", description: "Minimum confidence threshold for insights", effect: "audit", resource: "intelligence:insight", actions: ["generate"], conditions: { minConfidence: { gte: 0.5 } }, priority: 50, enabled: true },
      ],
      configuration: customConfig?.configuration ?? {
        settings: { maxObjectivesPerPlan: 10, maxEvidencePerSession: 1000 },
        defaults: { minEvidenceForInsight: 2, minInsightsForRecommendation: 1 },
        overrides: {},
        environment: {},
        features: { deduplication: true, relationshipDetection: true, autoPrioritize: true },
        timeouts: { plan: 30000, evidence: 60000, analysis: 45000, insight: 30000, recommendation: 30000, summary: 30000 },
        limits: { maxSessions: 10, maxObjectivesPerPlan: 10, maxEvidencePerSession: 1000, maxInsightsPerSession: 200, maxRecommendationsPerSession: 100 },
      },
      dependencies: customConfig?.dependencies ?? [],
      metadata: customConfig?.metadata ?? {
        displayName: "Enterprise Intelligence Capability",
        description: "Enterprise intelligence operating layer for research, analysis, and decision support",
        category: "analysis",
        tags: ["intelligence", "analysis", "enterprise"],
        provider: "cortexprime",
        homepage: "",
        documentation: "",
        license: "",
        maintainers: [],
        changelog: ["1.0.0 - Initial intelligence capability definition"],
      },
      createdAt: now,
      updatedAt: now,
    }
  }

  getDefinition(): CapabilityDefinition {
    return structuredClone(this.definition)
  }

  async register(): Promise<void> {
    const { CapabilityRegistry } = await import("@/capability-framework/CapabilityRegistry")
    await CapabilityRegistry.register(this.definition)
  }

  private createDefaultStages(): CapabilityStage[] {
    return [
      { id: "intel.setup", name: "Setup Intelligence Session", description: "Initialize intelligence session resources", type: "setup", order: 1, timeoutMs: 5000, maxRetries: 1, inputKeys: ["sessionId", "request"], outputKeys: ["sessionReady"], required: true, tags: ["setup", "session"] },
      { id: "intel.plan", name: "Build Intelligence Plan", description: "Create execution plan with objectives and stages", type: "execute", order: 2, timeoutMs: 15000, maxRetries: 2, inputKeys: ["request"], outputKeys: ["planId", "objectives"], required: true, tags: ["planning", "execution"] },
      { id: "intel.collect", name: "Collect Evidence", description: "Register and validate evidence items", type: "execute", order: 3, timeoutMs: 30000, maxRetries: 2, inputKeys: ["planId", "sources"], outputKeys: ["evidenceIds"], required: true, tags: ["evidence", "collection"] },
      { id: "intel.analyze", name: "Analyze Evidence", description: "Score confidence and detect relationships", type: "execute", order: 4, timeoutMs: 30000, maxRetries: 2, inputKeys: ["evidenceIds"], outputKeys: ["analysisResults"], required: true, tags: ["analysis", "evidence"] },
      { id: "intel.insights", name: "Generate Insights", description: "Create insights from analyzed evidence", type: "execute", order: 5, timeoutMs: 20000, maxRetries: 2, inputKeys: ["evidenceIds", "analysisResults"], outputKeys: ["insightIds"], required: true, tags: ["insights", "generation"] },
      { id: "intel.recommendations", name: "Generate Recommendations", description: "Create recommendations from insights and evidence", type: "execute", order: 6, timeoutMs: 20000, maxRetries: 2, inputKeys: ["insightIds", "evidenceIds"], outputKeys: ["recommendationIds"], required: true, tags: ["recommendations", "generation"] },
      { id: "intel.summary", name: "Build Summary", description: "Compile findings into structured summary", type: "execute", order: 7, timeoutMs: 15000, maxRetries: 1, inputKeys: ["insightIds", "recommendationIds"], outputKeys: ["summaryId"], required: true, tags: ["summary", "finalization"] },
      { id: "intel.cleanup", name: "Cleanup Intelligence Session", description: "Release intelligence session resources", type: "cleanup", order: 8, timeoutMs: 5000, maxRetries: 1, inputKeys: ["sessionId"], outputKeys: ["sessionClosed"], required: true, tags: ["cleanup", "session"] },
    ]
  }
}
