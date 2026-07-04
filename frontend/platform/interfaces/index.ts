import type { PlatformContext, PlatformCapability, PlatformError, PlatformLifecycle, PlatformMetadata } from "../contracts"

export interface IPlatformModule {
  id: string
  name: string
  version: string
  initialize(context: PlatformContext): Promise<void>
  shutdown(): Promise<void>
  getMetadata(): PlatformMetadata
}

export interface IKernel {
  createSession(context: PlatformContext): Promise<ISession>
  getSession(sessionId: string): Promise<ISession | null>
  closeSession(sessionId: string): Promise<void>
  registerModule(module: IPlatformModule): Promise<void>
  getModule(moduleId: string): Promise<IPlatformModule | null>
  getKernelMetadata(): Promise<PlatformMetadata>
}

export interface IRuntime {
  startExecution(sessionId: string): Promise<IExecutionResult>
  pauseExecution(sessionId: string): Promise<IExecutionResult>
  resumeExecution(sessionId: string): Promise<IExecutionResult>
  cancelExecution(sessionId: string): Promise<IExecutionResult>
  getExecutionState(sessionId: string): Promise<IExecutionState>
  getRuntimeMetadata(): Promise<PlatformMetadata>
}

export interface IExecutionContext {
  getContext(sessionId: string): Promise<PlatformContext>
  updateContext(sessionId: string, updates: Partial<PlatformContext>): Promise<PlatformContext>
  propagateContext(fromSessionId: string, toSessionId: string): Promise<PlatformContext>
  clearContext(sessionId: string): Promise<void>
}

export interface ITaskManager {
  createTask(sessionId: string, name: string, payload: Record<string, unknown>): Promise<string>
  assignTask(taskId: string, workerId: string): Promise<void>
  completeTask(taskId: string, result: Record<string, unknown>): Promise<void>
  cancelTask(taskId: string): Promise<void>
  getTaskStatus(taskId: string): Promise<string>
  listTasks(sessionId: string): Promise<string[]>
}

export interface IResourceManager {
  allocate(resourceType: string, amount: number, sessionId: string): Promise<string>
  release(allocationId: string): Promise<void>
  getAvailability(resourceType: string): Promise<number>
  getUsage(sessionId: string): Promise<Record<string, number>>
  getResourceMetadata(): Promise<PlatformMetadata>
}

export interface ICapabilityResolver {
  resolve(capabilityType: string, context: PlatformContext): Promise<string | null>
  getAvailableCapabilities(): Promise<PlatformCapability[]>
  isCapabilityAvailable(capabilityType: string): Promise<boolean>
  getResolverMetadata(): Promise<PlatformMetadata>
}

export interface IExecutionScheduler {
  schedule(sessionId: string, taskId: string, executeAt: string): Promise<string>
  cancelSchedule(scheduleId: string): Promise<void>
  getDueSessions(): Promise<string[]>
  getScheduleStatus(scheduleId: string): Promise<string>
  getSchedulerMetadata(): Promise<PlatformMetadata>
}

export interface IEventBus {
  publish(channel: string, eventType: string, payload: Record<string, unknown>): Promise<void>
  subscribe(channel: string, handlerName: string, handler: (event: Record<string, unknown>) => Promise<void>): Promise<string>
  unsubscribe(subscriptionId: string): Promise<void>
  getEventHistory(channel?: string): Promise<Array<{ eventType: string; timestamp: string }>>
  getBusMetadata(): Promise<PlatformMetadata>
}

export interface ITelemetry {
  recordEvent(name: string, properties: Record<string, unknown>): Promise<void>
  recordMetric(name: string, value: number, tags?: Record<string, string>): Promise<void>
  recordError(error: PlatformError): Promise<void>
  queryMetrics(query: string): Promise<Record<string, unknown>[]>
  getTelemetryMetadata(): Promise<PlatformMetadata>
}

export interface ILifecycle {
  getState(sessionId: string): Promise<PlatformLifecycle>
  transition(sessionId: string, targetState: string): Promise<PlatformLifecycle>
  getValidTransitions(sessionId: string): Promise<string[]>
  isTerminal(sessionId: string): Promise<boolean>
  getLifecycleMetadata(): Promise<PlatformMetadata>
}

export interface IWorker {
  getId(): string
  getName(): string
  getCapabilities(): PlatformCapability[]
  execute(taskId: string, payload: Record<string, unknown>, context: PlatformContext): Promise<IExecutionResult>
  cancel(): Promise<void>
  getStatus(): string
  getWorkerMetadata(): Promise<PlatformMetadata>
}

export interface ISession {
  getId(): string
  getContext(): Promise<PlatformContext>
  getState(): Promise<string>
  getLifecycle(): Promise<PlatformLifecycle>
  getErrors(): Promise<PlatformError[]>
}

export interface IExecutionPipeline {
  execute(sessionId: string, stages: string[]): Promise<IExecutionResult>
  getCurrentStage(sessionId: string): Promise<string>
  getPipelineStatus(sessionId: string): Promise<string>
  cancelPipeline(sessionId: string): Promise<void>
  getPipelineMetadata(): Promise<PlatformMetadata>
}

export interface IExecutionResult {
  sessionId: string
  success: boolean
  output: Record<string, unknown> | null
  error: PlatformError | null
  startedAt: string
  completedAt: string
  durationMs: number
}

export interface IExecutionState {
  sessionId: string
  status: string
  currentStage: string | null
  workerId: string | null
  progress: number
  startedAt: string
  updatedAt: string
}
