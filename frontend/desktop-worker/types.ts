export type DesktopSessionStatus = "created" | "active" | "paused" | "closed" | "failed"

export type DesktopActionType =
  | "mouse_move" | "mouse_click" | "mouse_double_click" | "mouse_right_click"
  | "mouse_drag" | "mouse_drop" | "mouse_scroll"
  | "keyboard_type" | "keyboard_combination" | "keyboard_shortcut" | "keyboard_hotkey"
  | "keyboard_paste" | "keyboard_copy"
  | "window_list" | "window_focus" | "window_minimize" | "window_maximize"
  | "window_restore" | "window_close"
  | "desktop_screenshot" | "descreen_info" | "desktop_monitor_info"
  | "clipboard_read" | "clipboard_write" | "clipboard_clear"
  | "file_create" | "file_move" | "file_rename" | "file_copy" | "file_delete"
  | "file_upload" | "file_download" | "file_search"
  | "dialog_open" | "dialog_save" | "dialog_file_picker"
  | "app_launch" | "app_apply" | "app_list" | "app_activate"

export type DesktopHealthStatus = "running" | "idle" | "busy" | "disconnected" | "recovering"

export type DesktopEventType =
  | "desktop.started" | "desktop.completed" | "desktop.failed"
  | "desktop.window.changed" | "desktop.file.changed"
  | "desktop.application.started" | "desktop.application.closed"

export interface DesktopCoordinates {
  x: number
  y: number
}

export interface DesktopMouseAction {
  type: "mouse_move" | "mouse_click" | "mouse_double_click" | "mouse_right_click"
  coordinates?: DesktopCoordinates
  button?: "left" | "right" | "middle"
  target?: string
}

export interface DesktopDragAction {
  type: "mouse_drag" | "mouse_drop"
  source: DesktopCoordinates
  target: DesktopCoordinates
}

export interface DesktopScrollAction {
  type: "mouse_scroll"
  deltaX: number
  deltaY: number
}

export interface DesktopKeyboardAction {
  type: "keyboard_type" | "keyboard_combination" | "keyboard_shortcut" | "keyboard_hotkey"
  text?: string
  keys?: string[]
  modifiers?: string[]
}

export interface DesktopKeyAction {
  type: "keyboard_paste" | "keyboard_copy"
}

export interface DesktopWindowAction {
  type: "window_list" | "window_focus" | "window_minimize" | "window_maximize" | "window_restore" | "window_close"
  windowId?: string
  windowTitle?: string
}

export interface DesktopInfoAction {
  type: "desktop_screenshot" | "descreen_info" | "desktop_monitor_info"
  format?: "png" | "jpeg"
  monitorIndex?: number
}

export interface DesktopClipboardAction {
  type: "clipboard_read" | "clipboard_write" | "clipboard_clear"
  content?: string
  format?: "text" | "html" | "image"
}

export interface DesktopFileAction {
  type: "file_create" | "file_move" | "file_rename" | "file_copy" | "file_delete"
  | "file_upload" | "file_download" | "file_search"
  path?: string
  sourcePath?: string
  destinationPath?: string
  content?: string
  query?: string
  url?: string
}

export interface DesktopDialogAction {
  type: "dialog_open" | "dialog_save" | "dialog_file_picker"
  path?: string
  filter?: string
  defaultName?: string
}

export interface DesktopApplicationAction {
  type: "app_launch" | "app_apply" | "app_list" | "app_activate"
  applicationName?: string
  applicationPath?: string
  arguments?: string[]
}

export type DesktopTaskPayload =
  | DesktopMouseAction | DesktopDragAction | DesktopScrollAction
  | DesktopKeyboardAction | DesktopKeyAction
  | DesktopWindowAction | DesktopInfoAction
  | DesktopClipboardAction | DesktopFileAction
  | DesktopDialogAction | DesktopApplicationAction

export interface DesktopActionResult {
  success: boolean
  output?: unknown
  screenshot?: string
  error?: string
  durationMs: number
  timestamp: string
}

export interface DesktopSession {
  id: string
  status: DesktopSessionStatus
  createdAt: string
  lastActivityAt: string
  actionCount: number
  errorCount: number
  metadata: Record<string, string>
}

export interface DesktopWorkerConfig {
  maxSessions: number
  sessionTimeoutMs: number
  screenshotOnAction: boolean
  screenshotFormat: "png" | "jpeg"
  allowedMonitors: number[]
  blockedPaths: string[]
  trustedApplications: string[]
  maxFileSizeBytes: number
}

export interface DesktopMetrics {
  totalCalls: number
  totalFailures: number
  successRate: number
  averageLatencyMs: number
  totalScreenshots: number
  totalSessions: number
  activeSessions: number
  actionBreakdown: Record<string, number>
  topApplications: Record<string, number>
}

export interface DesktopHealthStatusResult {
  status: DesktopHealthStatus
  sessions: { total: number; active: number; failed: number }
  lastAction: string | null
  lastActionAt: string | null
  uptimeMs: number
  consecutiveFailures: number
}

export interface DesktopCapabilityConfig {
  id: string
  name: string
  type: string
  version: string
  features: string[]
  enabled: boolean
  supportedActions: DesktopActionType[]
  maxSessions: number
  supportsScreenshots: boolean
  supportsFileOperations: boolean
  supportsClipboard: boolean
  supportsDialogs: boolean
  supportsApplications: boolean
}