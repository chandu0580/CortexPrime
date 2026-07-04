import type { CapabilityDefinition, CapabilityStage } from "@/capability-framework/types"
import { CapabilityBuilder } from "@/capability-framework/CapabilityBuilder"

export class VoiceCapability {
  private definition: CapabilityDefinition

  constructor(customConfig?: Partial<CapabilityDefinition>) {
    const now = new Date().toISOString()
    this.definition = {
      id: customConfig?.id ?? "voice.capability",
      descriptor: {
        id: customConfig?.descriptor?.id ?? "voice.capability",
        name: customConfig?.descriptor?.name ?? "Voice Capability",
        type: customConfig?.descriptor?.type ?? "voice",
        version: customConfig?.descriptor?.version ?? "1.0.0",
        description: customConfig?.descriptor?.description ?? "Deterministic voice execution capability for input processing, output generation, and session management",
        category: customConfig?.descriptor?.category ?? "execution",
        tags: customConfig?.descriptor?.tags ?? ["voice", "execution", "session"],
        icon: customConfig?.descriptor?.icon ?? "mic",
        provider: customConfig?.descriptor?.provider ?? "cortexprime",
        status: customConfig?.descriptor?.status ?? "active",
        createdAt: now,
        updatedAt: now,
      },
      stages: customConfig?.stages ?? this.createDefaultStages(),
      requirements: customConfig?.requirements ?? [
        { id: "req.audio.hardware", type: "hardware", key: "audio_device", value: "required", description: "Audio device for voice capture and playback", optional: false, validationHint: "Ensure microphone and speaker are available" },
        { id: "req.permission.audio", type: "permission", key: "audio_capture", value: "required", description: "Permission to capture audio input", optional: false, validationHint: "Grant microphone permission" },
      ],
      constraints: customConfig?.constraints ?? [
        { id: "con.rate.session", type: "rate_limit", key: "sessions_per_minute", value: 10, description: "Maximum voice sessions per minute", operator: "lte", severity: "error" },
        { id: "con.concurrency", type: "concurrency", key: "max_concurrent_sessions", value: 5, description: "Maximum concurrent voice sessions", operator: "lte", severity: "error" },
      ],
      policies: customConfig?.policies ?? [
        { id: "pol.voice.default", name: "Default Voice Allow", description: "Default allow policy for voice operations", effect: "allow", resource: "voice:*", actions: ["*"], conditions: {}, priority: 0, enabled: true },
      ],
      configuration: customConfig?.configuration ?? {
        settings: { sampleRate: 16000, encoding: "pcm_s16le", channels: 1 },
        defaults: { language: "en-US", inputTimeoutMs: 10000, silenceTimeoutMs: 1500 },
        overrides: {},
        environment: {},
        features: { streaming: true, vad: true, interruption: false },
        timeouts: { input: 10000, output: 15000, session: 300000 },
        limits: { maxSessionDurationMs: 300000, maxTurnDurationMs: 30000, maxConcurrentSessions: 5 },
      },
      dependencies: customConfig?.dependencies ?? [],
      metadata: customConfig?.metadata ?? {
        displayName: "Voice Capability",
        description: "Deterministic voice execution capability",
        category: "execution",
        tags: ["voice", "execution"],
        provider: "cortexprime",
        homepage: "",
        documentation: "",
        license: "",
        maintainers: [],
        changelog: ["1.0.0 - Initial voice capability definition"],
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
      { id: "voice.setup", name: "Setup Voice Session", description: "Initialize voice session resources", type: "setup", order: 1, timeoutMs: 5000, maxRetries: 1, inputKeys: ["sessionId", "config"], outputKeys: ["sessionReady"], required: true, tags: ["setup", "session"] },
      { id: "voice.input", name: "Process Voice Input", description: "Validate and process incoming voice input", type: "execute", order: 2, timeoutMs: 15000, maxRetries: 2, inputKeys: ["transcript", "language"], outputKeys: ["processedInput"], required: true, tags: ["input", "processing"] },
      { id: "voice.output", name: "Generate Voice Output", description: "Prepare and validate voice output", type: "execute", order: 3, timeoutMs: 15000, maxRetries: 2, inputKeys: ["text"], outputKeys: ["processedOutput"], required: true, tags: ["output", "processing"] },
      { id: "voice.cleanup", name: "Cleanup Voice Session", description: "Release voice session resources", type: "cleanup", order: 4, timeoutMs: 5000, maxRetries: 1, inputKeys: ["sessionId"], outputKeys: ["sessionClosed"], required: true, tags: ["cleanup", "session"] },
    ]
  }

  async buildExecutionPlan(): Promise<CapabilityStage[]> {
    return CapabilityBuilder.buildExecutionPlan(this.definition.id)
  }
}
