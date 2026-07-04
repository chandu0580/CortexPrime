"use client"

import { useEnterpriseReplayStore } from "@/store/enterpriseReplayStore"
import { Badge } from "./shared"
import { Puzzle, Activity, Clock, XCircle, RotateCw } from "lucide-react"
import { useState } from "react"

const CONNECTOR_ICONS: Record<string, string> = {
  github: "GH", jira: "JI", slack: "SL", teams: "TE",
  servicenow: "SN", confluence: "CF", notion: "NO", azure_devops: "AZ", azure: "AZ",
}

const CONNECTOR_COLORS: Record<string, string> = {
  github: "#24292E", jira: "#0052CC", slack: "#4A154B", teams: "#6264A7",
  servicenow: "#0072C6", confluence: "#0052CC", notion: "#000000", azure_devops: "#0078D7", azure: "#0078D7",
}

export function ConnectorReplayPanel() {
  const connectors = useEnterpriseReplayStore((s) => s.connectors)
  const [selectedConnector, setSelectedConnector] = useState<string | null>(null)

  if (!connectors) return <div className="text-center py-12 text-[0.82rem] text-[#6B7280]">No connector data loaded</div>

  const connectorTypes = Object.keys(connectors.connectors ?? {})
  const summary = connectors.summary as Record<string, unknown>

  return (
    <div className="space-y-5">
      {/* Summary cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-[18px] border border-[#E8EDF3] bg-white p-4">
          <div className="flex items-center gap-2 mb-1">
            <Puzzle className="h-4 w-4 text-[#38B88A]" />
            <span className="text-[0.71rem] font-semibold text-[#9CA3AF]">Total Calls</span>
          </div>
          <p className="text-[1.4rem] font-bold text-[#111827]">{String(summary.total_calls ?? 0)}</p>
        </div>
        <div className="rounded-[18px] border border-[#E8EDF3] bg-white p-4">
          <div className="flex items-center gap-2 mb-1">
            <Activity className="h-4 w-4 text-[#3B82F6]" />
            <span className="text-[0.71rem] font-semibold text-[#9CA3AF]">Connectors</span>
          </div>
          <p className="text-[1.4rem] font-bold text-[#111827]">{connectorTypes.length}</p>
        </div>
        <div className="rounded-[18px] border border-[#E8EDF3] bg-white p-4">
          <div className="flex items-center gap-2 mb-1">
            <XCircle className="h-4 w-4 text-[#EF4444]" />
            <span className="text-[0.71rem] font-semibold text-[#9CA3AF]">Failures</span>
          </div>
          <p className="text-[1.4rem] font-bold text-[#111827]">{String(summary.total_failures ?? 0)}</p>
        </div>
        <div className="rounded-[18px] border border-[#E8EDF3] bg-white p-4">
          <div className="flex items-center gap-2 mb-1">
            <RotateCw className="h-4 w-4 text-[#F59E0B]" />
            <span className="text-[0.71rem] font-semibold text-[#9CA3AF]">Retries</span>
          </div>
          <p className="text-[1.4rem] font-bold text-[#111827]">{String(summary.total_retries ?? 0)}</p>
        </div>
      </div>

      {/* Connector cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {connectorTypes.map((ct) => {
          const calls = connectors.connectors[ct] ?? []
          const color = CONNECTOR_COLORS[ct] ?? "#6B7280"
          const icon = CONNECTOR_ICONS[ct] ?? "CX"
          const totalLatency = calls.reduce((s, c) => s + (c.latency_ms ?? 0), 0)
          const failures = calls.filter((c) => c.status === "error").length

          return (
            <button key={ct} onClick={() => setSelectedConnector(selectedConnector === ct ? null : ct)}
              className="rounded-[18px] border border-[#E8EDF3] bg-white p-5 text-left hover:shadow-md transition-shadow">
              <div className="flex items-center gap-3 mb-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-[10px] text-[0.7rem] font-bold text-white"
                  style={{ background: color }}>
                  {icon}
                </div>
                <div>
                  <p className="text-[0.9rem] font-bold text-[#111827] capitalize">{ct.replace(/_/g, " ")}</p>
                  <p className="text-[0.7rem] text-[#6B7280]">{calls.length} calls</p>
                </div>
              </div>
              <div className="flex items-center gap-3 text-[0.7rem] text-[#6B7280]">
                <span className="flex items-center gap-1"><Clock className="h-3 w-3" />{totalLatency.toFixed(0)}ms</span>
                {failures > 0 && <span className="text-[#EF4444]">{failures} failed</span>}
              </div>
            </button>
          )
        })}
      </div>

      {/* Expanded connector details */}
      {selectedConnector && (
        <div className="rounded-[18px] border border-[#E8EDF3] bg-white p-5">
          <h3 className="text-[0.95rem] font-bold text-[#111827] mb-4 capitalize">{selectedConnector.replace(/_/g, " ")} Calls</h3>
          <div className="space-y-2 max-h-[400px] overflow-y-auto">
            {(connectors.connectors[selectedConnector] ?? []).map((call, i) => (
              <div key={i} className="p-3 rounded-[12px] bg-[#F8FAFC] border border-[#E8EDF3]">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-[0.72rem] font-semibold text-[#111827]">{call.method}</span>
                  <span className="text-[0.68rem] text-[#6B7280] font-mono truncate flex-1">{call.endpoint}</span>
                  <Badge tone={call.status === "error" ? "failed" : "completed"} label={call.status} />
                </div>
                <div className="flex items-center gap-3 text-[0.66rem] text-[#9CA3AF]">
                  {call.latency_ms != null && <span>{call.latency_ms.toFixed(0)}ms</span>}
                  {call.retry_count > 0 && <span>Retries: {call.retry_count}</span>}
                </div>
                {call.error && <p className="text-[0.68rem] text-[#EF4444] mt-1">{call.error}</p>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}