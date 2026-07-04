import type { Browser, BrowserContext, Page, BrowserType } from "playwright"
import { chromium, firefox, webkit } from "playwright"

export type PlaywrightBrowserType = "chromium" | "firefox" | "webkit"

const browserInstances = new Map<string, Browser>()
const contextInstances = new Map<string, BrowserContext>()
const pageInstances = new Map<string, Page>()

export const PlaywrightManager = {
  async launchBrowser(instanceId: string, browserType: PlaywrightBrowserType = "chromium", headless: boolean = true): Promise<Browser> {
    const types: Record<PlaywrightBrowserType, BrowserType> = { chromium, firefox, webkit }
    const browser = await types[browserType].launch({ headless })
    browserInstances.set(instanceId, browser)
    return browser
  },

  async createContext(browserId: string, contextId: string, options?: Record<string, unknown>): Promise<BrowserContext> {
    const browser = browserInstances.get(browserId)
    if (!browser) throw new Error(`Browser instance ${browserId} not found`)
    const ctx = options ? await browser.newContext(options as Parameters<Browser["newContext"]>[0]) : await browser.newContext()
    contextInstances.set(contextId, ctx)
    return ctx
  },

  async createPage(contextId: string, pageId: string): Promise<Page> {
    const ctx = contextInstances.get(contextId)
    if (!ctx) throw new Error(`Context ${contextId} not found`)
    const page = await ctx.newPage()
    pageInstances.set(pageId, page)
    return page
  },

  async getBrowser(instanceId: string): Promise<Browser | null> {
    return browserInstances.get(instanceId) ?? null
  },

  async getContext(contextId: string): Promise<BrowserContext | null> {
    return contextInstances.get(contextId) ?? null
  },

  async getPage(pageId: string): Promise<Page | null> {
    return pageInstances.get(pageId) ?? null
  },

  async closePage(pageId: string): Promise<void> {
    const page = pageInstances.get(pageId)
    if (page) { await page.close(); pageInstances.delete(pageId) }
  },

  async closeContext(contextId: string): Promise<void> {
    const ctx = contextInstances.get(contextId)
    if (ctx) { await ctx.close(); contextInstances.delete(contextId) }
  },

  async closeBrowser(instanceId: string): Promise<void> {
    const browser = browserInstances.get(instanceId)
    if (browser) { await browser.close(); browserInstances.delete(instanceId) }
  },

  async cleanup(): Promise<void> {
    for (const [id] of pageInstances) await this.closePage(id)
    for (const [id] of contextInstances) await this.closeContext(id)
    for (const [id] of browserInstances) await this.closeBrowser(id)
  },

  async getPageCount(): Promise<number> { return pageInstances.size },
  async getContextCount(): Promise<number> { return contextInstances.size },
  async getBrowserCount(): Promise<number> { return browserInstances.size },
}