import type { PlatformCapability } from "@/platform/contracts"
import type { PipelineStage } from "@/worker-pipeline/types"
import { AbstractPipeline } from "@/worker-pipeline/AbstractPipeline"

export class VoiceInputPipeline extends AbstractPipeline {
  pipelineId = "voice-input-pipeline"
  protected pipelineName = "Voice Input Pipeline"
  protected pipelineVersion = "1.0.0"
  protected pipelineDescription = "Deterministic pipeline for voice input processing stages"
  protected pipelineTags = ["voice", "input", "processing"]
  protected pipelineTimeoutMs = 30_000
  protected pipelineMaxRetries = 2

  getCapabilities(): PlatformCapability[] {
    return [
      { id: "voice.input.validate", name: "Voice Input Validation", type: "voice", version: "1.0.0", features: ["validate-input", "check-format"], enabled: true },
      { id: "voice.input.process", name: "Voice Input Processing", type: "voice", version: "1.0.0", features: ["process-transcript", "detect-language"], enabled: true },
      { id: "voice.input.analyze", name: "Voice Input Analysis", type: "voice", version: "1.0.0", features: ["detect-activity", "measure-duration"], enabled: true },
    ]
  }

  async startExecution(sessionId: string, correlationId: string, variables?: Record<string, unknown>) {
    return this.createExecution(sessionId, correlationId, variables)
  }

  async build(): Promise<void> {
    const stages: PipelineStage[] = [
      {
        id: "validate_input",
        name: "Validate Input",
        description: "Validate voice input structure and format",
        pipelineId: this.pipelineId,
        dependencies: [],
        order: 1,
        timeoutMs: 5_000,
        retryCount: 0,
        maxRetries: 1,
        inputSchema: { transcript: "string", confidence: "number", language: "string" },
        outputSchema: { valid: "boolean", normalizedTranscript: "string" },
        tags: ["validation", "input"],
      },
      {
        id: "process_transcript",
        name: "Process Transcript",
        description: "Normalize and prepare transcript for downstream stages",
        pipelineId: this.pipelineId,
        dependencies: ["validate_input"],
        order: 2,
        timeoutMs: 10_000,
        retryCount: 0,
        maxRetries: 2,
        inputSchema: { normalizedTranscript: "string", language: "string" },
        outputSchema: { processedText: "string", tokens: "string[]" },
        tags: ["processing", "transcript"],
      },
      {
        id: "detect_activity",
        name: "Detect Activity",
        description: "Detect voice activity state from input characteristics",
        pipelineId: this.pipelineId,
        dependencies: ["process_transcript"],
        order: 3,
        timeoutMs: 5_000,
        retryCount: 0,
        maxRetries: 1,
        inputSchema: { processedText: "string", durationMs: "number" },
        outputSchema: { activityType: "string", confidence: "number" },
        tags: ["analysis", "activity"],
      },
      {
        id: "prepare_output",
        name: "Prepare Output",
        description: "Prepare validated input data for output stage",
        pipelineId: this.pipelineId,
        dependencies: ["detect_activity"],
        order: 4,
        timeoutMs: 5_000,
        retryCount: 0,
        maxRetries: 1,
        inputSchema: { activityType: "string", processedText: "string" },
        outputSchema: { ready: "boolean", result: "object" },
        tags: ["output", "preparation"],
      },
    ]

    for (const stage of stages) {
      await this.addStage(stage)
    }
  }
}
