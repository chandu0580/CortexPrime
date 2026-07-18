"use client"

import { useQuery } from "@tanstack/react-query"
import { listConnectors, getConnectorActivity } from "@/services/connector-api"
import { ExecPanel, EmptyPanel } from "./ExecPanel"
import Link from "next/link"
import { ExternalLink, Play, Pause, CheckCircle2, AlertCircle, Clock } from "lucide-react"

export function ConnectedEnterprisePanel() {
  const { data: connectors } = useQuery({
    queryKey: ["command-center", "connectors"],
    queryFn: listConnectors,
    refetchInterval: 30000,
  })

  const activeWorkflows = connectors?.connectors
    ?.filter((c) => c.connection_state === "connected" || c.connection_state === "active")
    ?.slice(0, 5) ?? []

  return (
    <ExecPanel
      title="Connected Systems"
      subtitle="Active enterprise connectors"
      accent="violet"
      headerRight={
        <Link href="/executive-platform/connectors" className="text-[10px] text-white/30 hover:text-white/60 transition-colors flex items-center gap-1">
          Manage <ExternalLink className="w-3 h-3" />
        </Link>
      }
    >
      {activeWorkflows.length === 0 ? (
        <EmptyPanel title="No connected systems" description="Connect enterprise services to get started" />
      ) : (
        <div className="space-y-1.5">
          {activeWorkflows.map((conn) => (
            <div
              key={conn.type}
              className="flex items-center gap-3 p-2 rounded-lg hover:bg-white/5 transition-colors group"
            >
              <div className="w-7 h-7 rounded-lg bg-white/5 flex items-center justify-center shrink-0">
                <span className="text-[10px] font-bold text-white/40 uppercase">{conn.type.slice(0, 2)}</span>
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-xs text-white/70 font-medium truncate">{conn.name}</span>
                  <span className={`text-[9px] px-1.5 py-0.5 rounded-full uppercase font-semibold ${
                    conn.status === "connected" || conn.status === "active" ? "text-emerald-400 bg-emerald-500/10" :
                    conn.status === "error" || conn.status === "disconnected" ? "text-rose-400 bg-rose-500/10" :
                    "text-amber-400 bg-amber-500/10"
                  }`}>
                    {conn.connection_state || conn.status}
                  </span>
                </div>
                <div className="flex items-center gap-2 mt-0.5">
                  {conn.capabilities?.slice(0, 2).map((cap, i) => (
                    <span key={i} className="text-[9px] text-white/20 bg-white/5 px-1.5 py-0.5 rounded">
                      {cap}
                    </span>
                  ))}
                  {conn.latency_ms != null && (
                    <span className="text-[9px] text-white/20">{conn.latency_ms}ms</span>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
      <div className="mt-2 pt-2 border-t border-white/5">
        <div className="flex items-center justify-between text-[10px]">
          <span className="text-white/30">{activeWorkflows.length} connected · {connectors?.total ?? 0} total</span>
          <span className={`flex items-center gap-1 ${activeWorkflows.length > 0 ? "text-emerald-400" : "text-white/20"}`}>
            <span className="w-1.5 h-1.5 rounded-full bg-current" />
            {activeWorkflows.length > 0 ? "Live" : "Offline"}
          </span>
        </div>
      </div>
    </ExecPanel>
  )
}