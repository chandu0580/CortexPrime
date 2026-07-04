"use client"

import { useEnterpriseReplayStore } from "@/store/enterpriseReplayStore"
import { Badge } from "./shared"
import { Activity, GitBranch, Share2, TrendingUp, Network } from "lucide-react"
import { useState } from "react"

const ENTITY_TYPE_COLORS: Record<string, string> = {
  agent: "#38B88A", memory: "#3B82F6", concept: "#8B5CF6",
  mission: "#F59E0B", world_model: "#EF4444",
}

export function KnowledgeGraphReplayPanel() {
  const kg = useEnterpriseReplayStore((s) => s.knowledgeGraph)
  const [view, setView] = useState<"entities" | "relationships" | "evolution">("entities")

  if (!kg) return <div className="text-center py-12 text-[0.82rem] text-[#6B7280]">No knowledge graph data loaded</div>

  return (
    <div className="space-y-5">
      {/* Summary cards */}
      <div className="grid gap-4 sm:grid-cols-3">
        <div className="rounded-[18px] border border-[#E8EDF3] bg-white p-4">
          <div className="flex items-center gap-2 mb-1">
            <GitBranch className="h-4 w-4 text-[#38B88A]" />
            <span className="text-[0.71rem] font-semibold text-[#9CA3AF]">Entities</span>
          </div>
          <p className="text-[1.4rem] font-bold text-[#111827]">{kg.total_entities}</p>
        </div>
        <div className="rounded-[18px] border border-[#E8EDF3] bg-white p-4">
          <div className="flex items-center gap-2 mb-1">
            <Share2 className="h-4 w-4 text-[#3B82F6]" />
            <span className="text-[0.71rem] font-semibold text-[#9CA3AF]">Relationships</span>
          </div>
          <p className="text-[1.4rem] font-bold text-[#111827]">{kg.total_relationships}</p>
        </div>
        <div className="rounded-[18px] border border-[#E8EDF3] bg-white p-4">
          <div className="flex items-center gap-2 mb-1">
            <TrendingUp className="h-4 w-4 text-[#8B5CF6]" />
            <span className="text-[0.71rem] font-semibold text-[#9CA3AF]">Entity Types</span>
          </div>
          <p className="text-[1.4rem] font-bold text-[#111827]">{(kg.summary?.entity_types as string[])?.length ?? 0}</p>
        </div>
      </div>

      {/* View switcher */}
      <div className="flex items-center gap-2 p-1 rounded-[12px] bg-[#F8FAFC] w-fit">
        {(["entities", "relationships", "evolution"] as const).map((v) => (
          <button key={v} onClick={() => setView(v)}
            className={`px-4 py-2 rounded-[8px] text-[0.75rem] font-semibold transition-colors ${
              view === v ? "bg-white text-[#111827] shadow-sm" : "text-[#6B7280] hover:text-[#111827]"
            }`}>
            {v.charAt(0).toUpperCase() + v.slice(1)}
          </button>
        ))}
      </div>

      {/* Entities */}
      {view === "entities" && (
        <div className="rounded-[18px] border border-[#E8EDF3] bg-white p-5 max-h-[500px] overflow-y-auto">
          <h3 className="text-[0.95rem] font-bold text-[#111827] mb-4">Graph Entities</h3>
          <div className="space-y-2">
            {kg.entities.map((entity, i) => (
              <div key={entity.entity_id ?? i} className="p-3 rounded-[12px] border border-[#E8EDF3] flex items-center gap-3">
                <div className="flex h-8 w-8 items-center justify-center rounded-[8px] text-[0.6rem] font-bold text-white"
                  style={{ background: ENTITY_TYPE_COLORS[entity.entity_type.toLowerCase()] ?? "#6B7280" }}>
                  {entity.entity_type.slice(0, 2).toUpperCase()}
                </div>
                <div className="flex-1">
                  <p className="text-[0.78rem] font-semibold text-[#111827]">{entity.entity_name}</p>
                  <p className="text-[0.66rem] text-[#6B7280]">{entity.entity_type}</p>
                </div>
                <Badge tone={entity.operation === "create" ? "completed" : "info"} label={entity.operation} />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Relationships */}
      {view === "relationships" && (
        <div className="rounded-[18px] border border-[#E8EDF3] bg-white p-5 max-h-[500px] overflow-y-auto">
          <h3 className="text-[0.95rem] font-bold text-[#111827] mb-4">Graph Relationships</h3>
          <div className="space-y-2">
            {kg.relationships.map((rel, i) => (
              <div key={rel.relationship_id ?? i} className="p-3 rounded-[12px] border border-[#E8EDF3] flex items-center gap-3">
                <Network className="h-4 w-4 text-[#38B88A]" />
                <div className="flex-1">
                  <p className="text-[0.78rem] font-semibold text-[#111827]">{rel.source} → {rel.target}</p>
                  <p className="text-[0.66rem] text-[#6B7280]">{rel.relationship_type}</p>
                </div>
                <Badge tone="info" label={rel.operation} />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Evolution */}
      {view === "evolution" && (
        <div className="rounded-[18px] border border-[#E8EDF3] bg-white p-5 max-h-[500px] overflow-y-auto">
          <h3 className="text-[0.95rem] font-bold text-[#111827] mb-4">Graph Evolution</h3>
          <div className="space-y-2">
            {kg.evolution.map((ev, i) => (
              <div key={i} className="flex items-center gap-3 p-2">
                <div className="w-2 h-2 rounded-full bg-[#38B88A]" />
                <span className="text-[0.68rem] text-[#9CA3AF] font-mono">{(ev as Record<string, unknown>).timestamp as string ?? ""}</span>
                <span className="text-[0.72rem] text-[#6B7280]">{(ev as Record<string, unknown>).event as string}</span>
                <Badge tone={(ev as Record<string, unknown>).type === "entity_created" ? "completed" : "info"}
                  label={(ev as Record<string, unknown>).type as string} />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}