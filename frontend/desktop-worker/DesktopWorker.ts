import { AbstractWorker } from "@/worker-framework/AbstractWorker"
import type { IKernel, IEventBus, ITelemetry, IExecutionResult } from "@/platform/interfaces"
import type { PlatformContext } from "@/platform/contracts"
import type { PlatformCapability } from "@/platform/contracts"
import type { WorkerConfiguration } from "@/worker-framework/types"
import type { DesktopWorkerConfig, DesktopTaskPayload, DesktopSession } from "./types"
import { DesktopSessionManager } from "./DesktopSessionManager"
import { DesktopActionEngine } from "./DesktopActionEngine"
import { DesktopWindowManager } from "./DesktopWindowManager"
import { DesktopFileManager } from "./DesktopFileManager"
import { DesktopApplicationManager } from "./DesktopApplicationManager"
import { DesktopClipboardManager, DesktopDialogManager } from "./DesktopClipboardManager"
import { DesktopCapability } from "./DesktopCapability"
import { DesktopTelemetry } from "./DesktopTelemetry"
import { DesktopHealthManager } from "./DesktopHealthManager"
import { DesktopEventBus } from "./DesktopEventBus"

const DEFAULT_DESKTOP_CONFIG: DesktopWorkerConfig = {
  maxSessions: 3,
  sessionTimeoutMs: 300000,
  screenshotOnAction: true,
  screenshotFormat: "png",
  allowedMonitors: [0],
  blockedPaths: [],
  trustedApplications: ["notepad.exe", "calc.exe", "code.exe", "chrome.exe", "explorer.exe"],
  maxFileSizeBytes: 104857600,
}

const DEFAULT_WORKER_CONFIG: WorkerConfiguration = {
  maxConcurrentTasks: 3,
  heartbeatIntervalMs: 15000,
  healthCheckIntervalMs: 30000,
  taskTimeoutMs: 60000,
  autoRecovery: true,
  maxRetries: 3,
  settings: {},
}

const DESKTOP_CAPABILITIES: PlatformCapability[] = [
  DesktopCapability.createDefault().toPlatformCapability(),
]

export class DesktopWorker extends AbstractWorker {
  private readonly desktopConfig: DesktopWorkerConfig
  protected tasksCompleted = 0
  protected tasksFailed = 0

  constructor(kernel: IKernel, eventBus: IEventBus, telemetry: ITelemetry, desktopConfig?: Partial<DesktopWorkerConfig>) {
    const mergedConfig = { ...DEFAULT_DESKTOP_CONFIG, ...desktopConfig }
    super(
      {
        id: `desktop-worker-${Date.now()}`,
        name: "Desktop Worker",
        type: "desktop-worker",
        version: "1.0.0",
        description: "Desktop automation worker for mouse, keyboard, window, file, clipboard, dialog, and application operations",
        capabilities: DESKTOP_CAPABILITIES,
        metadata: { maxSessions: String(mergedConfig.maxSessions) },
      },
      { ...DEFAULT_WORKER_CONFIG, settings: { desktopConfig: mergedConfig } },
      kernel,
      eventBus,
      telemetry,
    )
    this.desktopConfig = mergedConfig
    DesktopEventBus.initialize()
  }

  async execute(taskId: string, payload: Record<string, unknown>, context: PlatformContext): Promise<IExecutionResult> {
    const taskPayload = payload as unknown as DesktopTaskPayload
    const startedAt = new Date().toISOString()
    const session = DesktopSessionManager.createSession({ taskId, type: taskPayload.type })

    try {
      const result = await this.dispatchAction(session, taskPayload)
      DesktopSessionManager.recordAction(session.id)
      DesktopHealthManager.recordSuccess()

      if (result.success) {
        this.tasksCompleted++
        await DesktopEventBus.publishAction(session.id, taskPayload.type, result)
        return {
          success: true,
          sessionId: session.id,
          output: (result.output ?? null) as Record<string, unknown> | null,
          error: null,
          startedAt,
          completedAt: new Date().toISOString(),
          durationMs: result.durationMs,
        }
      }

      this.tasksFailed++
      DesktopHealthManager.recordError()
      await DesktopEventBus.publishAction(session.id, taskPayload.type, result)
      return {
        success: false,
        sessionId: session.id,
        output: null,
        error: result.error ? {
          code: "DESKTOP_ACTION_FAILED",
          message: result.error,
          module: this.descriptor.id,
          severity: "error" as const,
          timestamp: new Date().toISOString(),
          details: null,
          cause: null,
        } : null,
        startedAt,
        completedAt: new Date().toISOString(),
        durationMs: result.durationMs,
      }
    } catch (err) {
      this.tasksFailed++
      DesktopHealthManager.recordError()
      const errorMessage = err instanceof Error ? err.message : String(err)
      await DesktopTelemetry.recordFailure(taskPayload.type, errorMessage)
      return {
        success: false,
        sessionId: session.id,
        output: null,
        error: {
          code: "DESKTOP_EXECUTION_FAILED",
          message: errorMessage,
          module: this.descriptor.id,
          severity: "error" as const,
          timestamp: new Date().toISOString(),
          details: null,
          cause: null,
        },
        startedAt,
        completedAt: new Date().toISOString(),
        durationMs: 0,
      }
    }
  }

  private async dispatchAction(session: DesktopSession, payload: DesktopTaskPayload) {
    switch (payload.type) {
      // Mouse actions
      case "mouse_move":
      case "mouse_click":
      case "mouse_double_click":
      case "mouse_right_click":
        return DesktopActionEngine.executeMouse(payload)

      // Keyboard actions
      case "keyboard_type":
      case "keyboard_combination":
      case "keyboard_shortcut":
      case "keyboard_hotkey":
        return DesktopActionEngine.executeKeyboard(payload)

      // Desktop info actions
      case "desktop_screenshot":
      case "descreen_info":
      case "desktop_monitor_info":
        return DesktopActionEngine.executeDesktop(payload)

      // Window actions
      case "window_list":
        return DesktopWindowManager.listWindows()
      case "window_focus":
        return DesktopWindowManager.focusWindow((payload as { windowId: string }).windowId)
      case "window_minimize":
        return DesktopWindowManager.minimizeWindow((payload as { windowId: string }).windowId ?? "")
      case "window_maximize":
        return DesktopWindowManager.maximizeWindow((payload as { windowId: string }).windowId ?? "")
      case "window_restore":
        return DesktopWindowManager.restoreWindow((payload as { windowId: string }).windowId ?? "")
      case "window_close":
        return DesktopWindowManager.closeWindow((payload as { windowId: string }).windowId ?? "")

      // File actions
      case "file_create":
        return DesktopFileManager.createFile((payload as { path: string; content?: string }).path, (payload as { content?: string }).content)
      case "file_move":
        return DesktopFileManager.moveFile((payload as { sourcePath: string; destinationPath: string }).sourcePath, (payload as { sourcePath: string; destinationPath: string }).destinationPath)
      case "file_rename":
        return DesktopFileManager.renameFile((payload as { path: string; destinationPath: string }).path, (payload as { path: string; destinationPath: string }).destinationPath)
      case "file_copy":
        return DesktopFileManager.copyFile((payload as { sourcePath: string; destinationPath: string }).sourcePath, (payload as { sourcePath: string; destinationPath: string }).destinationPath)
      case "file_delete":
        return DesktopFileManager.deleteFile((payload as { path: string }).path)
      case "file_search":
        return DesktopFileManager.searchFiles((payload as { query: string }).query)
      case "file_upload":
        return DesktopFileManager.uploadFile((payload as { url: string; destinationPath: string }).url, (payload as { url: string; destinationPath: string }).destinationPath)
      case "file_download":
        return DesktopFileManager.downloadFile((payload as { sourcePath: string; url: string }).sourcePath, (payload as { sourcePath: string; url: string }).url)

      // Clipboard actions
      case "clipboard_read":
        return DesktopClipboardManager.readClipboard()
      case "clipboard_write":
        return DesktopClipboardManager.writeClipboard((payload as { content: string }).content)
      case "clipboard_clear":
        return DesktopClipboardManager.clearClipboard()

      // Dialog actions
      case "dialog_open":
        return DesktopDialogManager.openDialog((payload as { path?: string; filter?: string }).path, (payload as { filter?: string }).filter)
      case "dialog_save":
        return DesktopDialogManager.saveDialog((payload as { path?: string; defaultName?: string }).path, (payload as { defaultName?: string }).defaultName)
      case "dialog_file_picker":
        return DesktopDialogManager.filePicker((payload as { path?: string; filter?: string }).path, (payload as { filter?: string }).filter)

      // Application actions
      case "app_launch":
        return DesktopApplicationManager.launchApplication((payload as { applicationName: string; arguments?: string[] }).applicationName, (payload as { arguments?: string[] }).arguments)
      case "app_apply":
        return DesktopApplicationManager.closeApplication((payload as { applicationName: string }).applicationName)
      case "app_list":
        return DesktopApplicationManager.listApplications()
      case "app_activate":
        return DesktopApplicationManager.activateApplication((payload as { applicationName: string }).applicationName)

      default:
        return { success: false, error: `Unknown desktop action: ${(payload as { type: string }).type}`, durationMs: 0, timestamp: new Date().toISOString() }
    }
  }

  getTasksCompleted(): number { return this.tasksCompleted }

  getTasksFailed(): number { return this.tasksFailed }

  getCapability(): DesktopCapability { return DesktopCapability.createDefault() }

  getHealth() { return DesktopHealthManager.getHealth() }

  getMetrics() { return DesktopTelemetry.getMetrics() }
}