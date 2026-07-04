import type { BrowserExtractionRule, BrowserExtractionFormat, BrowserActionResult } from "./types"
import { BrowserSessionManager } from "./BrowserSessionManager"
import { BrowserEventBus } from "./BrowserEventBus"

interface ExtractionResult { name: string; value: unknown; format: BrowserExtractionFormat; success: boolean; error: string | null }

export const BrowserExtractionEngine = {
  async extract(sessionId: string, rules: BrowserExtractionRule[]): Promise<BrowserActionResult> {
    const startTime = Date.now()
    const results: ExtractionResult[] = []
    const page = await BrowserSessionManager.getPage(sessionId)

    await BrowserEventBus.publishExtractionStarted(sessionId, rules.length)

    for (const rule of rules) {
      try {
        if (!page) throw new Error("No page available")
        const value = await this.extractWithPlaywright(rule, page)
        results.push({ name: rule.name, value, format: rule.format, success: true, error: null })
      } catch (err) {
        results.push({ name: rule.name, value: null, format: rule.format, success: false, error: err instanceof Error ? err.message : String(err) })
      }
    }

    const allSucceeded = results.every((r) => r.success)
    const succeededCount = results.filter((r) => r.success).length
    const failedCount = results.filter((r) => !r.success).length
    const completedAt = new Date().toISOString()

    await BrowserEventBus.publishExtractionCompleted(sessionId, rules.length, succeededCount, failedCount)

    return {
      actionId: `extract-${Date.now()}`, type: "extract", success: allSucceeded,
      data: { results: results.map((r) => ({ name: r.name, value: r.value, format: r.format })), ruleCount: rules.length, succeededCount, failedCount },
      error: allSucceeded ? null : { code: "EXTRACTION_PARTIAL_FAILURE", message: `${failedCount} of ${rules.length} extraction rules failed`, module: "BrowserExtractionEngine", severity: "warning", timestamp: completedAt, details: { failures: results.filter((r) => !r.success).map((r) => ({ name: r.name, error: r.error })) }, cause: null },
      startedAt: new Date(startTime).toISOString(), completedAt, durationMs: Date.now() - startTime,
    }
  },

  async extractWithPlaywright(rule: BrowserExtractionRule, page: Awaited<ReturnType<typeof BrowserSessionManager.getPage>>): Promise<unknown> {
    if (!page) throw new Error("No page available")
    const selector = rule.selector ?? ""

    switch (rule.format) {
      case "text": return rule.selector ? page.textContent(selector) : page.evaluate(() => document.body?.innerText ?? "")
      case "html": return rule.selector ? page.innerHTML(selector) : page.content()
      case "attribute": return page.evaluate(([sel, attr]) => document.querySelector(sel)?.getAttribute(attr), [selector, rule.attribute ?? "href"])
      case "links": return page.evaluate(() => Array.from(document.querySelectorAll("a")).map((a) => ({ href: a.href, text: a.textContent?.trim() ?? "" })))
      case "images": return page.evaluate(() => Array.from(document.querySelectorAll("img")).map((img) => ({ src: img.src, alt: img.alt, width: img.naturalWidth, height: img.naturalHeight })))
      case "forms": return page.evaluate(() => Array.from(document.forms).map((f) => ({ id: f.id, name: f.name, action: f.action, method: f.method, fields: Array.from(f.elements).map((e) => ({ name: (e as HTMLInputElement).name, type: (e as HTMLInputElement).type, value: (e as HTMLInputElement).value })) })))
      case "table": {
        const rows = await page.evaluate((sel) => {
          const table = document.querySelector(sel)
          if (!table) return []
          return Array.from(table.querySelectorAll("tr")).map((row) => Array.from(row.querySelectorAll("td, th")).map((cell) => cell.textContent?.trim() ?? ""))
        }, selector)
        return rows
      }
      case "json": {
        const text = rule.selector ? await page.textContent(selector) : await page.evaluate(() => document.body?.innerText ?? "")
        try { return JSON.parse(text ?? "{}") } catch { return text }
      }
      case "markdown": return rule.selector ? page.textContent(selector) : page.evaluate(() => document.body?.innerText ?? "")
      case "screenshot": {
        const buffer = rule.selector ? await page.locator(rule.selector).screenshot() : await page.screenshot()
        return buffer ? `data:image/png;base64,${buffer.toString("base64")}` : ""
      }
      default: throw new Error(`Unknown format: ${rule.format}`)
    }
  },
}