import axios from "axios"
import { apiUrl } from "@/lib/constants"
import type { TriggerPolicy, TriggerHistoryEntry } from "@/types/triggers"

export const enterpriseTriggerApi = {
  listPolicies: async (source?: string, enabled?: boolean): Promise<{ policies: TriggerPolicy[] }> => {
    const params = new URLSearchParams()
    if (source) params.set("source", source)
    if (enabled !== undefined) params.set("enabled", String(enabled))
    const res = await axios.get(`${apiUrl}/api/triggers?${params}`)
    return res.data
  },

  getSources: async (): Promise<{ sources: string[] }> => {
    const res = await axios.get(`${apiUrl}/api/triggers/sources`)
    return res.data
  },

  getHistory: async (source?: string, status?: string, limit?: number): Promise<{ history: TriggerHistoryEntry[] }> => {
    const params = new URLSearchParams()
    if (source) params.set("source", source)
    if (status) params.set("status", status)
    if (limit) params.set("limit", String(limit))
    const res = await axios.get(`${apiUrl}/api/triggers/history?${params}`)
    return res.data
  },

  getStats: async (): Promise<Record<string, unknown>> => {
    const res = await axios.get(`${apiUrl}/api/triggers/stats`)
    return res.data
  },

  createPolicy: async (payload: {
    name: string
    description?: string
    source?: string
    event_pattern?: string
    conditions?: Record<string, unknown>
    mission_template?: string
    requires_approval?: boolean
    cooldown_seconds?: number
    priority?: string
    enabled?: boolean
    tags?: string[]
  }): Promise<TriggerPolicy> => {
    const res = await axios.post(`${apiUrl}/api/triggers/policies`, payload)
    return res.data
  },

  updatePolicy: async (id: string, payload: Partial<TriggerPolicy>): Promise<TriggerPolicy> => {
    const res = await axios.put(`${apiUrl}/api/triggers/policies/${id}`, payload)
    return res.data
  },

  deletePolicy: async (id: string): Promise<void> => {
    await axios.delete(`${apiUrl}/api/triggers/policies/${id}`)
  },

  simulate: async (source: string, event_type: string, payload: Record<string, unknown>): Promise<Record<string, unknown>> => {
    const res = await axios.post(`${apiUrl}/api/triggers/simulate`, { source, event_type, payload })
    return res.data
  },
}
