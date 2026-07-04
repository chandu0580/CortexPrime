import { type RuntimePipeline, type RuntimeStage, RuntimeState } from "./types"
import { generateId } from "./shared"
import { RuntimeLoader } from "./RuntimeLoader"
import { RuntimeInitializer } from "./RuntimeInitializer"

const stagesConfig = [
  { name: "Precheck", order: 0 },
  { name: "Load", order: 1 },
  { name: "Initialize", order: 2 },
  { name: "Compose", order: 3 },
  { name: "Activate", order: 4 },
  { name: "Verify", order: 5 },
]

let pipelineData: RuntimePipeline | null = null

export const RuntimeStartupPipeline = {
  async execute(): Promise<RuntimePipeline> {
    const stages: RuntimeStage[] = stagesConfig.map((cfg) => ({
      id: generateId("stage"),
      name: cfg.name,
      order: cfg.order,
      state: RuntimeState.PENDING as RuntimeState,
      startedAt: null,
      completedAt: null,
      durationMs: 0,
    }))

    pipelineData = {
      id: generateId("pipeline"),
      stages,
      currentStage: null,
      state: RuntimeState.PREFLIGHT as RuntimeState,
      startedAt: new Date().toISOString(),
      completedAt: null,
    }

    const order = await RuntimeLoader.determineStartupOrder()

    for (const stage of stages) {
      pipelineData.currentStage = stage.name
      stage.state = RuntimeState.LOADING as RuntimeState
      stage.startedAt = new Date().toISOString()

      const start = Date.now()
      if (stage.name === "Precheck") {
        const missing = await RuntimeLoader.detectMissingModules()
        if (missing.length > 0) {
          stage.state = RuntimeState.FAILED as RuntimeState
        }
      } else if (stage.name === "Load") {
        await RuntimeLoader.loadModules()
      } else if (stage.name === "Initialize") {
        await RuntimeInitializer.initializeAll(order)
      } else if (stage.name === "Compose") {
        await RuntimeInitializer.activateAll(order)
      } else if (stage.name === "Activate") {
        await RuntimeInitializer.activateAll(order)
      } else if (stage.name === "Verify") {
        const { initialized, total } = await RuntimeInitializer.getProgress()
        if (initialized < total) stage.state = RuntimeState.FAILED as RuntimeState
      }

      stage.durationMs = Date.now() - start
      if (stage.state !== RuntimeState.FAILED) {
        stage.state = RuntimeState.ACTIVE as RuntimeState
      }
      stage.completedAt = new Date().toISOString()
    }

    pipelineData.state = RuntimeState.ACTIVE as RuntimeState
    pipelineData.completedAt = new Date().toISOString()
    return pipelineData
  },

  async getPipeline(): Promise<RuntimePipeline | null> {
    return pipelineData
  },

  async getCompletion(): Promise<{ completed: boolean; progress: number }> {
    if (!pipelineData) return { completed: false, progress: 0 }
    const done = pipelineData.stages.filter((s) => s.state === RuntimeState.ACTIVE).length
    return { completed: done === pipelineData.stages.length, progress: done / pipelineData.stages.length }
  },
}