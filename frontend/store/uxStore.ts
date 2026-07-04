import { create } from "zustand"

export type ThemeMode = "dark" | "light"
export type ContrastLevel = "normal" | "high" | "low"
export type ThemePreset = "cortex" | "minimal" | "ocean" | "sunset" | "forest"
export type FontSize = "small" | "medium" | "large"

export interface NotificationItem {
  id: string
  type: "mission_completed" | "approval_required" | "security_alert" | "worker_error" | "connector_sync" | "runtime_warning" | "replay_ready" | "deployment_success" | "certification_passed"
  title: string
  description: string
  timestamp: string
  read: boolean
  priority: "critical" | "high" | "medium" | "low"
}

export interface ActivityEvent {
  id: string
  type: "mission" | "security" | "governance" | "replay" | "memory" | "knowledge_graph" | "worker" | "connector"
  title: string
  description: string
  timestamp: string
  source: string
}

export interface Workspace {
  id: string
  label: string
  icon: string
  description: string
  pinnedWidgets: string[]
  layout: Record<string, { x: number; y: number; w: number; h: number }>
  isFavorite: boolean
}

export interface DashboardWidget {
  id: string
  type: string
  title: string
  x: number
  y: number
  w: number
  h: number
  settings?: Record<string, unknown>
}

export interface UserPrefs {
  language: string
  timezone: string
  dateFormat: string
  timeFormat: string
  notifications: Record<string, { enabled: boolean; channel: string }>
  dashboardPreferences: { showWelcome: boolean; defaultView: string; refreshInterval: number }
  workspacePreferences: { autoSwitch: boolean; rememberTabs: boolean }
}

interface UxState {
  commandCenterOpen: boolean
  notificationCenterOpen: boolean
  activityFeedOpen: boolean
  preferencesOpen: boolean
  shortcutsModalOpen: boolean
  themePanelOpen: boolean

  notifications: NotificationItem[]
  unreadCount: number

  accentColor: string
  themePreset: ThemePreset
  contrast: ContrastLevel
  fontSize: FontSize
  reducedMotion: boolean

  setCommandCenterOpen: (open: boolean) => void
  setNotificationCenterOpen: (open: boolean) => void
  setActivityFeedOpen: (open: boolean) => void
  setPreferencesOpen: (open: boolean) => void
  setShortcutsModalOpen: (open: boolean) => void
  setThemePanelOpen: (open: boolean) => void

  markNotificationRead: (id: string) => void
  markAllNotificationsRead: () => void
  addNotification: (n: NotificationItem) => void

  setAccentColor: (c: string) => void
  setThemePreset: (p: ThemePreset) => void
  setContrast: (c: ContrastLevel) => void
  setFontSize: (s: FontSize) => void
  setReducedMotion: (b: boolean) => void
}

const INITIAL_NOTIFICATIONS: NotificationItem[] = [
  { id: "n1", type: "mission_completed", title: "Research mission completed", description: "Market intelligence mission finished successfully in 24m 18s", timestamp: new Date(Date.now() - 120000).toISOString(), read: false, priority: "medium" },
  { id: "n2", type: "approval_required", title: "Approval required", description: "Deployment to production needs executive approval", timestamp: new Date(Date.now() - 300000).toISOString(), read: false, priority: "critical" },
  { id: "n3", type: "security_alert", title: "Security alert", description: "Unusual API key usage detected from new IP", timestamp: new Date(Date.now() - 600000).toISOString(), read: false, priority: "high" },
  { id: "n4", type: "worker_error", title: "Browser worker error", description: "Worker bw-004 encountered timeout on page load", timestamp: new Date(Date.now() - 900000).toISOString(), read: false, priority: "high" },
  { id: "n5", type: "connector_sync", title: "GitHub sync complete", description: "All repositories synchronized successfully", timestamp: new Date(Date.now() - 1800000).toISOString(), read: true, priority: "low" },
  { id: "n6", type: "runtime_warning", title: "High memory usage", description: "Runtime memory at 82% — consider scaling up", timestamp: new Date(Date.now() - 3600000).toISOString(), read: true, priority: "medium" },
  { id: "n7", type: "replay_ready", title: "Replay data available", description: "Enterprise replay data for exec-789 is ready for review", timestamp: new Date(Date.now() - 7200000).toISOString(), read: true, priority: "low" },
  { id: "n8", type: "deployment_success", title: "Deployment successful", description: "v3.2.1 deployed to staging environment", timestamp: new Date(Date.now() - 14400000).toISOString(), read: true, priority: "medium" },
  { id: "n9", type: "certification_passed", title: "Certification passed", description: "Full certification suite passed all 142 tests", timestamp: new Date(Date.now() - 28800000).toISOString(), read: false, priority: "medium" },
  { id: "n10", type: "mission_completed", title: "Data analysis complete", description: "Q3 financial analysis mission completed with 98% confidence", timestamp: new Date(Date.now() - 36000000).toISOString(), read: true, priority: "low" },
  { id: "n11", type: "connector_sync", title: "Jira sync delayed", description: "Jira connector sync delayed due to rate limiting", timestamp: new Date(Date.now() - 48000000).toISOString(), read: true, priority: "medium" },
  { id: "n12", type: "security_alert", title: "New user added", description: "User jane.doe@example.com was added to Engineering group", timestamp: new Date(Date.now() - 72000000).toISOString(), read: false, priority: "low" },
]

export const useUxStore = create<UxState>((set, get) => ({
  commandCenterOpen: false,
  notificationCenterOpen: false,
  activityFeedOpen: false,
  preferencesOpen: false,
  shortcutsModalOpen: false,
  themePanelOpen: false,

  notifications: INITIAL_NOTIFICATIONS,
  unreadCount: INITIAL_NOTIFICATIONS.filter((n) => !n.read).length,

  accentColor: "#38B88A",
  themePreset: "cortex",
  contrast: "normal",
  fontSize: "medium",
  reducedMotion: false,

  setCommandCenterOpen: (open) => set({ commandCenterOpen: open }),
  setNotificationCenterOpen: (open) => set({ notificationCenterOpen: open }),
  setActivityFeedOpen: (open) => set({ activityFeedOpen: open }),
  setPreferencesOpen: (open) => set({ preferencesOpen: open }),
  setShortcutsModalOpen: (open) => set({ shortcutsModalOpen: open }),
  setThemePanelOpen: (open) => set({ themePanelOpen: open }),

  markNotificationRead: (id) => {
    const notifications = get().notifications.map((n) => n.id === id ? { ...n, read: true } : n)
    set({ notifications, unreadCount: notifications.filter((n) => !n.read).length })
  },

  markAllNotificationsRead: () => {
    const notifications = get().notifications.map((n) => ({ ...n, read: true }))
    set({ notifications, unreadCount: 0 })
  },

  addNotification: (n) => {
    set((state) => ({
      notifications: [n, ...state.notifications],
      unreadCount: state.unreadCount + (n.read ? 0 : 1),
    }))
  },

  setAccentColor: (c) => set({ accentColor: c }),
  setThemePreset: (p) => set({ themePreset: p }),
  setContrast: (c) => set({ contrast: c }),
  setFontSize: (s) => set({ fontSize: s }),
  setReducedMotion: (b) => set({ reducedMotion: b }),
}))