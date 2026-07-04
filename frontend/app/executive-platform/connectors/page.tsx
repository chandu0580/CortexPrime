"use client"

import { useState } from "react"
import { PlugZap, GitFork, MessageSquare, ExternalLink, CheckCircle2, XCircle } from "lucide-react"

const CONNECTORS = [
  { name: "GitHub", icon: GitFork, status: "connected", latency: "45ms", auth: "OAuth2", lastActivity: "1m ago" },
  { name: "Jira", icon: ExternalLink, status: "connected", latency: "120ms", auth: "API Key", lastActivity: "5m ago" },
  { name: "Slack", icon: MessageSquare, status: "connected", latency: "30ms", auth: "OAuth2", lastActivity: "30s ago" },
  { name: "Teams", icon: ExternalLink, status: "disconnected", latency: "—", auth: "OIDC", lastActivity: "2h ago" },
  { name: "ServiceNow", icon: ExternalLink, status: "connected", latency: "200ms", auth: "Basic", lastActivity: "15m ago" },
  { name: "Confluence", icon: ExternalLink, status: "connected", latency: "80ms", auth: "API Key", lastActivity: "10m ago" },
]

export default function ConnectorCenter() {
  const [filter, setFilter] = useState<string>("all")

  const filtered = filter === "all" ? CONNECTORS : CONNECTORS.filter((c) => c.status === filter)

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Connectors</h1>
        <div className="flex items-center gap-2">
          {["all", "connected", "disconnected"].map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 py-1.5 rounded-lg text-xs transition-all ${
                filter === f ? "bg-white/10 text-white" : "text-white/30 hover:text-white/60"
              }`}
            >{f}</button>
          ))}
        </div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {filtered.map((c) => (
          <div key={c.name} className="border border-white/5 rounded-xl p-4 bg-white/[0.02] flex items-start gap-3">
            <div className="p-2 rounded-lg bg-white/5">
              <c.icon className="w-5 h-5 text-white/60" />
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium">{c.name}</span>
                {c.status === "connected" ? (
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                ) : (
                  <XCircle className="w-3.5 h-3.5 text-red-400" />
                )}
              </div>
              <div className="flex items-center gap-3 mt-1 text-xs text-white/40">
                <span>Latency: {c.latency}</span>
                <span>Auth: {c.auth}</span>
                <span>{c.lastActivity}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}