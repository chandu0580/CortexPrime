"use client"

import { useState, useMemo } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  GitBranch, GitPullRequest, MessageSquare, Container, Server, Activity,
  BarChart3, AlertTriangle, CheckCircle2, XCircle, RefreshCw,
  ExternalLink, ChevronRight, Clock, Filter, Search,
  Box, Layers, Cpu, HardDrive, Wifi,
} from "lucide-react"
import { cn } from "@/utils/cn"
import { stagger, variants } from "@/lib/motion-tokens"

interface IntegrationStatus {
  name: string
  icon: typeof GitBranch
  status: "connected" | "disconnected" | "error" | "degraded"
  lastSync: string
  metrics: { label: string; value: string }[]
  brandColor: string
  brandBg: string
}

const integrations: IntegrationStatus[] = [
  { name: "GitHub", icon: GitPullRequest, status: "connected", lastSync: "2m ago", metrics: [{ label: "Repos", value: "24" }, { label: "PRs Open", value: "8" }, { label: "Commits Today", value: "47" }], brandColor: "text-[#111827]", brandBg: "bg-white" },
  { name: "Jira", icon: GitBranch, status: "connected", lastSync: "5m ago", metrics: [{ label: "Issues", value: "142" }, { label: "In Progress", value: "23" }, { label: "Done Today", value: "12" }], brandColor: "text-[#0052CC]", brandBg: "bg-[#EFF6FF]" },
  { name: "Slack", icon: MessageSquare, status: "connected", lastSync: "1m ago", metrics: [{ label: "Channels", value: "18" }, { label: "Messages Today", value: "1.2K" }, { label: "Alerts", value: "3" }], brandColor: "text-[#E01E5A]", brandBg: "bg-[#FFF0F3]" },
  { name: "Docker", icon: Container, status: "connected", lastSync: "30s ago", metrics: [{ label: "Containers", value: "36" }, { label: "Running", value: "28" }, { label: "Images", value: "142" }], brandColor: "text-[#2496ED]", brandBg: "bg-[#EFF6FF]" },
  { name: "Kubernetes", icon: Server, status: "degraded", lastSync: "1m ago", metrics: [{ label: "Pods", value: "142" }, { label: "Nodes", value: "8" }, { label: "Alerts", value: "4" }], brandColor: "text-[#326CE5]", brandBg: "bg-[#EFF6FF]" },
  { name: "Prometheus", icon: Activity, status: "connected", lastSync: "15s ago", metrics: [{ label: "Targets", value: "64" }, { label: "Alerts Firing", value: "2" }, { label: "Uptime", value: "99.8%" }], brandColor: "text-[#E6522C]", brandBg: "bg-[#FFF0F0]" },
  { name: "Grafana", icon: BarChart3, status: "connected", lastSync: "1m ago", metrics: [{ label: "Dashboards", value: "18" }, { label: "Data Sources", value: "6" }, { label: "Panels", value: "142" }], brandColor: "text-[#F46800]", brandBg: "bg-[#FFF5EB]" },
]

const statusConfig = {
  connected: { icon: CheckCircle2, text: "text-[var(--success)]", bg: "bg-[var(--success-muted)]" },
  degraded: { icon: AlertTriangle, text: "text-[var(--warning)]", bg: "bg-[var(--warning-muted)]" },
  disconnected: { icon: XCircle, text: "text-[var(--text-muted)]", bg: "bg-[var(--surface-raised)]" },
  error: { icon: XCircle, text: "text-[var(--danger)]", bg: "bg-[var(--danger-muted)]" },
}

export function IntegrationStatusCards() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {integrations.map((integration, i) => {
        const sc = statusConfig[integration.status]
        const StatusIcon = sc.icon
        const IconComponent = integration.icon
        return (
          <motion.div
            key={integration.name}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.04 }}
            style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-md)" }}
            className="p-5 hover:shadow-sm transition-shadow"
          >
            <div className="flex items-start justify-between mb-3">
              <div className="flex items-center gap-3">
                <div className={cn("flex h-10 w-10 items-center justify-center", integration.brandBg, { "rounded-[12px]": true })}>
                  <IconComponent className={cn("h-5 w-5", integration.brandColor)} />
                </div>
                <div>
                  <p className="text-[0.85rem] font-bold" style={{ color: "var(--text-primary)" }}>{integration.name}</p>
                  <span className={cn("inline-flex items-center gap-1 text-[0.6rem] font-semibold", sc.text)}>
                    <StatusIcon className="h-3 w-3" />
                    {integration.status}
                  </span>
                </div>
              </div>
              <button
                aria-label={`Refresh ${integration.name}`}
                className="flex h-7 w-7 items-center justify-center hover:bg-[var(--surface-raised)] transition-colors"
                style={{ color: "var(--text-muted)", borderRadius: "var(--radius-sm)" }}
              >
                <RefreshCw className="h-3.5 w-3.5" />
              </button>
            </div>
            <div className="flex items-center gap-1 text-[0.6rem] mb-3" style={{ color: "var(--text-muted)" }}>
              <Clock className="h-3 w-3" /> Synced {integration.lastSync}
            </div>
            <div className="grid grid-cols-3 gap-2">
              {integration.metrics.map((m) => (
                <div key={m.label} className="rounded-[var(--radius-sm)] p-2 text-center" style={{ background: "var(--surface-raised)", border: "1px solid var(--border)" }}>
                  <p className="text-[0.6rem] font-semibold uppercase whitespace-nowrap" style={{ color: "var(--text-muted)" }}>{m.label}</p>
                  <p className="text-[0.8rem] font-bold" style={{ color: "var(--text-primary)" }}>{m.value}</p>
                </div>
              ))}
            </div>
          </motion.div>
        )
      })}
    </div>
  )
}

export function GitHubPanel() {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-[0.85rem] font-bold" style={{ color: "var(--text-primary)" }}>GitHub Integration</h3>
        <button
          aria-label="Sync GitHub"
          className="flex items-center gap-1.5 px-3 py-1.5 text-[0.7rem] font-semibold hover:bg-[var(--surface-raised)] transition-colors"
          style={{ borderRadius: "var(--radius-sm)", border: "1px solid var(--border)", background: "var(--surface)", color: "var(--text-secondary)" }}
        >
          <RefreshCw className="h-3.5 w-3.5" /> Sync
        </button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left" aria-label="GitHub repositories">
          <thead>
            <tr className="border-b text-[0.65rem] font-semibold uppercase" style={{ borderColor: "var(--border)", color: "var(--text-muted)" }}>
              <th className="pb-3 pr-4">Repository</th>
              <th className="pb-3 pr-4">Branch</th>
              <th className="pb-3 pr-4">PRs</th>
              <th className="pb-3 pr-4">Issues</th>
              <th className="pb-3 pr-4">Last Commit</th>
              <th className="pb-3 pr-4">Status</th>
            </tr>
          </thead>
          <tbody>
            {[
              { name: "cortexprime/core", branch: "main", prs: 3, issues: 12, lastCommit: "2h ago", status: "active" },
              { name: "cortexprime/frontend", branch: "develop", prs: 5, issues: 8, lastCommit: "30m ago", status: "active" },
              { name: "cortexprime/agents", branch: "feature/cognition", prs: 2, issues: 4, lastCommit: "1h ago", status: "active" },
              { name: "cortexprime/docs", branch: "main", prs: 1, issues: 3, lastCommit: "1d ago", status: "idle" },
            ].map((repo) => (
              <tr key={repo.name} className="border-b last:border-0" style={{ borderColor: "var(--border)" }}>
                <td className="py-3 pr-4">
                  <div className="flex items-center gap-2">
                    <GitPullRequest className="h-4 w-4" style={{ color: "var(--text-primary)" }} />
                    <span className="text-[0.78rem] font-semibold" style={{ color: "var(--text-primary)" }}>{repo.name}</span>
                  </div>
                </td>
                <td className="py-3 pr-4 text-[0.75rem] font-mono" style={{ color: "var(--text-secondary)" }}>{repo.branch}</td>
                <td className="py-3 pr-4 text-[0.75rem]" style={{ color: "var(--text-secondary)" }}>{repo.prs}</td>
                <td className="py-3 pr-4 text-[0.75rem]" style={{ color: "var(--text-secondary)" }}>{repo.issues}</td>
                <td className="py-3 pr-4 text-[0.75rem]" style={{ color: "var(--text-secondary)" }}>{repo.lastCommit}</td>
                <td className="py-3">
                  <span className={cn(
                    "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[0.6rem] font-semibold",
                    repo.status === "active" ? "bg-[var(--success-muted)] text-[var(--success)]" : "bg-[var(--surface-raised)] text-[var(--text-muted)]"
                  )}>
                    <span className={cn("h-1.5 w-1.5 rounded-full", repo.status === "active" ? "bg-[var(--success)]" : "bg-[var(--text-muted)]")} />
                    {repo.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export function JiraPanel() {
  return (
    <div className="space-y-4">
      <h3 className="text-[0.85rem] font-bold" style={{ color: "var(--text-primary)" }}>Jira Integration</h3>
      <div className="space-y-2">
        {[
          { id: "COR-142", title: "Implement agent delegation graph", status: "In Progress", priority: "High", assignee: "Alex" },
          { id: "COR-141", title: "Add shared memory visualization", status: "In Progress", priority: "Medium", assignee: "Sarah" },
          { id: "COR-140", title: "Fix streaming response in chat", status: "Done", priority: "Critical", assignee: "Alex" },
          { id: "COR-139", title: "Update API rate limits", status: "Review", priority: "Low", assignee: "Mike" },
          { id: "COR-138", title: "Add dark mode support for graphs", status: "To Do", priority: "Medium", assignee: "Unassigned" },
        ].map((issue) => (
          <div key={issue.id} className="flex items-center gap-3 rounded-[var(--radius-sm)] p-3 transition-colors hover:bg-[var(--surface-raised)]" style={{ border: "1px solid var(--border)" }}>
            <span className="text-[0.6rem] font-mono font-bold text-[#3B82F6]">{issue.id}</span>
            <p className="flex-1 text-[0.78rem] font-medium" style={{ color: "var(--text-primary)" }}>{issue.title}</p>
            <span className={cn(
              "rounded-full px-2 py-0.5 text-[0.55rem] font-semibold",
              issue.status === "In Progress" ? "bg-[#EFF6FF] text-[#3B82F6]" :
              issue.status === "Done" ? "bg-[var(--success-muted)] text-[var(--success)]" :
              issue.status === "Review" ? "bg-[var(--warning-muted)] text-[var(--warning)]" :
              "bg-[var(--surface-raised)] text-[var(--text-muted)]"
            )}>{issue.status}</span>
            <span className={cn(
              "text-[0.6rem] font-semibold",
              issue.priority === "Critical" ? "text-[var(--danger)]" :
              issue.priority === "High" ? "text-[var(--warning)]" :
              issue.priority === "Medium" ? "text-[var(--success)]" :
              "text-[var(--text-muted)]"
            )}>{issue.priority}</span>
            <span className="text-[0.65rem]" style={{ color: "var(--text-muted)" }}>{issue.assignee}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

export function SlackPanel() {
  const channels = [
    { name: "#engineering", members: 24, messages: 142, alerts: 0 },
    { name: "#ai-agents", members: 18, messages: 89, alerts: 2 },
    { name: "#ops-alerts", members: 12, messages: 34, alerts: 5 },
    { name: "#product", members: 15, messages: 56, alerts: 0 },
    { name: "#general", members: 48, messages: 210, alerts: 0 },
  ]
  return (
    <div className="space-y-4">
      <h3 className="text-[0.85rem] font-bold" style={{ color: "var(--text-primary)" }}>Slack Integration</h3>
      <div className="grid gap-3 sm:grid-cols-2">
        {channels.map((ch) => (
          <div key={ch.name} className="flex items-center gap-3 rounded-[var(--radius-sm)] p-4" style={{ border: "1px solid var(--border)" }}>
            <div className="flex h-10 w-10 items-center justify-center rounded-[10px] bg-[#FFF0F3]">
              <MessageSquare className="h-5 w-5 text-[#E01E5A]" />
            </div>
            <div className="flex-1">
              <p className="text-[0.8rem] font-bold" style={{ color: "var(--text-primary)" }}>{ch.name}</p>
              <div className="flex items-center gap-3 text-[0.6rem] mt-0.5" style={{ color: "var(--text-muted)" }}>
                <span>{ch.members} members</span>
                <span>{ch.messages} msgs today</span>
              </div>
            </div>
            {ch.alerts > 0 && (
              <span className="rounded-full bg-[var(--danger)] px-2 py-0.5 text-[0.55rem] font-bold text-white">{ch.alerts}</span>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

export function DockerPanel() {
  const containers = [
    { name: "cortexprime-api", image: "cortexprime/api:latest", status: "running", port: "8000", cpu: "12%", mem: "256MB" },
    { name: "cortexprime-frontend", image: "cortexprime/frontend:latest", status: "running", port: "3000", cpu: "8%", mem: "184MB" },
    { name: "cortexprime-worker", image: "cortexprime/worker:2.1.0", status: "running", port: "9001", cpu: "24%", mem: "512MB" },
    { name: "cortexprime-redis", image: "redis:7-alpine", status: "running", port: "6379", cpu: "4%", mem: "64MB" },
    { name: "cortexprime-db", image: "postgres:16", status: "running", port: "5432", cpu: "6%", mem: "128MB" },
  ]
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-[0.85rem] font-bold" style={{ color: "var(--text-primary)" }}>Docker Containers</h3>
        <button
          aria-label="Sync Docker"
          className="rounded-[var(--radius-sm)] px-2.5 py-1 text-[0.65rem] font-semibold hover:bg-[var(--surface-raised)] transition-colors"
          style={{ border: "1px solid var(--border)", color: "var(--text-secondary)" }}
        >
          <RefreshCw className="h-3 w-3 inline mr-1" />Sync
        </button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left" aria-label="Docker containers">
          <thead>
            <tr className="border-b text-[0.65rem] font-semibold uppercase" style={{ borderColor: "var(--border)", color: "var(--text-muted)" }}>
              <th className="pb-3 pr-4">Container</th>
              <th className="pb-3 pr-4">Image</th>
              <th className="pb-3 pr-4">Port</th>
              <th className="pb-3 pr-4">CPU</th>
              <th className="pb-3 pr-4">Memory</th>
              <th className="pb-3 pr-4">Status</th>
            </tr>
          </thead>
          <tbody>
            {containers.map((c) => (
              <tr key={c.name} className="border-b last:border-0" style={{ borderColor: "var(--border)" }}>
                <td className="py-3 pr-4">
                  <div className="flex items-center gap-2">
                    <Container className="h-4 w-4 text-[#2496ED]" />
                    <span className="text-[0.78rem] font-semibold" style={{ color: "var(--text-primary)" }}>{c.name}</span>
                  </div>
                </td>
                <td className="py-3 pr-4 text-[0.68rem] font-mono" style={{ color: "var(--text-secondary)" }}>{c.image}</td>
                <td className="py-3 pr-4 text-[0.75rem]" style={{ color: "var(--text-secondary)" }}>{c.port}</td>
                <td className="py-3 pr-4 text-[0.75rem]" style={{ color: "var(--text-secondary)" }}>{c.cpu}</td>
                <td className="py-3 pr-4 text-[0.75rem]" style={{ color: "var(--text-secondary)" }}>{c.mem}</td>
                <td className="py-3">
                  <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[0.6rem] font-semibold bg-[var(--success-muted)] text-[var(--success)]">
                    <span className="h-1.5 w-1.5 rounded-full bg-[var(--success)]" />
                    {c.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export function KubernetesPanel() {
  return (
    <div className="space-y-4">
      <h3 className="text-[0.85rem] font-bold" style={{ color: "var(--text-primary)" }}>Kubernetes Cluster</h3>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[
          { label: "Namespaces", value: "6", icon: Box },
          { label: "Pods", value: "142", icon: HardDrive },
          { label: "Services", value: "24", icon: Wifi },
          { label: "Deployments", value: "18", icon: Layers },
        ].map((m) => {
          const Icon = m.icon
          return (
            <div key={m.label} className="rounded-[var(--radius-sm)] p-4" style={{ border: "1px solid var(--border)", background: "var(--surface)" }}>
              <div className="flex items-center gap-2 mb-2">
                <Icon className="h-4 w-4 text-[#326CE5]" />
                <span className="text-[0.6rem] font-semibold uppercase" style={{ color: "var(--text-muted)" }}>{m.label}</span>
              </div>
              <p className="text-[1.2rem] font-extrabold" style={{ color: "var(--text-primary)" }}>{m.value}</p>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export function PrometheusPanel() {
  return (
    <div className="space-y-4">
      <h3 className="text-[0.85rem] font-bold" style={{ color: "var(--text-primary)" }}>Prometheus Alerts</h3>
      <div className="space-y-2">
        {[
          { name: "HighMemoryUsage", severity: "warning", status: "firing", value: "87%", threshold: "80%", duration: "5m" },
          { name: "APIErrorRate", severity: "critical", status: "firing", value: "5.2%", threshold: "3%", duration: "2m" },
          { name: "PodCrashLoop", severity: "critical", status: "firing", value: "2 pods", threshold: "0", duration: "1m" },
          { name: "NodeCPUHigh", severity: "warning", status: "resolved", value: "72%", threshold: "85%", duration: "10m" },
        ].map((alert) => (
          <div key={alert.name} className={cn(
            "flex items-center gap-3 rounded-[var(--radius-sm)] border p-3",
            alert.status === "firing" ? "bg-[var(--danger-muted)] border-[var(--danger-border)]" : "bg-[var(--success-muted)] border-[var(--success-border)]"
          )}>
            <AlertTriangle className={cn("h-4 w-4 shrink-0", alert.severity === "critical" ? "text-[var(--danger)]" : "text-[var(--warning)]")} />
            <div className="flex-1 min-w-0">
              <p className="text-[0.75rem] font-semibold" style={{ color: "var(--text-primary)" }}>{alert.name}</p>
              <div className="flex items-center gap-2 text-[0.6rem]" style={{ color: "var(--text-secondary)" }}>
                <span>{alert.value} / {alert.threshold}</span>
                <span>{alert.duration}</span>
              </div>
            </div>
            <span className={cn(
              "rounded-full px-2 py-0.5 text-[0.55rem] font-semibold capitalize text-white",
              alert.status === "firing" ? "bg-[var(--danger)]" : "bg-[var(--success)]"
            )}>{alert.status}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

export function GrafanaPanel() {
  const dashboards = [
    { title: "Platform Overview", datasource: "Prometheus", panels: 24, starred: true },
    { title: "Agent Performance", datasource: "Prometheus", panels: 16, starred: true },
    { title: "Infrastructure Health", datasource: "Loki + Prometheus", panels: 32, starred: false },
    { title: "API Metrics", datasource: "Prometheus", panels: 12, starred: false },
    { title: "Cost Analysis", datasource: "PostgreSQL", panels: 8, starred: false },
  ]
  return (
    <div className="space-y-4">
      <h3 className="text-[0.85rem] font-bold" style={{ color: "var(--text-primary)" }}>Grafana Dashboards</h3>
      <div className="space-y-2">
        {dashboards.map((d) => (
          <div
            key={d.title}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") e.preventDefault() }}
            className="flex items-center gap-3 rounded-[var(--radius-sm)] p-3 transition-colors hover:bg-[var(--surface-raised)] cursor-pointer"
            style={{ border: "1px solid var(--border)" }}
          >
            <BarChart3 className="h-5 w-5 text-[#F46800]" />
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <p className="text-[0.78rem] font-semibold" style={{ color: "var(--text-primary)" }}>{d.title}</p>
                {d.starred && <span className="text-[var(--warning)] text-[0.7rem]" aria-label="Starred dashboard">&#9733;</span>}
              </div>
              <p className="text-[0.6rem]" style={{ color: "var(--text-muted)" }}>{d.datasource} &middot; {d.panels} panels</p>
            </div>
            <ExternalLink className="h-3.5 w-3.5" style={{ color: "var(--text-muted)" }} />
          </div>
        ))}
      </div>
    </div>
  )
}
