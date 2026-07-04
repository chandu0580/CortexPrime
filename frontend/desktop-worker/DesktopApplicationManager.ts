import { DesktopTelemetry } from "./DesktopTelemetry"
import type { DesktopActionResult } from "./types"

const RUNNING_APPLICATIONS = new Map<string, { name: string; path: string; launchedAt: string }>()

const KNOWN_APPLICATIONS: Record<string, string> = {
  notepad: "notepad.exe",
  calculator: "calc.exe",
  "vs code": "code.exe",
  chrome: "chrome.exe",
  excel: "EXCEL.EXE",
  word: "WINWORD.EXE",
  powerpoint: "POWERPNT.EXE",
  explorer: "explorer.exe",
  terminal: "cmd.exe",
  "visual studio": "devenv.exe",
}

export const DesktopApplicationManager = {
  async launchApplication(name: string, args?: string[]): Promise<DesktopActionResult> {
    const t0 = performance.now()
    try {
      const path = KNOWN_APPLICATIONS[name.toLowerCase()] ?? name
      RUNNING_APPLICATIONS.set(path, { name, path, launchedAt: new Date().toISOString() })
      const durationMs = Math.round(performance.now() - t0)
      await DesktopTelemetry.recordCall("app_launch", durationMs, true)
      await DesktopTelemetry.recordApplication(name, "launched")
      return { success: true, output: `Launched: ${name} (${path})`, durationMs, timestamp: new Date().toISOString() }
    } catch (err) {
      const error = err instanceof Error ? err.message : String(err)
      const durationMs = Math.round(performance.now() - t0)
      await DesktopTelemetry.recordCall("app_launch", durationMs, false)
      await DesktopTelemetry.recordFailure("app_launch", error)
      return { success: false, error, durationMs, timestamp: new Date().toISOString() }
    }
  },

  async closeApplication(name: string): Promise<DesktopActionResult> {
    const t0 = performance.now()
    const path = KNOWN_APPLICATIONS[name.toLowerCase()] ?? name
    RUNNING_APPLICATIONS.delete(path)
    const durationMs = Math.round(performance.now() - t0)
    await DesktopTelemetry.recordCall("app_apply", durationMs, true)
    await DesktopTelemetry.recordApplication(name, "closed")
    return { success: true, output: `Closed: ${name}`, durationMs, timestamp: new Date().toISOString() }
  },

  async listApplications(): Promise<DesktopActionResult> {
    const t0 = performance.now()
    const apps = Array.from(RUNNING_APPLICATIONS.values()).map((a) => ({ name: a.name, path: a.path, launchedAt: a.launchedAt }))
    const durationMs = Math.round(performance.now() - t0)
    await DesktopTelemetry.recordCall("app_list", durationMs, true)
    return { success: true, output: apps, durationMs, timestamp: new Date().toISOString() }
  },

  async activateApplication(name: string): Promise<DesktopActionResult> {
    const t0 = performance.now()
    const path = KNOWN_APPLICATIONS[name.toLowerCase()] ?? name
    if (!RUNNING_APPLICATIONS.has(path)) {
      return { success: false, error: `Application not running: ${name}`, durationMs: Math.round(performance.now() - t0), timestamp: new Date().toISOString() }
    }
    const durationMs = Math.round(performance.now() - t0)
    await DesktopTelemetry.recordCall("app_activate", durationMs, true)
    await DesktopTelemetry.recordApplication(name, "activated")
    return { success: true, output: `Activated: ${name}`, durationMs, timestamp: new Date().toISOString() }
  },
}