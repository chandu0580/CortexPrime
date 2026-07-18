export interface TriggerPolicy {
  policy_id: string
  name: string
  description: string
  source: string
  event_pattern: string
  conditions: Record<string, unknown>
  mission_template: string
  requires_approval: boolean
  cooldown_seconds: number
  priority: string
  enabled: boolean
  tags: string[]
  created_at: string
  updated_at: string
}

export interface TriggerHistoryEntry {
  entry_id: string
  source: string
  event_type: string
  policy_id: string
  policy_name: string
  matched: boolean
  mission_id: string
  status: string
  payload: Record<string, unknown>
  error: string
  timestamp: string
}

export const TRIGGER_SOURCES = [
  "github", "azure_devops", "jira", "slack", "teams",
  "servicenow", "monitoring", "recommendations", "learning", "scheduler",
] as const

export type TriggerSource = typeof TRIGGER_SOURCES[number]
