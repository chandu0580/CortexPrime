import axios from "axios"
import { apiUrl } from "@/lib/constants"

export interface RepositoryInfo {
  name: string
  url: string
  default_branch: string
  active_branch: string
  languages: Record<string, number>
  frameworks: string[]
  build_system: string
  test_framework: string
  package_managers: string[]
  cicd_configs: string[]
  docker_files: string[]
  kubernetes_manifests: string[]
  services: string[]
  modules: string[]
  dependency_graph: Record<string, unknown>
  statistics: {
    total_files_detected: number
    language_count: number
    has_docker: boolean
    has_cicd: boolean
    has_tests: boolean
  }
  analyzed_at: string
}

export interface WorkspaceItem {
  id: string
  name: string
  repo_url: string
  branch: string
  status: string
  created_at: string
  updated_at: string
  locked: boolean
  locked_by: string | null
  metadata: Record<string, unknown>
  artifacts: WorkspaceArtifact[]
  snapshot: Record<string, unknown> | null
  repository: RepositoryInfo | null
  execution_history: Record<string, unknown>[]
}

export interface WorkspaceArtifact {
  id: string
  type: string
  name: string
  data: Record<string, unknown>
  created_at: string
}

export interface WorkspaceStatus {
  id: string
  name: string
  status: string
  locked: boolean
  locked_by: string | null
  branch: string
  repo_url: string
  artifact_count: number
  has_snapshot: boolean
  updated_at: string
}

export const enterpriseWorkspaceApi = {
  listRepositories: async (): Promise<{ repositories: { url: string; name: string; languages: Record<string, number>; analyzed_at: string }[]; total: number }> => {
    const res = await axios.get(`${apiUrl}/api/engineering/repositories`)
    return res.data
  },

  getRepositoryIntelligence: async (repoUrl: string, branch = "main"): Promise<RepositoryInfo> => {
    const res = await axios.get(`${apiUrl}/api/engineering/repositories/${encodeURIComponent(repoUrl)}`, { params: { branch } })
    return res.data
  },

  createWorkspace: async (name: string, repoUrl?: string, branch?: string): Promise<WorkspaceItem> => {
    const res = await axios.post(`${apiUrl}/api/engineering/workspaces`, { name, repo_url: repoUrl, branch })
    return res.data
  },

  listWorkspaces: async (status?: string): Promise<{ workspaces: WorkspaceItem[]; total: number }> => {
    const params: Record<string, string> = {}
    if (status) params.status = status
    const res = await axios.get(`${apiUrl}/api/engineering/workspaces`, { params })
    return res.data
  },

  getWorkspace: async (id: string): Promise<WorkspaceItem> => {
    const res = await axios.get(`${apiUrl}/api/engineering/workspaces/${id}`)
    return res.data
  },

  destroyWorkspace: async (id: string): Promise<{ status: string; id: string }> => {
    const res = await axios.delete(`${apiUrl}/api/engineering/workspaces/${id}`)
    return res.data
  },

  checkoutBranch: async (wsId: string, branch: string): Promise<{ workspace_id: string; previous_branch: string; current_branch: string }> => {
    const res = await axios.post(`${apiUrl}/api/engineering/workspaces/${wsId}/checkout`, {}, { params: { branch } })
    return res.data
  },

  getWorkspaceStatus: async (wsId: string): Promise<WorkspaceStatus> => {
    const res = await axios.get(`${apiUrl}/api/engineering/workspaces/${wsId}/status`)
    return res.data
  },

  getWorkspaceArtifacts: async (wsId: string): Promise<{ artifacts: WorkspaceArtifact[]; total: number }> => {
    const res = await axios.get(`${apiUrl}/api/engineering/workspaces/${wsId}/artifacts`)
    return res.data
  },

  getWorkspaceSnapshot: async (wsId: string): Promise<Record<string, unknown>> => {
    const res = await axios.get(`${apiUrl}/api/engineering/workspaces/${wsId}/snapshot`)
    return res.data
  },
}
