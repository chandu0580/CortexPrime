"use client"

import { useEnterpriseReplayStore } from "@/store/enterpriseReplayStore"
import { Badge } from "./shared"
import { ListTodo, Activity, Globe, ShieldCheck, Database, Network, Puzzle, Bot } from "lucide-react"
import { useState } from "react"

type IconProps = React.SVGProps<SVGSVGElement> & { className?: string }
const CATEGORY_CONFIG: Record<string, { icon: React.ComponentType<IconProps>; color: string }> = {
  mission: { icon: Activity, color: "#38B88A" },
  worker: { icon: Bot, color: "#3B82F6" },
  connector: { icon: Puzzle, color: "#F59E0B" },
  memory: { icon: Database, color: "#8B5CF6" },
  graph: { icon: Network, color: "#2F9F77" },
  governance: { icon: ShieldCheck, color: "#EF4444" },
  approval: { icon: ShieldCheck, color: "#C2410C" },
  security: { icon: ShieldCheck, color: "#B91C1C" },
}

export function EventExplorerPanel() {
  const events = useEnterpriseReplayStore((s) => s.events)
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null)

  if (!events) return <div className="text-center py-12 text-[0.82rem] text-[#6B7280]">No event data loaded</div>

  const filtered = categoryFilter
    ? events.events.filter((e) => e.category === categoryFilter)
    : events.events

  return (
    <div className="space-y-5">
      {/* Category breakdown */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-6">
        {Object.entries(events.by_category).map(([cat, count]) => {
          const config = CATEGORY_CONFIG[cat] ?? { icon: ListTodo, color: "#6B7280" }
          const Icon = config.icon
          const isSelected = categoryFilter === cat

          return (
            <button key={cat} onClick={() => setCategoryFilter(isSelected ? null : cat)}
              className="rounded-[14px] border p-4 text-left transition-all"
              style={{
                borderColor: isSelected ? config.color : "#E8EDF3",
                background: isSelected ? `${config.color}08` : "#FFFFFF",
              }}>
              <div className="flex items-center gap-2 mb-2">
                <Icon className="h-4 w-4" color={config.color} />
                <span className="text-[0.72rem] font-semibold text-[#6B7280] capitalize">{cat}</span>
              </div>
              <p className="text-[1.2rem] font-bold text-[#111827]">{count}</p>
            </button>
          )
        })}
      </div>

      {/* Event list */}
      <div className="rounded-[18px] border border-[#E8EDF3] bg-white p-5 max-h-[500px] overflow-y-auto">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-[0.95rem] font-bold text-[#111827]">
            {categoryFilter ? `${categoryFilter} Events` : "All Events"}
            <span className="text-[0.75rem] font-normal text-[#9CA3AF] ml-2">({filtered.length})</span>
          </h3>
        </div>

        <div className="space-y-1">
          {filtered.map((event, i) => {
            const config = CATEGORY_CONFIG[event.category] ?? { icon: ListTodo, color: "#6B7280" }
            const Icon = config.icon

            return (
              <div key={event.event_id ?? i}
                className="flex items-start gap-3 p-2.5 rounded-[10px] hover:bg-[#F8FAFC] transition-colors">
                <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-[8px]"
                  style={{ background: `${config.color}15` }}>
                  <Icon className="h-3.5 w-3.5" style={{ color: config.color }} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-[0.72rem] font-semibold text-[#111827]">{event.event_type}</span>
                    <span className="text-[0.64rem] text-[#9CA3AF]">from {event.source}</span>
                  </div>
                  {event.message && (
                    <p className="text-[0.7rem] text-[#6B7280] truncate">{event.message}</p>
                  )}
                  {event.channel && (
                    <p className="text-[0.62rem] text-[#9CA3AF] mt-0.5">Channel: {event.channel}</p>
                  )}
                </div>
                {event.offset_ms != null && (
                  <span className="text-[0.64rem] text-[#9CA3AF] font-mono shrink-0">
                    +{event.offset_ms.toFixed(0)}ms
                  </span>
                )}
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}