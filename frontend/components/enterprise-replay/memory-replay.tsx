"use client"

import { useEnterpriseReplayStore } from "@/store/enterpriseReplayStore"
import { Badge } from "./shared"
import { Database, Brain, BookOpen, RefreshCw, Layers } from "lucide-react"
import { useState } from "react"

const MEMORY_COLORS: Record<string, string> = {
  working: "#3B82F6", semantic: "#8B5CF6", episodic: "#F59E0B",
}

type _IconProps = React.SVGProps<SVGSVGElement> & { className?: string }
const MEMORY_ICONS: Record<string, React.ComponentType<_IconProps>> = {
  working: Layers, semantic: BookOpen, episodic: RefreshCw,
}

export function MemoryReplayPanel() {
  const memory = useEnterpriseReplayStore((s) => s.memory)
  const [selectedType, setSelectedType] = useState<string | null>(null)

  if (!memory) return <div className="text-center py-12 text-[0.82rem] text-[#6B7280]">No memory replay data loaded</div>

  const types = [
    { key: "working_memory", label: "Working Memory", count: memory.working_memory.length },
    { key: "semantic_memory", label: "Semantic Memory", count: memory.semantic_memory.length },
    { key: "episodic_memory", label: "Episodic Memory", count: memory.episodic_memory.length },
  ]

  return (
    <div className="space-y-5">
      {/* Summary */}
      <div className="grid gap-4 sm:grid-cols-3">
        {types.map((t) => {
          const color = MEMORY_COLORS[t.key.replace("_memory", "")] ?? "#6B7280"
          const Icon = MEMORY_ICONS[t.key.replace("_memory", "")] ?? Database
          return (
            <button key={t.key} onClick={() => setSelectedType(selectedType === t.key ? null : t.key)}
              className="rounded-[18px] border border-[#E8EDF3] bg-white p-5 text-left hover:shadow-md transition-shadow"
              style={{ borderColor: selectedType === t.key ? color : undefined }}>
              <div className="flex items-center gap-3 mb-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-[12px]" style={{ background: `${color}15` }}>
                  <Icon className="h-5 w-5" style={{ color }} />
                </div>
                <div>
                  <p className="text-[0.9rem] font-bold text-[#111827]">{t.label}</p>
                  <p className="text-[0.72rem] text-[#6B7280]">{t.count} entries</p>
                </div>
              </div>
              <Badge tone={t.count > 0 ? "completed" : "info"} label={t.count > 0 ? `${t.count} recorded` : "No data"} />
            </button>
          )
        })}
      </div>

      {/* Detail sections */}
      {selectedType && (
        <div className="rounded-[18px] border border-[#E8EDF3] bg-white p-5">
          <h3 className="text-[0.95rem] font-bold text-[#111827] mb-4 capitalize">
            {selectedType.replace(/_/g, " ")}
          </h3>
          <div className="space-y-2 max-h-[400px] overflow-y-auto">
            {(memory[selectedType as keyof typeof memory] as Array<Record<string, unknown>> ?? []).map((entry, i) => (
              <div key={(entry.memory_id as string) ?? i} className="p-3 rounded-[12px] bg-[#F8FAFC] border border-[#E8EDF3]">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-[0.72rem] font-semibold text-[#111827]">{entry.agent as string}</span>
                  <Badge tone={entry.operation === "create" ? "completed" : entry.operation === "update" ? "info" : "warning"} label={entry.operation as string} />
                </div>
                <p className="text-[0.7rem] text-[#6B7280]">{entry.content as string}</p>
                {entry.relevance_score != null && (
                  <p className="text-[0.66rem] text-[#9CA3AF] mt-1">Relevance: {((entry.relevance_score as number) * 100).toFixed(0)}%</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Changes over time */}
      {memory.changes_over_time && memory.changes_over_time.length > 0 && (
        <div className="rounded-[18px] border border-[#E8EDF3] bg-white p-5">
          <h3 className="text-[0.95rem] font-bold text-[#111827] mb-4">Changes Over Time</h3>
          <div className="space-y-1">
            {memory.changes_over_time.map((change, i) => (
              <div key={i} className="flex items-center gap-2 text-[0.7rem] text-[#6B7280] py-1">
                <div className="w-1.5 h-1.5 rounded-full bg-[#38B88A]" />
                <span className="font-mono text-[#9CA3AF]">{(change as Record<string, unknown>).timestamp as string ?? ""}</span>
                <span>{(change as Record<string, unknown>).operation as string}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}