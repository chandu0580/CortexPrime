import type { PlatformContext, PlatformCapability } from "@/platform/contracts"
import type { IKernel, IEventBus, ITelemetry, IExecutionResult } from "@/platform/interfaces"
import type { WorkerConfiguration } from "@/worker-framework/types"
import { AbstractWorker } from "@/worker-framework/AbstractWorker"
import type { BrowserWorkerConfig, BrowserTaskPayload } from "./types"
import { BrowserSessionManager } from "./BrowserSessionManager"
import { BrowserNavigationEngine } from "./BrowserNavigationEngine"
import { BrowserActionEngine } from "./BrowserActionEngine"
import { BrowserExtractionEngine } from "./BrowserExtractionEngine"
import { BrowserTelemetry } from "./BrowserTelemetry"

const DEFAULT_BROWSER_CONFIG: BrowserWorkerConfig = {
  maxConcurrentSessions: 5,
  sessionTimeoutMs: 300_000,
  defaultNavigationTimeoutMs: 30_000,
  defaultWaitTimeoutMs: 5_000,
  maxActionsPerSession: 100,
  headless: true,
  viewportWidth: 1920,
  viewportHeight: 1080,
  userAgent: "CortexPrime-BrowserWorker/1.0",
  browserType: "chromium",
  defaultSecurityPolicy: {
    allowedDomains: [],
    blockedDomains: [],
    allowedActions: [],
    blockedActions: ["evaluate"],
    maxNavigationDepth: 5,
    maxPageSizeBytes: 10_485_760,
    sandboxEnabled: true,
    javascriptEnabled: true,
    cookiePolicy: "allow_session",
    contentSecurityPolicy: null,
  },
}

const DEFAULT_WORKER_CONFIG: WorkerConfiguration = {
  maxConcurrentTasks: 5,
  heartbeatIntervalMs: 15_000,
  healthCheckIntervalMs: 30_000,
  taskTimeoutMs: 120_000,
  autoRecovery: true,
  maxRetries: 3,
  settings: {},
}

const BROWSER_CAPABILITIES: PlatformCapability[] = [
  { id: "browser.navigation", name: "Browser Navigation", type: "browser", version: "1.0.0", features: ["navigate", "back", "forward", "reload", "waitForNavigation"], enabled: true },
  { id: "browser.interaction", name: "Browser Interaction", type: "browser", version: "1.0.0", features: ["click", "doubleClick", "type", "fill", "select", "hover", "focus", "blur", "press", "check", "uncheck", "scroll", "dragAndDrop", "upload", "download"], enabled: true },
  { id: "browser.extraction", name: "Content Extraction", type: "browser", version: "1.0.0", features: ["text", "html", "attribute", "table", "json", "markdown", "links", "images", "forms"], enabled: true },
  { id: "browser.screenshot", name: "Page Screenshot", type: "browser", version: "1.0.0", features: ["fullpage", "viewport", "element", "png", "jpeg"], enabled: true },
  { id: "browser.pdf", name: "PDF Generation", type: "browser", version: "1.0.0", features: ["page_pdf", "custom_format", "landscape", "margins"], enabled: true },
  { id: "browser.evaluation", name: "Script Evaluation", type: "browser", version: "1.0.0", features: ["javascript"], enabled: false },
  { id: "browser.cookies", name: "Cookie Management", type: "browser", version: "1.0.0", features: ["read", "write", "clear", "session_persistence"], enabled: true },
  { id: "browser.security", name: "Browser Security", type: "browser", version: "1.0.0", features: ["domain-allowlist", "sandbox", "csp"], enabled: true },
]

export class BrowserWorker extends AbstractWorker {
  private readonly browserConfig: BrowserWorkerConfig

  constructor(
    kernel: IKernel,
    eventBus: IEventBus,
    telemetry: ITelemetry,
    browserConfig?: Partial<BrowserWorkerConfig>,
  ) {
    const mergedConfig = { ...DEFAULT_BROWSER_CONFIG, ...browserConfig }

    super(
      {
        id: `browser-worker-${Date.now()}`,
        name: "Browser Worker",
        type: "browser-worker",
        version: "1.0.0",
        description: "Web browser automation worker for navigation, interaction, and content extraction",
        capabilities: BROWSER_CAPABILITIES,
        metadata: {
          viewport: `${mergedConfig.viewportWidth}x${mergedConfig.viewportHeight}`,
          headless: String(mergedConfig.headless),
          userAgent: mergedConfig.userAgent,
          browserType: mergedConfig.browserType,
        },
      },
      { ...DEFAULT_WORKER_CONFIG, settings: { browserConfig: mergedConfig } },
      kernel,
      eventBus,
      telemetry,
    )

    this.browserConfig = mergedConfig
  }

  async execute(taskId: string, payload: Record<string, unknown>, context: PlatformContext): Promise<IExecutionResult> {
    const startTime = Date.now()
    const startedAt = new Date(startTime).toISOString()

    const activeSessions = await BrowserSessionManager.getActiveSessions()
    if (activeSessions.length >= this.browserConfig.maxConcurrentSessions) {
      return this.createError(startedAt, "MAX_SESSIONS_EXCEEDED", `Maximum concurrent sessions (${this.browserConfig.maxConcurrentSessions}) reached`)
    }

    const taskPayload = payload as unknown as BrowserTaskPayload

    const session = await BrowserSessionManager.createSession(
      this.browserConfig.defaultSecurityPolicy,
      this.browserConfig.browserType,
      this.browserConfig.headless,
    )

    try {
      let output: Record<string, unknown>

      switch (taskPayload.type) {
        case "navigation": {
          const navState = await BrowserNavigationEngine.navigate(session.id, taskPayload.target)
          const actionResults = taskPayload.actions.length > 0
            ? await BrowserActionEngine.executeActions(session.id, taskPayload.actions)
            : []
          output = {
            navigationState: navState,
            actions: actionResults,
            sessionId: session.id,
          }
          break
        }

        case "extraction": {
          const navState = await BrowserNavigationEngine.navigate(session.id, taskPayload.target)
          const extractionResult = await BrowserExtractionEngine.extract(session.id, taskPayload.rules)
          output = {
            navigationState: navState,
            extraction: extractionResult,
            sessionId: session.id,
          }
          break
        }

        case "screenshot": {
          const navState = await BrowserNavigationEngine.navigate(session.id, taskPayload.target)
          const page = await BrowserSessionManager.getPage(session.id)
          if (!page) throw new Error("No page available for screenshot")

          let screenshotData: string
          if (taskPayload.selector) {
            const buffer = await page.locator(taskPayload.selector).screenshot({
              type: taskPayload.format,
              quality: taskPayload.format === "jpeg" ? taskPayload.quality : undefined,
            })
            screenshotData = `data:image/${taskPayload.format};base64,${buffer.toString("base64")}`
          } else {
            const buffer = await page.screenshot({
              fullPage: taskPayload.fullPage,
              type: taskPayload.format,
              quality: taskPayload.format === "jpeg" ? taskPayload.quality : undefined,
            })
            screenshotData = `data:image/${taskPayload.format};base64,${buffer.toString("base64")}`
          }

          await BrowserTelemetry.recordCall("screenshot", Date.now() - startTime, true)

          output = {
            navigationState: navState,
            screenshot: {
              format: taskPayload.format,
              fullPage: taskPayload.fullPage,
              quality: taskPayload.quality,
              data: screenshotData,
              selector: taskPayload.selector ?? null,
              timestamp: new Date().toISOString(),
            },
            sessionId: session.id,
          }
          break
        }

        case "interaction": {
          const navState = await BrowserNavigationEngine.navigate(session.id, taskPayload.target)
          const actionResults = await BrowserActionEngine.executeActions(session.id, taskPayload.actions)
          let extractionResult = null
          if (taskPayload.extractAfter && taskPayload.extractAfter.length > 0) {
            extractionResult = await BrowserExtractionEngine.extract(session.id, taskPayload.extractAfter)
          }
          output = {
            navigationState: navState,
            actions: actionResults,
            extraction: extractionResult,
            sessionId: session.id,
          }
          break
        }

        case "evaluation": {
          const navState = await BrowserNavigationEngine.navigate(session.id, taskPayload.target)
          const page = await BrowserSessionManager.getPage(session.id)
          if (!page) throw new Error("No page available for evaluation")

          const evalResult = await page.evaluate(taskPayload.script, taskPayload.args)
          await BrowserTelemetry.recordCall("evaluate", Date.now() - startTime, true)

          output = {
            navigationState: navState,
            evaluation: {
              script: taskPayload.script,
              args: taskPayload.args,
              result: evalResult,
              timestamp: new Date().toISOString(),
            },
            sessionId: session.id,
          }
          break
        }

        case "pdf": {
          const navState = await BrowserNavigationEngine.navigate(session.id, taskPayload.target)
          const page = await BrowserSessionManager.getPage(session.id)
          if (!page) throw new Error("No page available for PDF generation")

          const pdfBuffer = await page.pdf({
            format: taskPayload.options?.format ?? "A4",
            landscape: taskPayload.options?.landscape ?? false,
            printBackground: taskPayload.options?.printBackground ?? true,
            margin: taskPayload.options?.margin ?? { top: "1cm", right: "1cm", bottom: "1cm", left: "1cm" },
          })

          await BrowserTelemetry.recordCall("pdf", Date.now() - startTime, true)

          output = {
            navigationState: navState,
            pdf: {
              data: `data:application/pdf;base64,${pdfBuffer.toString("base64")}`,
              format: taskPayload.options?.format ?? "A4",
              landscape: taskPayload.options?.landscape ?? false,
              timestamp: new Date().toISOString(),
            },
            sessionId: session.id,
          }
          break
        }

        case "cookies": {
          const navState = await BrowserNavigationEngine.navigate(session.id, taskPayload.target)
          const page = await BrowserSessionManager.getPage(session.id)
          if (!page) throw new Error("No page available for cookie operations")

          let cookieResult: Record<string, unknown>
          switch (taskPayload.operation) {
            case "read": {
              const context = page.context()
              const cookies = await context.cookies()
              cookieResult = { operation: "read", cookies, count: cookies.length }
              break
            }
            case "write": {
              if (taskPayload.cookies && taskPayload.cookies.length > 0) {
                const context = page.context()
                await context.addCookies(taskPayload.cookies)
                cookieResult = { operation: "write", count: taskPayload.cookies.length, success: true }
              } else {
                cookieResult = { operation: "write", count: 0, success: false, error: "No cookies provided" }
              }
              break
            }
            case "clear": {
              const context = page.context()
              await context.clearCookies()
              cookieResult = { operation: "clear", success: true }
              break
            }
            default:
              throw new Error(`Unknown cookie operation: ${taskPayload.operation}`)
          }

          await BrowserTelemetry.recordCall("cookies", Date.now() - startTime, true)

          output = {
            navigationState: navState,
            cookies: cookieResult,
            sessionId: session.id,
          }
          break
        }

        default:
          return this.createError(startedAt, "UNKNOWN_TASK_TYPE", `Unknown browser task type: ${(payload as { type?: string }).type ?? "undefined"}`)
      }

      this.tasksCompleted++

      const completedAt = new Date().toISOString()
      return {
        sessionId: context.sessionId,
        success: true,
        output,
        error: null,
        startedAt,
        completedAt,
        durationMs: Date.now() - startTime,
      }
    } catch (err) {
      this.tasksFailed++

      const completedAt = new Date().toISOString()
      return {
        sessionId: context.sessionId,
        success: false,
        output: { sessionId: session.id, taskId },
        error: {
          code: "BROWSER_TASK_FAILED",
          message: err instanceof Error ? err.message : String(err),
          module: "BrowserWorker",
          severity: "error",
          timestamp: completedAt,
          details: { taskId, payloadType: (payload as { type?: string }).type ?? "unknown" },
          cause: null,
        },
        startedAt,
        completedAt,
        durationMs: Date.now() - startTime,
      }
    } finally {
      await BrowserSessionManager.closeSession(session.id)
    }
  }

  getBrowserConfig(): BrowserWorkerConfig {
    return { ...this.browserConfig }
  }

  async getActiveSessionCount(): Promise<number> {
    return (await BrowserSessionManager.getActiveSessions()).length
  }

  private createError(startedAt: string, code: string, message: string): IExecutionResult {
    const completedAt = new Date().toISOString()
    return {
      sessionId: "",
      success: false,
      output: null,
      error: {
        code,
        message,
        module: "BrowserWorker",
        severity: "error",
        timestamp: completedAt,
        details: null,
        cause: null,
      },
      startedAt,
      completedAt,
      durationMs: 0,
    }
  }
}
