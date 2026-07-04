import type { BrowserSession, BrowserSessionStatus, BrowserSecurityPolicy, BrowserActionResult } from "./types"
import { BrowserSecurityEngine } from "./BrowserSecurityEngine"
import { PlaywrightManager, PlaywrightBrowserType } from "./PlaywrightManager"
import { generateId } from "@/worker-framework/shared"
import { BrowserTelemetry } from "./BrowserTelemetry"
import { BrowserEventBus } from "./BrowserEventBus"

const sessions = new Map<string, BrowserSession & { browserId: string; contextId: string; pageId: string }>()

export const BrowserSessionManager = {
  async createSession(securityPolicy?: BrowserSecurityPolicy, browserType: PlaywrightBrowserType = "chromium", headless: boolean = true): Promise<BrowserSession> {
    const sessionId = generateId("browser-session")
    const browserId = generateId("browser")
    const contextId = generateId("context")
    const pageId = generateId("page")

    await PlaywrightManager.launchBrowser(browserId, browserType, headless)
    await PlaywrightManager.createContext(browserId, contextId, {
      viewport: { width: 1920, height: 1080 },
      userAgent: "CortexPrime-BrowserWorker/1.0",
    })
    await PlaywrightManager.createPage(contextId, pageId)

    const session = {
      id: sessionId,
      status: "created" as BrowserSessionStatus,
      createdAt: new Date().toISOString(),
      lastActivityAt: new Date().toISOString(),
      currentUrl: null,
      currentTitle: null,
      navigationStatus: "pending" as BrowserSession["navigationStatus"],
      tabCount: 1,
      actionHistory: [] as BrowserActionResult[],
      cookies: {} as Record<string, string>,
      localStorage: {} as Record<string, string>,
      securityPolicy: securityPolicy ?? BrowserSecurityEngine.createDefaultPolicy(),
      browserId,
      contextId,
      pageId,
    }
    sessions.set(sessionId, session)
    await this.transitionStatus(sessionId, "active")

    await BrowserTelemetry.recordSession({
      id: sessionId,
      browserType,
      createdAt: session.createdAt,
      closedAt: null,
      actionCount: 0,
      errorCount: 0,
    })

    await BrowserEventBus.publishSessionCreated(sessionId, browserType, headless)

    return session
  },

  async getSession(sessionId: string): Promise<(BrowserSession & { browserId: string; contextId: string; pageId: string }) | null> {
    return sessions.get(sessionId) ?? null
  },

  async getPage(sessionId: string) {
    const session = sessions.get(sessionId)
    if (!session) return null
    return PlaywrightManager.getPage(session.pageId)
  },

  async getContext(sessionId: string) {
    const session = sessions.get(sessionId)
    if (!session) return null
    return PlaywrightManager.getContext(session.contextId)
  },

  async closeSession(sessionId: string): Promise<void> {
    const session = sessions.get(sessionId)
    if (!session) throw new Error(`Browser session ${sessionId} not found`)
    await PlaywrightManager.closePage(session.pageId)
    await PlaywrightManager.closeContext(session.contextId)
    await PlaywrightManager.closeBrowser(session.browserId)
    sessions.delete(sessionId)

    await BrowserTelemetry.updateSession(sessionId, { closedAt: new Date().toISOString() })
    await BrowserEventBus.publishSessionClosed(sessionId)
  },

  async recordAction(sessionId: string, result: BrowserActionResult): Promise<void> {
    const session = sessions.get(sessionId)
    if (!session) throw new Error(`Browser session ${sessionId} not found`)
    session.actionHistory.push(result)
    session.lastActivityAt = new Date().toISOString()
    if (result.type === "navigate" && result.success && result.data?.url) {
      session.currentUrl = result.data.url as string
      session.currentTitle = (result.data.title as string) ?? null
    }

    const sessionRecord = await BrowserTelemetry.getSessionHistory()
    const record = sessionRecord.find((s) => s.id === sessionId)
    if (record) {
      await BrowserTelemetry.updateSession(sessionId, {
        actionCount: record.actionCount + 1,
        errorCount: record.errorCount + (result.success ? 0 : 1),
      })
    }
  },

  async updateNavigationState(sessionId: string, url: string, title: string | null, status: BrowserSession["navigationStatus"]): Promise<void> {
    const session = sessions.get(sessionId)
    if (!session) throw new Error(`Browser session ${sessionId} not found`)
    session.currentUrl = url
    session.currentTitle = title
    session.navigationStatus = status
    session.lastActivityAt = new Date().toISOString()
  },

  async setSecurityPolicy(sessionId: string, policy: BrowserSecurityPolicy): Promise<void> {
    const session = sessions.get(sessionId)
    if (!session) throw new Error(`Browser session ${sessionId} not found`)
    session.securityPolicy = policy
  },

  async getActiveSessions(): Promise<BrowserSession[]> {
    return Array.from(sessions.values()).filter((s) => s.status === "active" || s.status === "busy")
  },

  async sessionCount(): Promise<number> { return sessions.size },

  async cleanupExpired(timeoutMs: number): Promise<string[]> {
    const now = Date.now()
    const expired: string[] = []
    for (const [id, session] of sessions.entries()) {
      if (now - new Date(session.lastActivityAt).getTime() > timeoutMs) {
        await this.closeSession(id)
        expired.push(id)
      }
    }
    return expired
  },

  async transitionStatus(sessionId: string, target: BrowserSessionStatus): Promise<void> {
    const session = sessions.get(sessionId)
    if (!session) throw new Error(`Browser session ${sessionId} not found`)
    const valid = this.getValidTransitions(session.status)
    if (!valid.includes(target)) throw new Error(`Invalid browser session transition: ${session.status} → ${target}`)
    session.status = target
    session.lastActivityAt = new Date().toISOString()
  },

  getValidTransitions(current: BrowserSessionStatus): BrowserSessionStatus[] {
    const map: Record<BrowserSessionStatus, BrowserSessionStatus[]> = {
      created: ["active"], active: ["busy", "paused", "closed", "errored"],
      busy: ["active", "errored", "closed"], paused: ["active", "closed", "errored"],
      closed: [], errored: ["active", "closed"],
    }
    return map[current]
  },
}