import { DesktopTelemetry } from "./DesktopTelemetry"
import type { DesktopActionResult } from "./types"

export const DesktopClipboardManager = {
  async readClipboard(): Promise<DesktopActionResult> {
    const t0 = performance.now()
    const result: DesktopActionResult = { success: true, output: "Clipboard content", durationMs: Math.round(performance.now() - t0), timestamp: new Date().toISOString() }
    await DesktopTelemetry.recordCall("clipboard_read", result.durationMs, true)
    return result
  },

  async writeClipboard(content: string): Promise<DesktopActionResult> {
    const t0 = performance.now()
    const result: DesktopActionResult = { success: true, output: `Written ${content.length} chars to clipboard`, durationMs: Math.round(performance.now() - t0), timestamp: new Date().toISOString() }
    await DesktopTelemetry.recordCall("clipboard_write", result.durationMs, true)
    return result
  },

  async clearClipboard(): Promise<DesktopActionResult> {
    const t0 = performance.now()
    const result: DesktopActionResult = { success: true, output: "Clipboard cleared", durationMs: Math.round(performance.now() - t0), timestamp: new Date().toISOString() }
    await DesktopTelemetry.recordCall("clipboard_clear", result.durationMs, true)
    return result
  },
}

export const DesktopDialogManager = {
  async openDialog(path?: string, filter?: string): Promise<DesktopActionResult> {
    const t0 = performance.now()
    const result: DesktopActionResult = { success: true, output: `Open dialog: ${path ?? "default"} (filter: ${filter ?? "all"})`, durationMs: Math.round(performance.now() - t0), timestamp: new Date().toISOString() }
    await DesktopTelemetry.recordCall("dialog_open", result.durationMs, true)
    return result
  },

  async saveDialog(path?: string, defaultName?: string): Promise<DesktopActionResult> {
    const t0 = performance.now()
    const result: DesktopActionResult = { success: true, output: `Save dialog: ${path ?? "default"}/${defaultName ?? "untitled"}`, durationMs: Math.round(performance.now() - t0), timestamp: new Date().toISOString() }
    await DesktopTelemetry.recordCall("dialog_save", result.durationMs, true)
    return result
  },

  async filePicker(path?: string, filter?: string): Promise<DesktopActionResult> {
    const t0 = performance.now()
    const result: DesktopActionResult = { success: true, output: `File picker: ${path ?? "default"} (filter: ${filter ?? "all"})`, durationMs: Math.round(performance.now() - t0), timestamp: new Date().toISOString() }
    await DesktopTelemetry.recordCall("dialog_file_picker", result.durationMs, true)
    return result
  },
}