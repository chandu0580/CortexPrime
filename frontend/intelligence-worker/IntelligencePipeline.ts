import type { PlatformCapability } from "@/platform/contracts"
import type { PipelineStage } from "@/worker-pipeline/types"
import { AbstractPipeline } from "@/worker-pipeline/AbstractPipeline"

export class IntelligencePipeline extends AbstractPipeline {
  pipelineId = "intelligence-pipeline"
  protected pipelineName = "Intelligence Pipeline"
  protected pipelineVersion = "1.0.0"
  protected pipelineDescription = "Deterministic pipeline for intelligence execution stages: request validation through summary finalization"
  protected pipelineTags = ["intelligence", "analysis", "planning"]
  protected pipelineTimeoutMs = 120_000
  protected pipelineMaxRetries = 3

  getCapabilities(): PlatformCapability[] {
    return [
      { id: "intelligence.request", name: "Request Validation", type: "custom", version: "1.0.0", features: ["validate-request", "parse-constraints"], enabled: true },
      { id: "intelligence.planning", name: "Intelligence Planning", type: "custom", version: "1.0.0", features: ["build-plan", "define-objectives"], enabled: true },
      { id: "intelligence.evidence", name: "Evidence Collection", type: "custom", version: "1.0.0", features: ["collect-evidence", "validate-evidence", "categorize-evidence"], enabled: true },
      { id: "intelligence.analysis", name: "Evidence Analysis", type: "custom", version: "1.0.0", features: ["analyze-evidence", "score-confidence", "detect-relationships"], enabled: true },
      { id: "intelligence.insights", name: "Insight Generation", type: "custom", version: "1.0.0", features: ["generate-insights", "prioritize-insights"], enabled: true },
      { id: "intelligence.recommendations", name: "Recommendation Generation", type: "custom", version: "1.0.0", features: ["generate-recommendations", "prioritize-recommendations"], enabled: true },
      { id: "intelligence.summary", name: "Summary Building", type: "custom", version: "1.0.0", features: ["build-summary", "finalize-report"], enabled: true },
    ]
  }

  async startExecution(sessionId: string, correlationId: string, variables?: Record<string, unknown>) {
    return this.createExecution(sessionId, correlationId, variables)
  }

  async build(): Promise<void> {
    const stages: PipelineStage[] = [
      {
        id: "validate_request",
        name: "Validate Request",
        description: "Validate intelligence request structure, type, and constraints",
        pipelineId: this.pipelineId,
        dependencies: [],
        order: 1,
        timeoutMs: 10_000,
        retryCount: 0,
        maxRetries: 1,
        inputSchema: { requestType: "string", query: "string", constraints: "string[]" },
        outputSchema: { valid: "boolean", normalizedQuery: "string" },
        tags: ["validation", "request"],
      },
      {
        id: "build_plan",
        name: "Build Plan",
        description: "Create intelligence plan with objectives and staged execution order",
        pipelineId: this.pipelineId,
        dependencies: ["validate_request"],
        order: 2,
        timeoutMs: 15_000,
        retryCount: 0,
        maxRetries: 2,
        inputSchema: { normalizedQuery: "string", requestType: "string" },
        outputSchema: { planId: "string", objectives: "object[]" },
        tags: ["planning", "execution"],
      },
      {
        id: "collect_evidence",
        name: "Collect Evidence",
        description: "Register, validate, categorize, and deduplicate evidence items",
        pipelineId: this.pipelineId,
        dependencies: ["build_plan"],
        order: 3,
        timeoutMs: 30_000,
        retryCount: 0,
        maxRetries: 2,
        inputSchema: { planId: "string", evidenceSources: "string[]" },
        outputSchema: { evidenceIds: "string[]", validatedCount: "number" },
        tags: ["evidence", "collection"],
      },
      {
        id: "analyze_evidence",
        name: "Analyze Evidence",
        description: "Score confidence, detect relationships, and categorize collected evidence",
        pipelineId: this.pipelineId,
        dependencies: ["collect_evidence"],
        order: 4,
        timeoutMs: 20_000,
        retryCount: 0,
        maxRetries: 2,
        inputSchema: { evidenceIds: "string[]" },
        outputSchema: { scored: "boolean", relationships: "object[]" },
        tags: ["analysis", "evidence"],
      },
      {
        id: "generate_insights",
        name: "Generate Insights",
        description: "Create insights from analyzed evidence with priority assignment",
        pipelineId: this.pipelineId,
        dependencies: ["analyze_evidence"],
        order: 5,
        timeoutMs: 20_000,
        retryCount: 0,
        maxRetries: 2,
        inputSchema: { evidenceIds: "string[]", analysisResults: "object" },
        outputSchema: { insightIds: "string[]", groupedInsights: "object" },
        tags: ["insights", "generation"],
      },
      {
        id: "generate_recommendations",
        name: "Generate Recommendations",
        description: "Create deterministic recommendations from evidence and insights",
        pipelineId: this.pipelineId,
        dependencies: ["generate_insights"],
        order: 6,
        timeoutMs: 20_000,
        retryCount: 0,
        maxRetries: 2,
        inputSchema: { insightIds: "string[]", evidenceIds: "string[]" },
        outputSchema: { recommendationIds: "string[]", prioritizedList: "object[]" },
        tags: ["recommendations", "generation"],
      },
      {
        id: "build_summary",
        name: "Build Summary",
        description: "Compile findings, insights, and recommendations into structured summary",
        pipelineId: this.pipelineId,
        dependencies: ["generate_recommendations"],
        order: 7,
        timeoutMs: 15_000,
        retryCount: 0,
        maxRetries: 1,
        inputSchema: { insightIds: "string[]", recommendationIds: "string[]" },
        outputSchema: { summaryId: "string", keyFindings: "string[]" },
        tags: ["summary", "finalization"],
      },
      {
        id: "finalize",
        name: "Finalize",
        description: "Finalize intelligence execution and mark completion",
        pipelineId: this.pipelineId,
        dependencies: ["build_summary"],
        order: 8,
        timeoutMs: 10_000,
        retryCount: 0,
        maxRetries: 1,
        inputSchema: { summaryId: "string" },
        outputSchema: { finalized: "boolean", executionComplete: "boolean" },
        tags: ["finalization", "completion"],
      },
    ]

    for (const stage of stages) {
      await this.addStage(stage)
    }
  }
}
