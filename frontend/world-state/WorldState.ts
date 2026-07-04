import type { IEventBus, ITelemetry } from "@/platform/interfaces"
import type { CapabilityDefinition } from "@/capability-framework/types"
import type {
  StateEntry, StateSnapshot, StateTransition,
  StateValidation, StateSynchronization, StateScope, StateChangeType,
  StateContext, StateMetrics, StateHealth, StateConfiguration,
  StateResolution, StateDiff, WorldStateRequest, StateSynchronizationStrategy,
} from "./types"
import { WorldStateManager } from "./WorldStateManager"
import { StateRegistry } from "./StateRegistry"
import { StateSnapshotManager } from "./StateSnapshotManager"
import { StateTransitionEngine } from "./StateTransitionEngine"
import { StateValidationEngine } from "./StateValidationEngine"
import { StateSynchronizationEngine } from "./StateSynchronizationEngine"
import { StatePolicyEngine } from "./StatePolicyEngine"
import { StateMetricsCollector } from "./StateMetricsCollector"
import { StateHealthManager } from "./StateHealthManager"
import { WorldStateCapability } from "./WorldStateCapability"

export class WorldState {
  private readonly systemId: string
  private readonly eventBus: IEventBus
  private readonly telemetry: ITelemetry
  private readonly capabilityDefinition: CapabilityDefinition
  private readonly config: StateConfiguration
  private initialized: boolean = false

  constructor(
    eventBus: IEventBus,
    telemetry: ITelemetry,
    config?: Partial<StateConfiguration>,
    capabilityDefinition?: CapabilityDefinition,
  ) {
    this.systemId = `world-state-${Date.now()}`
    this.eventBus = eventBus
    this.telemetry = telemetry

    const capability = new WorldStateCapability(capabilityDefinition)
    this.capabilityDefinition = capability.getDefinition()

    this.config = {
      maxEntries: 50000,
      maxSnapshotHistory: 50,
      autoSnapshotIntervalMs: 60000,
      enableAutoValidation: true,
      enableConflictDetection: true,
      defaultScope: "global",
      syncStrategy: "full",
      policies: [
        { id: "state.default.allow", name: "Default Allow", description: "Default allow for state operations", category: "authority", effect: "allow", rules: [{ field: "action", operator: "exists", value: null, message: "" }], priority: 0, enabled: true },
      ],
      ...config,
    }
  }

  async initialize(name: string = "CortexPrime World State"): Promise<void> {
    if (this.initialized) return

    await WorldStateManager.createState(name)
    await StateMetricsCollector.initialize(this.systemId)
    await StateHealthManager.initialize(this.systemId)

    for (const policy of this.config.policies) {
      await StatePolicyEngine.registerPolicy(policy)
    }

    const types = await StateRegistry.getRegisteredTypes()
    await StateMetricsCollector.setRegisteredTypes(this.systemId, types.length)

    this.initialized = true

    await this.eventBus.publish("world", "world.state.initialized", {
      systemId: this.systemId,
      name,
    })
  }

  async shutdown(): Promise<void> {
    await this.eventBus.publish("world", "world.state.shutdown", {
      systemId: this.systemId,
    })
  }

  async create(key: string, value: unknown, context: StateContext): Promise<StateEntry> {
    this.requireInitialized()

    const policyResult = await StatePolicyEngine.evaluate({
      action: "create", key, domain: context.domain, actor: context.actor, scope: context.scope,
    })
    if (!policyResult.allowed) {
      throw new Error(`Policy denied state creation: ${policyResult.reasons.join(", ")}`)
    }

    const exists = await WorldStateManager.entryExists(key)
    if (exists) throw new Error(`State entry '${key}' already exists. Use update() to modify.`)

    const transition = await StateTransitionEngine.transition(key, value, "create", context.actor, `Created state entry '${key}'`, context.metadata)
    await StateMetricsCollector.recordTransition(this.systemId, transition.durationMs)
    await StateMetricsCollector.recordEntry(this.systemId, "active")

    if (!(await StateRegistry.exists(key))) {
      await StateRegistry.register(key, typeof value, context.domain, context.scope)
    }

    await this.eventBus.publish("world", "world.state.created", {
      systemId: this.systemId, key, domain: context.domain, actor: context.actor,
    })

    const entry = await WorldStateManager.getEntry(key)
    return entry!
  }

  async update(key: string, value: unknown, context: StateContext): Promise<StateEntry> {
    this.requireInitialized()

    const policyResult = await StatePolicyEngine.evaluate({
      action: "update", key, domain: context.domain, actor: context.actor, scope: context.scope,
    })
    if (!policyResult.allowed) {
      throw new Error(`Policy denied state update: ${policyResult.reasons.join(", ")}`)
    }

    const transition = await StateTransitionEngine.transition(key, value, "update", context.actor, `Updated state entry '${key}'`, context.metadata)
    await StateMetricsCollector.recordTransition(this.systemId, transition.durationMs)

    await this.eventBus.publish("world", "world.state.updated", {
      systemId: this.systemId, key, domain: context.domain, actor: context.actor, version: transition.status,
    })

    const entry = await WorldStateManager.getEntry(key)
    return entry!
  }

  async get(key: string): Promise<StateEntry | null> {
    this.requireInitialized()
    return WorldStateManager.getEntry(key)
  }

  async remove(key: string, context: StateContext): Promise<void> {
    this.requireInitialized()

    const policyResult = await StatePolicyEngine.evaluate({
      action: "remove", key, domain: context.domain, actor: context.actor, scope: context.scope,
    })
    if (!policyResult.allowed) {
      throw new Error(`Policy denied state removal: ${policyResult.reasons.join(", ")}`)
    }

    const transition = await StateTransitionEngine.transition(key, null, "remove", context.actor, `Removed state entry '${key}'`, context.metadata)
    await StateMetricsCollector.recordTransition(this.systemId, transition.durationMs)
    await StateMetricsCollector.recordEntry(this.systemId, "deleted")

    await this.eventBus.publish("world", "world.state.removed", {
      systemId: this.systemId, key, domain: context.domain, actor: context.actor,
    })
  }

  async transition(key: string, to: unknown, type: StateChangeType, actor: string, reason: string, metadata?: Record<string, string>): Promise<StateTransition> {
    this.requireInitialized()

    const validation = await StateTransitionEngine.validateTransition(key, to, type)
    if (!validation.valid) throw new Error(validation.reason)

    const transition = await StateTransitionEngine.transition(key, to, type, actor, reason, metadata)
    await StateMetricsCollector.recordTransition(this.systemId, transition.durationMs)

    await this.eventBus.publish("world", "world.state.transitioned", {
      systemId: this.systemId, key, type, actor,
    })

    return transition
  }

  async rollback(transitionId: string): Promise<StateTransition> {
    this.requireInitialized()
    const result = await StateTransitionEngine.rollback(transitionId)

    await this.eventBus.publish("world", "world.state.rolled_back", {
      systemId: this.systemId, transitionId,
    })

    return result
  }

  async snapshot(label: string, metadata?: Record<string, string>): Promise<StateSnapshot> {
    this.requireInitialized()
    const snapshot = await StateSnapshotManager.createSnapshot(label, metadata)
    await StateMetricsCollector.recordSnapshot(this.systemId)

    await this.eventBus.publish("world", "world.state.snapshot", {
      systemId: this.systemId, snapshotId: snapshot.id, label,
    })

    return snapshot
  }

  async restoreSnapshot(snapshotId: string): Promise<void> {
    this.requireInitialized()
    await StateSnapshotManager.restoreSnapshot(snapshotId)

    await this.eventBus.publish("world", "world.state.restored", {
      systemId: this.systemId, snapshotId,
    })
  }

  async compareSnapshots(snapshotId1: string, snapshotId2: string): Promise<StateDiff[]> {
    this.requireInitialized()
    return StateSnapshotManager.compareSnapshots(snapshotId1, snapshotId2)
  }

  async listSnapshots(): Promise<StateSnapshot[]> {
    this.requireInitialized()
    return StateSnapshotManager.listSnapshots()
  }

  async synchronize(strategy?: StateSynchronizationStrategy, sourceScope?: StateScope, targetScope?: StateScope): Promise<StateSynchronization> {
    this.requireInitialized()
    const sync = await StateSynchronizationEngine.synchronize(
      strategy ?? "full", sourceScope, targetScope,
    )
    await StateMetricsCollector.recordSynchronization(this.systemId, sync.durationMs)

    await this.eventBus.publish("world", "world.state.synchronized", {
      systemId: this.systemId, entriesSynchronized: sync.entriesSynchronized,
      conflictsResolved: sync.conflictsResolved,
    })

    return sync
  }

  async reconcile(): Promise<{ reconciled: number; remainingConflicts: number }> {
    this.requireInitialized()
    const result = await StateSynchronizationEngine.reconcile()
    await StateMetricsCollector.recordResolution(this.systemId, result.reconciled)

    await this.eventBus.publish("world", "world.state.reconciled", {
      systemId: this.systemId, reconciled: result.reconciled,
      remainingConflicts: result.remainingConflicts,
    })

    return result
  }

  async resolveConflict(conflictId: string, resolvedValue: unknown, resolvedBy: string, resolution: string): Promise<StateResolution> {
    this.requireInitialized()
    const result = await StateSynchronizationEngine.resolveConflict(conflictId, resolvedValue, resolvedBy, resolution)
    await StateMetricsCollector.recordResolution(this.systemId)

    await this.eventBus.publish("world", "world.state.conflict.resolved", {
      systemId: this.systemId, conflictId, resolvedBy,
    })

    return result
  }

  async validate(): Promise<StateValidation> {
    this.requireInitialized()
    await StateMetricsCollector.recordValidation(this.systemId)

    const validation = await StateValidationEngine.validate()

    const staleEntries = await StateValidationEngine.detectStaleEntries()
    const orphanEntries = await StateValidationEngine.detectOrphanEntries()

    await StateHealthManager.recordIntegrity(this.systemId, {
      consistencyScore: validation.consistencyScore,
      staleEntries: staleEntries.length,
      orphanEntries: orphanEntries.length,
      invalidReferences: validation.invalidReferences.length,
      conflictCount: validation.conflicts.length,
      synchronizationBacklog: 0,
    })

    await StateMetricsCollector.setStaleEntries(this.systemId, staleEntries.length)
    await StateMetricsCollector.recordConflict(this.systemId, validation.conflicts.length)

    if (validation.conflicts.length > 0) {
      await this.eventBus.publish("world", "world.state.conflicts.detected", {
        systemId: this.systemId, count: validation.conflicts.length,
      })
    }

    return validation
  }

  async request(request: WorldStateRequest): Promise<unknown> {
    this.requireInitialized()
    const context: StateContext = {
      sessionId: "request",
      actor: request.actor,
      scope: request.scope ?? this.config.defaultScope,
      domain: request.domain ?? "default",
      metadata: request.metadata ?? {},
    }

    switch (request.type) {
      case "create":
        if (!request.key) throw new Error("Key is required for create")
        return this.create(request.key, request.value, context)
      case "update":
        if (!request.key) throw new Error("Key is required for update")
        return this.update(request.key, request.value, context)
      case "remove":
        if (!request.key) throw new Error("Key is required for remove")
        await this.remove(request.key, context)
        return
      case "query":
        return this.get(request.key ?? "")
      case "snapshot":
        return this.snapshot(`snapshot-${Date.now()}`)
      case "synchronize":
        return this.synchronize()
      case "validate":
        return this.validate()
      default:
        throw new Error(`Unknown request type: ${request.type}`)
    }
  }

  async queryByScope(scope: StateScope): Promise<StateEntry[]> {
    this.requireInitialized()
    return WorldStateManager.queryByScope(scope)
  }

  async queryByDomain(domain: string): Promise<StateEntry[]> {
    this.requireInitialized()
    return WorldStateManager.queryByDomain(domain)
  }

  async history(entryKey?: string): Promise<StateTransition[]> {
    this.requireInitialized()
    return StateTransitionEngine.history(entryKey)
  }

  async registerType(key: string, type: string, domain: string, scope?: StateScope, schema?: Record<string, unknown>): Promise<void> {
    this.requireInitialized()
    await StateRegistry.register(key, type, domain, scope, schema)
    const types = await StateRegistry.getRegisteredTypes()
    await StateMetricsCollector.setRegisteredTypes(this.systemId, types.length)
  }

  async metrics(): Promise<StateMetrics> {
    this.requireInitialized()
    const validation = await StateValidationEngine.validate()
    return StateMetricsCollector.collect(this.systemId, validation.consistencyScore)
  }

  async health(): Promise<StateHealth> {
    this.requireInitialized()

    const staleEntries = await StateValidationEngine.detectStaleEntries()
    const orphanEntries = await StateValidationEngine.detectOrphanEntries()
    const validation = await StateValidationEngine.validate()

    await StateHealthManager.recordIntegrity(this.systemId, {
      consistencyScore: validation.consistencyScore,
      staleEntries: staleEntries.length,
      orphanEntries: orphanEntries.length,
      invalidReferences: validation.invalidReferences.length,
      conflictCount: validation.conflicts.length,
      synchronizationBacklog: 0,
    })

    return StateHealthManager.check(this.systemId)
  }

  private requireInitialized(): void {
    if (!this.initialized) {
      throw new Error("WorldState not initialized. Call initialize() first.")
    }
  }
}
