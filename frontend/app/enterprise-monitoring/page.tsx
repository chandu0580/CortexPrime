"use client"

import { useState } from "react"
import { motion } from "framer-motion"
import CortexShell from "@/components/layout/CortexShell"
import { stagger, variants } from "@/lib/motion-tokens"
import {
  useMonitoringWatchers,
  useMonitoringRules,
  useMonitoringEvents,
  useMonitoringMissions,
  useMonitoringStatistics,
  useMonitoringHealth,
  useTriggerPoll,
} from "@/hooks/queries/enterprise/useEnterpriseMonitoring"
import {
  Activity,
  AlertTriangle,
  Bell,
  CheckCircle2,
  Cpu,
  Eye,
  FileText,
  GitPullRequest,
  Loader2,
  RefreshCw,
  Server,
  Settings,
  Shield,
  Zap,
} from "lucide-react"

function SeverityBadge({ severity }: { severity: string }) {
  const colors: Record<string, string> = {
    critical: "bg-red-100 text-red-700 border-red-200",
    high: "bg-amber-100 text-amber-700 border-amber-200",
    medium: "bg-blue-100 text-blue-700 border-blue-200",
    low: "bg-gray-100 text-gray-600 border-gray-200",
  }
  return (
    <span className={`rounded-full border px-2 py-0.5 text-[0.6rem] font-medium capitalize ${colors[severity] || colors.low}`}>
      {severity}
    </span>
  )
}

function StatCard({ icon: Icon, label, value, color }: { icon: React.ElementType; label: string; value: string | number; color: string }) {
  return (
    <motion.div variants={variants.fadeUp} className="rounded-xl border border-[#E8EDF3] bg-white p-4">
      <div className="flex items-center gap-3">
        <div className={`rounded-lg p-2.5 ${color}`}>
          <Icon className="h-4 w-4 text-white" />
        </div>
        <div>
          <p className="text-[0.7rem] font-medium text-[#6B7280]">{label}</p>
          <p className="text-xl font-bold text-[#111827]">{value}</p>
        </div>
      </div>
    </motion.div>
  )
}

function WatcherPanel() {
  const { data: watchers, isLoading } = useMonitoringWatchers()

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8 text-[0.78rem] text-[#6B7280]">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Loading watchers...
      </div>
    )
  }

  if (!watchers || watchers.length === 0) {
    return <p className="py-6 text-center text-[0.78rem] text-[#9CA3AF]">No watchers configured.</p>
  }

  return (
    <div className="space-y-2">
      {watchers.map((w) => (
        <div key={w.connector} className="flex items-center gap-3 rounded-lg border border-[#E8EDF3] bg-white px-3.5 py-2.5">
          <div className={`h-2.5 w-2.5 shrink-0 rounded-full ${w.available ? "bg-[#38B88A]" : "bg-red-400"}`} />
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-[#111827] capitalize">{w.connector}</span>
              <span className={`rounded px-1.5 py-0.5 text-[0.6rem] font-medium ${w.running ? "bg-[#F0FDF4] text-[#38B88A]" : "bg-gray-100 text-gray-500"}`}>
                {w.running ? "Running" : "Stopped"}
              </span>
            </div>
            <p className="mt-0.5 text-[0.7rem] text-[#6B7280]">
              Poll interval: {w.poll_interval}s — Status: {w.status}
            </p>
          </div>
        </div>
      ))}
    </div>
  )
}

function RulesPanel() {
  const { data: rules, isLoading } = useMonitoringRules()

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8 text-[0.78rem] text-[#6B7280]">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Loading rules...
      </div>
    )
  }

  if (!rules || rules.length === 0) {
    return <p className="py-6 text-center text-[0.78rem] text-[#9CA3AF]">No monitoring rules configured.</p>
  }

  return (
    <div className="max-h-80 space-y-2 overflow-y-auto">
      {rules.map((r) => (
        <div key={r.rule_id} className="flex items-start gap-3 rounded-lg border border-[#E8EDF3] bg-white px-3.5 py-2.5">
          <div className={`mt-1 h-2 w-2 shrink-0 rounded-full ${r.enabled ? "bg-[#38B88A]" : "bg-gray-300"}`} />
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="text-[0.78rem] font-medium text-[#111827]">{r.name}</span>
              <SeverityBadge severity={r.severity} />
              {r.auto_create_mission && (
                <Zap className="h-3 w-3 text-amber-500" />
              )}
            </div>
            <p className="mt-0.5 text-[0.65rem] text-[#6B7280]">
              {r.connector} / {r.event_type}
              {r.description && ` — ${r.description}`}
            </p>
          </div>
        </div>
      ))}
    </div>
  )
}

function EventsPanel() {
  const { data: events, isLoading } = useMonitoringEvents(20)

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8 text-[0.78rem] text-[#6B7280]">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Loading events...
      </div>
    )
  }

  if (!events || events.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-10 text-[#6B7280]">
        <Activity className="mb-2 h-8 w-8 opacity-30" />
        <p className="text-[0.78rem]">No events detected yet.</p>
      </div>
    )
  }

  return (
    <div className="max-h-80 space-y-2 overflow-y-auto">
      {events.map((ev, i) => (
        <div key={i} className="rounded-lg border border-[#E8EDF3] bg-white p-3">
          <div className="flex items-start gap-2.5">
            <AlertTriangle className={`mt-0.5 h-4 w-4 shrink-0 ${
              ev.severity === "critical" ? "text-red-500" : ev.severity === "high" ? "text-amber-500" : "text-blue-500"
            }`} />
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="text-[0.78rem] font-medium text-[#111827]">{ev.title}</span>
                <SeverityBadge severity={ev.severity} />
              </div>
              <p className="mt-0.5 text-[0.65rem] text-[#6B7280]">
                {ev.connector_type} — {ev.event_type}
              </p>
              {ev.description && (
                <p className="mt-0.5 line-clamp-1 text-[0.65rem] text-[#9CA3AF]">{ev.description}</p>
              )}
            </div>
            {ev.detected_at && (
              <span className="shrink-0 text-[0.6rem] text-[#9CA3AF]">
                {new Date(ev.detected_at).toLocaleTimeString()}
              </span>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}

function MissionsPanel() {
  const { data: missions, isLoading } = useMonitoringMissions(10)

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8 text-[0.78rem] text-[#6B7280]">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Loading missions...
      </div>
    )
  }

  if (!missions || missions.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-10 text-[#6B7280]">
        <GitPullRequest className="mb-2 h-8 w-8 opacity-30" />
        <p className="text-[0.78rem]">No missions auto-generated yet.</p>
      </div>
    )
  }

  return (
    <div className="max-h-80 space-y-2 overflow-y-auto">
      {missions.map((m, i) => (
        <div key={m.execution_id || i} className="rounded-lg border border-[#E8EDF3] bg-white p-3">
          <div className="flex items-start gap-2.5">
            <Zap className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" />
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="text-[0.78rem] font-medium text-[#111827]">{m.event_title}</span>
                <SeverityBadge severity={m.severity} />
              </div>
              <p className="mt-0.5 text-[0.65rem] text-[#6B7280]">
                Template: {m.template} — Connector: {m.connector}
              </p>
              <div className="mt-1 flex items-center gap-2">
                <span className={`rounded px-1.5 py-0.5 text-[0.6rem] font-medium ${
                  m.status === "completed" ? "bg-[#F0FDF4] text-[#38B88A]"
                  : m.status === "failed" ? "bg-red-50 text-red-600"
                  : "bg-amber-50 text-amber-600"
                }`}>
                  {m.status}
                </span>
                <span className="text-[0.6rem] text-[#9CA3AF]">{m.rule_name}</span>
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

function EventTimeline() {
  const { data: events, isLoading } = useMonitoringEvents(15)

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8 text-[0.78rem] text-[#6B7280]">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
      </div>
    )
  }

  if (!events || events.length === 0) {
    return <p className="py-4 text-center text-[0.7rem] text-[#9CA3AF]">No events.</p>
  }

  const severityDots: Record<string, string> = {
    critical: "bg-red-500",
    high: "bg-amber-500",
    medium: "bg-blue-500",
    low: "bg-gray-400",
  }

  return (
    <div className="relative space-y-0">
      {events.slice(0, 10).map((ev, i) => (
        <div key={i} className="flex gap-3 pb-3 last:pb-0">
          <div className="flex flex-col items-center">
            <div className={`h-2.5 w-2.5 shrink-0 rounded-full ${severityDots[ev.severity] || "bg-gray-400"}`} />
            {i < Math.min(events.length, 10) - 1 && <div className="mt-1 h-full w-px bg-[#E8EDF3]" />}
          </div>
          <div className="min-w-0 flex-1 pb-2">
            <p className="text-[0.72rem] font-medium text-[#111827]">{ev.title}</p>
            <p className="text-[0.6rem] text-[#6B7280]">
              {ev.connector_type} — {ev.event_type}
              {ev.detected_at && ` — ${new Date(ev.detected_at).toLocaleTimeString()}`}
            </p>
          </div>
        </div>
      ))}
    </div>
  )
}

export default function AutonomousMonitoringCenter() {
  const [activeTab, setActiveTab] = useState("overview")
  const { data: stats, isLoading: statsLoading } = useMonitoringStatistics()
  const { data: health } = useMonitoringHealth()
  const pollMutation = useTriggerPoll()

  const tabs = [
    { id: "overview", label: "Overview", icon: Eye },
    { id: "watchers", label: "Watchers", icon: Cpu },
    { id: "rules", label: "Rules", icon: Settings },
    { id: "events", label: "Events", icon: Activity },
    { id: "missions", label: "Missions", icon: GitPullRequest },
    { id: "timeline", label: "Timeline", icon: FileText },
  ]

  return (
    <CortexShell title="Autonomous Monitoring Center" subtitle="Continuous enterprise event detection, rule evaluation, and automatic mission generation">
      <div className="relative z-10 mx-auto max-w-7xl space-y-6">
        {/* Summary Stats */}
        <motion.div initial="hidden" animate="visible" variants={stagger(0.04, 0.01)}>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-6">
            <StatCard icon={Eye} label="Watchers" value={stats?.total_rules ?? "-"} color="bg-blue-500" />
            <StatCard icon={Settings} label="Rules" value={stats?.total_rules ?? 0} color="bg-[#38B88A]" />
            <StatCard icon={Activity} label="Events Detected" value={stats?.total_events ?? 0} color="bg-amber-500" />
            <StatCard icon={Zap} label="Auto Missions" value={stats?.total_missions ?? 0} color="bg-purple-500" />
            <StatCard icon={RefreshCw} label="Active Recoveries" value={stats?.active_recoveries ?? 0} color="bg-red-500" />
            <StatCard icon={Shield} label="Watcher Health" value={`${health?.watchers_available ?? 0}/${health?.watchers_total ?? 0}`} color="bg-indigo-500" />
          </div>
        </motion.div>

        {/* Action Bar */}
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-center justify-between rounded-xl border border-[#E8EDF3] bg-white p-4"
        >
          <div className="flex items-center gap-2">
            <Bell className="h-5 w-5 text-[#38B88A]" />
            <span className="text-sm font-medium text-[#111827]">
              Monitoring is {health?.status === "healthy" ? "active" : "degraded"} — {health?.watchers_available ?? 0} of {health?.watchers_total ?? 0} watchers available
            </span>
          </div>
          <button
            onClick={() => pollMutation.mutate(undefined)}
            disabled={pollMutation.isPending}
            className="ml-4 flex shrink-0 items-center gap-2 rounded-lg bg-[#38B88A] px-4 py-2 text-sm font-medium text-white transition-all hover:bg-[#2EA07A] disabled:opacity-50"
          >
            {pollMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
            {pollMutation.isPending ? "Polling..." : "Poll Now"}
          </button>
        </motion.div>

        {/* Poll Result Feedback */}
        {pollMutation.data && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            className="rounded-xl border border-[#38B88A]/30 bg-[#F0FDF4] p-3 text-center text-[0.78rem] text-[#38B88A]"
          >
            Poll complete: {pollMutation.data.events_detected} event(s), {pollMutation.data.rules_matched} rule(s) matched, {pollMutation.data.missions_created} mission(s) created
          </motion.div>
        )}

        {/* Tab Navigation */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="flex flex-wrap gap-1 rounded-xl border border-[#E8EDF3] bg-white p-1"
        >
          {tabs.map((tab) => {
            const TabIcon = tab.icon
            const isActive = activeTab === tab.id
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 rounded-lg px-4 py-2 text-[0.78rem] font-medium transition-all ${
                  isActive
                    ? "bg-[#38B88A] text-white shadow-sm"
                    : "text-[#6B7280] hover:bg-[#F4F7FA]"
                }`}
              >
                <TabIcon className="h-4 w-4" />
                {tab.label}
              </button>
            )
          })}
        </motion.div>

        {/* Tab Content */}
        <motion.div key={activeTab} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
          {/* Overview Tab */}
          {activeTab === "overview" && (
            <div className="grid gap-5 lg:grid-cols-2">
              <div className="rounded-xl border border-[#E8EDF3] bg-white p-5">
                <div className="mb-4 flex items-center gap-2">
                  <Activity className="h-4 w-4 text-[#38B88A]" />
                  <h2 className="text-sm font-bold text-[#111827]">Recent Events</h2>
                </div>
                <EventsPanel />
              </div>
              <div className="rounded-xl border border-[#E8EDF3] bg-white p-5">
                <div className="mb-4 flex items-center gap-2">
                  <Zap className="h-4 w-4 text-amber-500" />
                  <h2 className="text-sm font-bold text-[#111827]">Auto-Generated Missions</h2>
                </div>
                <MissionsPanel />
              </div>
              <div className="rounded-xl border border-[#E8EDF3] bg-white p-5">
                <div className="mb-4 flex items-center gap-2">
                  <Cpu className="h-4 w-4 text-blue-500" />
                  <h2 className="text-sm font-bold text-[#111827]">Active Watchers</h2>
                </div>
                <WatcherPanel />
              </div>
              <div className="rounded-xl border border-[#E8EDF3] bg-white p-5">
                <div className="mb-4 flex items-center gap-2">
                  <Settings className="h-4 w-4 text-purple-500" />
                  <h2 className="text-sm font-bold text-[#111827]">Active Rules</h2>
                </div>
                <RulesPanel />
              </div>
            </div>
          )}

          {/* Watchers Tab */}
          {activeTab === "watchers" && (
            <div className="rounded-xl border border-[#E8EDF3] bg-white p-5">
              <div className="mb-4 flex items-center gap-2">
                <Cpu className="h-4 w-4 text-blue-500" />
                <h2 className="text-sm font-bold text-[#111827]">All Watchers</h2>
                <span className="ml-auto text-[0.65rem] text-[#9CA3AF]">Health: {health?.watchers_available ?? 0}/{health?.watchers_total ?? 0} available</span>
              </div>
              <WatcherPanel />
            </div>
          )}

          {/* Rules Tab */}
          {activeTab === "rules" && (
            <div className="rounded-xl border border-[#E8EDF3] bg-white p-5">
              <div className="mb-4 flex items-center gap-2">
                <Settings className="h-4 w-4 text-purple-500" />
                <h2 className="text-sm font-bold text-[#111827]">Monitoring Rules</h2>
              </div>
              <RulesPanel />
            </div>
          )}

          {/* Events Tab */}
          {activeTab === "events" && (
            <div className="rounded-xl border border-[#E8EDF3] bg-white p-5">
              <div className="mb-4 flex items-center gap-2">
                <Activity className="h-4 w-4 text-[#38B88A]" />
                <h2 className="text-sm font-bold text-[#111827]">Detected Events</h2>
              </div>
              <EventsPanel />
            </div>
          )}

          {/* Missions Tab */}
          {activeTab === "missions" && (
            <div className="rounded-xl border border-[#E8EDF3] bg-white p-5">
              <div className="mb-4 flex items-center gap-2">
                <GitPullRequest className="h-4 w-4 text-amber-500" />
                <h2 className="text-sm font-bold text-[#111827]">Auto-Generated Missions</h2>
              </div>
              <MissionsPanel />
            </div>
          )}

          {/* Timeline Tab */}
          {activeTab === "timeline" && (
            <div className="grid gap-5 lg:grid-cols-2">
              <div className="rounded-xl border border-[#E8EDF3] bg-white p-5">
                <div className="mb-4 flex items-center gap-2">
                  <FileText className="h-4 w-4 text-[#38B88A]" />
                  <h2 className="text-sm font-bold text-[#111827]">Event Timeline</h2>
                </div>
                <EventTimeline />
              </div>
              <div className="rounded-xl border border-[#E8EDF3] bg-white p-5">
                <div className="mb-4 flex items-center gap-2">
                  <Server className="h-4 w-4 text-amber-500" />
                  <h2 className="text-sm font-bold text-[#111827]">Auto-Heal Status</h2>
                </div>
                <div className="space-y-3">
                  {[
                    { label: "Active Recoveries", value: stats?.active_recoveries ?? 0, color: "text-red-500" },
                    { label: "Total Auto Missions", value: stats?.total_missions ?? 0, color: "text-purple-500" },
                    { label: "Enabled Rules", value: stats?.enabled_rules ?? 0, color: "text-[#38B88A]" },
                  ].map((s, i) => (
                    <div key={i} className="flex items-center justify-between rounded-lg border border-[#E8EDF3] px-4 py-3">
                      <span className="text-[0.78rem] text-[#6B7280]">{s.label}</span>
                      <span className={`text-sm font-bold ${s.color}`}>{s.value}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </motion.div>
      </div>
    </CortexShell>
  )
}
