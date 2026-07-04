"use client"

import { useEnterpriseReplayStore } from "@/store/enterpriseReplayStore"
import { Badge } from "./shared"
import { Globe, Mic, Monitor, Bot, Play, Terminal } from "lucide-react"
import { useState } from "react"

type _IconProps = React.SVGProps<SVGSVGElement> & { className?: string }
const WORKER_ICONS: Record<string, React.ComponentType<_IconProps>> = {
  browser: Globe, voice: Mic, desktop: Monitor,
}

const WORKER_COLORS: Record<string, string> = {
  browser: "#3B82F6", voice: "#8B5CF6", desktop: "#F59E0B",
}

export function WorkerReplayPanel() {
  const workers = useEnterpriseReplayStore((s) => s.workers)
  const [expandedWorker, setExpandedWorker] = useState<string | null>(null)

  if (!workers) return <div className="text-center py-12 text-[0.82rem] text-[#6B7280]">No worker replay data loaded</div>

  const workerTypes = Object.keys(workers.workers ?? {})

  return (
    <div className="space-y-5">
      <div className="grid gap-4 sm:grid-cols-3">
        {workerTypes.map((type) => {
          const actions = workers.workers[type] ?? []
          const Icon = WORKER_ICONS[type] ?? Bot
          const color = WORKER_COLORS[type] ?? "#6B7280"
          return (
            <button key={type} onClick={() => setExpandedWorker(expandedWorker === type ? null : type)}
              className="rounded-[18px] border border-[#E8EDF3] bg-white p-5 text-left hover:shadow-md transition-shadow">
              <div className="flex items-center gap-3 mb-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-[12px]" style={{ background: `${color}15` }}>
                  <Icon className="h-5 w-5" style={{ color }} />
                </div>
                <div>
                  <p className="text-[0.95rem] font-bold text-[#111827] capitalize">{type}</p>
                  <p className="text-[0.72rem] text-[#6B7280]">{actions.length} actions</p>
                </div>
              </div>
              <Badge tone={actions.some((a) => a.status === "error") ? "failed" : "completed"} label={actions.length > 0 ? `${actions.length} recorded` : "No data"} />
            </button>
          )
        })}
      </div>

      {/* Expanded worker details */}
      {expandedWorker && (
        <div className="rounded-[18px] border border-[#E8EDF3] bg-white p-5">
          <h3 className="text-[0.95rem] font-bold text-[#111827] mb-4 capitalize">{expandedWorker} Actions</h3>
          <div className="space-y-2 max-h-[400px] overflow-y-auto">
            {(workers.workers[expandedWorker] ?? []).map((action, i) => (
              <div key={action.action_id ?? i}
                className="flex items-start gap-3 p-3 rounded-[12px] bg-[#F8FAFC] border border-[#E8EDF3]">
                <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-[6px] bg-[#ECFBF4]">
                  <Play className="h-3 w-3 text-[#38B88A]" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-[0.75rem] font-semibold text-[#111827]">{action.action_type}</span>
                    <Badge tone={action.status === "error" ? "failed" : "completed"} label={action.status} />
                  </div>
                  <p className="text-[0.72rem] text-[#6B7280] truncate">{action.action}</p>
                  {action.duration_ms && (
                    <p className="text-[0.66rem] text-[#9CA3AF] mt-1 font-mono">{action.duration_ms.toFixed(0)}ms</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Runtime state */}
      {workers.runtime_state && (
        <div className="rounded-[18px] border border-[#E8EDF3] bg-white p-5">
          <h3 className="text-[0.95rem] font-bold text-[#111827] mb-3">Runtime State</h3>
          <div className="grid grid-cols-3 gap-3">
            {Object.entries(workers.runtime_state).map(([key, val]) => (
              <div key={key} className="flex items-center gap-2 p-2 rounded-[10px] bg-[#F8FAFC]">
                <Terminal className="h-4 w-4 text-[#38B88A]" />
                <div>
                  <p className="text-[0.66rem] text-[#9CA3AF]">{key.replace(/_/g, " ")}</p>
                  <p className="text-[0.75rem] font-semibold text-[#111827]">{String(val)}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}