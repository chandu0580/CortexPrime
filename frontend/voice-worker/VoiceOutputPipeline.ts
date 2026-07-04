import type { PlatformCapability } from "@/platform/contracts"
import type { PipelineStage } from "@/worker-pipeline/types"
import { AbstractPipeline } from "@/worker-pipeline/AbstractPipeline"

export class VoiceOutputPipeline extends AbstractPipeline {
  pipelineId = "voice-output-pipeline"
  protected pipelineName = "Voice Output Pipeline"
  protected pipelineVersion = "1.0.0"
  protected pipelineDescription = "Deterministic pipeline for voice output processing stages"
  protected pipelineTags = ["voice", "output", "processing"]
  protected pipelineTimeoutMs = 30_000
  protected pipelineMaxRetries = 2

  getCapabilities(): PlatformCapability[] {
    return [
      { id: "voice.output.validate", name: "Voice Output Validation", type: "voice", version: "1.0.0", features: ["validate-output", "check-length"], enabled: true },
      { id: "voice.output.process", name: "Voice Output Processing", type: "voice", version: "1.0.0", features: ["process-text", "format-output"], enabled: true },
      { id: "voice.output.finalize", name: "Voice Output Finalization", type: "voice", version: "1.0.0", features: ["finalize-output", "prepare-stream"], enabled: true },
    ]
  }

  async startExecution(sessionId: string, correlationId: string, variables?: Record<string, unknown>) {
    return this.createExecution(sessionId, correlationId, variables)
  }

  async build(): Promise<void> {
    const stages: PipelineStage[] = [
      {
        id: "validate_output",
        name: "Validate Output",
        description: "Validate voice output text and structure",
        pipelineId: this.pipelineId,
        dependencies: [],
        order: 1,
        timeoutMs: 5_000,
        retryCount: 0,
        maxRetries: 1,
        inputSchema: { text: "string", streamId: "string" },
        outputSchema: { valid: "boolean", normalizedText: "string" },
        tags: ["validation", "output"],
      },
      {
        id: "process_output",
        name: "Process Output",
        description: "Process and format output text for voice delivery",
        pipelineId: this.pipelineId,
        dependencies: ["validate_output"],
        order: 2,
        timeoutMs: 10_000,
        retryCount: 0,
        maxRetries: 2,
        inputSchema: { normalizedText: "string" },
        outputSchema: { processedText: "string", segments: "string[]" },
        tags: ["processing", "formatting"],
      },
      {
        id: "finalize",
        name: "Finalize Output",
        description: "Finalize output and mark stream as ready",
        pipelineId: this.pipelineId,
        dependencies: ["process_output"],
        order: 3,
        timeoutMs: 5_000,
        retryCount: 0,
        maxRetries: 1,
        inputSchema: { processedText: "string", segments: "string[]" },
        outputSchema: { finalized: "boolean", outputMetadata: "object" },
        tags: ["finalization", "output"],
      },
    ]

    for (const stage of stages) {
      await this.addStage(stage)
    }
  }
}
