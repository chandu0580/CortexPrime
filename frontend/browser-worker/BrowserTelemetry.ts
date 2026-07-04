interface BrowserCallRecord { action: string; latencyMs: number; success: boolean; timestamp: string }
interface BrowserFailureRecord { action: string; error: string; timestamp: string }
interface BrowserDownloadRecord { id: string; url: string; suggestedFilename: string; mimeType: string; startedAt: string; completedAt: string | null; filePath: string | null; fileSizeBytes: number | null; success: boolean; error: string | null }
interface BrowserUploadRecord { id: string; filePath: string; selector: string; uploadedAt: string; success: boolean; error: string | null }
interface BrowserScreenshotRecord { id: string; format: string; fullPage: boolean; selector: string | null; timestamp: string; sizeBytes: number | null }
interface BrowserPdfRecord { id: string; format: string; landscape: boolean; timestamp: string; sizeBytes: number | null }
interface BrowserSessionRecord { id: string; browserType: string; createdAt: string; closedAt: string | null; actionCount: number; errorCount: number }

const calls: BrowserCallRecord[] = []
const failures: BrowserFailureRecord[] = []
const downloads: BrowserDownloadRecord[] = []
const uploads: BrowserUploadRecord[] = []
const screenshots: BrowserScreenshotRecord[] = []
const pdfs: BrowserPdfRecord[] = []
const sessions: BrowserSessionRecord[] = []

const MAX_CALLS = 1000
const MAX_FAILURES = 100
const MAX_DOWNLOADS = 500
const MAX_UPLOADS = 500
const MAX_SCREENSHOTS = 500
const MAX_PDFS = 500
const MAX_SESSIONS = 500

export const BrowserTelemetry = {
  async recordCall(action: string, latencyMs: number, success: boolean): Promise<void> {
    calls.push({ action, latencyMs, success, timestamp: new Date().toISOString() })
    if (calls.length > MAX_CALLS) calls.shift()
  },

  async recordFailure(action: string, error: string): Promise<void> {
    failures.push({ action, error, timestamp: new Date().toISOString() })
    if (failures.length > MAX_FAILURES) failures.shift()
  },

  async recordDownload(download: BrowserDownloadRecord): Promise<void> {
    downloads.push(download)
    if (downloads.length > MAX_DOWNLOADS) downloads.shift()
  },

  async recordUpload(upload: BrowserUploadRecord): Promise<void> {
    uploads.push(upload)
    if (uploads.length > MAX_UPLOADS) uploads.shift()
  },

  async recordScreenshot(screenshot: BrowserScreenshotRecord): Promise<void> {
    screenshots.push(screenshot)
    if (screenshots.length > MAX_SCREENSHOTS) screenshots.shift()
  },

  async recordPdf(pdf: BrowserPdfRecord): Promise<void> {
    pdfs.push(pdf)
    if (pdfs.length > MAX_PDFS) pdfs.shift()
  },

  async recordSession(session: BrowserSessionRecord): Promise<void> {
    sessions.push(session)
    if (sessions.length > MAX_SESSIONS) sessions.shift()
  },

  async updateSession(sessionId: string, updates: Partial<BrowserSessionRecord>): Promise<void> {
    const session = sessions.find((s) => s.id === sessionId)
    if (session) Object.assign(session, updates)
  },

  async getMetrics(): Promise<{
    totalCalls: number
    totalFailures: number
    successRate: number
    averageLatencyMs: number
    totalDownloads: number
    successfulDownloads: number
    totalUploads: number
    successfulUploads: number
    totalScreenshots: number
    totalPdfs: number
    totalSessions: number
    activeSessions: number
    actionBreakdown: Record<string, number>
  }> {
    const totalCalls = calls.length
    const totalFailures = failures.length
    const successRate = totalCalls > 0 ? Math.round(((totalCalls - totalFailures) / totalCalls) * 100) : 100
    const averageLatencyMs = totalCalls > 0 ? Math.round(calls.reduce((s, c) => s + c.latencyMs, 0) / totalCalls) : 0

    const actionBreakdown: Record<string, number> = {}
    for (const call of calls) {
      actionBreakdown[call.action] = (actionBreakdown[call.action] ?? 0) + 1
    }

    return {
      totalCalls,
      totalFailures,
      successRate,
      averageLatencyMs,
      totalDownloads: downloads.length,
      successfulDownloads: downloads.filter((d) => d.success).length,
      totalUploads: uploads.length,
      successfulUploads: uploads.filter((u) => u.success).length,
      totalScreenshots: screenshots.length,
      totalPdfs: pdfs.length,
      totalSessions: sessions.length,
      activeSessions: sessions.filter((s) => s.closedAt === null).length,
      actionBreakdown,
    }
  },

  async getCallHistory(limit?: number): Promise<BrowserCallRecord[]> {
    const sliced = limit ? calls.slice(-limit) : calls
    return [...sliced]
  },

  async getFailureHistory(limit?: number): Promise<BrowserFailureRecord[]> {
    const sliced = limit ? failures.slice(-limit) : failures
    return [...sliced]
  },

  async getDownloadHistory(limit?: number): Promise<BrowserDownloadRecord[]> {
    const sliced = limit ? downloads.slice(-limit) : downloads
    return [...sliced]
  },

  async getUploadHistory(limit?: number): Promise<BrowserUploadRecord[]> {
    const sliced = limit ? uploads.slice(-limit) : uploads
    return [...sliced]
  },

  async getScreenshotHistory(limit?: number): Promise<BrowserScreenshotRecord[]> {
    const sliced = limit ? screenshots.slice(-limit) : screenshots
    return [...sliced]
  },

  async getPdfHistory(limit?: number): Promise<BrowserPdfRecord[]> {
    const sliced = limit ? pdfs.slice(-limit) : pdfs
    return [...sliced]
  },

  async getSessionHistory(limit?: number): Promise<BrowserSessionRecord[]> {
    const sliced = limit ? sessions.slice(-limit) : sessions
    return [...sliced]
  },

  async clearHistory(): Promise<void> {
    calls.length = 0
    failures.length = 0
    downloads.length = 0
    uploads.length = 0
    screenshots.length = 0
    pdfs.length = 0
    sessions.length = 0
  },
}