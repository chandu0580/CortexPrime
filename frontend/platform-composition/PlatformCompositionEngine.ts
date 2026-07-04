import type { CompositionState, CompositionValidation, CompositionMetricsData, CompositionHealthData, CompositionNode, CompositionEdge } from "./types"
import { CompositionRegistry } from "./CompositionRegistry"
import { CompositionGraph } from "./CompositionGraph"
import { CompositionLifecycle } from "./CompositionLifecycle"
import { CompositionDependencyResolver } from "./CompositionDependencyResolver"
import { CompositionContextManager } from "./CompositionContext"
import { CompositionCoordinator } from "./CompositionCoordinator"
import { CompositionValidator } from "./CompositionValidator"
import { CompositionMetrics } from "./CompositionMetrics"
import { CompositionHealth } from "./CompositionHealth"
import { cortexEventBus } from "@/event-bus/cortexEventBus"

export class PlatformCompositionEngine {
  private startTime = Date.now()
  private operationCount = 0

  registry(): typeof CompositionRegistry { return CompositionRegistry }
  graph(): typeof CompositionGraph { return CompositionGraph }
  lifecycle(): typeof CompositionLifecycle { return CompositionLifecycle }
  resolver(): typeof CompositionDependencyResolver { return CompositionDependencyResolver }
  context(): typeof CompositionContextManager { return CompositionContextManager }
  coordinator(): typeof CompositionCoordinator { return CompositionCoordinator }
  validator(): typeof CompositionValidator { return CompositionValidator }
  metrics(): typeof CompositionMetrics { return CompositionMetrics }
  health(): typeof CompositionHealth { return CompositionHealth }

  async compose(): Promise<{ nodes: CompositionNode[]; edges: CompositionEdge[] }> {
    this.operationCount++
    const result = await CompositionCoordinator.compose()
    await this.publish("composition.composed", { nodeCount: result.nodes.length, edgeCount: result.edges.length })
    return result
  }

  async initialize(): Promise<CompositionState> {
    this.operationCount++
    const state = await CompositionCoordinator.initialize()
    await this.publish("composition.initialized", { state })
    return state
  }

  async shutdown(): Promise<CompositionState> {
    this.operationCount++
    await CompositionMetrics.recordShutdownStart()
    const state = await CompositionCoordinator.shutdown()
    await this.publish("composition.shutdown", { state })
    return state
  }

  async validate(): Promise<CompositionValidation> {
    this.operationCount++
    return CompositionValidator.validateAll()
  }

  async getMetrics(): Promise<CompositionMetricsData> {
    return CompositionMetrics.collect()
  }

  async getHealth(): Promise<CompositionHealthData> {
    return CompositionHealth.check()
  }

  private async publish(event: string, data: Record<string, unknown>): Promise<void> {
    await cortexEventBus.publish("platform", "composition", `platform.${event}`, "PlatformCompositionEngine", data)
  }
}