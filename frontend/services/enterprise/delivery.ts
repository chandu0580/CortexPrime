import axios from "axios"
import { apiUrl } from "@/lib/constants"
import type { DeliveryItem, DeliveryArtifact, TimelineEntry, DeliveryBlueprint } from "@/types/delivery"

export const enterpriseDeliveryApi = {
  list: async (status?: string, mission?: string, limit?: number): Promise<{ deliveries: DeliveryItem[] }> => {
    const params = new URLSearchParams()
    if (status) params.set("status", status)
    if (mission) params.set("mission", mission)
    if (limit) params.set("limit", String(limit))
    const res = await axios.get(`${apiUrl}/api/delivery?${params}`)
    return res.data
  },

  getById: async (id: string): Promise<DeliveryItem> => {
    const res = await axios.get(`${apiUrl}/api/delivery/${id}`)
    return res.data
  },

  start: async (payload: {
    mission: string
    repository: string
    workspace?: string
    patch?: string
    build?: string
    artifacts?: Record<string, unknown>[]
    deployment?: string
  }): Promise<DeliveryItem> => {
    const res = await axios.post(`${apiUrl}/api/delivery/start`, payload)
    return res.data
  },

  pause: async (id: string): Promise<DeliveryItem> => {
    const res = await axios.post(`${apiUrl}/api/delivery/${id}/pause`)
    return res.data
  },

  resume: async (id: string): Promise<DeliveryItem> => {
    const res = await axios.post(`${apiUrl}/api/delivery/${id}/resume`)
    return res.data
  },

  cancel: async (id: string): Promise<DeliveryItem> => {
    const res = await axios.post(`${apiUrl}/api/delivery/${id}/cancel`)
    return res.data
  },

  rollback: async (id: string): Promise<DeliveryItem> => {
    const res = await axios.post(`${apiUrl}/api/delivery/${id}/rollback`)
    return res.data
  },

  getTimeline: async (id: string): Promise<{ delivery_id: string; total_entries: number; timeline: TimelineEntry[] }> => {
    const res = await axios.get(`${apiUrl}/api/delivery/${id}/timeline`)
    return res.data
  },

  getArtifacts: async (id: string): Promise<{ delivery_id: string; total_artifacts: number; artifacts: DeliveryArtifact[] }> => {
    const res = await axios.get(`${apiUrl}/api/delivery/${id}/artifacts`)
    return res.data
  },

  getBlueprint: async (id: string): Promise<{ delivery_id: string; blueprint: DeliveryBlueprint }> => {
    const res = await axios.get(`${apiUrl}/api/delivery/${id}/blueprint`)
    return res.data
  },

  getStats: async (): Promise<Record<string, unknown>> => {
    const res = await axios.get(`${apiUrl}/api/delivery/stats`)
    return res.data
  },
}
