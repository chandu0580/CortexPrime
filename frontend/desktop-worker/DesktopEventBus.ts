import type { DesktopEventType, DesktopActionResult, DesktopSession } from "./types"

const SUBSCRIBERS = new Map<string, Set<(data: Record<string, unknown>) => void>>()

export const DesktopEventBus = {
  initialize(): void {
  },

  async publish(eventType: DesktopEventType, data: Record<string, unknown>): Promise<void> {
    const handlers = SUBSCRIBERS.get(eventType)
    if (handlers) {
      for (const handler of handlers) {
        try { handler(data) } catch { }
      }
    }
  },

  subscribe(eventType: DesktopEventType, handler: (data: Record<string, unknown>) => void): () => void {
    if (!SUBSCRIBERS.has(eventType)) SUBSCRIBERS.set(eventType, new Set())
    SUBSCRIBERS.get(eventType)!.add(handler)
    return () => SUBSCRIBERS.get(eventType)?.delete(handler)
  },

  async publishAction(sessionId: string, action: string, result: DesktopActionResult): Promise<void> {
    await DesktopEventBus.publish(result.success ? "desktop.completed" : "desktop.failed", {
      sessionId, action, success: result.success, durationMs: result.durationMs, error: result.error,
    })
  },

  async publishWindowChanged(sessionId: string, windowId: string, action: string): Promise<void> {
    await DesktopEventBus.publish("desktop.window.changed", { sessionId, windowId, action })
  },

  async publishFileChanged(sessionId: string, path: string, action: string): Promise<void> {
    await DesktopEventBus.publish("desktop.file.changed", { sessionId, path, action })
  },

  async publishApplicationEvent(sessionId: string, app: string, action: "started" | "closed"): Promise<void> {
    const eventType = action === "started" ? "desktop.application.started" : "desktop.application.closed"
    await DesktopEventBus.publish(eventType, { sessionId, application: app })
  },
}