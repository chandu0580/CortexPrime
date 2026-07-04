"use client"

import { useEnterpriseReplayStore } from "@/store/enterpriseReplayStore"
import { Badge, Sparkline } from "./shared"
import { DollarSign, Cpu, BarChart3, Calendar, TrendingUp, PieChart } from "lucide-react"
import { useState } from "react"

export function CostReplayPanel() {
  const costs = useEnterpriseReplayStore((s) => s.costs)
  const [view, setView] = useState<"overview" | "by-category" | "by-day">("overview")

  if (!costs) return <div className="text-center py-12 text-[0.82rem] text-[#6B7280]">No cost data loaded</div>

  const summary = costs.summary as Record<string, unknown>

  return (
    <div className="space-y-5">
      {/* Summary cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-[18px] border border-[#E8EDF3] bg-white p-4">
          <div className="flex items-center gap-2 mb-1">
            <DollarSign className="h-4 w-4 text-[#38B88A]" />
            <span className="text-[0.71rem] font-semibold text-[#9CA3AF]">Total Cost</span>
          </div>
          <p className="text-[1.4rem] font-bold text-[#111827]">${costs.total_cost.toFixed(4)}</p>
        </div>
        <div className="rounded-[18px] border border-[#E8EDF3] bg-white p-4">
          <div className="flex items-center gap-2 mb-1">
            <Cpu className="h-4 w-4 text-[#3B82F6]" />
            <span className="text-[0.71rem] font-semibold text-[#9CA3AF]">Total Tokens</span>
          </div>
          <p className="text-[1.4rem] font-bold text-[#111827]">{(summary.total_tokens as number ?? 0).toLocaleString()}</p>
        </div>
        <div className="rounded-[18px] border border-[#E8EDF3] bg-white p-4">
          <div className="flex items-center gap-2 mb-1">
            <BarChart3 className="h-4 w-4 text-[#8B5CF6]" />
            <span className="text-[0.71rem] font-semibold text-[#9CA3AF]">LLM Calls</span>
          </div>
          <p className="text-[1.4rem] font-bold text-[#111827]">{String(summary.total_llm_calls ?? 0)}</p>
        </div>
        <div className="rounded-[18px] border border-[#E8EDF3] bg-white p-4">
          <div className="flex items-center gap-2 mb-1">
            <TrendingUp className="h-4 w-4 text-[#F59E0B]" />
            <span className="text-[0.71rem] font-semibold text-[#9CA3AF]">Avg Cost/Call</span>
          </div>
          <p className="text-[1.4rem] font-bold text-[#111827]">${(summary.avg_cost_per_call as number ?? 0).toFixed(6)}</p>
        </div>
      </div>

      {/* View tabs */}
      <div className="flex items-center gap-2 p-1 rounded-[12px] bg-[#F8FAFC] w-fit">
        {(["overview", "by-category", "by-day"] as const).map((v) => (
          <button key={v} onClick={() => setView(v)}
            className={`px-4 py-2 rounded-[8px] text-[0.75rem] font-semibold transition-colors ${
              view === v ? "bg-white text-[#111827] shadow-sm" : "text-[#6B7280] hover:text-[#111827]"
            }`}>
            {v === "overview" ? "All Entries" : v === "by-category" ? "By Category" : "By Day"}
          </button>
        ))}
      </div>

      {/* Cost entries */}
      {view === "overview" && (
        <div className="rounded-[18px] border border-[#E8EDF3] bg-white p-5 max-h-[500px] overflow-y-auto">
          <h3 className="text-[0.95rem] font-bold text-[#111827] mb-4">Cost Entries</h3>
          <div className="space-y-2">
            {costs.entries.map((entry, i) => (
              <div key={entry.cost_id ?? i} className="p-3 rounded-[12px] border border-[#E8EDF3] flex items-center gap-3">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-[0.75rem] font-semibold text-[#111827] capitalize">{entry.category}</span>
                    {entry.model && <span className="text-[0.66rem] text-[#9CA3AF]">{entry.provider}/{entry.model}</span>}
                  </div>
                  {entry.tokens != null && (
                    <p className="text-[0.66rem] text-[#6B7280]">{entry.tokens.toLocaleString()} tokens</p>
                  )}
                </div>
                <div className="text-right">
                  <p className="text-[0.8rem] font-bold text-[#111827]">${entry.cost.toFixed(6)}</p>
                  {entry.date && <p className="text-[0.6rem] text-[#9CA3AF]">{entry.date}</p>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* By category */}
      {view === "by-category" && (
        <div className="rounded-[18px] border border-[#E8EDF3] bg-white p-5">
          <h3 className="text-[0.95rem] font-bold text-[#111827] mb-4">Cost by Category</h3>
          <div className="space-y-3">
            {Object.entries(costs.by_category).map(([category, cost]) => {
              const pct = costs.total_cost > 0 ? (cost / costs.total_cost) * 100 : 0
              return (
                <div key={category} className="flex items-center gap-3">
                  <span className="text-[0.72rem] font-semibold text-[#6B7280] w-20 capitalize">{category}</span>
                  <div className="flex-1 h-4 rounded-full bg-[#E8EDF3] overflow-hidden">
                    <div className="h-full rounded-full bg-[#38B88A] transition-all" style={{ width: `${pct}%` }} />
                  </div>
                  <span className="text-[0.72rem] font-bold text-[#111827] w-20 text-right">${cost.toFixed(4)}</span>
                  <span className="text-[0.66rem] text-[#9CA3AF] w-12 text-right">{pct.toFixed(1)}%</span>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* By day */}
      {view === "by-day" && (
        <div className="rounded-[18px] border border-[#E8EDF3] bg-white p-5">
          <h3 className="text-[0.95rem] font-bold text-[#111827] mb-4">Daily Costs</h3>
          <div className="space-y-2">
            {Object.entries(costs.by_day).map(([day, cost]) => (
              <div key={day} className="flex items-center justify-between p-2 rounded-[8px] hover:bg-[#F8FAFC]">
                <span className="text-[0.72rem] text-[#6B7280]">{day}</span>
                <span className="text-[0.78rem] font-bold text-[#111827]">${(cost as number).toFixed(4)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}