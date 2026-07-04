import type { BrowserAction, BrowserActionResult, BrowserSession, BrowserCookie } from "./types"
import { BrowserSecurityEngine } from "./BrowserSecurityEngine"
import { BrowserSessionManager } from "./BrowserSessionManager"
import { BrowserTelemetry } from "./BrowserTelemetry"
import { BrowserEventBus } from "./BrowserEventBus"
import type { Page } from "playwright"

async function getPage(sessionId: string): Promise<Page> {
  const page = await BrowserSessionManager.getPage(sessionId)
  if (!page) throw new Error(`No page for session ${sessionId}`)
  return page
}

const actionHandlers: Record<string, (action: BrowserAction, session: BrowserSession & { browserId: string; contextId: string; pageId: string }) => Promise<Record<string, unknown>>> = {
  click: async (action, _session) => {
    const page = await getPage(_session.id)
    const selector = action.selector ?? ""
    await page.click(selector)
    return { selector, clickedAt: new Date().toISOString(), elementFound: true }
  },
  doubleClick: async (action, _session) => {
    const page = await getPage(_session.id); await page.dblclick(action.selector ?? ""); return { selector: action.selector }
  },
  hover: async (action, _session) => {
    const page = await getPage(_session.id); await page.hover(action.selector ?? ""); return { selector: action.selector }
  },
  focus: async (action, _session) => {
    const page = await getPage(_session.id); await page.focus(action.selector ?? ""); return { selector: action.selector }
  },
  blur: async (action, _session) => {
    const page = await getPage(_session.id); await page.evaluate((sel: string) => { const el = document.querySelector(sel); if (el) (el as HTMLElement).blur() }, action.selector ?? ""); return { selector: action.selector }
  },
  fill: async (action, _session) => {
    const page = await getPage(_session.id); await page.fill(action.selector ?? "", action.value ?? ""); return { selector: action.selector, value: action.value }
  },
  type: async (action, _session) => {
    const page = await getPage(_session.id); await page.type(action.selector ?? "", action.value ?? ""); return { selector: action.selector, charCount: action.value?.length ?? 0 }
  },
  press: async (action, _session) => {
    const page = await getPage(_session.id); await page.press(action.selector ?? "", action.value ?? "Enter"); return { selector: action.selector, key: action.value }
  },
  check: async (action, _session) => {
    const page = await getPage(_session.id); await page.check(action.selector ?? ""); return { selector: action.selector, checked: true }
  },
  uncheck: async (action, _session) => {
    const page = await getPage(_session.id); await page.uncheck(action.selector ?? ""); return { selector: action.selector, checked: false }
  },
  select: async (action, _session) => {
    const page = await getPage(_session.id); const values = await page.selectOption(action.selector ?? "", action.value ?? ""); return { selector: action.selector, selectedValue: values }
  },
  scroll: async (action, _session) => {
    const page = await getPage(_session.id)
    const direction = action.value ?? "down"
    const amount = (action.options?.amount as number) ?? 500
    if (direction === "down") await page.evaluate((y: number) => window.scrollBy(0, y), amount)
    else if (direction === "up") await page.evaluate((y: number) => window.scrollBy(0, -y), amount)
    else if (direction === "top") await page.evaluate(() => window.scrollTo(0, 0))
    else if (direction === "bottom") await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight))
    else if (direction === "left") await page.evaluate((x: number) => window.scrollBy(-x, 0), amount)
    else if (direction === "right") await page.evaluate((x: number) => window.scrollBy(x, 0), amount)
    return { direction, amount, position: await page.evaluate(() => ({ x: window.scrollX, y: window.scrollY })) }
  },
  evaluate: async (action, _session) => {
    const page = await getPage(_session.id); const result = await page.evaluate(action.value ?? ""); return { script: action.value, result }
  },
  screenshot: async (action, _session) => {
    const page = await getPage(_session.id)
    const fullPage = action.options?.fullPage as boolean ?? false
    const format = (action.options?.format as "png" | "jpeg") ?? "png"
    const quality = action.options?.quality as number | undefined
    const buffer = action.selector
      ? await page.locator(action.selector).screenshot({ type: format, quality: format === "jpeg" ? quality : undefined })
      : await page.screenshot({ fullPage, type: format, quality: format === "jpeg" ? quality : undefined })
    return { format, data: buffer ? `data:image/${format};base64,${buffer.toString("base64")}` : "", width: 1920, height: 1080, fullPage, selector: action.selector ?? null }
  },
  wait: async (action, _session) => {
    const page = await getPage(_session.id)
    const condition = action.options?.condition as string ?? "timeout"
    const ms = action.options?.durationMs as number ?? 1000
    if (condition === "network_idle") await page.waitForLoadState("networkidle", { timeout: ms })
    else if (condition === "dom_ready") await page.waitForLoadState("domcontentloaded", { timeout: ms })
    else if (condition === "element_visible" && action.selector) await page.waitForSelector(action.selector, { state: "visible", timeout: ms })
    else if (condition === "element_present" && action.selector) await page.waitForSelector(action.selector, { state: "attached", timeout: ms })
    else if (condition === "element_hidden" && action.selector) await page.waitForSelector(action.selector, { state: "hidden", timeout: ms })
    else if (condition === "navigation_complete") await page.waitForLoadState("networkidle", { timeout: ms })
    else await new Promise((resolve) => setTimeout(resolve, ms))
    return { condition, durationMs: ms }
  },
  navigate: async (action, _session) => {
    const page = await getPage(_session.id)
    const url = action.value ?? ""
    await page.goto(url, { waitUntil: "load" })
    return { url: page.url(), title: await page.title(), navigationStatus: "loaded", statusCode: 200, redirectChain: [] }
  },
  back: async (action, _session) => {
    const page = await getPage(_session.id); await page.goBack(); return { previousUrl: page.url() }
  },
  forward: async (action, _session) => {
    const page = await getPage(_session.id); await page.goForward(); return { nextUrl: page.url() }
  },
  reload: async (action, _session) => {
    const page = await getPage(_session.id); await page.reload(); return { url: page.url(), reloadedAt: new Date().toISOString() }
  },
  close: async (action, _session) => {
    await BrowserSessionManager.closeSession(_session.id); return { closed: true }
  },
  dragAndDrop: async (action, _session) => {
    const page = await getPage(_session.id)
    const sourceSelector = action.selector ?? ""
    const targetSelector = (action.options?.targetSelector as string) ?? ""
    if (!sourceSelector || !targetSelector) throw new Error("dragAndDrop requires both selector and options.targetSelector")
    await page.dragAndDrop(sourceSelector, targetSelector)
    return { sourceSelector, targetSelector, draggedAt: new Date().toISOString() }
  },
  upload: async (action, _session) => {
    const page = await getPage(_session.id)
    const selector = action.selector ?? ""
    const filePaths = (action.options?.filePaths as string[]) ?? []
    if (!selector) throw new Error("upload requires a selector")
    if (filePaths.length === 0) throw new Error("upload requires options.filePaths")
    const fileChooserPromise = page.waitForEvent("filechooser")
    await page.click(selector)
    const fileChooser = await fileChooserPromise
    await fileChooser.setFiles(filePaths)
    return { selector, filePaths, uploadedAt: new Date().toISOString(), fileCount: filePaths.length }
  },
  download: async (action, _session) => {
    const page = await getPage(_session.id)
    const downloadPromise = page.waitForEvent("download")
    if (action.selector) {
      await page.click(action.selector)
    } else if (action.value) {
      await page.goto(action.value)
    }
    const download = await downloadPromise
    const suggestedFilename = download.suggestedFilename()
    const mimeType = download.page().url()
    return { url: download.url(), suggestedFilename, mimeType, startedAt: new Date().toISOString() }
  },
  extract: async (action, _session) => {
    const page = await getPage(_session.id)
    const selector = action.selector ?? ""
    const format = (action.options?.format as string) ?? "text"
    let value: unknown
    switch (format) {
      case "text": value = selector ? await page.textContent(selector) : await page.evaluate(() => document.body?.innerText ?? ""); break
      case "html": value = selector ? await page.innerHTML(selector) : await page.content(); break
      case "attribute": value = await page.evaluate((args: string[]) => document.querySelector(args[0])?.getAttribute(args[1]) ?? null, [selector, (action.options?.attribute as string) ?? "href"]); break
      case "links": value = await page.evaluate(() => Array.from(document.querySelectorAll("a")).map((a) => ({ href: a.href, text: a.textContent?.trim() ?? "" }))); break
      case "images": value = await page.evaluate(() => Array.from(document.querySelectorAll("img")).map((img) => ({ src: img.src, alt: img.alt, width: img.naturalWidth, height: img.naturalHeight }))); break
      case "forms": value = await page.evaluate(() => Array.from(document.forms).map((f) => ({ id: f.id, name: f.name, action: f.action, method: f.method, fields: Array.from(f.elements).map((e) => ({ name: (e as HTMLInputElement).name, type: (e as HTMLInputElement).type, value: (e as HTMLInputElement).value })) }))); break
      case "table": value = await page.evaluate((sel: string) => { const table = document.querySelector(sel); if (!table) return []; return Array.from(table.querySelectorAll("tr")).map((row) => Array.from(row.querySelectorAll("td, th")).map((cell) => cell.textContent?.trim() ?? "")); }, selector); break
      case "json": { const text = selector ? await page.textContent(selector) : await page.evaluate(() => document.body?.innerText ?? ""); try { value = JSON.parse(text ?? "{}"); } catch { value = text; } break; }
      case "markdown": value = selector ? await page.textContent(selector) : await page.evaluate(() => document.body?.innerText ?? ""); break
      default: throw new Error(`Unknown extraction format: ${format}`)
    }
    return { selector, format, value, extractedAt: new Date().toISOString() }
  },
  pdf: async (action, _session) => {
    const page = await getPage(_session.id)
    const format = (action.options?.format as "A4" | "Letter" | "Legal") ?? "A4"
    const landscape = (action.options?.landscape as boolean) ?? false
    const printBackground = (action.options?.printBackground as boolean) ?? true
    const margin = (action.options?.margin as { top?: string; right?: string; bottom?: string; left?: string }) ?? { top: "1cm", right: "1cm", bottom: "1cm", left: "1cm" }
    const buffer = await page.pdf({ format, landscape, printBackground, margin })
    return { format, landscape, data: `data:application/pdf;base64,${buffer.toString("base64")}`, timestamp: new Date().toISOString() }
  },
  cookie_read: async (action, _session) => {
    const page = await getPage(_session.id)
    const context = page.context()
    const cookies = await context.cookies()
    const filter = action.options?.filter as { name?: string; domain?: string; path?: string } | undefined
    let filtered = cookies
    if (filter?.name) filtered = filtered.filter((c) => c.name === filter.name)
    if (filter?.domain) filtered = filtered.filter((c) => c.domain === filter.domain)
    if (filter?.path) filtered = filtered.filter((c) => c.path === filter.path)
    return { cookies: filtered, count: filtered.length }
  },
  cookie_write: async (action, _session) => {
    const page = await getPage(_session.id)
    const context = page.context()
    const cookies = (action.options?.cookies as BrowserCookie[]) ?? []
    if (cookies.length === 0) throw new Error("cookie_write requires options.cookies")
    await context.addCookies(cookies)
    return { writtenCount: cookies.length, success: true }
  },
  cookie_clear: async (action, _session) => {
    const page = await getPage(_session.id)
    const context = page.context()
    await context.clearCookies()
    return { cleared: true, timestamp: new Date().toISOString() }
  },
}

export const BrowserActionEngine = {
  async executeAction(sessionId: string, action: BrowserAction): Promise<BrowserActionResult> {
    const startTime = Date.now()
    const session = await BrowserSessionManager.getSession(sessionId)
    if (!session) throw new Error(`Browser session ${sessionId} not found`)

    const validation = BrowserSecurityEngine.validateAction(action.type, session.securityPolicy)
    if (!validation.allowed) return this.createError(action, "ACTION_BLOCKED", validation.reason ?? `Action ${action.type} not allowed`)

    const handler = actionHandlers[action.type]
    if (!handler) return this.createError(action, "UNKNOWN_ACTION", `No handler for action type: ${action.type}`)

    await BrowserSessionManager.transitionStatus(sessionId, "busy")
    await BrowserEventBus.publishActionStarted(sessionId, action.type, action.selector)

    try {
      const data = await handler(action, session)
      const result: BrowserActionResult = { actionId: action.id, type: action.type, success: true, data, error: null, startedAt: new Date(startTime).toISOString(), completedAt: new Date().toISOString(), durationMs: Date.now() - startTime }
      await BrowserSessionManager.recordAction(sessionId, result)
      await BrowserSessionManager.transitionStatus(sessionId, "active")
      await BrowserTelemetry.recordCall(action.type, Date.now() - startTime, true)
      await BrowserEventBus.publishActionCompleted(sessionId, action.type, Date.now() - startTime, true)
      return result
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : String(err)
      await BrowserTelemetry.recordFailure(action.type, errorMessage)
      await BrowserEventBus.publishActionFailed(sessionId, action.type, errorMessage)
      const result: BrowserActionResult = { actionId: action.id, type: action.type, success: false, data: null, error: { code: "ACTION_EXECUTION_FAILED", message: errorMessage, module: "BrowserActionEngine", severity: "error", timestamp: new Date().toISOString(), details: { actionType: action.type, selector: action.selector }, cause: null }, startedAt: new Date(startTime).toISOString(), completedAt: new Date().toISOString(), durationMs: Date.now() - startTime }
      await BrowserSessionManager.recordAction(sessionId, result)
      await BrowserSessionManager.transitionStatus(sessionId, "errored")
      return result
    }
  },

  async executeActions(sessionId: string, actions: BrowserAction[]): Promise<BrowserActionResult[]> {
    const results: BrowserActionResult[] = []
    for (const action of actions) results.push(await this.executeAction(sessionId, action))
    return results
  },

  async getActionHistory(sessionId: string): Promise<BrowserActionResult[]> {
    const session = await BrowserSessionManager.getSession(sessionId)
    if (!session) throw new Error(`Browser session ${sessionId} not found`)
    return [...session.actionHistory]
  },

  createError(action: BrowserAction, code: string, message: string): BrowserActionResult {
    return { actionId: action.id, type: action.type, success: false, data: null, error: { code, message, module: "BrowserActionEngine", severity: "error", timestamp: new Date().toISOString(), details: { actionType: action.type, selector: action.selector }, cause: null }, startedAt: new Date().toISOString(), completedAt: new Date().toISOString(), durationMs: 0 }
  },
}