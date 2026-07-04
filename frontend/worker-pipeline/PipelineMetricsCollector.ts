import type { PipelineMetrics, PipelineExecution } from "./types"

export const PipelineMetricsCollector = {
  async collect(pipelineId: string, executionId: string, execution: PipelineExecution): Promise<PipelineMetrics> {
    const stageDurations: Record<string, number> = {}
    let totalDurationMs = 0
    let completedStages = 0
    let failedStages = 0
    let skippedStages = 0
    let retryCount = 0
    let errorCount = 0

    for (const result of execution.stageResults) {
      stageDurations[result.stageId] = result.durationMs
      totalDurationMs += result.durationMs

      switch (result.status) {
        case "completed":
          completedStages++
          break
        case "failed":
          failedStages++
          errorCount += result.error ? 1 : 0
          break
        case "skipped":
          skippedStages++
          break
      }

      retryCount += result.retryAttempt
    }

    const totalStages = execution.stageResults.length
    const averageStageDurationMs = completedStages > 0 ? totalDurationMs / completedStages : 0
    const pipelineDurationMs = execution.completedAt
      ? new Date(execution.completedAt).getTime() - new Date(execution.startedAt).getTime()
      : Date.now() - new Date(execution.startedAt).getTime()

    return {
      pipelineId,
      executionId,
      totalStages,
      completedStages,
      failedStages,
      skippedStages,
      totalDurationMs: pipelineDurationMs,
      averageStageDurationMs,
      stageDurations,
      retryCount,
      errorCount,
      startedAt: execution.startedAt,
      collectedAt: new Date().toISOString(),
    }
  },

  async summarize(executions: PipelineExecution[]): Promise<{
    totalExecutions: number
    completedExecutions: number
    failedExecutions: number
    cancelledExecutions: number
    averageDurationMs: number
    totalStageExecutions: number
    totalErrors: number
  }> {
    const completed = executions.filter((e) => e.state === "completed")
    const failed = executions.filter((e) => e.state === "failed")
    const cancelled = executions.filter((e) => e.state === "cancelled")

    const totalDurationMs = completed.reduce((sum, e) => {
      if (e.completedAt) {
        return sum + (new Date(e.completedAt).getTime() - new Date(e.startedAt).getTime())
      }
      return sum
    }, 0)

    const totalStageExecutions = executions.reduce((sum, e) => sum + e.stageResults.length, 0)
    const totalErrors = executions.reduce((sum, e) => sum + e.stageResults.filter((r) => r.error).length, 0)

    return {
      totalExecutions: executions.length,
      completedExecutions: completed.length,
      failedExecutions: failed.length,
      cancelledExecutions: cancelled.length,
      averageDurationMs: completed.length > 0 ? totalDurationMs / completed.length : 0,
      totalStageExecutions,
      totalErrors,
    }
  },
}
