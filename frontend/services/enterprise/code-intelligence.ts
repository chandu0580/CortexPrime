import axios from "axios"
import { apiUrl } from "@/lib/constants"
import type { RepositoryScan, DependencyGraph, ImpactResult } from "@/types/code-intelligence"

export const enterpriseCodeApi = {
  listRepositories: async (): Promise<{ repositories: Record<string, unknown>[] }> => {
    const res = await axios.get(`${apiUrl}/api/code/repositories`)
    return res.data
  },

  scan: async (path: string): Promise<RepositoryScan> => {
    const res = await axios.post(`${apiUrl}/api/code/scan`, { path })
    return res.data
  },

  getGraph: async (repoId?: string): Promise<DependencyGraph> => {
    const params = repoId ? `?repo_id=${repoId}` : ""
    const res = await axios.get(`${apiUrl}/api/code/graph${params}`)
    return res.data
  },

  getFunctions: async (repoId?: string): Promise<{ functions: Record<string, unknown>[] }> => {
    const params = repoId ? `?repo_id=${repoId}` : ""
    const res = await axios.get(`${apiUrl}/api/code/functions${params}`)
    return res.data
  },

  getClasses: async (repoId?: string): Promise<{ classes: Record<string, unknown>[] }> => {
    const params = repoId ? `?repo_id=${repoId}` : ""
    const res = await axios.get(`${apiUrl}/api/code/classes${params}`)
    return res.data
  },

  getDependencies: async (nodeId?: string): Promise<DependencyGraph> => {
    const params = nodeId ? `?node_id=${nodeId}` : ""
    const res = await axios.get(`${apiUrl}/api/code/dependencies${params}`)
    return res.data
  },

  analyzeImpact: async (changedFile: string, repoId?: string): Promise<ImpactResult> => {
    const res = await axios.post(`${apiUrl}/api/code/impact`, { changed_file: changedFile, repo_id: repoId || "" })
    return res.data
  },
}
