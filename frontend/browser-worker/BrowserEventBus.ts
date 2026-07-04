import type { IEventBus } from "@/platform/interfaces"

export interface BrowserEvent {
  type: string
  timestamp: string
  sessionId?: string
  data?: Record<string, unknown>
  error?: { code: string; message: string }
}

let eventBusInstance: IEventBus | null = null

async function publishEvent(eventType: string, data: Record<string, unknown>): Promise<void> {
  if (!eventBusInstance) return

  try {
    await eventBusInstance.publish("browser", eventType, data)
  } catch {
    // Silently fail if event bus is unavailable
  }
}

export const BrowserEventBus = {
  initialize(bus: IEventBus): void {
    eventBusInstance = bus
  },

  async publishSessionCreated(sessionId: string, browserType: string, headless: boolean): Promise<void> {
    await publishEvent("browser.session.created", { sessionId, browserType, headless })
  },

  async publishSessionClosed(sessionId: string, reason?: string): Promise<void> {
    await publishEvent("browser.session.closed", { sessionId, reason })
  },

  async publishNavigationStarted(sessionId: string, url: string): Promise<void> {
    await publishEvent("browser.navigation.started", { sessionId, url })
  },

  async publishNavigationCompleted(sessionId: string, url: string, statusCode: number | null, durationMs: number): Promise<void> {
    await publishEvent("browser.navigation.completed", { sessionId, url, statusCode, durationMs })
  },

  async publishNavigationFailed(sessionId: string, url: string, error: string): Promise<void> {
    await publishEvent("browser.navigation.failed", { sessionId, url, error })
  },

  async publishActionStarted(sessionId: string, actionType: string, selector?: string): Promise<void> {
    await publishEvent("browser.action.started", { sessionId, actionType, selector })
  },

  async publishActionCompleted(sessionId: string, actionType: string, durationMs: number, success: boolean): Promise<void> {
    await publishEvent("browser.action.completed", { sessionId, actionType, durationMs, success })
  },

  async publishActionFailed(sessionId: string, actionType: string, error: string): Promise<void> {
    await publishEvent("browser.action.failed", { sessionId, actionType, error })
  },

  async publishScreenshotTaken(sessionId: string, format: string, fullPage: boolean, selector?: string): Promise<void> {
    await publishEvent("browser.screenshot.taken", { sessionId, format, fullPage, selector })
  },

  async publishPdfGenerated(sessionId: string, format: string, landscape: boolean): Promise<void> {
    await publishEvent("browser.pdf.generated", { sessionId, format, landscape })
  },

  async publishDownloadStarted(sessionId: string, url: string, suggestedFilename: string): Promise<void> {
    await publishEvent("browser.download.started", { sessionId, url, suggestedFilename })
  },

  async publishDownloadCompleted(sessionId: string, url: string, filePath: string | null, success: boolean): Promise<void> {
    await publishEvent("browser.download.completed", { sessionId, url, filePath, success })
  },

  async publishUploadStarted(sessionId: string, filePath: string, selector: string): Promise<void> {
    await publishEvent("browser.upload.started", { sessionId, filePath, selector })
  },

  async publishUploadCompleted(sessionId: string, filePath: string, success: boolean): Promise<void> {
    await publishEvent("browser.upload.completed", { sessionId, filePath, success })
  },

  async publishExtractionStarted(sessionId: string, ruleCount: number): Promise<void> {
    await publishEvent("browser.extraction.started", { sessionId, ruleCount })
  },

  async publishExtractionCompleted(sessionId: string, ruleCount: number, succeededCount: number, failedCount: number): Promise<void> {
    await publishEvent("browser.extraction.completed", { sessionId, ruleCount, succeededCount, failedCount })
  },

  async publishCookieRead(sessionId: string, count: number): Promise<void> {
    await publishEvent("browser.cookie.read", { sessionId, count })
  },

  async publishCookieWritten(sessionId: string, count: number): Promise<void> {
    await publishEvent("browser.cookie.written", { sessionId, count })
  },

  async publishCookieCleared(sessionId: string): Promise<void> {
    await publishEvent("browser.cookie.cleared", { sessionId })
  },

  async publishHealthCheck(health: Record<string, unknown>): Promise<void> {
    await publishEvent("browser.health.check", health)
  },

  async publishError(sessionId: string, code: string, message: string): Promise<void> {
    await publishEvent("browser.error", { sessionId, code, message })
  },
}
