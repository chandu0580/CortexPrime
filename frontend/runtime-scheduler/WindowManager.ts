import type { ScheduleWindow, ExecutionCalendar, WindowRecurrence } from "./types"
import { generateId } from "./shared"

export const WindowManager = {
  async createWindow(
    openAt: string,
    closeAt: string,
    timezone: string = "UTC",
    recurrence: WindowRecurrence = "none",
    daysOfWeek: number[] = [],
  ): Promise<ScheduleWindow> {
    return {
      id: generateId("window"),
      openAt,
      closeAt,
      timezone,
      recurrence,
      daysOfWeek,
    }
  },

  async isWithinWindow(window: ScheduleWindow): Promise<boolean> {
    const now = new Date()
    const open = new Date(window.openAt)
    const close = new Date(window.closeAt)

    if (window.recurrence === "none") {
      return now >= open && now <= close
    }

    if (window.daysOfWeek.length > 0) {
      const today = now.getDay()
      if (!window.daysOfWeek.includes(today)) return false
    }

    const timeOfDay = now.getHours() * 60 + now.getMinutes()
    const openTime = open.getHours() * 60 + open.getMinutes()
    const closeTime = close.getHours() * 60 + close.getMinutes()

    return timeOfDay >= openTime && timeOfDay <= closeTime
  },

  async getNextWindowOpen(window: ScheduleWindow): Promise<string | null> {
    if (window.recurrence === "none") {
      const open = new Date(window.openAt)
      return open > new Date() ? window.openAt : null
    }

    const now = new Date()
    const open = new Date(window.openAt)
    const candidate = new Date(open)

    while (candidate <= now) {
      if (window.recurrence === "daily") {
        candidate.setDate(candidate.getDate() + 1)
      } else if (window.recurrence === "weekly") {
        candidate.setDate(candidate.getDate() + 7)
      } else if (window.recurrence === "monthly") {
        candidate.setMonth(candidate.getMonth() + 1)
      } else {
        break
      }

      if (window.daysOfWeek.length > 0) {
        const day = candidate.getDay()
        if (!window.daysOfWeek.includes(day)) continue
      }

      if (candidate > now) {
        return candidate.toISOString()
      }
    }

    return candidate > now ? candidate.toISOString() : null
  },

  async createCalendar(sessionId: string, windows: ScheduleWindow[]): Promise<ExecutionCalendar> {
    const now = new Date()
    const currentWindow = windows.find((w) => {
      const open = new Date(w.openAt)
      const close = new Date(w.closeAt)
      return now >= open && now <= close
    }) ?? null

    return {
      id: generateId("calendar"),
      sessionId,
      availableWindows: windows,
      blockedWindows: [],
      currentWindow,
    }
  },
}
