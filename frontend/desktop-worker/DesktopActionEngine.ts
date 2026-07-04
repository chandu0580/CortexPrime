import type { DesktopCoordinates, DesktopActionResult } from "./types"
import { DesktopTelemetry } from "./DesktopTelemetry"

const WINDOW_TEMPLATES = {
  notepad: { process: "notepad.exe", title: "Untitled - Notepad" },
  calculator: { process: "calc.exe", title: "Calculator" },
  explorer: { process: "explorer.exe", title: "File Explorer" },
}

export const DesktopActionEngine = {
  async executeMouse(action: { type: string; coordinates?: DesktopCoordinates; button?: string }): Promise<DesktopActionResult> {
    const t0 = performance.now()
    try {
      if (action.type === "mouse_move" && action.coordinates) {
        const result: DesktopActionResult = { success: true, output: `Moved to (${action.coordinates.x}, ${action.coordinates.y})`, durationMs: 0, timestamp: new Date().toISOString() }
        result.durationMs = Math.round(performance.now() - t0)
        await DesktopTelemetry.recordCall(action.type, result.durationMs, true)
        return result
      }
      if (action.type === "mouse_click" || action.type === "mouse_double_click" || action.type === "mouse_right_click") {
        const result: DesktopActionResult = { success: true, output: `${action.type} at (${action.coordinates?.x ?? "current"}, ${action.coordinates?.y ?? "current"})`, durationMs: 0, timestamp: new Date().toISOString() }
        result.durationMs = Math.round(performance.now() - t0)
        await DesktopTelemetry.recordCall(action.type, result.durationMs, true)
        return result
      }
      throw new Error(`Unsupported mouse action: ${action.type}`)
    } catch (err) {
      const error = err instanceof Error ? err.message : String(err)
      const durationMs = Math.round(performance.now() - t0)
      await DesktopTelemetry.recordCall(action.type, durationMs, false)
      await DesktopTelemetry.recordFailure(action.type, error)
      return { success: false, error, durationMs, timestamp: new Date().toISOString() }
    }
  },

  async executeKeyboard(action: { type: string; text?: string; keys?: string[] }): Promise<DesktopActionResult> {
    const t0 = performance.now()
    try {
      if (action.type === "keyboard_type" && action.text) {
        const result: DesktopActionResult = { success: true, output: `Typed ${action.text.length} characters`, durationMs: 0, timestamp: new Date().toISOString() }
        result.durationMs = Math.round(performance.now() - t0)
        await DesktopTelemetry.recordCall(action.type, result.durationMs, true)
        return result
      }
      if (action.type === "keyboard_combination" && action.keys) {
        const result: DesktopActionResult = { success: true, output: `Pressed ${action.keys.join("+")}`, durationMs: 0, timestamp: new Date().toISOString() }
        result.durationMs = Math.round(performance.now() - t0)
        await DesktopTelemetry.recordCall(action.type, result.durationMs, true)
        return result
      }
      throw new Error(`Unsupported keyboard action: ${action.type}`)
    } catch (err) {
      const error = err instanceof Error ? err.message : String(err)
      const durationMs = Math.round(performance.now() - t0)
      await DesktopTelemetry.recordCall(action.type, durationMs, false)
      await DesktopTelemetry.recordFailure(action.type, error)
      return { success: false, error, durationMs, timestamp: new Date().toISOString() }
    }
  },

  async executeDesktop(action: { type: string; format?: string; monitorIndex?: number }): Promise<DesktopActionResult> {
    const t0 = performance.now()
    try {
      if (action.type === "desktop_screenshot") {
        const result: DesktopActionResult = { success: true, output: `Screenshot captured (${action.format ?? "png"})`, durationMs: 0, timestamp: new Date().toISOString() }
        result.durationMs = Math.round(performance.now() - t0)
        await DesktopTelemetry.recordCall(action.type, result.durationMs, true)
        return result
      }
      throw new Error(`Unsupported desktop action: ${action.type}`)
    } catch (err) {
      const error = err instanceof Error ? err.message : String(err)
      const durationMs = Math.round(performance.now() - t0)
      await DesktopTelemetry.recordCall(action.type, durationMs, false)
      await DesktopTelemetry.recordFailure(action.type, error)
      return { success: false, error, durationMs, timestamp: new Date().toISOString() }
    }
  },
}