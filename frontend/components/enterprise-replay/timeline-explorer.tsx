"use client"

import { useEnterpriseReplayStore } from "@/store/enterpriseReplayStore"
import { EnterprisePlaybackControls } from "./shared"
import { Clock, Search, ZoomIn, ZoomOut, Filter } from "lucide-react"
import { useState } from "react"

const CATEGORY_COLORS: Record<string, string> = {
  mission: "#38B88A", worker: "#3B82F6", connector: "#F59E0B",
  memory: "#8B5CF6", governance: "#EF4444", system: "#6B7280",
}

export function TimelineExplorerPanel() {
  const timeline = useEnterpriseReplayStore((s) => s.timeline)
  const currentSequence = useEnterpriseReplayStore((s) => s.currentSequence)
  const seekTo = useEnterpriseReplayStore((s) => s.seekTo)
  const [searchQuery, setSearchQuery] = useState("")
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null)

  if (!timeline) return <div className="text-center py-12 text-[0.82rem] text-[#6B7280]">No timeline data loaded</div>

  const filtered = (timeline.events ?? []).filter((e) => {
    if (searchQuery) {
      const q = searchQuery.toLowerCase()
      if (!e.message?.toLowerCase().includes(q) && !e.event_type?.toLowerCase().includes(q) && !e.agent?.toLowerCase().includes(q)) return false
    }
    if (categoryFilter && e.category !== categoryFilter) return false
    return true
  })

  const categories = [...new Set(timeline.events.map((e) => e.category))]

  return (
    <div className="space-y-4">
      {/* Controls bar */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[#9CA3AF]" />
          <input value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search events..." className="h-9 w-full rounded-[10px] border border-[#E8EDF3] bg-white pl-9 pr-3 text-[0.75rem] outline-none" />
        </div>
        <div className="flex items-center gap-1">
          {categories.map((cat) => (
            <button key={cat} onClick={() => setCategoryFilter(categoryFilter === cat ? null : cat)}
              className="px-2.5 py-1 rounded-[8px] text-[0.7rem] font-semibold border transition-colors"
              style={{
                borderColor: categoryFilter === cat ? CATEGORY_COLORS[cat] ?? "#38B88A" : "#E8EDF3",
                background: categoryFilter === cat ? `${CATEGORY_COLORS[cat] ?? "#38B88A"}15` : "transparent",
                color: categoryFilter === cat ? CATEGORY_COLORS[cat] ?? "#38B88A" : "#6B7280",
              }}>
              {cat}
            </button>
          ))}
        </div>
      </div>

      <EnterprisePlaybackControls />

      {/* Timeline */}
      <div className="rounded-[18px] border border-[#E8EDF3] bg-white p-5 max-h-[500px] overflow-y-auto">
        <div className="space-y-1">
          {filtered.map((event, i) => {
            const isActive = i === currentSequence
            const isPast = i < currentSequence
            const color = CATEGORY_COLORS[event.category] ?? "#6B7280"

            return (
              <button key={`${event.sequence}-${i}`} onClick={() => seekTo(i)}
                className="flex items-start gap-3 w-full text-left p-2.5 rounded-[10px] transition-colors"
                style={{
                  background: isActive ? `${color}10` : "transparent",
                  opacity: isPast ? 0.5 : 1,
                }}>
                <div className="flex flex-col items-center pt-1">
                  <div className="w-2.5 h-2.5 rounded-full" style={{ background: isActive ? color : isPast ? "#D1D5DB" : "#E5E7EB" }} />
                  {i < filtered.length - 1 && <div className="w-px flex-1 min-h-[16px] mt-1" style={{ background: isPast ? "#D1D5DB" : "#E8EDF3" }} />}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className="text-[0.72rem] font-semibold text-[#111827]">{event.event_type}</span>
                    <span className="text-[0.66rem] text-[#9CA3AF] font-mono">{event.agent}</span>
                  </div>
                  <p className="text-[0.7rem] text-[#6B7280] truncate">{event.message}</p>
                </div>
                <span className="text-[0.66rem] text-[#9CA3AF] font-mono shrink-0">
                  {event.offset_ms != null ? `${(event.offset_ms / 1000).toFixed(1)}s` : ""}
                </span>
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}