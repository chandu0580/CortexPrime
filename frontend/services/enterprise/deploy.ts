import axios from "axios"
import { apiUrl } from "@/lib/constants"

export interface EnvironmentItem {
  id: string
  name: string
  type: string
  url: string
  region: string
  config: Record<string, unknown>
  health: string
  current_deployment_id: string
  deployment_history: string[]
  metrics?: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface DeploymentItem {
  id: string
  workspace_id: string
  environment_id: string
  environment_name: string
  artifact_id: string
  build_id: string
  version: string
  strategy: string
  status: string
  config_override: Record<string, unknown>
  approvals_required: number
  approvals_granted: string[]
  rollback_id: string
  result: Record<string, unknown>
  log: DeployLogEntry[]
  created_at: string
  updated_at: string
  started_at: string
  completed_at: string
}

export interface DeployLogEntry {
  timestamp: string
  message: string
}

export const enterpriseDeployApi = {
  // Environments
  createEnvironment: async (payload: {
    name: string
    env_type?: string
    url?: string
    region?: string
    config?: Record<string, unknown>
  }): Promise<EnvironmentItem> => {
    const res = await axios.post(`${apiUrl}/api/engineering/environments`, payload)
    return res.data
  },

  listEnvironments: async (): Promise<{ environments: EnvironmentItem[] }> => {
    const res = await axios.get(`${apiUrl}/api/engineering/environments`)
    return res.data
  },

  getEnvironment: async (id: string): Promise<EnvironmentItem> => {
    const res = await axios.get(`${apiUrl}/api/engineering/environments/${id}`)
    return res.data
  },

  deleteEnvironment: async (id: string): Promise<void> => {
    await axios.delete(`${apiUrl}/api/engineering/environments/${id}`)
  },

  // Deployments
  createDeployment: async (payload: {
    workspace_id: string
    environment_id: string
    artifact_id?: string
    build_id?: string
    version?: string
    strategy?: string
    config_override?: Record<string, unknown>
    approvals_required?: number
  }): Promise<DeploymentItem> => {
    const res = await axios.post(`${apiUrl}/api/engineering/deployments`, payload)
    return res.data
  },

  listDeployments: async (params?: {
    workspace_id?: string
    environment_id?: string
    status?: string
    limit?: number
  }): Promise<{ deployments: DeploymentItem[] }> => {
    const searchParams = new URLSearchParams()
    if (params?.workspace_id) searchParams.set("workspace_id", params.workspace_id)
    if (params?.environment_id) searchParams.set("environment_id", params.environment_id)
    if (params?.status) searchParams.set("status", params.status)
    if (params?.limit) searchParams.set("limit", String(params.limit))
    const res = await axios.get(`${apiUrl}/api/engineering/deployments?${searchParams}`)
    return res.data
  },

  getDeployment: async (id: string): Promise<DeploymentItem> => {
    const res = await axios.get(`${apiUrl}/api/engineering/deployments/${id}`)
    return res.data
  },

  executeDeployment: async (id: string): Promise<DeploymentItem> => {
    const res = await axios.post(`${apiUrl}/api/engineering/deployments/${id}/execute`)
    return res.data
  },

  rollbackDeployment: async (id: string): Promise<DeploymentItem> => {
    const res = await axios.post(`${apiUrl}/api/engineering/deployments/${id}/rollback`)
    return res.data
  },

  approveDeployment: async (id: string, approver: string): Promise<DeploymentItem> => {
    const res = await axios.post(`${apiUrl}/api/engineering/deployments/${id}/approve`, { approver })
    return res.data
  },
}
