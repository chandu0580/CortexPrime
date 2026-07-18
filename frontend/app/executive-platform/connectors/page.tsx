"use client"

import { useState, useMemo } from "react"
import { CheckCircle2, XCircle, PlugZap } from "lucide-react"
import { useConnectors } from "@/hooks/queries/connectors"

const CONNECTOR_META: Record<string, { icon: string }> = {
  github: { icon: "🔧" },
  jira: { icon: "📋" },
  slack: { icon: "💬" },
  "microsoft-teams": { icon: "👥" },
  "azure-devops": { icon: "⚙️" },
  confluence: { icon: "📝" },
  servicenow: { icon: "🔄" },
  notion: { icon: "📚" },
}

export default function ConnectorCenter() {
  const [filter, setFilter] = useState<string>("all")
  const { data, isLoading } = useConnectors()

  const connectors = data?.connectors ?? []

  const filtered = useMemo(() => {
    if (filter === "all") return connectors
    return connectors.filter((c) => {
      if (filter === "connected") return c.connection_state === "connected"
      if (filter === "disconnected") return c.connection_state === "disconnected"
      return true
    })
  }, [connectors, filter])

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
      {isLoading ? (
        <div className="text-white/40 text-sm text-center py-12">Loading connectors...</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {filtered.map((c) => {
            const meta = CONNECTOR_META[c.type] ?? { icon: "🔌" }
            const isConnected = c.connection_state === "connected"
            return (
              <div key={c.type} className="border border-white/5 rounded-xl p-4 bg-white/[0.02] flex items-start gap-3">
                <div className="p-2 rounded-lg bg-white/5 text-lg">
                  {meta.icon}
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium">{c.name}</span>
                    {isConnected ? (
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                    ) : (
                      <XCircle className="w-3.5 h-3.5 text-red-400" />
                    )}
                  </div>
                  <div className="flex items-center gap-3 mt-1 text-xs text-white/40">
                    <span>Latency: {c.latency_ms != null ? `${c.latency_ms}ms` : "—"}</span>
                    <span>Auth: {c.authentication_type}</span>
                    <span>{c.connection_state}</span>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
