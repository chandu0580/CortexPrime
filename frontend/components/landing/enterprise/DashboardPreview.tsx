"use client";

import {
  AlertCircle,
  Bell,
  Bot,
  ChevronDown,
  ChevronLeft,
  CircleAlert,
  Clock3,
  Cpu,
  Gauge,
  Globe,
  LayoutDashboard,
  MemoryStick,
  Mic,
  MonitorSmartphone,
  Search,
  Settings,
  Shield,
  Sparkles,
  SquareTerminal,
  UserRound,
  Workflow,
} from "lucide-react";

import LandingLogo from "@/components/landing/enterprise/LandingLogo";
import {
  agentItems,
  alertItems,
  missionItems,
  overviewMetrics,
  systemMetrics,
} from "@/components/landing/enterprise/data";
import { LandingCard, MetricCard } from "@/components/landing/enterprise/primitives";
import { cn } from "@/utils/cn";

const sidebarItems = [
  { label: "Overview", icon: LayoutDashboard, active: true },
  { label: "Runtime", icon: SquareTerminal },
  { label: "Agents", icon: Bot },
  { label: "Missions", icon: Workflow },
  { label: "Voice", icon: Mic },
  { label: "Memory", icon: MemoryStick },
  { label: "Research", icon: Search },
  { label: "Computer Use", icon: MonitorSmartphone },
  { label: "Browser Agent", icon: Globe },
  { label: "Governance", icon: Shield },
  { label: "Replay", icon: Clock3 },
  { label: "Analytics", icon: Gauge },
  { label: "Monitoring", icon: Cpu },
  { label: "Integrations", icon: Sparkles },
  { label: "Settings", icon: Settings },
];

const statusTone: Record<string, string> = {
  Running: "text-[#22C55E]",
  Completed: "text-[#22C55E]",
  Listening: "text-[#22C55E]",
  Executing: "text-[#22C55E]",
  Idle: "text-[#9CA3AF]",
};



const missionStatusClass: Record<string, string> = {
  Running: "text-[#22C55E]",
  Completed: "text-[#22C55E]",
};

const alertTone: Record<string, string> = {
  warning: "bg-[#FFF7ED] text-[#F59E0B]",
  info: "bg-[#EEF5FF] text-[#3B82F6]",
  danger: "bg-[#FEF2F2] text-[#EF4444]",
};

function StatusDot({
  status = "active",
}: {
  status?: "active" | "idle" | "completed";
}) {
  return (
    <span
      className={cn(
        "inline-flex h-2 w-2 rounded-full",
        status === "idle" ? "bg-[#CBD5E1]" : "bg-[#22C55E]",
      )}
      aria-hidden="true"
    />
  );
}

export default function DashboardPreview() {
  return (
    <LandingCard className="overflow-hidden rounded-[30px]">
      <div className="flex flex-col lg:flex-row">
        <aside className="border-b border-[#E5E7EB] bg-[#FBFDFC] lg:w-[152px] lg:border-b-0 lg:border-r">
          <div className="flex h-[78px] items-center px-5">
            <LandingLogo compact textClassName="text-[0.95rem]" />
          </div>
          <nav aria-label="Dashboard sections" className="grid gap-0.5 px-3 pb-3 lg:block">
            {sidebarItems.map((item) => (
              <button
                key={item.label}
                type="button"
                className={cn(
                  "flex w-full items-center gap-2.5 rounded-[10px] px-3 py-2 text-left text-[0.7rem] font-medium transition-colors",
                  item.active
                    ? "bg-[#38B88A] text-white shadow-[0_8px_18px_rgba(56,184,138,0.22)]"
                    : "text-[#374151] hover:bg-[#F3F7F5]",
                )}
              >
                <item.icon className="h-3 w-3 shrink-0" />
                <span className="truncate">{item.label}</span>
              </button>
            ))}
          </nav>
          <div className="hidden px-4 pb-4 lg:block">
            <button
              type="button"
              className="flex w-full items-center gap-2 rounded-[12px] px-3 py-2 text-[0.73rem] text-[#6B7280] hover:bg-[#F3F7F5]"
            >
              <ChevronLeft className="h-3.5 w-3.5" />
              <span>Collapse</span>
            </button>
          </div>
        </aside>

        <div className="min-w-0 flex-1 bg-white">
          <div className="flex flex-col gap-4 border-b border-[#EEF2F7] px-5 py-4 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <h2 className="text-[1.9rem] font-semibold tracking-[-0.05em] text-[#111827]">
                Overview
              </h2>
              <p className="text-[0.82rem] text-[#6B7280]">
                Welcome back, Operator
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <label className="relative block min-w-[220px] flex-1 lg:min-w-[260px]">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#9CA3AF]" />
                <input
                  type="search"
                  aria-label="Search dashboard"
                  placeholder="Search anything..."
                  className="h-11 w-full rounded-[14px] border border-[#E5E7EB] bg-[#FCFDFC] pl-10 pr-11 text-[0.82rem] text-[#111827] outline-none transition focus:border-[#B7E5D3] focus:ring-2 focus:ring-[#DDF5EA]"
                />
                <Sparkles className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#9CA3AF]" />
              </label>

              <button
                type="button"
                aria-label="Notifications"
                className="relative flex h-11 w-11 items-center justify-center rounded-[14px] border border-[#E5E7EB] bg-[#FCFDFC] text-[#374151]"
              >
                <Bell className="h-4 w-4" />
                <span className="absolute right-2 top-2 h-2.5 w-2.5 rounded-full bg-[#EF4444]" />
              </button>

              <div className="flex items-center gap-3 rounded-[16px] border border-[#E5E7EB] bg-[#FCFDFC] px-3 py-2.5">
                <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[#EAFBF4] text-[#38B88A]">
                  <UserRound className="h-4 w-4" />
                </div>
                <div className="leading-tight">
                  <p className="text-[0.76rem] font-semibold text-[#111827]">
                    Operator
                  </p>
                  <p className="text-[0.7rem] text-[#6B7280]">Enterprise</p>
                </div>
              </div>
            </div>
          </div>

          <div className="space-y-4 p-4 lg:p-5">
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              {overviewMetrics.map((metric) => (
                <MetricCard
                  key={metric.label}
                  label={metric.label}
                  value={metric.value}
                  delta={metric.delta}
                  footer={metric.footer}
                  trend={metric.trend}
                  accent={metric.label === "System Health" ? "neutral" : "green"}
                />
              ))}
            </div>

            <div className="grid gap-4 xl:grid-cols-[1.25fr_1fr]">
              <LandingCard className="rounded-[24px] px-5 py-4 shadow-[0_10px_30px_rgba(148,163,184,0.08)]">
                <div className="mb-4 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <h3 className="text-[0.98rem] font-semibold tracking-[-0.03em] text-[#111827]">
                      Mission Timeline
                    </h3>
                    <ChevronDown className="h-3.5 w-3.5 text-[#9CA3AF]" />
                  </div>
                  <span className="rounded-full bg-[#F0FBF6] px-2.5 py-1 text-[0.68rem] font-medium text-[#2F9F77]">
                    Live
                  </span>
                </div>

                <div className="space-y-4">
                  {missionItems.map((item) => (
                    <div
                      key={item.title}
                      className="flex items-start justify-between gap-4"
                    >
                      <div className="flex min-w-0 items-start gap-3">
                        <div className="mt-0.5 flex h-9 w-9 items-center justify-center rounded-full bg-[#ECFBF4] text-[#38B88A]">
                          <Shield className="h-3.5 w-3.5" />
                        </div>
                        <div className="min-w-0">
                          <p className="truncate text-[0.78rem] font-semibold text-[#111827]">
                            {item.title}
                          </p>
                          <p className="text-[0.68rem] text-[#9CA3AF]">{item.agent}</p>
                        </div>
                      </div>
                      <div className="shrink-0 text-right">
                        <p
                          className={cn(
                            "inline-flex items-center gap-1 text-[0.7rem] font-medium",
                            missionStatusClass[item.status],
                          )}
                        >
                          <StatusDot status={item.status === "Completed" ? "completed" : "active"} />
                          {item.status}
                        </p>
                        <p className="mt-0.5 text-[0.65rem] text-[#9CA3AF]">{item.time}</p>
                      </div>
                    </div>
                  ))}
                </div>

                <button
                  type="button"
                  className="mt-4 flex h-10 w-full items-center justify-center rounded-[14px] bg-[#F6F8FA] text-[0.74rem] font-medium text-[#374151] transition hover:bg-[#EEF2F6]"
                >
                  View All Missions
                </button>
              </LandingCard>

              <LandingCard className="rounded-[24px] px-5 py-4 shadow-[0_10px_30px_rgba(148,163,184,0.08)]">
                <div className="mb-4 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <h3 className="text-[0.98rem] font-semibold tracking-[-0.03em] text-[#111827]">
                      Agent Status
                    </h3>
                    <ChevronDown className="h-3.5 w-3.5 text-[#9CA3AF]" />
                  </div>
                  <button
                    type="button"
                    className="rounded-full bg-[#F8FAFC] px-2.5 py-1 text-[0.68rem] font-medium text-[#6B7280]"
                  >
                    View All
                  </button>
                </div>

                <div className="space-y-4">
                  {agentItems.map((item) => (
                    <div key={item.title} className="flex items-center justify-between gap-3">
                      <div className="flex min-w-0 items-center gap-3">
                        <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[#ECFBF4] text-[#2F9F77]">
                          {item.title.includes("Voice") ? (
                            <Mic className="h-3.5 w-3.5" />
                          ) : item.title.includes("Browser") ? (
                            <Globe className="h-3.5 w-3.5" />
                          ) : item.title.includes("Computer") ? (
                            <MonitorSmartphone className="h-3.5 w-3.5" />
                          ) : (
                            <Bot className="h-3.5 w-3.5" />
                          )}
                        </div>
                        <div className="min-w-0">
                          <p className="truncate text-[0.78rem] font-semibold text-[#111827]">
                            {item.title}
                          </p>
                        </div>
                      </div>
                      <div className="flex shrink-0 items-center gap-3">
                        <span className="text-[0.68rem] text-[#9CA3AF]">{item.version}</span>
                        <span
                          className={cn(
                            "inline-flex items-center gap-1 text-[0.7rem] font-medium",
                            statusTone[item.status],
                          )}
                        >
                          <StatusDot status={item.status === "Idle" ? "idle" : "active"} />
                          {item.status}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </LandingCard>
            </div>

            <div className="grid gap-4 xl:grid-cols-[1fr_0.95fr]">
              <LandingCard className="rounded-[24px] px-5 py-4 shadow-[0_10px_30px_rgba(148,163,184,0.08)]">
                <div className="mb-4 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <h3 className="text-[0.98rem] font-semibold tracking-[-0.03em] text-[#111827]">
                      System Metrics
                    </h3>
                    <ChevronDown className="h-3.5 w-3.5 text-[#9CA3AF]" />
                  </div>
                  <button
                    type="button"
                    className="inline-flex items-center gap-2 rounded-[12px] border border-[#E5E7EB] px-3 py-2 text-[0.72rem] font-medium text-[#374151]"
                  >
                    Last 24h
                    <ChevronDown className="h-3.5 w-3.5" />
                  </button>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  {systemMetrics.map((metric) => (
                    <MetricCard
                      key={metric.label}
                      label={metric.label}
                      value={metric.value}
                      trend={metric.trend}
                      compact
                    />
                  ))}
                </div>
              </LandingCard>

              <LandingCard className="rounded-[24px] px-5 py-4 shadow-[0_10px_30px_rgba(148,163,184,0.08)]">
                <div className="mb-4 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <h3 className="text-[0.98rem] font-semibold tracking-[-0.03em] text-[#111827]">
                      Recent Alerts
                    </h3>
                    <ChevronDown className="h-3.5 w-3.5 text-[#9CA3AF]" />
                  </div>
                  <button
                    type="button"
                    className="rounded-full bg-[#F8FAFC] px-2.5 py-1 text-[0.68rem] font-medium text-[#6B7280]"
                  >
                    View All
                  </button>
                </div>

                <div className="space-y-4">
                  {alertItems.map((alert) => (
                    <div key={alert.title} className="flex items-start justify-between gap-3">
                      <div className="flex min-w-0 items-start gap-3">
                        <div
                          className={cn(
                            "flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
                            alertTone[alert.tone],
                          )}
                        >
                          {alert.tone === "warning" ? (
                            <AlertCircle className="h-4 w-4" />
                          ) : alert.tone === "info" ? (
                            <CircleAlert className="h-4 w-4" />
                          ) : (
                            <Bell className="h-4 w-4" />
                          )}
                        </div>
                        <p className="min-w-0 text-[0.8rem] font-medium text-[#111827]">
                          {alert.title}
                        </p>
                      </div>
                      <span className="shrink-0 text-[0.7rem] text-[#9CA3AF]">
                        {alert.time}
                      </span>
                    </div>
                  ))}
                </div>
              </LandingCard>
            </div>
          </div>
        </div>
      </div>
    </LandingCard>
  );
}
