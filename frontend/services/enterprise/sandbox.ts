import axios from "axios"
import { apiUrl } from "@/lib/constants"
import type { Sandbox } from "@/types/sandbox"

export const enterpriseSandboxApi = {
  list: async (status?: string, language?: string): Promise<{ sandboxes: Sandbox[] }> => {
    const params = new URLSearchParams()
    if (status) params.set("status", status)
    if (language) params.set("language", language)
    const res = await axios.get(`${apiUrl}/api/sandboxes?${params}`)
    return res.data
  },

  getLanguages: async (): Promise<{ languages: string[] }> => {
    const res = await axios.get(`${apiUrl}/api/sandboxes/languages`)
    return res.data
  },

  get: async (id: string): Promise<Sandbox> => {
    const res = await axios.get(`${apiUrl}/api/sandboxes/${id}`)
    return res.data
  },

  create: async (payload: {
    name: string
    repo_url?: string
    branch?: string
    language?: string
  }): Promise<Sandbox> => {
    const res = await axios.post(`${apiUrl}/api/sandboxes`, payload)
    return res.data
  },

  prepare: async (id: string): Promise<Sandbox> => {
    const res = await axios.post(`${apiUrl}/api/sandboxes/${id}/prepare`)
    return res.data
  },

  execute: async (id: string, command?: string, language?: string, timeout?: number): Promise<Record<string, unknown>> => {
    const res = await axios.post(`${apiUrl}/api/sandboxes/${id}/execute`, {
      command: command || "",
      language: language || "",
      timeout: timeout || 300,
    })
    return res.data
  },

  pause: async (id: string): Promise<Sandbox> => {
    const res = await axios.post(`${apiUrl}/api/sandboxes/${id}/pause`)
    return res.data
  },

  resume: async (id: string): Promise<Sandbox> => {
    const res = await axios.post(`${apiUrl}/api/sandboxes/${id}/resume`)
    return res.data
  },

  destroy: async (id: string): Promise<Sandbox> => {
    const res = await axios.post(`${apiUrl}/api/sandboxes/${id}/destroy`)
    return res.data
  },

  getArtifacts: async (id: string): Promise<{ artifacts: Record<string, unknown>[] }> => {
    const res = await axios.get(`${apiUrl}/api/sandboxes/${id}/artifacts`)
    return res.data
  },

  getLogs: async (id: string): Promise<{ logs: Record<string, unknown>[] }> => {
    const res = await axios.get(`${apiUrl}/api/sandboxes/${id}/logs`)
    return res.data
  },

  getResources: async (id: string): Promise<Record<string, unknown>> => {
    const res = await axios.get(`${apiUrl}/api/sandboxes/${id}/resources`)
    return res.data
  },
}
