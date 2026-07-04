import { BootstrapState, BootstrapStageType } from "./types"
import { type BootstrapSequenceData, type BootstrapStage, BootstrapStrategy } from "./types"
import { generateId } from "./shared"
import { BootstrapRegistry } from "./BootstrapRegistry"

const stagesList: BootstrapStage[] = []
let sequenceData: BootstrapSequenceData | null = null

const stageOrder: BootstrapStageType[] = [BootstrapStageType.PRECHECK, BootstrapStageType.LOAD, BootstrapStageType.INITIALIZE, BootstrapStageType.CONFIGURE, BootstrapStageType.ACTIVATE, BootstrapStageType.VERIFY]

export const BootstrapSequence = {
  async buildSequence(strategy: BootstrapStrategy = BootstrapStrategy.TOPOLOGICAL): Promise<BootstrapSequenceData> {
    const modules = await BootstrapRegistry.listModules()
    stagesList.length = 0

    for (const stageType of stageOrder) {
      const stageModules = modules.filter((m) => m.stage === stageType)
      const stage: BootstrapStage = {
        id: generateId("stage"),
        type: stageType,
        label: stageType.charAt(0).toUpperCase() + stageType.slice(1),
        modules: stageModules.map((m) => m.id),
        status: BootstrapState.PENDING,
        startedAt: null,
        completedAt: null,
      }
      stagesList.push(stage)
    }

    sequenceData = {
      id: generateId("seq"),
      stages: [...stagesList],
      strategy,
      status: BootstrapState.PENDING,
      startedAt: null,
      completedAt: null,
    }
    return sequenceData
  },

  async getSequence(): Promise<BootstrapSequenceData | null> {
    return sequenceData
  },

  async updateStageStatus(stageType: BootstrapStageType, status: BootstrapState): Promise<BootstrapStage | null> {
    const stage = stagesList.find((s) => s.type === stageType)
    if (!stage) return null
    const now = new Date().toISOString()
    const updated: BootstrapStage = {
      ...stage,
      status,
      startedAt: status === BootstrapState.INITIALIZING ? now : stage.startedAt,
      completedAt: status === BootstrapState.ACTIVE ? now : stage.completedAt,
    }
    const index = stagesList.findIndex((s) => s.type === stageType)
    if (index >= 0) stagesList[index] = updated

    const completedCount = stagesList.filter((s) => s.status === BootstrapState.ACTIVE).length
    const failedCount = stagesList.filter((s) => s.status === BootstrapState.FAILED).length

    if (sequenceData) {
      sequenceData = {
        ...sequenceData,
        stages: [...stagesList],
        status: failedCount > 0 ? BootstrapState.FAILED : completedCount === stagesList.length ? BootstrapState.ACTIVE : BootstrapState.BOOTSTRAPPING,
        completedAt: completedCount === stagesList.length ? now : null,
      }
    }
    return updated
  },

  async getCompletedStages(): Promise<BootstrapStage[]> {
    return stagesList.filter((s) => s.status === BootstrapState.ACTIVE)
  },

  async rollback(): Promise<void> {
    for (const stage of [...stagesList].reverse()) {
      const index = stagesList.findIndex((s) => s.type === stage.type)
      if (index >= 0) {
        stagesList[index] = { ...stage, status: BootstrapState.PENDING, completedAt: null }
      }
      const modules = await BootstrapRegistry.listModulesByStage(stage.type)
      for (const mod of modules) {
        await BootstrapRegistry.updateModuleStatus(mod.id, BootstrapState.PENDING)
      }
    }
    if (sequenceData) {
      sequenceData = { ...sequenceData, status: BootstrapState.PENDING, completedAt: null }
    }
  },
}
