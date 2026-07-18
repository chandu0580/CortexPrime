"use client"

import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  BookOpen, CheckCircle, AlertCircle, XCircle,
  Search, Loader2,
  ChevronDown, ChevronRight, Clock,
} from "lucide-react"
import { useDecisionMemoryStore, type DecisionRecord } from "@/store/decisionMemoryStore"
import { cn } from "@/utils/cn"

function OutcomeBadge({ outcome }: { outcome: string }) {
  const color =
    outcome === "success" ? "text-emerald-600 bg-emerald-50 border-emerald-200" :
    outcome === "failure" ? "text-red-600 bg-red-50 border-red-200" :
    outcome === "partial" ? "text-amber-600 bg-amber-50 border-amber-200" :
    "text-gray-600 bg-gray-50 border-gray-200"
  return (
    <span className={cn("rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider", color)}>
      {outcome}
    </span>
  )
}

function DecisionCard({ decision, expanded, onToggle }: { decision: DecisionRecord; expanded: boolean; onToggle: () => void }) {
  return (
    <motion.div
      className={cn(
        "rounded-[10px] border transition-all cursor-pointer",
        expanded ? "border-[#38B88A] shadow-sm" : "border-[#E8EDF3] hover:border-gray-300"
      )}
    >
      <div className="flex items-start gap-3 px-4 py-3" onClick={onToggle}>
        <div className={cn(
          "flex h-7 w-7 shrink-0 items-center justify-center rounded-[6px]",
          decision.outcome === "success" ? "bg-[#ECFBF4] text-[#38B88A]" :
          decision.outcome === "failure" ? "bg-red-50 text-red-500" :
          decision.outcome === "partial" ? "bg-amber-50 text-amber-500" :
          "bg-gray-50 text-gray-400"
        )}>
          {decision.outcome === "success" ? <CheckCircle size={12} /> :
           decision.outcome === "failure" ? <XCircle size={12} /> :
           decision.outcome === "partial" ? <AlertCircle size={12} /> :
           <Loader2 size={12} />}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-[0.78rem] font-semibold text-[#374151] truncate">{decision.decision}</span>
            <OutcomeBadge outcome={decision.outcome} />
          </div>
          <p className="mt-0.5 text-[0.7rem] text-[#6B7280] line-clamp-1">{decision.rationale}</p>
          <div className="mt-1 flex items-center gap-3 text-[10px] text-[#9CA3AF]">
            <span className="flex items-center gap-1">
              <Clock size={9} />
              {new Date(decision.timestamp).toLocaleDateString()}
            </span>
            <span>Confidence: {(decision.confidence * 100).toFixed(0)}%</span>
            <span>Risk: {decision.riskLevel}</span>
          </div>
        </div>
        <div className="shrink-0 text-[#9CA3AF]">
          {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </div>
      </div>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="border-t border-[#E8EDF3] px-4 py-3 space-y-3">
              {/* Rationale */}
              <div>
                <p className="text-[0.7rem] font-bold text-[#374151] mb-1">Rationale</p>
                <p className="text-[0.72rem] text-[#6B7280] leading-relaxed">{decision.rationale}</p>
              </div>

              {/* Alternatives */}
              {decision.alternatives.length > 0 && (
                <div>
                  <p className="text-[0.7rem] font-bold text-[#374151] mb-1">Alternatives Considered</p>
                  <div className="space-y-1.5">
                    {decision.alternatives.map((alt, i) => (
                      <div key={i} className="rounded-[8px] border border-[#E8EDF3] bg-[#FAFCFB] p-2.5">
                        <p className="text-[0.72rem] font-semibold text-[#374151] mb-1">{alt.description}</p>
                        <div className="flex gap-3">
                          <div className="flex-1">
                            <p className="text-[10px] text-[#38B88A] font-semibold mb-0.5">Pros</p>
                            {alt.pros.map((pro, j) => (
                              <p key={j} className="text-[0.68rem] text-[#6B7280]">+ {pro}</p>
                            ))}
                          </div>
                          <div className="flex-1">
                            <p className="text-[10px] text-red-500 font-semibold mb-0.5">Cons</p>
                            {alt.cons.map((con, j) => (
                              <p key={j} className="text-[0.68rem] text-[#6B7280]">- {con}</p>
                            ))}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Metrics */}
              {decision.metrics && Object.keys(decision.metrics).length > 0 && (
                <div>
                  <p className="text-[0.7rem] font-bold text-[#374151] mb-1">Decision Metrics</p>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(decision.metrics).map(([k, v]) => (
                      <span key={k} className="rounded-[4px] border border-[#E8EDF3] bg-white px-2 py-1 text-[10px] text-[#6B7280]">
                        {k}: <strong>{v}</strong>
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

export function DecisionMemoryPanel() {
  const { decisions, isLoading, error, filter, setFilter, clearFilter } = useDecisionMemoryStore()
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const filtered = decisions.filter((d) => {
    if (filter.outcome && d.outcome !== filter.outcome) return false
    if (filter.riskLevel && d.riskLevel !== filter.riskLevel) return false
    if (filter.search) {
      const q = filter.search.toLowerCase()
      if (!d.decision.toLowerCase().includes(q) && !d.rationale.toLowerCase().includes(q)) return false
    }
    return true
  })

  return (
    <div className="flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <BookOpen size={16} className="text-[#38B88A]" />
          <h3 className="text-[0.9rem] font-bold text-[#111827]">Decision Memory</h3>
          <span className="rounded-full bg-[#ECFBF4] px-2 py-0.5 text-[10px] font-bold text-[#38B88A]">
            {decisions.length}
          </span>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-2">
        <div className="relative flex-1">
          <Search size={12} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#9CA3AF]" />
          <input
            type="text"
            placeholder="Search decisions..."
            value={filter.search || ""}
            onChange={(e) => setFilter({ search: e.target.value })}
            className="w-full rounded-[8px] border border-[#E8EDF3] bg-white py-2 pl-8 pr-3 text-[0.72rem] text-[#374151] placeholder:text-[#9CA3AF] outline-none focus:border-[#38B88A]"
          />
        </div>
        <select
          value={filter.outcome || ""}
          onChange={(e) => setFilter({ outcome: e.target.value || undefined })}
          className="rounded-[8px] border border-[#E8EDF3] bg-white px-2.5 py-2 text-[0.7rem] text-[#374151] outline-none focus:border-[#38B88A]"
        >
          <option value="">All outcomes</option>
          <option value="success">Success</option>
          <option value="failure">Failure</option>
          <option value="partial">Partial</option>
          <option value="pending">Pending</option>
        </select>
        <select
          value={filter.riskLevel || ""}
          onChange={(e) => setFilter({ riskLevel: e.target.value || undefined })}
          className="rounded-[8px] border border-[#E8EDF3] bg-white px-2.5 py-2 text-[0.7rem] text-[#374151] outline-none focus:border-[#38B88A]"
        >
          <option value="">All risks</option>
          <option value="low">Low</option>
          <option value="medium">Medium</option>
          <option value="high">High</option>
          <option value="critical">Critical</option>
        </select>
        {(filter.outcome || filter.riskLevel || filter.search) && (
          <button
            onClick={clearFilter}
            className="rounded-[8px] border border-[#E8EDF3] px-2.5 py-2 text-[0.7rem] text-[#6B7280] hover:bg-gray-50"
          >
            Clear
          </button>
        )}
      </div>

      {error && (
        <div className="rounded-[10px] border border-red-200 bg-red-50 px-4 py-3">
          <p className="text-[0.78rem] text-red-700">{error}</p>
        </div>
      )}

      {isLoading && (
        <div className="flex items-center justify-center py-8">
          <Loader2 size={16} className="animate-spin text-[#38B88A]" />
        </div>
      )}

      {/* Decision list */}
      <div className="space-y-2">
        {filtered.length === 0 && !isLoading && (
          <div className="rounded-[12px] border border-dashed border-[#D1D9E6] bg-white py-8 text-center">
            <div className="mx-auto mb-2 flex h-10 w-10 items-center justify-center rounded-[10px] bg-[#F8FAFC]">
              <BookOpen size={18} className="text-[#D1D5DB]" />
            </div>
            <p className="text-[0.84rem] font-medium text-[#9CA3AF]">
              {decisions.length === 0 ? "No decisions recorded" : "No matching decisions"}
            </p>
            <p className="mt-1 text-[0.74rem] text-[#B0B7C3]">
              {decisions.length === 0
                ? "Executive decisions will appear here as missions are executed"
                : "Try adjusting your filters"}
            </p>
          </div>
        )}
        {filtered.map((decision) => (
          <DecisionCard
            key={decision.id}
            decision={decision}
            expanded={expandedId === decision.id}
            onToggle={() => setExpandedId(expandedId === decision.id ? null : decision.id)}
          />
        ))}
      </div>
    </div>
  )
}
