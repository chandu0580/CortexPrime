import type { PlatformError, PlatformCapability } from "@/platform/contracts"

export type BrowserActionType =
  | "navigate"
  | "click"
  | "doubleClick"
  | "hover"
  | "focus"
  | "blur"
  | "fill"
  | "type"
  | "press"
  | "check"
  | "uncheck"
  | "select"
  | "dragAndDrop"
  | "scroll"
  | "upload"
  | "download"
  | "extract"
  | "screenshot"
  | "evaluate"
  | "wait"
  | "back"
  | "forward"
  | "reload"
  | "close"
  | "pdf"
  | "cookie_read"
  | "cookie_write"
  | "cookie_clear"

export type BrowserWaitCondition =
  | "dom_ready"
  | "network_idle"
  | "element_visible"
  | "element_present"
  | "element_hidden"
  | "navigation_complete"
  | "timeout"
  | "custom"

export type BrowserNavigationStatus =
  | "pending"
  | "loading"
  | "loaded"
  | "error"
  | "timeout"
  | "cancelled"

export type BrowserSessionStatus =
  | "created"
  | "active"
  | "busy"
  | "paused"
  | "closed"
  | "errored"

export type BrowserExtractionFormat =
  | "text"
  | "html"
  | "attribute"
  | "table"
  | "json"
  | "markdown"
  | "screenshot"
  | "links"
  | "images"
  | "forms"

export type BrowserBrowserType = "chromium" | "firefox" | "webkit"

export interface BrowserNavigationTarget {
  url: string
  referrer?: string
  headers?: Record<string, string>
  timeoutMs: number
  waitCondition: BrowserWaitCondition
  waitForSelector?: string
  waitForTimeoutMs?: number
}

export interface BrowserAction {
  id: string
  type: BrowserActionType
  target?: string
  value?: string
  selector?: string
  frameSelector?: string[]
  options?: Record<string, unknown>
  waitBeforeMs?: number
  waitAfterMs?: number
  description: string
}

export interface BrowserActionResult {
  actionId: string
  type: BrowserActionType
  success: boolean
  data: Record<string, unknown> | null
  error: PlatformError | null
  startedAt: string
  completedAt: string
  durationMs: number
  screenshot?: string
}

export interface BrowserExtractionRule {
  name: string
  selector: string
  attribute?: string
  format: BrowserExtractionFormat
  multiple: boolean
  nested?: BrowserExtractionRule[]
  transform?: string
}

export interface BrowserSecurityPolicy {
  allowedDomains: string[]
  blockedDomains: string[]
  allowedActions: BrowserActionType[]
  blockedActions: BrowserActionType[]
  maxNavigationDepth: number
  maxPageSizeBytes: number
  sandboxEnabled: boolean
  javascriptEnabled: boolean
  cookiePolicy: "allow_all" | "allow_session" | "block_all"
  contentSecurityPolicy: string | null
}

export interface BrowserSession {
  id: string
  status: BrowserSessionStatus
  createdAt: string
  lastActivityAt: string
  currentUrl: string | null
  currentTitle: string | null
  navigationStatus: BrowserNavigationStatus
  tabCount: number
  actionHistory: BrowserActionResult[]
  cookies: Record<string, string>
  localStorage: Record<string, string>
  securityPolicy: BrowserSecurityPolicy
}

export interface BrowserNavigationState {
  url: string
  title: string | null
  status: BrowserNavigationStatus
  loadedAt: string | null
  statusCode: number | null
  redirectChain: string[]
  pageSizeBytes: number | null
  domNodeCount: number | null
  error: PlatformError | null
}

export interface BrowserWorkerConfig {
  maxConcurrentSessions: number
  sessionTimeoutMs: number
  defaultNavigationTimeoutMs: number
  defaultWaitTimeoutMs: number
  maxActionsPerSession: number
  headless: boolean
  viewportWidth: number
  viewportHeight: number
  userAgent: string
  defaultSecurityPolicy: BrowserSecurityPolicy
  browserType: BrowserBrowserType
}

export interface BrowserCookie {
  name: string
  value: string
  domain?: string
  path?: string
  expires?: number
  httpOnly?: boolean
  secure?: boolean
  sameSite?: "Strict" | "Lax" | "None"
}

export interface BrowserDownload {
  id: string
  url: string
  suggestedFilename: string
  mimeType: string
  startedAt: string
  completedAt: string | null
  filePath: string | null
  fileSizeBytes: number | null
  success: boolean
  error: string | null
}

export interface BrowserUpload {
  id: string
  filePath: string
  selector: string
  uploadedAt: string
  success: boolean
  error: string | null
}

export interface BrowserPdfOptions {
  format?: "A4" | "Letter" | "Legal"
  landscape?: boolean
  printBackground?: boolean
  margin?: { top?: string; right?: string; bottom?: string; left?: string }
}

export interface BrowserScreenshotOptions {
  fullPage?: boolean
  format?: "png" | "jpeg"
  quality?: number
  selector?: string
}

export interface BrowserHealthStatus {
  browserProcessAlive: boolean
  memoryUsageMb: number | null
  activeSessions: number
  pageCount: number
  contextCount: number
  browserCount: number
  crashCount: number
  lastHealthCheck: string
}

export interface BrowserMetrics {
  totalSessions: number
  activeSessions: number
  totalPages: number
  totalActions: number
  totalDownloads: number
  totalUploads: number
  totalScreenshots: number
  totalPdfs: number
  totalNavigations: number
  totalExtractions: number
  averageActionLatencyMs: number
  successRate: number
}

export interface BrowserCapability extends PlatformCapability {
  browserType: BrowserBrowserType
  maxSessions: number
  supportedActions: BrowserActionType[]
  supportedExtractionFormats: BrowserExtractionFormat[]
}

export type BrowserTaskPayload =
  | { type: "navigation"; target: BrowserNavigationTarget; actions: BrowserAction[] }
  | { type: "extraction"; target: BrowserNavigationTarget; rules: BrowserExtractionRule[] }
  | { type: "screenshot"; target: BrowserNavigationTarget; fullPage: boolean; format: "png" | "jpeg"; quality: number; selector?: string }
  | { type: "interaction"; target: BrowserNavigationTarget; actions: BrowserAction[]; extractAfter?: BrowserExtractionRule[] }
  | { type: "evaluation"; target: BrowserNavigationTarget; script: string; args: Record<string, unknown>[] }
  | { type: "pdf"; target: BrowserNavigationTarget; options?: BrowserPdfOptions }
  | { type: "cookies"; target: BrowserNavigationTarget; operation: "read" | "write" | "clear"; cookies?: BrowserCookie[] }
