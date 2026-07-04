import type { PlatformContext, PlatformCapability } from "@/platform/contracts"
import type { IKernel, IEventBus, ITelemetry, IExecutionResult } from "@/platform/interfaces"
import type { WorkerConfiguration } from "@/worker-framework/types"
import type { CapabilityDefinition } from "@/capability-framework/types"
import { AbstractWorker } from "@/worker-framework/AbstractWorker"
import type { CognitiveMemory } from "@/cognitive-memory/CognitiveMemory"
import type { WorldState } from "@/world-state/WorldState"
import type { VoiceTaskPayload, VoiceMetrics, VoiceWorkerConfig } from "./types"
import { VoiceSessionManager } from "./VoiceSessionManager"
import { VoiceActivityManager } from "./VoiceActivityManager"
import { VoiceTurnManager } from "./VoiceTurnManager"
import { VoiceStreamManager } from "./VoiceStreamManager"
import { VoiceInputPipeline } from "./VoiceInputPipeline"
import { VoiceOutputPipeline } from "./VoiceOutputPipeline"
import { VoicePolicyEngine } from "./VoicePolicyEngine"
import { VoiceMetricsCollector } from "./VoiceMetricsCollector"
import { VoiceHealthManager, type VoiceHealthReport } from "./VoiceHealthManager"
import { VoiceCapability } from "./VoiceCapability"
import { LiveKitManager } from "./LiveKitManager"
import { DeepgramManager } from "./DeepgramManager"
import { ElevenLabsManager } from "./ElevenLabsManager"
import { VoiceEventBus } from "./VoiceEventBus"

const DEFAULT_VOICE_CONFIG: VoiceWorkerConfig = {
  maxInputTimeoutMs: 10_000,
  maxOutputTimeoutMs: 15_000,
  defaultLanguage: "en-US",
  defaultSampleRate: 16000,
  defaultEncoding: "pcm_s16le",
  defaultChannels: 1,
  policies: [
    { id: "voice.default.allow", name: "Default Allow", description: "Default allow for voice actions", effect: "allow", actions: ["*"], conditions: {}, priority: 0, enabled: true },
    { id: "voice.session.limit", name: "Session Limit", description: "Max concurrent sessions", effect: "deny", actions: ["create_session"], conditions: { maxConcurrent: { gte: 5 } }, priority: 100, enabled: true },
  ],
}

const DEFAULT_WORKER_CONFIG: WorkerConfiguration = {
  maxConcurrentTasks: 5,
  heartbeatIntervalMs: 15_000,
  healthCheckIntervalMs: 30_000,
  taskTimeoutMs: 120_000,
  autoRecovery: true,
  maxRetries: 3,
  settings: {},
}

const VOICE_CAPABILITIES: PlatformCapability[] = [
  { id: "voice.input", name: "Voice Input Processing", type: "voice", version: "1.0.0", features: ["validate-input", "process-transcript", "detect-activity", "deepgram-stt"], enabled: true },
  { id: "voice.output", name: "Voice Output Processing", type: "voice", version: "1.0.0", features: ["validate-output", "process-output", "finalize", "elevenlabs-tts"], enabled: true },
  { id: "voice.session", name: "Voice Session Management", type: "voice", version: "1.0.0", features: ["create-session", "close-session", "manage-state", "livekit-room"], enabled: true },
  { id: "voice.stream", name: "Voice Stream Management", type: "voice", version: "1.0.0", features: ["open-stream", "close-stream", "link-turn", "chunk-tracking"], enabled: true },
  { id: "voice.policy", name: "Voice Policy Enforcement", type: "voice", version: "1.0.0", features: ["evaluate-action", "validate-session"], enabled: true },
  { id: "voice.realtime", name: "Real-time Voice", type: "voice", version: "1.0.0", features: ["livekit", "deepgram", "elevenlabs", "streaming", "interruption"], enabled: true },
]

export class VoiceWorker extends AbstractWorker {
  private readonly voiceConfig: VoiceWorkerConfig
  private readonly capabilityDefinition: CapabilityDefinition
  private readonly inputPipeline: VoiceInputPipeline
  private readonly outputPipeline: VoiceOutputPipeline
  private readonly startedAt: string
  private readonly cognitiveMemory: CognitiveMemory | null
  private readonly worldState: WorldState | null
  private memorySessionId: string | null = null

  constructor(
    kernel: IKernel,
    eventBus: IEventBus,
    telemetry: ITelemetry,
    capabilityDefinition?: CapabilityDefinition,
    voiceConfig?: Partial<VoiceWorkerConfig>,
    cognitiveMemory?: CognitiveMemory,
    worldState?: WorldState,
  ) {
    const mergedConfig = { ...DEFAULT_VOICE_CONFIG, ...voiceConfig }

    super(
      {
        id: `voice-worker-${Date.now()}`,
        name: "Voice Worker",
        type: "voice-worker",
        version: "1.0.0",
        description: "Real-time voice execution worker for input processing, output generation, and session management with LiveKit, Deepgram, and ElevenLabs",
        capabilities: VOICE_CAPABILITIES,
        metadata: {
          language: mergedConfig.defaultLanguage,
          sampleRate: String(mergedConfig.defaultSampleRate),
          encoding: mergedConfig.defaultEncoding,
          livekit: String(!!mergedConfig.livekit),
          deepgram: String(!!mergedConfig.deepgram),
          elevenlabs: String(!!mergedConfig.elevenlabs),
        },
      },
      { ...DEFAULT_WORKER_CONFIG, settings: { voiceConfig: mergedConfig } },
      kernel,
      eventBus,
      telemetry,
    )

    this.voiceConfig = mergedConfig
    this.startedAt = new Date().toISOString()
    this.cognitiveMemory = cognitiveMemory ?? null
    this.worldState = worldState ?? null

    const capability = new VoiceCapability(capabilityDefinition)
    this.capabilityDefinition = capability.getDefinition()

    this.inputPipeline = new VoiceInputPipeline()
    this.outputPipeline = new VoiceOutputPipeline()
  }

  async register(): Promise<void> {
    await super.register()
    await VoiceMetricsCollector.initialize(this.descriptor.id)
    await VoiceHealthManager.initialize(this.descriptor.id)

    VoiceEventBus.initialize(this.eventBus)

    if (this.cognitiveMemory) {
      const memSession = await this.cognitiveMemory.createSession(this.descriptor.id, "user", this.descriptor.id)
      this.memorySessionId = memSession.id
    }

    if (this.worldState) {
      await this.worldState.create(`voice:worker:${this.descriptor.id}:status`, {
        status: "registered", startedAt: this.startedAt, workerId: this.descriptor.id,
      }, { sessionId: this.descriptor.id, actor: this.descriptor.id, scope: "global", domain: "voice", metadata: {} })
    }

    await this.eventBus.publish("voice", "voice.capability.registered", {
      workerId: this.descriptor.id,
      capabilityId: this.capabilityDefinition.id,
      stages: this.capabilityDefinition.stages.length,
    })

    for (const policy of this.voiceConfig.policies) {
      await VoicePolicyEngine.registerPolicy(policy)
    }
  }

  async initialize(): Promise<void> {
    await super.initialize()
    await this.inputPipeline.registerPipeline()
    await this.outputPipeline.registerPipeline()
    await this.inputPipeline.build()
    await this.outputPipeline.build()

    await this.eventBus.publish("voice", "voice.pipeline.initialized", {
      workerId: this.descriptor.id,
      inputPipeline: this.inputPipeline.pipelineId,
      outputPipeline: this.outputPipeline.pipelineId,
    })
  }

  async start(): Promise<void> {
    await super.start()

    if (this.worldState) {
      await this.worldState.update(`voice:worker:${this.descriptor.id}:status`, {
        status: "started", startedAt: this.startedAt, workerId: this.descriptor.id,
      }, { sessionId: this.descriptor.id, actor: this.descriptor.id, scope: "global", domain: "voice", metadata: {} })
    }

    await this.eventBus.publish("voice", "voice.worker.started", {
      workerId: this.descriptor.id,
      capabilityId: this.capabilityDefinition.id,
    })
  }

  async execute(taskId: string, payload: Record<string, unknown>, context: PlatformContext): Promise<IExecutionResult> {
    const startTime = Date.now()
    const startedAt = new Date(startTime).toISOString()

    const taskPayload = payload as VoiceTaskPayload

    try {
      switch (taskPayload.type) {
        case "process_input":
          return await this.executeProcessInput(taskId, taskPayload, context, startTime, startedAt)
        case "generate_output":
          return await this.executeGenerateOutput(taskId, taskPayload, context, startTime, startedAt)
        case "manage_stream":
          return await this.executeManageStream(taskId, taskPayload, context, startTime, startedAt)
        case "control_session":
          return await this.executeControlSession(taskId, taskPayload, context, startTime, startedAt)
        case "join_room":
          return await this.executeJoinRoom(taskId, taskPayload, context, startTime, startedAt)
        case "leave_room":
          return await this.executeLeaveRoom(taskId, taskPayload, context, startTime, startedAt)
        case "start_listening":
          return await this.executeStartListening(taskId, taskPayload, context, startTime, startedAt)
        case "stop_listening":
          return await this.executeStopListening(taskId, taskPayload, context, startTime, startedAt)
        case "start_speaking":
          return await this.executeStartSpeaking(taskId, taskPayload, context, startTime, startedAt)
        case "stop_speaking":
          return await this.executeStopSpeaking(taskId, taskPayload, context, startTime, startedAt)
        default:
          return this.createError(startedAt, "UNKNOWN_VOICE_TASK", `Unknown voice task type: ${(payload as { type?: string }).type ?? "undefined"}`)
      }
    } catch (err) {
      this.tasksFailed++
      await VoiceHealthManager.recordError(this.descriptor.id)
      await VoiceMetricsCollector.recordError(this.descriptor.id)

      const completedAt = new Date().toISOString()
      return {
        sessionId: context.sessionId,
        success: false,
        output: { taskId },
        error: {
          code: "VOICE_TASK_FAILED",
          message: err instanceof Error ? err.message : String(err),
          module: "VoiceWorker",
          severity: "error",
          timestamp: completedAt,
          details: { taskId, payloadType: (payload as { type?: string }).type ?? "unknown" },
          cause: null,
        },
        startedAt,
        completedAt,
        durationMs: Date.now() - startTime,
      }
    }
  }

  private async executeProcessInput(
    taskId: string,
    taskPayload: VoiceTaskPayload & { type: "process_input" },
    context: PlatformContext,
    startTime: number,
    startedAt: string,
  ): Promise<IExecutionResult> {
    const policyResult = await VoicePolicyEngine.validateSessionAction(taskPayload.sessionId, "process_input", { taskId })
    if (!policyResult.allowed) {
      this.tasksFailed++
      return this.createError(startedAt, "POLICY_DENIED", policyResult.reason)
    }

    const session = await VoiceSessionManager.getSession(taskPayload.sessionId)
    if (!session) {
      this.tasksFailed++
      return this.createError(startedAt, "SESSION_NOT_FOUND", `Voice session ${taskPayload.sessionId} not found`)
    }

    await VoiceSessionManager.transitionState(taskPayload.sessionId, "processing")
    await VoiceHealthManager.recordActivity(this.descriptor.id)
    await VoiceMetricsCollector.recordActivity(this.descriptor.id)

    const activity = await VoiceActivityManager.recordActivity(taskPayload.sessionId, "listening", null)
    await VoiceMetricsCollector.recordInputDuration(this.descriptor.id, taskPayload.input.durationMs)

    if (taskPayload.input.words) {
      await VoiceMetricsCollector.recordWordsTranscribed(this.descriptor.id, taskPayload.input.words.length)
    }

    await VoiceActivityManager.completeActivity(activity.id)

    const execution = await this.inputPipeline.startExecution(
      context.sessionId,
      context.correlationId,
      { taskId, input: taskPayload.input, sessionId: taskPayload.sessionId },
    )

    const advanceResult = await this.inputPipeline.advance(execution.id)

    await VoiceSessionManager.transitionState(taskPayload.sessionId, "idle")

    if (this.cognitiveMemory && this.memorySessionId) {
      await this.cognitiveMemory.storeWorking(
        this.memorySessionId,
        `voice:session:${taskPayload.sessionId}:input`,
        { input: taskPayload.input, pipelineState: advanceResult.state },
        undefined, "medium", "user", [`voice:${this.descriptor.id}`],
        { sessionId: taskPayload.sessionId, taskId },
      )
    }

    this.tasksCompleted++

    const completedAt = new Date().toISOString()
    return {
      sessionId: context.sessionId,
      success: true,
      output: {
        sessionId: taskPayload.sessionId,
        input: taskPayload.input,
        pipelineStatus: advanceResult.state,
        pipelineExecutionId: execution.id,
      },
      error: null,
      startedAt,
      completedAt,
      durationMs: Date.now() - startTime,
    }
  }

  private async executeGenerateOutput(
    taskId: string,
    taskPayload: VoiceTaskPayload & { type: "generate_output" },
    context: PlatformContext,
    startTime: number,
    startedAt: string,
  ): Promise<IExecutionResult> {
    const policyResult = await VoicePolicyEngine.validateSessionAction(taskPayload.sessionId, "generate_output", { taskId })
    if (!policyResult.allowed) {
      this.tasksFailed++
      return this.createError(startedAt, "POLICY_DENIED", policyResult.reason)
    }

    const turn = await VoiceTurnManager.getTurn(taskPayload.turnId)
    if (!turn) {
      this.tasksFailed++
      return this.createError(startedAt, "TURN_NOT_FOUND", `Voice turn ${taskPayload.turnId} not found`)
    }

    await VoiceSessionManager.transitionState(taskPayload.sessionId, "speaking")
    await VoiceHealthManager.recordActivity(this.descriptor.id)
    await VoiceMetricsCollector.recordActivity(this.descriptor.id)

    const activity = await VoiceActivityManager.recordActivity(taskPayload.sessionId, "speaking", taskPayload.turnId)

    const execution = await this.outputPipeline.startExecution(
      context.sessionId,
      context.correlationId,
      { taskId, text: taskPayload.text, sessionId: taskPayload.sessionId, turnId: taskPayload.turnId },
    )

    const advanceResult = await this.outputPipeline.advance(execution.id)

    const output = {
      text: taskPayload.text,
      streamId: null,
      startTime: startedAt,
      endTime: new Date().toISOString(),
      durationMs: Date.now() - startTime,
      interrupted: false,
      characterCount: taskPayload.text.length,
      audioDurationMs: Math.round(taskPayload.text.length * 80),
    }

    await VoiceTurnManager.completeTurn(taskPayload.turnId, output)
    await VoiceActivityManager.completeActivity(activity.id)
    await VoiceSessionManager.transitionState(taskPayload.sessionId, "idle")
    await VoiceMetricsCollector.recordOutputDuration(this.descriptor.id, output.durationMs)
    await VoiceMetricsCollector.recordCharactersSynthesized(this.descriptor.id, taskPayload.text.length)
    await VoiceMetricsCollector.recordTTSDuration(this.descriptor.id, output.durationMs)

    if (this.cognitiveMemory && this.memorySessionId) {
      await this.cognitiveMemory.storeWorking(
        this.memorySessionId,
        `voice:session:${taskPayload.sessionId}:output:${taskPayload.turnId}`,
        { text: taskPayload.text, output, pipelineState: advanceResult.state },
        undefined, "medium", "user", [`voice:${this.descriptor.id}`],
        { sessionId: taskPayload.sessionId, turnId: taskPayload.turnId, taskId },
      )
    }

    this.tasksCompleted++

    const completedAt = new Date().toISOString()
    return {
      sessionId: context.sessionId,
      success: true,
      output: {
        turnId: taskPayload.turnId,
        output,
        pipelineStatus: advanceResult.state,
        pipelineExecutionId: execution.id,
      },
      error: null,
      startedAt,
      completedAt,
      durationMs: Date.now() - startTime,
    }
  }

  private async executeManageStream(
    taskId: string,
    taskPayload: VoiceTaskPayload & { type: "manage_stream" },
    context: PlatformContext,
    startTime: number,
    startedAt: string,
  ): Promise<IExecutionResult> {
    const policyResult = await VoicePolicyEngine.validateSessionAction(taskPayload.sessionId, "manage_stream", { taskId, action: taskPayload.action })
    if (!policyResult.allowed) {
      this.tasksFailed++
      return this.createError(startedAt, "POLICY_DENIED", policyResult.reason)
    }

    let streamResult: { streamId: string; state: string }

    switch (taskPayload.action) {
      case "open": {
        const stream = await VoiceStreamManager.createStream(
          taskPayload.sessionId,
          "input",
          "raw",
          this.voiceConfig.defaultEncoding,
          this.voiceConfig.defaultSampleRate,
          this.voiceConfig.defaultChannels,
        )
        streamResult = { streamId: stream.id, state: stream.state }
        await VoiceMetricsCollector.recordStream(this.descriptor.id)
        await VoiceEventBus.publishStreamOpened(taskPayload.sessionId, stream.id, "input")
        break
      }
      case "close": {
        const stream = await VoiceStreamManager.completeStream(taskPayload.streamId)
        streamResult = { streamId: stream.id, state: stream.state }
        await VoiceEventBus.publishStreamClosed(taskPayload.sessionId, stream.id, stream.durationMs ?? 0)
        break
      }
      default:
        this.tasksFailed++
        return this.createError(startedAt, "INVALID_STREAM_ACTION", `Invalid stream action: ${taskPayload.action}`)
    }

    this.tasksCompleted++

    const completedAt = new Date().toISOString()
    return {
      sessionId: context.sessionId,
      success: true,
      output: streamResult,
      error: null,
      startedAt,
      completedAt,
      durationMs: Date.now() - startTime,
    }
  }

  private async executeControlSession(
    taskId: string,
    taskPayload: VoiceTaskPayload & { type: "control_session" },
    context: PlatformContext,
    startTime: number,
    startedAt: string,
  ): Promise<IExecutionResult> {
    const policyResult = await VoicePolicyEngine.validateSessionAction(taskPayload.sessionId, "control_session", { taskId, action: taskPayload.action })
    if (!policyResult.allowed) {
      this.tasksFailed++
      return this.createError(startedAt, "POLICY_DENIED", policyResult.reason)
    }

    const wsCtx = { sessionId: taskPayload.sessionId, actor: this.descriptor.id, scope: "session" as const, domain: "voice", metadata: {} }

    switch (taskPayload.action) {
      case "pause":
        await VoiceSessionManager.transitionStatus(taskPayload.sessionId, "paused")
        await VoiceSessionManager.transitionState(taskPayload.sessionId, "paused")
        if (this.worldState) {
          await this.worldState.update(`voice:session:${taskPayload.sessionId}:state`, "paused", wsCtx)
        }
        await VoiceEventBus.publishSessionPaused(taskPayload.sessionId)
        break
      case "resume":
        await VoiceSessionManager.transitionStatus(taskPayload.sessionId, "active")
        await VoiceSessionManager.transitionState(taskPayload.sessionId, "idle")
        if (this.worldState) {
          await this.worldState.update(`voice:session:${taskPayload.sessionId}:state`, "active", wsCtx)
        }
        await VoiceEventBus.publishSessionResumed(taskPayload.sessionId)
        break
      case "stop":
        await VoiceSessionManager.closeSession(taskPayload.sessionId)
        if (this.worldState) {
          await this.worldState.update(`voice:session:${taskPayload.sessionId}:state`, "closed", wsCtx)
        }
        if (this.cognitiveMemory && this.memorySessionId) {
          const vmSession = await VoiceSessionManager.getSession(taskPayload.sessionId)
          const turns = vmSession ? await VoiceTurnManager.getTurnsBySession(taskPayload.sessionId) : []
          await this.cognitiveMemory.storeEpisode(
            this.memorySessionId, this.descriptor.id,
            `Voice session ${taskPayload.sessionId} completed`,
            turns.map((t) => ({ id: `${t.id}-event`, timestamp: t.startedAt, type: "turn", description: `Turn ${t.turnNumber}`, data: { input: t.input, output: t.output } })),
            Date.now() - new Date(vmSession?.startedAt ?? Date.now()).getTime(),
            "medium", "user", [`voice:${this.descriptor.id}`],
            { sessionId: taskPayload.sessionId, turnCount: String(turns.length) },
          )
        }
        await VoiceEventBus.publishSessionClosed(taskPayload.sessionId)
        break
      default:
        this.tasksFailed++
        return this.createError(startedAt, "INVALID_SESSION_ACTION", `Invalid session action: ${taskPayload.action}`)
    }

    this.tasksCompleted++

    const completedAt = new Date().toISOString()
    return {
      sessionId: context.sessionId,
      success: true,
      output: {
        sessionId: taskPayload.sessionId,
        action: taskPayload.action,
      },
      error: null,
      startedAt,
      completedAt,
      durationMs: Date.now() - startTime,
    }
  }

  private async executeJoinRoom(
    taskId: string,
    taskPayload: VoiceTaskPayload & { type: "join_room" },
    context: PlatformContext,
    startTime: number,
    startedAt: string,
  ): Promise<IExecutionResult> {
    const policyResult = await VoicePolicyEngine.validateSessionAction(taskPayload.sessionId, "join_room", { taskId })
    if (!policyResult.allowed) {
      this.tasksFailed++
      return this.createError(startedAt, "POLICY_DENIED", policyResult.reason)
    }

    if (!this.voiceConfig.livekit) {
      this.tasksFailed++
      return this.createError(startedAt, "LIVEKIT_NOT_CONFIGURED", "LiveKit configuration is missing")
    }

    const room = await LiveKitManager.joinRoom(this.voiceConfig.livekit, taskPayload.roomName, taskPayload.identity)
    await VoiceSessionManager.joinLiveKitRoom(taskPayload.sessionId, room.name, room.sid)
    await VoiceMetricsCollector.recordConnection(this.descriptor.id)
    await VoiceEventBus.publishRoomJoined(taskPayload.sessionId, room.name, taskPayload.identity)

    this.tasksCompleted++

    const completedAt = new Date().toISOString()
    return {
      sessionId: context.sessionId,
      success: true,
      output: { roomName: room.name, roomSid: room.sid, state: room.state },
      error: null,
      startedAt,
      completedAt,
      durationMs: Date.now() - startTime,
    }
  }

  private async executeLeaveRoom(
    taskId: string,
    taskPayload: VoiceTaskPayload & { type: "leave_room" },
    context: PlatformContext,
    startTime: number,
    startedAt: string,
  ): Promise<IExecutionResult> {
    const policyResult = await VoicePolicyEngine.validateSessionAction(taskPayload.sessionId, "leave_room", { taskId })
    if (!policyResult.allowed) {
      this.tasksFailed++
      return this.createError(startedAt, "POLICY_DENIED", policyResult.reason)
    }

    const session = await VoiceSessionManager.getSession(taskPayload.sessionId)
    if (session?.livekitRoomName) {
      await LiveKitManager.leaveRoom(session.livekitRoomName, taskPayload.sessionId)
      await VoiceEventBus.publishRoomLeft(taskPayload.sessionId, session.livekitRoomName)
    }

    this.tasksCompleted++

    const completedAt = new Date().toISOString()
    return {
      sessionId: context.sessionId,
      success: true,
      output: { sessionId: taskPayload.sessionId, left: true },
      error: null,
      startedAt,
      completedAt,
      durationMs: Date.now() - startTime,
    }
  }

  private async executeStartListening(
    taskId: string,
    taskPayload: VoiceTaskPayload & { type: "start_listening" },
    context: PlatformContext,
    startTime: number,
    startedAt: string,
  ): Promise<IExecutionResult> {
    const policyResult = await VoicePolicyEngine.validateSessionAction(taskPayload.sessionId, "start_listening", { taskId })
    if (!policyResult.allowed) {
      this.tasksFailed++
      return this.createError(startedAt, "POLICY_DENIED", policyResult.reason)
    }

    if (!this.voiceConfig.deepgram) {
      this.tasksFailed++
      return this.createError(startedAt, "DEEPGRAM_NOT_CONFIGURED", "Deepgram configuration is missing")
    }

    const deepgramSession = await DeepgramManager.startSession(this.voiceConfig.deepgram, taskPayload.sessionId)
    await VoiceSessionManager.setDeepgramSessionId(taskPayload.sessionId, deepgramSession.id)
    await VoiceSessionManager.transitionState(taskPayload.sessionId, "listening")
    await VoiceEventBus.publishTranscriptStarted(taskPayload.sessionId)

    this.tasksCompleted++

    const completedAt = new Date().toISOString()
    return {
      sessionId: context.sessionId,
      success: true,
      output: { sessionId: taskPayload.sessionId, deepgramSessionId: deepgramSession.id, state: "listening" },
      error: null,
      startedAt,
      completedAt,
      durationMs: Date.now() - startTime,
    }
  }

  private async executeStopListening(
    taskId: string,
    taskPayload: VoiceTaskPayload & { type: "stop_listening" },
    context: PlatformContext,
    startTime: number,
    startedAt: string,
  ): Promise<IExecutionResult> {
    const policyResult = await VoicePolicyEngine.validateSessionAction(taskPayload.sessionId, "stop_listening", { taskId })
    if (!policyResult.allowed) {
      this.tasksFailed++
      return this.createError(startedAt, "POLICY_DENIED", policyResult.reason)
    }

    const session = await VoiceSessionManager.getSession(taskPayload.sessionId)
    if (session?.deepgramSessionId) {
      await DeepgramManager.stopSession(session.deepgramSessionId)
    }
    await VoiceSessionManager.transitionState(taskPayload.sessionId, "idle")
    await VoiceEventBus.publishTranscriptEnded(taskPayload.sessionId)

    this.tasksCompleted++

    const completedAt = new Date().toISOString()
    return {
      sessionId: context.sessionId,
      success: true,
      output: { sessionId: taskPayload.sessionId, stopped: true },
      error: null,
      startedAt,
      completedAt,
      durationMs: Date.now() - startTime,
    }
  }

  private async executeStartSpeaking(
    taskId: string,
    taskPayload: VoiceTaskPayload & { type: "start_speaking" },
    context: PlatformContext,
    startTime: number,
    startedAt: string,
  ): Promise<IExecutionResult> {
    const policyResult = await VoicePolicyEngine.validateSessionAction(taskPayload.sessionId, "start_speaking", { taskId })
    if (!policyResult.allowed) {
      this.tasksFailed++
      return this.createError(startedAt, "POLICY_DENIED", policyResult.reason)
    }

    if (!this.voiceConfig.elevenlabs) {
      this.tasksFailed++
      return this.createError(startedAt, "ELEVENLABS_NOT_CONFIGURED", "ElevenLabs configuration is missing")
    }

    await VoiceSessionManager.transitionState(taskPayload.sessionId, "speaking")
    await VoiceEventBus.publishTTSStarted(taskPayload.sessionId, taskPayload.turnId, taskPayload.text)

    const chunk = await ElevenLabsManager.synthesize(
      taskPayload.sessionId,
      taskPayload.text,
      this.voiceConfig.elevenlabs.voiceId,
    )

    await VoiceMetricsCollector.recordTTSDuration(this.descriptor.id, chunk.alignment?.audioDurationMs ?? 0)
    await VoiceMetricsCollector.recordCharactersSynthesized(this.descriptor.id, taskPayload.text.length)
    await VoiceEventBus.publishTTSCompleted(taskPayload.sessionId, taskPayload.turnId, chunk.alignment?.audioDurationMs ?? 0, taskPayload.text.length)

    this.tasksCompleted++

    const completedAt = new Date().toISOString()
    return {
      sessionId: context.sessionId,
      success: true,
      output: {
        sessionId: taskPayload.sessionId,
        turnId: taskPayload.turnId,
        audioDurationMs: chunk.alignment?.audioDurationMs,
        characterCount: taskPayload.text.length,
      },
      error: null,
      startedAt,
      completedAt,
      durationMs: Date.now() - startTime,
    }
  }

  private async executeStopSpeaking(
    taskId: string,
    taskPayload: VoiceTaskPayload & { type: "stop_speaking" },
    context: PlatformContext,
    startTime: number,
    startedAt: string,
  ): Promise<IExecutionResult> {
    const policyResult = await VoicePolicyEngine.validateSessionAction(taskPayload.sessionId, "stop_speaking", { taskId })
    if (!policyResult.allowed) {
      this.tasksFailed++
      return this.createError(startedAt, "POLICY_DENIED", policyResult.reason)
    }

    await VoiceSessionManager.transitionState(taskPayload.sessionId, "idle")
    await ElevenLabsManager.clearQueue(taskPayload.sessionId)
    await VoiceEventBus.publishTTSInterrupted(taskPayload.sessionId, "", "user_interrupted")

    this.tasksCompleted++

    const completedAt = new Date().toISOString()
    return {
      sessionId: context.sessionId,
      success: true,
      output: { sessionId: taskPayload.sessionId, stopped: true },
      error: null,
      startedAt,
      completedAt,
      durationMs: Date.now() - startTime,
    }
  }

  async getVoiceMetrics(): Promise<VoiceMetrics> {
    const sessions = await VoiceSessionManager.getActiveSessions()
    return VoiceMetricsCollector.collect(this.descriptor.id, sessions.length)
  }

  async getVoiceHealth(): Promise<VoiceHealthReport> {
    return VoiceHealthManager.check(this.descriptor.id)
  }

  getCapabilityDefinition(): CapabilityDefinition {
    return structuredClone(this.capabilityDefinition)
  }

  getVoiceConfig(): VoiceWorkerConfig {
    return { ...this.voiceConfig }
  }

  private createError(startedAt: string, code: string, message: string): IExecutionResult {
    const completedAt = new Date().toISOString()
    return {
      sessionId: "",
      success: false,
      output: null,
      error: {
        code,
        message,
        module: "VoiceWorker",
        severity: "error",
        timestamp: completedAt,
        details: null,
        cause: null,
      },
      startedAt,
      completedAt,
      durationMs: 0,
    }
  }
}
