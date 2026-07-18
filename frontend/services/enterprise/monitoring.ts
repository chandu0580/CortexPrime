import axios from "axios"
import { apiUrl } from "@/lib/constants"

export interface WatcherInfo {
  connector: string
  running: boolean
  poll_interval: number
  available: boolean
  status: string
}

export interface MonitoringRule {
  rule_id: string
  name: string
  description: string
  connector: string
  event_type: string
  severity: string
  conditions: Record<string, unknown>
  enabled: boolean
  business_hours: Record<string, unknown> | null
  cooldown_seconds: number
  retry_policy: Record<string, unknown>
  auto_create_mission: boolean
  mission_template: string
  requires_approval: boolean
  notification_targets: string[]
  created_at: string
  updated_at: string
}

export interface DetectedEvent {
  connector_type: string
  event_type: string
  severity: string
  title: string
  description: string
  metadata: Record<string, unknown>
  detected_at: string
}

export interface AutoMission {
  execution_id: string
  template: string
  status: string
  event_title: string
  connector: string
  rule_name: string
  severity: string
  created_at: string
}

export interface MonitoringStatistics {
  total_events: number
  total_rules: number
  enabled_rules: number
  auto_mission_rules: number
  events_by_severity: Record<string, number>
  events_by_connector: Record<string, number>
  total_missions: number
  missions_by_connector: Record<string, number>
  missions_by_template: Record<string, number>
  missions_by_severity: Record<string, number>
  active_recoveries: number
}

export interface MonitoringHealth {
  status: string
  watchers_available: number
  watchers_total: number
  rules_enabled: number
  rules_total: number
  auto_generated_missions: number
  watcher_health: Record<string, unknown>
}

export interface PollResult {
  status: string
  events_detected: number
  rules_matched: number
  missions_created: number
}

export const enterpriseMonitoringApi = {
  getWatchers: async (): Promise<{ watchers: WatcherInfo[]; total: number }> => {
    const res = await axios.get(`${apiUrl}/api/monitoring/watchers`)
    return res.data
  },

  getRules: async (): Promise<{ rules: MonitoringRule[]; total: number }> => {
    const res = await axios.get(`${apiUrl}/api/monitoring/rules`)
    return res.data
  },

  createRule: async (ruleData: Record<string, unknown>): Promise<{ rule: MonitoringRule; status: string }> => {
    const res = await axios.post(`${apiUrl}/api/monitoring/rules`, ruleData)
    return res.data
  },

  updateRule: async (ruleId: string, ruleData: Record<string, unknown>): Promise<{ rule: MonitoringRule; status: string }> => {
    const res = await axios.put(`${apiUrl}/api/monitoring/rules/${ruleId}`, ruleData)
    return res.data
  },

  deleteRule: async (ruleId: string): Promise<{ status: string; rule_id: string }> => {
    const res = await axios.delete(`${apiUrl}/api/monitoring/rules/${ruleId}`)
    return res.data
  },

  getEvents: async (limit = 100, connector?: string, severity?: string): Promise<{ events: DetectedEvent[]; total: number }> => {
    const params: Record<string, string | number> = { limit }
    if (connector) params.connector = connector
    if (severity) params.severity = severity
    const res = await axios.get(`${apiUrl}/api/monitoring/events`, { params })
    return res.data
  },

  getMissions: async (limit = 50, connector?: string): Promise<{ missions: AutoMission[]; total: number }> => {
    const params: Record<string, string | number> = { limit }
    if (connector) params.connector = connector
    const res = await axios.get(`${apiUrl}/api/monitoring/missions`, { params })
    return res.data
  },

  getStatistics: async (): Promise<MonitoringStatistics> => {
    const res = await axios.get(`${apiUrl}/api/monitoring/statistics`)
    return res.data
  },

  getHealth: async (): Promise<MonitoringHealth> => {
    const res = await axios.get(`${apiUrl}/api/monitoring/health`)
    return res.data
  },

  triggerPoll: async (connector?: string): Promise<PollResult> => {
    const params: Record<string, string> = {}
    if (connector) params.connector = connector
    const res = await axios.post(`${apiUrl}/api/monitoring/poll`, null, { params })
    return res.data
  },
}
