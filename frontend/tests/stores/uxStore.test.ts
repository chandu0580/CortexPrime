import { describe, it, expect, beforeEach } from "vitest"
import { useUxStore } from "@/store/uxStore"
import type { NotificationItem } from "@/store/uxStore"

function buildNotifications(): NotificationItem[] {
  return [
    { id: "n1", type: "mission_completed", title: "Research mission completed", description: "Market intelligence mission finished successfully in 24m 18s", timestamp: "", read: false, priority: "medium" },
    { id: "n2", type: "approval_required", title: "Approval required", description: "Deployment to production needs executive approval", timestamp: "", read: false, priority: "critical" },
    { id: "n3", type: "security_alert", title: "Security alert", description: "Unusual API key usage detected from new IP", timestamp: "", read: false, priority: "high" },
    { id: "n4", type: "worker_error", title: "Browser worker error", description: "Worker bw-004 encountered timeout on page load", timestamp: "", read: false, priority: "high" },
    { id: "n5", type: "connector_sync", title: "GitHub sync complete", description: "All repositories synchronized successfully", timestamp: "", read: true, priority: "low" },
    { id: "n6", type: "runtime_warning", title: "High memory usage", description: "Runtime memory at 82% — consider scaling up", timestamp: "", read: true, priority: "medium" },
    { id: "n7", type: "replay_ready", title: "Replay data available", description: "Enterprise replay data for exec-789 is ready for review", timestamp: "", read: true, priority: "low" },
    { id: "n8", type: "deployment_success", title: "Deployment successful", description: "v3.2.1 deployed to staging environment", timestamp: "", read: true, priority: "medium" },
    { id: "n9", type: "certification_passed", title: "Certification passed", description: "Full certification suite passed all 142 tests", timestamp: "", read: false, priority: "medium" },
    { id: "n10", type: "mission_completed", title: "Data analysis complete", description: "Q3 financial analysis mission completed with 98% confidence", timestamp: "", read: true, priority: "low" },
    { id: "n11", type: "connector_sync", title: "Jira sync delayed", description: "Jira connector sync delayed due to rate limiting", timestamp: "", read: true, priority: "medium" },
    { id: "n12", type: "security_alert", title: "New user added", description: "User jane.doe@example.com was added to Engineering group", timestamp: "", read: false, priority: "low" },
  ]
}

describe("useUxStore", () => {
  beforeEach(() => {
    useUxStore.setState({
      commandCenterOpen: false,
      notificationCenterOpen: false,
      activityFeedOpen: false,
      preferencesOpen: false,
      shortcutsModalOpen: false,
      themePanelOpen: false,
      notifications: buildNotifications(),
      unreadCount: 6,
      accentColor: "#38B88A",
      themePreset: "cortex",
      contrast: "normal",
      fontSize: "medium",
      reducedMotion: false,
    })
  })

  it("has correct initial state with 12 notifications and correct unreadCount", () => {
    const state = useUxStore.getState()
    expect(state.notifications).toHaveLength(12)
    expect(state.unreadCount).toBe(6)
    expect(state.commandCenterOpen).toBe(false)
    expect(state.notificationCenterOpen).toBe(false)
    expect(state.activityFeedOpen).toBe(false)
    expect(state.preferencesOpen).toBe(false)
    expect(state.shortcutsModalOpen).toBe(false)
    expect(state.themePanelOpen).toBe(false)
    expect(state.accentColor).toBe("#38B88A")
    expect(state.themePreset).toBe("cortex")
    expect(state.contrast).toBe("normal")
    expect(state.fontSize).toBe("medium")
    expect(state.reducedMotion).toBe(false)
  })

  it("markNotificationRead marks specific notification as read and decrements unreadCount", () => {
    const n2 = useUxStore.getState().notifications.find((n) => n.id === "n2")
    expect(n2?.read).toBe(false)

    useUxStore.getState().markNotificationRead("n2")

    const updated = useUxStore.getState().notifications.find((n) => n.id === "n2")
    expect(updated?.read).toBe(true)
    expect(useUxStore.getState().unreadCount).toBe(5)
  })

  it("markNotificationRead does not affect other notifications", () => {
    useUxStore.getState().markNotificationRead("n2")

    const n1 = useUxStore.getState().notifications.find((n) => n.id === "n1")
    expect(n1?.read).toBe(false)
  })

  it("markAllNotificationsRead marks all as read and sets unreadCount to 0", () => {
    useUxStore.getState().markAllNotificationsRead()

    const state = useUxStore.getState()
    expect(state.notifications.every((n) => n.read)).toBe(true)
    expect(state.unreadCount).toBe(0)
  })

  it("addNotification prepends to list and increments unreadCount", () => {
    const newNotif: NotificationItem = {
      id: "n13",
      type: "mission_completed",
      title: "New mission",
      description: "Test",
      timestamp: new Date().toISOString(),
      read: false,
      priority: "low",
    }

    useUxStore.getState().addNotification(newNotif)

    const state = useUxStore.getState()
    expect(state.notifications).toHaveLength(13)
    expect(state.notifications[0].id).toBe("n13")
    expect(state.unreadCount).toBe(7)
  })

  it("addNotification does not increment unreadCount for pre-read notifications", () => {
    const newNotif: NotificationItem = {
      id: "n13",
      type: "mission_completed",
      title: "New mission",
      description: "Test",
      timestamp: new Date().toISOString(),
      read: true,
      priority: "low",
    }

    useUxStore.getState().addNotification(newNotif)

    expect(useUxStore.getState().unreadCount).toBe(6)
  })

  it("setCommandCenterOpen updates commandCenterOpen", () => {
    useUxStore.getState().setCommandCenterOpen(true)
    expect(useUxStore.getState().commandCenterOpen).toBe(true)
  })

  it("setNotificationCenterOpen updates notificationCenterOpen", () => {
    useUxStore.getState().setNotificationCenterOpen(true)
    expect(useUxStore.getState().notificationCenterOpen).toBe(true)
  })

  it("setActivityFeedOpen updates activityFeedOpen", () => {
    useUxStore.getState().setActivityFeedOpen(true)
    expect(useUxStore.getState().activityFeedOpen).toBe(true)
  })

  it("setPreferencesOpen updates preferencesOpen", () => {
    useUxStore.getState().setPreferencesOpen(true)
    expect(useUxStore.getState().preferencesOpen).toBe(true)
  })

  it("setShortcutsModalOpen updates shortcutsModalOpen", () => {
    useUxStore.getState().setShortcutsModalOpen(true)
    expect(useUxStore.getState().shortcutsModalOpen).toBe(true)
  })

  it("setThemePanelOpen updates themePanelOpen", () => {
    useUxStore.getState().setThemePanelOpen(true)
    expect(useUxStore.getState().themePanelOpen).toBe(true)
  })

  it("setAccentColor updates accentColor", () => {
    useUxStore.getState().setAccentColor("#ff0000")
    expect(useUxStore.getState().accentColor).toBe("#ff0000")
  })

  it("setThemePreset updates themePreset", () => {
    useUxStore.getState().setThemePreset("ocean")
    expect(useUxStore.getState().themePreset).toBe("ocean")
  })

  it("setContrast updates contrast", () => {
    useUxStore.getState().setContrast("high")
    expect(useUxStore.getState().contrast).toBe("high")
  })

  it("setFontSize updates fontSize", () => {
    useUxStore.getState().setFontSize("large")
    expect(useUxStore.getState().fontSize).toBe("large")
  })

  it("setReducedMotion updates reducedMotion", () => {
    useUxStore.getState().setReducedMotion(true)
    expect(useUxStore.getState().reducedMotion).toBe(true)
  })
})
