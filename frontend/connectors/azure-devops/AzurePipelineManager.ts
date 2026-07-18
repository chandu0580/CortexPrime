import { AzurePipelineRun, PipelineStatus, AzureStage } from "./types"
import { AzureDevOpsClient } from "./AzureDevOpsClient"

export const AzurePipelineManager = {
  async listRuns(pipelineId: string): Promise<AzurePipelineRun[]> {
    const parts = pipelineId.split("/")
    const projectId = parts[0] ?? ""
    const pid = parts[1] ?? pipelineId
    const result = await AzureDevOpsClient.get<Record<string, unknown>>(`/${projectId}/_apis/pipelines/${pid}/runs?$top=100`)
    if (result.success && result.data?.value) {
      return (result.data.value as Record<string, unknown>[]).map((r) => mapApiRun(r, pid, projectId))
    }
    return []
  },
}

function mapApiRun(api: Record<string, unknown>, pipelineId: string, projectId: string): AzurePipelineRun {
  const repos = (api.resources as Record<string, unknown>)?.repositories as Record<string, unknown> | undefined
  const selfRef = repos?.self as Record<string, unknown> | undefined
  return {
    id: String(api.id), pipelineId, projectId, runNumber: Number(api.runNumber ?? api.run_number ?? 0),
    status: (api.state as string ?? "queued").toLowerCase() as PipelineStatus,
    triggeredBy: String((api.createdBy as Record<string, unknown>)?.displayName ?? api.triggeredBy ?? ""),
    branch: String(selfRef?.refName ?? "").replace("refs/heads/", ""),
    commitSha: String(selfRef?.version ?? api.commitSha ?? ""),
    stages: [], startedAt: String(api.createdDate ?? api.created_at ?? ""),
    completedAt: api.finishedDate as string ?? api.completedAt as string ?? null,
  }
}