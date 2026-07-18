import axios from "axios"
import { apiUrl } from "@/lib/constants"

export interface PatchFileChange {
  filename: string
  lines_added?: number
  lines_removed?: number
  added?: number
  removed?: number
  change_type?: string
  old_content?: string
  new_content?: string
}

export interface PatchItem {
  id: string
  workspace_id: string
  title: string
  description: string
  engineer: string
  branch: string
  repository_url: string
  mission_execution_id: string
  status: string
  files_changed: PatchFileChange[]
  categories: string[]
  lines_added: number
  lines_deleted: number
  directories_changed: string[]
  rollback_patch_id: string | null
  diff: Record<string, unknown> | null
  dependency_analysis: Record<string, unknown> | null
  validation_results: {
    syntax: string
    dependencies: string
    consistency: string
    conflicts: unknown[]
    risk_score: number
    warnings?: string[]
    verified: boolean
  }
  verified: boolean
  created_at: string
  updated_at: string
}

export interface DiffSummary {
  total_files: number
  total_added: number
  total_removed: number
  total_hunks: number
  files: { filename: string; added: number; removed: number }[]
}

// ── Patch Pipeline types (Sprint 72) ───────────────────────────────────

export interface PatchPlanInput {
  input_type: string
  description: string
  source?: string
  affected_areas?: string[]
  candidate_count?: number
}

export interface PatchPlanDTO {
  plan: PatchPlan
  candidates: PatchCandidateDTO[]
}

export interface PatchPlan {
  plan_id: string
  input_type: string
  source: string
  description: string
  affected_areas: string[]
  estimated_files: number
  risk: string
  required_tests: string[]
  complexity: string
  status: string
  created_at: string
}

export interface PatchCandidateDTO {
  candidate_id: string
  plan_id: string
  approach: string
  index: number
  files_changed: { path: string; lines_added: number; lines_removed: number }[]
  reasoning: string
  confidence: number
  estimated_impact: { files: number; lines_added: number; lines_removed: number }
  status: string
  validation: Record<string, unknown> | null
  score: number | null
  created_at: string
}

export interface ValidateInput {
  candidate_id: string
  sandbox_id?: string
}

export interface CompareInput {
  plan_id: string
}

export interface AnalyzeInput {
  directory: string
}

export interface ApplyRefactorInput {
  suggestion_id: string
}

export const enterprisePatchPipelineApi = {
  listPlans: async (): Promise<{ plans: PatchPlan[] }> => {
    const res = await axios.get(`${apiUrl}/api/patches/plans`)
    return res.data
  },

  listCandidates: async (planId?: string): Promise<{ candidates: PatchCandidateDTO[] }> => {
    const params: Record<string, string> = {}
    if (planId) params.plan_id = planId
    const res = await axios.get(`${apiUrl}/api/patches/candidates`, { params })
    return res.data
  },

  generate: async (payload: PatchPlanInput): Promise<PatchPlanDTO> => {
    const res = await axios.post(`${apiUrl}/api/patches/generate`, payload)
    return res.data
  },

  validate: async (payload: ValidateInput): Promise<Record<string, unknown>> => {
    const res = await axios.post(`${apiUrl}/api/patches/validate`, payload)
    return res.data
  },

  compare: async (payload: CompareInput): Promise<Record<string, unknown>> => {
    const res = await axios.post(`${apiUrl}/api/patches/compare`, payload)
    return res.data
  },

  analyzeRefactor: async (payload: AnalyzeInput): Promise<Record<string, unknown>> => {
    const res = await axios.post(`${apiUrl}/api/patches/refactor/analyze`, payload)
    return res.data
  },

  applyRefactor: async (payload: ApplyRefactorInput): Promise<Record<string, unknown>> => {
    const res = await axios.post(`${apiUrl}/api/patches/refactor/apply`, payload)
    return res.data
  },
}

export const enterprisePatchApi = {
  list: async (workspaceId?: string, status?: string): Promise<{ patches: PatchItem[]; total: number }> => {
    const params: Record<string, string> = {}
    if (workspaceId) params.workspace_id = workspaceId
    if (status) params.status = status
    const res = await axios.get(`${apiUrl}/api/engineering/patches`, { params })
    return res.data
  },

  create: async (payload: {
    workspace_id: string
    title: string
    description?: string
    engineer?: string
    branch?: string
    repository_url?: string
    mission_execution_id?: string
    files_changed?: PatchFileChange[]
    categories?: string[]
  }): Promise<PatchItem> => {
    const res = await axios.post(`${apiUrl}/api/engineering/patches`, payload)
    return res.data
  },

  getById: async (id: string): Promise<PatchItem> => {
    const res = await axios.get(`${apiUrl}/api/engineering/patches/${id}`)
    return res.data
  },

  validate: async (id: string): Promise<{ syntax: string; dependencies: string; consistency: string; conflicts: unknown[]; risk_score: number; verified: boolean }> => {
    const res = await axios.post(`${apiUrl}/api/engineering/patches/${id}/validate`)
    return res.data
  },

  rollback: async (id: string): Promise<PatchItem> => {
    const res = await axios.post(`${apiUrl}/api/engineering/patches/${id}/rollback`)
    return res.data
  },

  getDiff: async (id: string): Promise<DiffSummary> => {
    const res = await axios.get(`${apiUrl}/api/engineering/patches/${id}/diff`)
    return res.data
  },
}
