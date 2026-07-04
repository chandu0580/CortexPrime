import { GitHubWorkflow, GitHubActionRun, WorkflowStatus } from "./types"
import { GitHubClient } from "./GitHubClient"

function mapApiWorkflow(apiWf: Record<string, unknown>, repositoryId: string): GitHubWorkflow {
  return { id: String(apiWf.id), repositoryId, name: String(apiWf.name), path: String(apiWf.path), state: (apiWf.state as GitHubWorkflow["state"]) ?? "active", createdAt: String(apiWf.created_at), updatedAt: String(apiWf.updated_at) }
}

function mapApiRun(apiRun: Record<string, unknown>, workflowId: string, repositoryId: string): GitHubActionRun {
  return { id: String(apiRun.id), workflowId, repositoryId, runNumber: Number(apiRun.run_number), status: (apiRun.status as WorkflowStatus) ?? "queued", conclusion: apiRun.conclusion as string ?? null, headBranch: String(apiRun.head_branch), headSha: String(apiRun.head_sha), triggeredBy: (apiRun.actor as Record<string, unknown>)?.login as string ?? "", startedAt: String(apiRun.created_at), completedAt: apiRun.updated_at as string ?? null }
}

export const GitHubActionManager = {
  async listWorkflows(owner: string, repo: string): Promise<GitHubWorkflow[]> {
    const result = await GitHubClient.get<Record<string, unknown>>(`/repos/${owner}/${repo}/actions/workflows?per_page=100`)
    if (result.success && result.data) {
      const workflows = (result.data as Record<string, unknown>).workflows as Record<string, unknown>[]
      return (workflows ?? []).map((w) => mapApiWorkflow(w, `${owner}/${repo}`))
    }
    return []
  },

  async getWorkflow(owner: string, repo: string, workflowId: string): Promise<GitHubWorkflow | null> {
    const result = await GitHubClient.get<Record<string, unknown>>(`/repos/${owner}/${repo}/actions/workflows/${workflowId}`)
    if (result.success && result.data) return mapApiWorkflow(result.data, `${owner}/${repo}`)
    return null
  },

  async triggerWorkflowDispatch(owner: string, repo: string, workflowId: string, ref: string, inputs?: Record<string, string>): Promise<boolean> {
    const body: Record<string, unknown> = { ref }
    if (inputs) body.inputs = inputs
    const result = await GitHubClient.post(`/repos/${owner}/${repo}/actions/workflows/${workflowId}/dispatches`, body)
    return result.success
  },

  async listRuns(owner: string, repo: string, workflowId: string): Promise<GitHubActionRun[]> {
    const result = await GitHubClient.get<Record<string, unknown>>(`/repos/${owner}/${repo}/actions/workflows/${workflowId}/runs?per_page=100`)
    if (result.success && result.data) {
      const runs = (result.data as Record<string, unknown>).workflow_runs as Record<string, unknown>[]
      return (runs ?? []).map((r) => mapApiRun(r, workflowId, `${owner}/${repo}`))
    }
    return []
  },

  async getRun(owner: string, repo: string, runId: string): Promise<GitHubActionRun | null> {
    const result = await GitHubClient.get<Record<string, unknown>>(`/repos/${owner}/${repo}/actions/runs/${runId}`)
    if (result.success && result.data) return mapApiRun(result.data, String(result.data.workflow_id), `${owner}/${repo}`)
    return null
  },
}