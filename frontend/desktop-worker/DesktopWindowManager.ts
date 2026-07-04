import { DesktopTelemetry } from "./DesktopTelemetry"
import type { DesktopActionResult } from "./types"

const WINDOW_LABELS = { "notepad.exe": "Notepad", "calc.exe": "Calculator", "explorer.exe": "File Explorer", "code.exe": "VS Code", "chrome.exe": "Chrome" }

export const DesktopWindowManager = {
  async listWindows(): Promise<DesktopActionResult> {
    const t0 = performance.now()
    const windows = Object.entries(WINDOW_LABELS).map(([process, title]) => ({ id: `win_${process}`, title, process, focused: false }))
    const result: DesktopActionResult = { success: true, output: windows, durationMs: Math.round(performance.now() - t0), timestamp: new Date().toISOString() }
    await DesktopTelemetry.recordCall("window_list", result.durationMs, true)
    return result
  },

  async focusWindow(windowId: string): Promise<DesktopActionResult> {
    const t0 = performance.now()
    try {
      const process = windowId.replace("win_", "")
      const title = WINDOW_LABELS[process as keyof typeof WINDOW_LABELS] ?? process
      const result: DesktopActionResult = { success: true, output: `Focused: ${title}`, durationMs: Math.round(performance.now() - t0), timestamp: new Date().toISOString() }
      await DesktopTelemetry.recordCall("window_focus", result.durationMs, true)
      return result
    } catch (err) {
      const error = err instanceof Error ? err.message : String(err)
      const durationMs = Math.round(performance.now() - t0)
      await DesktopTelemetry.recordCall("window_focus", durationMs, false)
      await DesktopTelemetry.recordFailure("window_focus", error)
      return { success: false, error, durationMs, timestamp: new Date().toISOString() }
    }
  },

  async minimizeWindow(windowId: string): Promise<DesktopActionResult> {
    const t0 = performance.now()
    const result: DesktopActionResult = { success: true, output: `Minimized: ${windowId}`, durationMs: Math.round(performance.now() - t0), timestamp: new Date().toISOString() }
    await DesktopTelemetry.recordCall("window_minimize", result.durationMs, true)
    return result
  },

  async maximizeWindow(windowId: string): Promise<DesktopActionResult> {
    const t0 = performance.now()
    const result: DesktopActionResult = { success: true, output: `Maximized: ${windowId}`, durationMs: Math.round(performance.now() - t0), timestamp: new Date().toISOString() }
    await DesktopTelemetry.recordCall("window_maximize", result.durationMs, true)
    return result
  },

  async restoreWindow(windowId: string): Promise<DesktopActionResult> {
    const t0 = performance.now()
    const result: DesktopActionResult = { success: true, output: `Restored: ${windowId}`, durationMs: Math.round(performance.now() - t0), timestamp: new Date().toISOString() }
    await DesktopTelemetry.recordCall("window_restore", result.durationMs, true)
    return result
  },

  async closeWindow(windowId: string): Promise<DesktopActionResult> {
    const t0 = performance.now()
    const result: DesktopActionResult = { success: true, output: `Closed: ${windowId}`, durationMs: Math.round(performance.now() - t0), timestamp: new Date().toISOString() }
    await DesktopTelemetry.recordCall("window_close", result.durationMs, true)
    return result
  },
}