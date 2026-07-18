import type { PipelineRun, PipelineCreateRequest, PipelineDashboardStats, PatchToPrRequest, PatchToPrResult } from "@/types/pipeline"

const BASE = "/api/pipeline"

async function fetchJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  })
  if (!res.ok) {
    const body = await res.text()
    throw new Error(`Pipeline API ${res.status}: ${body}`)
  }
  return res.json()
}

export async function listPipelines(status = "", limit = 50): Promise<PipelineRun[]> {
  const params = new URLSearchParams()
  if (status) params.set("status", status)
  params.set("limit", String(limit))
  const data = await fetchJSON<{ pipelines?: PipelineRun[] } | PipelineRun[]>(`${BASE}/pipelines?${params}`)
  return Array.isArray(data) ? data : (data as { pipelines: PipelineRun[] }).pipelines ?? []
}

export async function createPipeline(req: PipelineCreateRequest): Promise<PipelineRun> {
  const params = new URLSearchParams()
  if (req.name) params.set("name", req.name)
  if (req.description) params.set("description", req.description)
  if (req.mission_id) params.set("mission_id", req.mission_id)
  if (req.repo_url) params.set("repo_url", req.repo_url)
  if (req.workspace_id) params.set("workspace_id", req.workspace_id)
  if (req.sandbox_id) params.set("sandbox_id", req.sandbox_id)
  if (req.trigger_policy_id) params.set("trigger_policy_id", req.trigger_policy_id)
  return fetchJSON<PipelineRun>(`${BASE}/pipelines?${params}`, { method: "POST" })
}

export async function getPipeline(pipeline_id: string): Promise<PipelineRun> {
  return fetchJSON<PipelineRun>(`${BASE}/pipelines/${pipeline_id}`)
}

export async function deletePipeline(pipeline_id: string): Promise<void> {
  await fetchJSON(`${BASE}/pipelines/${pipeline_id}`, { method: "DELETE" })
}

export async function startPipeline(pipeline_id: string): Promise<{ status: string; pipeline: PipelineRun }> {
  return fetchJSON(`${BASE}/pipelines/${pipeline_id}/start`, { method: "POST" })
}

export async function pausePipeline(pipeline_id: string): Promise<{ status: string; pipeline: PipelineRun }> {
  return fetchJSON(`${BASE}/pipelines/${pipeline_id}/pause`, { method: "POST" })
}

export async function resumePipeline(pipeline_id: string): Promise<{ status: string; pipeline: PipelineRun }> {
  return fetchJSON(`${BASE}/pipelines/${pipeline_id}/resume`, { method: "POST" })
}

export async function cancelPipeline(pipeline_id: string): Promise<{ status: string; pipeline: PipelineRun }> {
  return fetchJSON(`${BASE}/pipelines/${pipeline_id}/cancel`, { method: "POST" })
}

export async function patchToPr(req: PatchToPrRequest): Promise<{ status: string } & PatchToPrResult> {
  const params = new URLSearchParams()
  params.set("repo_url", req.repo_url)
  params.set("plan_id", req.plan_id)
  params.set("candidate_id", req.candidate_id)
  if (req.branch_name) params.set("branch_name", req.branch_name)
  if (req.mission_id) params.set("mission_id", req.mission_id)
  if (req.commit_description) params.set("commit_description", req.commit_description)
  if (req.pr_title) params.set("pr_title", req.pr_title)
  if (req.reviewers?.length) params.set("reviewers", JSON.stringify(req.reviewers))
  if (req.labels?.length) params.set("labels", JSON.stringify(req.labels))
  return fetchJSON(`${BASE}/patch-to-pr?${params}`, { method: "POST" })
}

export async function getPipelineDashboard(): Promise<PipelineDashboardStats> {
  return fetchJSON<PipelineDashboardStats>(`${BASE}/dashboard`)
}
