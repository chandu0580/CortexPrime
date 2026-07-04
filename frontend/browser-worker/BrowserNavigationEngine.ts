import type { BrowserNavigationTarget, BrowserNavigationState } from "./types"
import { BrowserSecurityEngine } from "./BrowserSecurityEngine"
import { BrowserSessionManager } from "./BrowserSessionManager"
import { BrowserTelemetry } from "./BrowserTelemetry"
import { BrowserEventBus } from "./BrowserEventBus"

const navigationHistory = new Map<string, BrowserNavigationState[]>()

export const BrowserNavigationEngine = {
  async navigate(sessionId: string, target: BrowserNavigationTarget): Promise<BrowserNavigationState> {
    const startTime = Date.now()
    const session = await BrowserSessionManager.getSession(sessionId)
    if (!session) throw new Error(`Browser session ${sessionId} not found`)

    const validation = BrowserSecurityEngine.validateNavigation(target, session.securityPolicy)
    if (!validation.valid) return this.createErrorState(target.url, "NAVIGATION_BLOCKED", validation.reason ?? "Blocked by security policy")

    const cleanUrl = BrowserSecurityEngine.sanitizeUrl(target.url)
    if (!cleanUrl) return this.createErrorState(target.url, "INVALID_URL", "Failed to sanitize URL")

    await BrowserSessionManager.updateNavigationState(sessionId, cleanUrl, null, "loading")
    await BrowserEventBus.publishNavigationStarted(sessionId, cleanUrl)

    try {
      const page = await BrowserSessionManager.getPage(sessionId)
      if (!page) return this.createErrorState(cleanUrl, "NO_PAGE", "No page available in session")

      const waitUntil = target.waitCondition === "network_idle" ? "networkidle" as const : target.waitCondition === "dom_ready" ? "domcontentloaded" as const : "load" as const
      const response = await page.goto(cleanUrl, { waitUntil, timeout: target.timeoutMs })

      const title = await page.title()
      const state: BrowserNavigationState = {
        url: page.url(), title, status: "loaded", loadedAt: new Date().toISOString(),
        statusCode: response?.status() ?? null, redirectChain: response?.request()?.redirectedFrom()?.url() ? [response.request()!.redirectedFrom()!.url()] : [],
        pageSizeBytes: null, domNodeCount: null, error: null,
      }

      const history = navigationHistory.get(sessionId) ?? []
      history.push(state)
      navigationHistory.set(sessionId, history)

      await BrowserSessionManager.updateNavigationState(sessionId, state.url, state.title, state.status)
      await BrowserTelemetry.recordCall("navigate", Date.now() - startTime, true)
      await BrowserEventBus.publishNavigationCompleted(sessionId, state.url, state.statusCode, Date.now() - startTime)
      return state
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : String(err)
      await BrowserTelemetry.recordFailure("navigate", errorMessage)
      await BrowserEventBus.publishNavigationFailed(sessionId, cleanUrl, errorMessage)
      return this.createErrorState(cleanUrl, "NAVIGATION_FAILED", errorMessage)
    }
  },

  async reload(sessionId: string): Promise<BrowserNavigationState> {
    const page = await BrowserSessionManager.getPage(sessionId)
    if (!page) return this.createErrorState("", "NO_PAGE", "No page available")
    await page.reload()
    return { url: page.url(), title: await page.title(), status: "loaded", loadedAt: new Date().toISOString(), statusCode: null, redirectChain: [], pageSizeBytes: null, domNodeCount: null, error: null }
  },

  async back(sessionId: string): Promise<BrowserNavigationState> {
    const page = await BrowserSessionManager.getPage(sessionId)
    if (!page) return this.createErrorState("", "NO_PAGE", "No page available")
    await page.goBack()
    return { url: page.url(), title: await page.title(), status: "loaded", loadedAt: new Date().toISOString(), statusCode: null, redirectChain: [], pageSizeBytes: null, domNodeCount: null, error: null }
  },

  async forward(sessionId: string): Promise<BrowserNavigationState> {
    const page = await BrowserSessionManager.getPage(sessionId)
    if (!page) return this.createErrorState("", "NO_PAGE", "No page available")
    await page.goForward()
    return { url: page.url(), title: await page.title(), status: "loaded", loadedAt: new Date().toISOString(), statusCode: null, redirectChain: [], pageSizeBytes: null, domNodeCount: null, error: null }
  },

  async getNavigationHistory(sessionId: string): Promise<BrowserNavigationState[]> {
    return navigationHistory.get(sessionId) ?? []
  },

  createErrorState(url: string, code: string, message: string): BrowserNavigationState {
    return { url, title: null, status: "error", loadedAt: null, statusCode: null, redirectChain: [], pageSizeBytes: null, domNodeCount: null, error: { code, message, module: "BrowserNavigationEngine", severity: "error", timestamp: new Date().toISOString(), details: { url }, cause: null } }
  },
}