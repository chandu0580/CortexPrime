import axios from "axios"
import { apiUrl } from "@/lib/constants"

export interface BuildItem {
  id: string
  workspace_id: string
  branch: string
  commit_hash: string
  status: string
  steps: string[]
  current_step: string
  progress: number
  environment: Record<string, string>
  trigger: string
  patches: string[]
  artifacts: BuildArtifact[]
  log: BuildLogEntry[]
  result: Record<string, unknown>
  created_at: string
  updated_at: string
  started_at: string
  completed_at: string
}

export interface BuildArtifact {
  id: string
  name: string
  path: string
  size_bytes: number
  type: string
  metadata: Record<string, unknown>
  created_at: string
}

export interface BuildLogEntry {
  timestamp: string
  message: string
}

export const enterpriseBuildApi = {
  create: async (payload: {
    workspace_id: string
    branch?: string
    commit_hash?: string
    steps?: string[]
    environment?: Record<string, string>
    trigger?: string
    patches?: string[]
  }): Promise<BuildItem> => {
    const res = await axios.post(`${apiUrl}/api/engineering/builds`, payload)
    return res.data
  },

  list: async (workspace_id?: string, status?: string, limit?: number): Promise<{ builds: BuildItem[] }> => {
    const params = new URLSearchParams()
    if (workspace_id) params.set("workspace_id", workspace_id)
    if (status) params.set("status", status)
    if (limit) params.set("limit", String(limit))
    const res = await axios.get(`${apiUrl}/api/engineering/builds?${params}`)
    return res.data
  },

  getById: async (id: string): Promise<BuildItem> => {
    const res = await axios.get(`${apiUrl}/api/engineering/builds/${id}`)
    return res.data
  },

  execute: async (id: string): Promise<BuildItem> => {
    const res = await axios.post(`${apiUrl}/api/engineering/builds/${id}/execute`)
    return res.data
  },

  cancel: async (id: string): Promise<BuildItem> => {
    const res = await axios.post(`${apiUrl}/api/engineering/builds/${id}/cancel`)
    return res.data
  },

  addArtifact: async (id: string, payload: {
    name: string
    path: string
    size_bytes?: number
    artifact_type?: string
    metadata?: Record<string, unknown>
  }) => {
    const res = await axios.post(`${apiUrl}/api/engineering/builds/${id}/artifacts`, payload)
    return res.data
  },

  addLog: async (id: string, message: string) => {
    const res = await axios.post(`${apiUrl}/api/engineering/builds/${id}/log`, { message })
    return res.data
  },
}
