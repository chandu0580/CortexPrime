"use client"

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  Globe,
  Bell,
  LayoutDashboard,
  Settings2,
  RotateCcw,
  SlidersHorizontal,
  Clock,
  Calendar,
  ChevronDown,
  Check,
} from "lucide-react"

import { cn } from "@/utils/cn"

// ─── Types ─────────────────────────────────────────────────────────────────

type Language = "en" | "es" | "fr" | "de" | "ja" | "zh"
type DateFormat = "MM/DD/YYYY" | "DD/MM/YYYY" | "YYYY-MM-DD"
type TimeFormat = "12h" | "24h"
type NotificationChannel = "in-app" | "email" | "both"

interface NotificationSettings {
  enabled: boolean
  channel: NotificationChannel
}

type NotificationKey =
  | "mission"
  | "approval"
  | "security"
  | "worker"
  | "connector"
  | "runtime"
  | "replay"
  | "deployment"
  | "certification"

type NotificationMap = Record<NotificationKey, NotificationSettings>

interface DashboardPreferences {
  showWelcome: boolean
  defaultView: "overview" | "analytics" | "activity"
  refreshInterval: number
}

interface WorkspacePreferences {
  autoSwitch: boolean
  rememberTabs: boolean
}

interface Preferences {
  language: Language
  timezone: string
  dateFormat: DateFormat
  timeFormat: TimeFormat
  notifications: NotificationMap
  dashboardPreferences: DashboardPreferences
  workspacePreferences: WorkspacePreferences
}

interface PreferencesContextValue extends Preferences {
  setLanguage: (l: Language) => void
  setTimezone: (tz: string) => void
  setDateFormat: (f: DateFormat) => void
  setTimeFormat: (f: TimeFormat) => void
  updateNotification: (key: NotificationKey, settings: Partial<NotificationSettings>) => void
  updateDashboardPrefs: (p: Partial<DashboardPreferences>) => void
  updateWorkspacePrefs: (p: Partial<WorkspacePreferences>) => void
  resetAll: () => void
}

// ─── Defaults ──────────────────────────────────────────────────────────────

const DEFAULT_NOTIFICATIONS: NotificationMap = {
  mission: { enabled: true, channel: "in-app" },
  approval: { enabled: true, channel: "email" },
  security: { enabled: true, channel: "both" },
  worker: { enabled: true, channel: "in-app" },
  connector: { enabled: true, channel: "in-app" },
  runtime: { enabled: true, channel: "in-app" },
  replay: { enabled: true, channel: "in-app" },
  deployment: { enabled: true, channel: "email" },
  certification: { enabled: true, channel: "email" },
}

function defaultPreferences(): Preferences {
  let tz = "UTC"
  if (typeof window !== "undefined") {
    try {
      tz = Intl.DateTimeFormat().resolvedOptions().timeZone
    } catch {}
  }
  return {
    language: "en",
    timezone: tz,
    dateFormat: "MM/DD/YYYY",
    timeFormat: "12h",
    notifications: { ...DEFAULT_NOTIFICATIONS },
    dashboardPreferences: { showWelcome: true, defaultView: "overview", refreshInterval: 30 },
    workspacePreferences: { autoSwitch: true, rememberTabs: true },
  }
}

// ─── Storage ───────────────────────────────────────────────────────────────

const STORAGE_KEY = "cortex-preferences"

function loadPreferences(): Preferences {
  if (typeof window === "undefined") return defaultPreferences()
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return defaultPreferences()
    return JSON.parse(raw) as Preferences
  } catch {
    return defaultPreferences()
  }
}

function savePreferences(prefs: Preferences): void {
  if (typeof window === "undefined") return
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs))
  } catch {}
}

// ─── Context ───────────────────────────────────────────────────────────────

const PreferencesContext = createContext<PreferencesContextValue | null>(null)

// ─── Provider ──────────────────────────────────────────────────────────────

export function PreferencesProvider({ children }: { children: ReactNode }) {
  const [prefs, setPrefs] = useState<Preferences>(loadPreferences)

  useEffect(() => {
    savePreferences(prefs)
  }, [prefs])

  const setLanguage = useCallback((l: Language) => {
    setPrefs((prev) => ({ ...prev, language: l }))
  }, [])

  const setTimezone = useCallback((tz: string) => {
    setPrefs((prev) => ({ ...prev, timezone: tz }))
  }, [])

  const setDateFormat = useCallback((f: DateFormat) => {
    setPrefs((prev) => ({ ...prev, dateFormat: f }))
  }, [])

  const setTimeFormat = useCallback((f: TimeFormat) => {
    setPrefs((prev) => ({ ...prev, timeFormat: f }))
  }, [])

  const updateNotification = useCallback(
    (key: NotificationKey, settings: Partial<NotificationSettings>) => {
      setPrefs((prev) => ({
        ...prev,
        notifications: {
          ...prev.notifications,
          [key]: { ...prev.notifications[key], ...settings },
        },
      }))
    },
    [],
  )

  const updateDashboardPrefs = useCallback((p: Partial<DashboardPreferences>) => {
    setPrefs((prev) => ({
      ...prev,
      dashboardPreferences: { ...prev.dashboardPreferences, ...p },
    }))
  }, [])

  const updateWorkspacePrefs = useCallback((p: Partial<WorkspacePreferences>) => {
    setPrefs((prev) => ({
      ...prev,
      workspacePreferences: { ...prev.workspacePreferences, ...p },
    }))
  }, [])

  const resetAll = useCallback(() => {
    setPrefs(defaultPreferences())
  }, [])

  const value = useMemo<PreferencesContextValue>(
    () => ({
      ...prefs,
      setLanguage,
      setTimezone,
      setDateFormat,
      setTimeFormat,
      updateNotification,
      updateDashboardPrefs,
      updateWorkspacePrefs,
      resetAll,
    }),
    [prefs, setLanguage, setTimezone, setDateFormat, setTimeFormat, updateNotification, updateDashboardPrefs, updateWorkspacePrefs, resetAll],
  )

  return (
    <PreferencesContext.Provider value={value}>
      {children}
    </PreferencesContext.Provider>
  )
}

// ─── Hook ──────────────────────────────────────────────────────────────────

export function usePreferences(): PreferencesContextValue {
  const ctx = useContext(PreferencesContext)
  if (!ctx) throw new Error("usePreferences must be used within a PreferencesProvider")
  return ctx
}

// ─── Constants ─────────────────────────────────────────────────────────────

const LANGUAGES: { value: Language; label: string }[] = [
  { value: "en", label: "English" },
  { value: "es", label: "Spanish" },
  { value: "fr", label: "French" },
  { value: "de", label: "German" },
  { value: "ja", label: "Japanese" },
  { value: "zh", label: "Chinese" },
]

const DATE_FORMATS: DateFormat[] = ["MM/DD/YYYY", "DD/MM/YYYY", "YYYY-MM-DD"]
const TIME_FORMATS: TimeFormat[] = ["12h", "24h"]

const NOTIFICATION_LABELS: Record<NotificationKey, string> = {
  mission: "Mission",
  approval: "Approval",
  security: "Security",
  worker: "Worker",
  connector: "Connector",
  runtime: "Runtime",
  replay: "Replay",
  deployment: "Deployment",
  certification: "Certification",
}

const CHANNEL_OPTIONS: NotificationChannel[] = ["in-app", "email", "both"]

// ─── PreferencesPanel ──────────────────────────────────────────────────────

const TABS = [
  { id: "general", label: "General", icon: Globe },
  { id: "notifications", label: "Notifications", icon: Bell },
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "workspace", label: "Workspace", icon: Settings2 },
] as const

type TabId = (typeof TABS)[number]["id"]

export function PreferencesPanel({ className }: { className?: string }) {
  const [activeTab, setActiveTab] = useState<TabId>("general")
  const [tzSearch, setTzSearch] = useState("")
  const [tzOpen, setTzOpen] = useState(false)
  const prefs = usePreferences()

  const timezones = useMemo(() => {
    try {
      return (Intl as any).supportedValuesOf
        ? (Intl as any).supportedValuesOf("timeZone") as string[]
        : ["UTC", "America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles", "Europe/London", "Europe/Paris", "Europe/Berlin", "Asia/Tokyo", "Asia/Shanghai", "Australia/Sydney"]
    } catch {
      return ["UTC"]
    }
  }, [])

  const filteredTz = useMemo(
    () => timezones.filter((tz) => tz.toLowerCase().includes(tzSearch.toLowerCase())),
    [timezones, tzSearch],
  )

  const tabContent = useMemo(() => {
    switch (activeTab) {
      case "general":
        return (
          <div className="space-y-6">
            {/* Language */}
            <div>
              <label className="mb-2 block text-sm font-semibold text-[#111827]">Language</label>
              <div className="flex flex-wrap gap-2">
                {LANGUAGES.map((lang) => (
                  <motion.button
                    key={lang.value}
                    onClick={() => prefs.setLanguage(lang.value)}
                    whileTap={{ scale: 0.97 }}
                    className={cn(
                      "rounded-[12px] border px-3.5 py-2 text-xs font-semibold transition-colors",
                      prefs.language === lang.value
                        ? "border-[#38B88A] bg-[#38B88A] text-white"
                        : "border-[#E8EDF3] bg-white text-[#374151] hover:border-[#D1D5DB]",
                    )}
                  >
                    {lang.label}
                  </motion.button>
                ))}
              </div>
            </div>

            {/* Timezone */}
            <div className="relative">
              <label className="mb-2 block text-sm font-semibold text-[#111827]">Timezone</label>
              <div className="relative">
                <button
                  onClick={() => setTzOpen((o) => !o)}
                  className="flex h-11 w-full items-center justify-between rounded-[14px] border border-[#E8EDF3] bg-white px-4 text-sm text-[#374151] transition-colors hover:border-[#D1D5DB]"
                >
                  <span>{prefs.timezone}</span>
                  <ChevronDown className={cn("h-4 w-4 text-[#9CA3AF] transition-transform", tzOpen && "rotate-180")} />
                </button>
                <AnimatePresence>
                  {tzOpen && (
                    <motion.div
                      initial={{ opacity: 0, y: -8 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -8 }}
                      transition={{ duration: 0.15 }}
                      className="absolute left-0 right-0 top-full z-10 mt-1 max-h-52 overflow-y-auto rounded-[14px] border border-[#E8EDF3] bg-white shadow-[0_8px_24px_rgba(148,163,184,0.12)]"
                    >
                      <div className="sticky top-0 border-b border-[#E8EDF3] bg-white p-2">
                        <input
                          value={tzSearch}
                          onChange={(e) => setTzSearch(e.target.value)}
                          placeholder="Search timezones..."
                          className="h-9 w-full rounded-[10px] border border-[#E8EDF3] bg-[#F9FAFB] px-3 text-xs outline-none focus:border-[#38B88A]"
                        />
                      </div>
                      {filteredTz.map((tz) => (
                        <button
                          key={tz}
                          onClick={() => {
                            prefs.setTimezone(tz)
                            setTzOpen(false)
                            setTzSearch("")
                          }}
                          className={cn(
                            "flex w-full items-center gap-2 px-4 py-2.5 text-left text-xs font-medium transition-colors hover:bg-[#F9FAFB]",
                            prefs.timezone === tz ? "text-[#38B88A]" : "text-[#374151]",
                          )}
                        >
                          {prefs.timezone === tz && <Check className="h-3.5 w-3.5" />}
                          <span className={prefs.timezone === tz ? "" : "ml-5"}>{tz}</span>
                        </button>
                      ))}
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </div>

            {/* Date Format */}
            <div>
              <label className="mb-2 block text-sm font-semibold text-[#111827]">Date Format</label>
              <div className="flex gap-2">
                {DATE_FORMATS.map((fmt) => (
                  <motion.button
                    key={fmt}
                    onClick={() => prefs.setDateFormat(fmt)}
                    whileTap={{ scale: 0.97 }}
                    className={cn(
                      "flex items-center gap-1.5 rounded-[12px] border px-3.5 py-2 text-xs font-semibold transition-colors",
                      prefs.dateFormat === fmt
                        ? "border-[#38B88A] bg-[#38B88A] text-white"
                        : "border-[#E8EDF3] bg-white text-[#374151] hover:border-[#D1D5DB]",
                    )}
                  >
                    <Calendar className="h-3.5 w-3.5" />
                    {fmt}
                  </motion.button>
                ))}
              </div>
            </div>

            {/* Time Format */}
            <div>
              <label className="mb-2 block text-sm font-semibold text-[#111827]">Time Format</label>
              <div className="flex gap-2">
                {TIME_FORMATS.map((fmt) => (
                  <motion.button
                    key={fmt}
                    onClick={() => prefs.setTimeFormat(fmt)}
                    whileTap={{ scale: 0.97 }}
                    className={cn(
                      "flex items-center gap-1.5 rounded-[12px] border px-3.5 py-2 text-xs font-semibold transition-colors",
                      prefs.timeFormat === fmt
                        ? "border-[#38B88A] bg-[#38B88A] text-white"
                        : "border-[#E8EDF3] bg-white text-[#374151] hover:border-[#D1D5DB]",
                    )}
                  >
                    <Clock className="h-3.5 w-3.5" />
                    {fmt === "12h" ? "12-hour" : "24-hour"}
                  </motion.button>
                ))}
              </div>
            </div>
          </div>
        )

      case "notifications":
        return (
          <div className="space-y-3">
            {(Object.keys(NOTIFICATION_LABELS) as NotificationKey[]).map((key) => {
              const notif = prefs.notifications[key]
              return (
                <div
                  key={key}
                  className="flex items-center justify-between rounded-[14px] border border-[#E8EDF3] p-4"
                >
                  <div className="flex items-center gap-3">
                    <button
                      onClick={() => prefs.updateNotification(key, { enabled: !notif.enabled })}
                      className={cn(
                        "flex h-5 w-5 items-center justify-center rounded-[6px] border transition-colors",
                        notif.enabled
                          ? "border-[#38B88A] bg-[#38B88A]"
                          : "border-[#D1D5DB] bg-white",
                      )}
                    >
                      {notif.enabled && <Check className="h-3.5 w-3.5 text-white" strokeWidth={3} />}
                    </button>
                    <span className="text-sm font-semibold text-[#111827]">
                      {NOTIFICATION_LABELS[key]}
                    </span>
                  </div>
                  <div className="flex gap-1">
                    {CHANNEL_OPTIONS.map((ch) => (
                      <button
                        key={ch}
                        onClick={() => prefs.updateNotification(key, { channel: ch })}
                        className={cn(
                          "rounded-[8px] px-2.5 py-1 text-[10px] font-semibold transition-colors",
                          notif.channel === ch
                            ? "bg-[#38B88A] text-white"
                            : "bg-[#F3F4F6] text-[#6B7280] hover:bg-[#E5E7EB]",
                        )}
                      >
                        {ch}
                      </button>
                    ))}
                  </div>
                </div>
              )
            })}
          </div>
        )

      case "dashboard":
        return (
          <div className="space-y-6">
            <div className="flex items-center justify-between rounded-[14px] border border-[#E8EDF3] p-4">
              <span className="text-sm font-semibold text-[#111827]">Show Welcome</span>
              <button
                onClick={() => prefs.updateDashboardPrefs({ showWelcome: !prefs.dashboardPreferences.showWelcome })}
                className={cn(
                  "relative h-6 w-11 rounded-full transition-colors",
                  prefs.dashboardPreferences.showWelcome ? "bg-[#38B88A]" : "bg-[#D1D5DB]",
                )}
              >
                <span
                  className={cn(
                    "absolute left-0.5 top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform",
                    prefs.dashboardPreferences.showWelcome && "translate-x-5",
                  )}
                />
              </button>
            </div>

            <div>
              <label className="mb-2 block text-sm font-semibold text-[#111827]">Default View</label>
              <div className="flex gap-2">
                {(["overview", "analytics", "activity"] as const).map((view) => (
                  <motion.button
                    key={view}
                    onClick={() => prefs.updateDashboardPrefs({ defaultView: view })}
                    whileTap={{ scale: 0.97 }}
                    className={cn(
                      "rounded-[12px] border px-3.5 py-2 text-xs font-semibold capitalize transition-colors",
                      prefs.dashboardPreferences.defaultView === view
                        ? "border-[#38B88A] bg-[#38B88A] text-white"
                        : "border-[#E8EDF3] bg-white text-[#374151] hover:border-[#D1D5DB]",
                    )}
                  >
                    {view}
                  </motion.button>
                ))}
              </div>
            </div>

            <div>
              <label className="mb-2 block text-sm font-semibold text-[#111827]">
                Refresh Interval: {prefs.dashboardPreferences.refreshInterval}s
              </label>
              <input
                type="range"
                min="10"
                max="300"
                step="10"
                value={prefs.dashboardPreferences.refreshInterval}
                onChange={(e) => prefs.updateDashboardPrefs({ refreshInterval: Number(e.target.value) })}
                className="w-full accent-[#38B88A]"
              />
              <div className="mt-1 flex justify-between text-[10px] text-[#9CA3AF]">
                <span>10s</span>
                <span>300s</span>
              </div>
            </div>
          </div>
        )

      case "workspace":
        return (
          <div className="space-y-4">
            <div className="flex items-center justify-between rounded-[14px] border border-[#E8EDF3] p-4">
              <div>
                <p className="text-sm font-semibold text-[#111827]">Auto-Switch Workspace</p>
                <p className="text-xs text-[#6B7280]">Automatically switch to last active workspace</p>
              </div>
              <button
                onClick={() => prefs.updateWorkspacePrefs({ autoSwitch: !prefs.workspacePreferences.autoSwitch })}
                className={cn(
                  "relative h-6 w-11 rounded-full transition-colors",
                  prefs.workspacePreferences.autoSwitch ? "bg-[#38B88A]" : "bg-[#D1D5DB]",
                )}
              >
                <span
                  className={cn(
                    "absolute left-0.5 top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform",
                    prefs.workspacePreferences.autoSwitch && "translate-x-5",
                  )}
                />
              </button>
            </div>

            <div className="flex items-center justify-between rounded-[14px] border border-[#E8EDF3] p-4">
              <div>
                <p className="text-sm font-semibold text-[#111827]">Remember Tabs</p>
                <p className="text-xs text-[#6B7280]">Restore open tabs on workspace switch</p>
              </div>
              <button
                onClick={() => prefs.updateWorkspacePrefs({ rememberTabs: !prefs.workspacePreferences.rememberTabs })}
                className={cn(
                  "relative h-6 w-11 rounded-full transition-colors",
                  prefs.workspacePreferences.rememberTabs ? "bg-[#38B88A]" : "bg-[#D1D5DB]",
                )}
              >
                <span
                  className={cn(
                    "absolute left-0.5 top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform",
                    prefs.workspacePreferences.rememberTabs && "translate-x-5",
                  )}
                />
              </button>
            </div>
          </div>
        )
    }
  }, [activeTab, prefs, tzSearch, filteredTz, tzOpen])

  return (
    <div className={cn("rounded-[18px] border border-[#E8EDF3] bg-white shadow-[0_4px_12px_rgba(148,163,184,0.08)]", className)}>
      {/* Tabs */}
      <div className="flex border-b border-[#E8EDF3]">
        {TABS.map((tab) => {
          const Icon = tab.icon
          const isActive = activeTab === tab.id
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                "flex flex-1 items-center justify-center gap-2 border-b-2 px-4 py-3.5 text-xs font-semibold transition-colors",
                isActive
                  ? "border-[#38B88A] text-[#38B88A]"
                  : "border-transparent text-[#6B7280] hover:text-[#374151]",
              )}
            >
              <Icon className="h-4 w-4" />
              {tab.label}
            </button>
          )
        })}
      </div>

      {/* Content */}
      <div className="p-5">
        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.15 }}
          >
            {tabContent}
          </motion.div>
        </AnimatePresence>
      </div>

      {/* Reset */}
      <div className="border-t border-[#E8EDF3] px-5 py-4">
        <motion.button
          onClick={prefs.resetAll}
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          className="flex w-full items-center justify-center gap-2 rounded-[14px] border border-[#EF4444]/30 bg-[#FEF2F2] px-4 py-2.5 text-xs font-semibold text-[#EF4444] transition-colors hover:bg-[#FEE2E2]"
        >
          <RotateCcw className="h-3.5 w-3.5" />
          Reset All Preferences
        </motion.button>
      </div>
    </div>
  )
}