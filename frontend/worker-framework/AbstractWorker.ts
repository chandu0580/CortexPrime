import type { PlatformContext, PlatformCapability, PlatformMetadata } from "@/platform/contracts"
import type { IWorker, IKernel, IEventBus, ITelemetry, IExecutionResult } from "@/platform/interfaces"
import type { WorkerDescriptor, WorkerConfiguration, WorkerState, WorkerLifecycle, WorkerHealth, WorkerMetrics } from "./types"
import { WorkerLifecycleManager } from "./WorkerLifecycleManager"
import { WorkerContextManager } from "./WorkerContextManager"
import { WorkerHealthManager } from "./WorkerHealthManager"
import { WorkerHeartbeatManager } from "./WorkerHeartbeatManager"
import { WorkerConfigurationManager } from "./WorkerConfigurationManager"
import { WorkerMetricsCollector } from "./WorkerMetricsCollector"

export abstract class AbstractWorker implements IWorker {
  protected state: WorkerState = "CREATED"
  protected lifecycle: WorkerLifecycle
  protected tasksCompleted: number = 0
  protected tasksFailed: number = 0
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null
  private healthTimer: ReturnType<typeof setInterval> | null = null

  constructor(
    protected readonly descriptor: WorkerDescriptor,
    protected readonly config: WorkerConfiguration,
    protected readonly kernel: IKernel,
    protected readonly eventBus: IEventBus,
    protected readonly telemetry: ITelemetry,
  ) {
    this.lifecycle = {
      state: "CREATED",
      previousState: null,
      transitions: [],
      startedAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      completedAt: null,
    }
  }

  getId(): string {
    return this.descriptor.id
  }

  getName(): string {
    return this.descriptor.name
  }

  getCapabilities(): PlatformCapability[] {
    return [...this.descriptor.capabilities]
  }

  getStatus(): string {
    return this.state
  }

  async getWorkerMetadata(): Promise<PlatformMetadata> {
    return {
      key: `worker.${this.descriptor.id}`,
      value: `${this.descriptor.name} v${this.descriptor.version}`,
      tags: [this.descriptor.type, this.state],
      createdAt: this.lifecycle.startedAt,
    }
  }

  abstract execute(taskId: string, payload: Record<string, unknown>, context: PlatformContext): Promise<IExecutionResult>

  async cancel(): Promise<void> {
    await this.stop()
  }

  async register(): Promise<void> {
    await this.transitionTo("REGISTERED")
    await this.eventBus.publish("worker", `${this.descriptor.type}.registered`, {
      workerId: this.descriptor.id,
      name: this.descriptor.name,
      state: this.state,
    })
  }

  async initialize(): Promise<void> {
    await WorkerConfigurationManager.initialize(this.descriptor.id, this.config)
    await WorkerContextManager.initialize(this.descriptor.id)
    await this.transitionTo("INITIALIZED")
    await this.telemetry.recordEvent("worker.initialized", { workerId: this.descriptor.id })
  }

  async start(): Promise<void> {
    await this.transitionTo("READY")
    await this.transitionTo("RUNNING")
    this.startHeartbeat()
    this.startHealthChecks()
    await this.eventBus.publish("worker", `${this.descriptor.type}.started`, {
      workerId: this.descriptor.id,
    })
  }

  async pause(): Promise<void> {
    this.stopTimers()
    await this.transitionTo("PAUSED")
    await this.eventBus.publish("worker", `${this.descriptor.type}.paused`, {
      workerId: this.descriptor.id,
    })
  }

  async resume(): Promise<void> {
    await this.transitionTo("READY")
    await this.transitionTo("RUNNING")
    this.startHeartbeat()
    this.startHealthChecks()
    await this.eventBus.publish("worker", `${this.descriptor.type}.resumed`, {
      workerId: this.descriptor.id,
    })
  }

  async stop(): Promise<void> {
    this.stopTimers()
    await this.transitionTo("STOPPED")
    await this.eventBus.publish("worker", `${this.descriptor.type}.stopped`, {
      workerId: this.descriptor.id,
    })
  }

  async shutdown(): Promise<void> {
    this.stopTimers()
    await this.transitionTo("SHUTDOWN")
    await this.eventBus.publish("worker", `${this.descriptor.type}.shutdown`, {
      workerId: this.descriptor.id,
    })
    await this.telemetry.recordEvent("worker.shutdown", { workerId: this.descriptor.id })
  }

  async heartbeat(): Promise<void> {
    const hb = await WorkerHeartbeatManager.record(this.descriptor.id, this.state, null)
    await WorkerContextManager.touch(this.descriptor.id)
    await this.eventBus.publish("worker", `${this.descriptor.type}.heartbeat`, {
      workerId: this.descriptor.id,
      timestamp: hb.timestamp,
      state: this.state,
    })
  }

  async health(): Promise<WorkerHealth> {
    const latestHb = await WorkerHeartbeatManager.getLatest(this.descriptor.id)
    return WorkerHealthManager.check(this.descriptor.id, this.state, latestHb?.timestamp ?? null)
  }

  async metrics(): Promise<WorkerMetrics> {
    return WorkerMetricsCollector.collect(
      this.descriptor.id,
      this.state,
      this.tasksCompleted,
      this.tasksFailed,
      this.lifecycle.startedAt,
    )
  }

  protected async transitionTo(target: WorkerState): Promise<void> {
    const lifecycle = await WorkerLifecycleManager.transition(this.state, target)
    this.state = lifecycle.state
    this.lifecycle = lifecycle
  }

  private startHeartbeat(): void {
    this.stopTimers()
    this.heartbeatTimer = setInterval(() => {
      this.heartbeat().catch((err) => {
        this.telemetry.recordError({
          code: "HEARTBEAT_FAILED",
          message: err instanceof Error ? err.message : String(err),
          module: this.descriptor.id,
          severity: "warning",
          timestamp: new Date().toISOString(),
          details: null,
          cause: null,
        })
      })
    }, this.config.heartbeatIntervalMs)
  }

  private startHealthChecks(): void {
    this.healthTimer = setInterval(async () => {
      const health = await this.health()
      if (health.status === "unhealthy" && this.config.autoRecovery) {
        await this.telemetry.recordEvent("worker.recovery", {
          workerId: this.descriptor.id,
          healthStatus: health.status,
        })
      }
    }, this.config.healthCheckIntervalMs)
  }

  private stopTimers(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer)
      this.heartbeatTimer = null
    }
    if (this.healthTimer) {
      clearInterval(this.healthTimer)
      this.healthTimer = null
    }
  }
}
