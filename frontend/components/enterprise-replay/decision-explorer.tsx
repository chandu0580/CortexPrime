"use client"

import { useEnterpriseReplayStore } from "@/store/enterpriseReplayStore"
import { Badge } from "./shared"
import { Brain, MessageSquare, ShieldCheck, CheckCircle2, AlertTriangle } from "lucide-react"
import { useState } from "react"

export function DecisionExplorerPanel() {
  const decisions = useEnterpriseReplayStore((s) => s.decisions)
  const [selectedDecision, setSelectedDecision] = useState<number | null>(null)

  if (!decisions) return <div className="text-center py-12 text-[0.82rem] text-[#6B7280]">No decision data loaded</div>

  return (
    <div className="space-y-5">
      {/* Summary cards */}
      <div className="grid gap-4 sm:grid-cols-4">
        <div className="rounded-[18px] border border-[#E8EDF3] bg-white p-4">
          <div className="flex items-center gap-2 mb-2">
            <Brain className="h-4 w-4 text-[#38B88A]" />
            <span className="text-[0.71rem] font-semibold text-[#9CA3AF]">Total Decisions</span>
          </div>
          <p className="text-[1.4rem] font-bold text-[#111827]">{decisions.total_decisions}</p>
        </div>
        <div className="rounded-[18px] border border-[#E8EDF3] bg-white p-4">
          <div className="flex items-center gap-2 mb-2">
            <MessageSquare className="h-4 w-4 text-[#3B82F6]" />
            <span className="text-[0.71rem] font-semibold text-[#9CA3AF]">LLM Requests</span>
          </div>
          <p className="text-[1.4rem] font-bold text-[#111827]">{String(decisions.summary?.total_llm_requests ?? 0)}</p>
        </div>
        <div className="rounded-[18px] border border-[#E8EDF3] bg-white p-4">
          <div className="flex items-center gap-2 mb-2">
            <CheckCircle2 className="h-4 w-4 text-[#2F9F77]" />
            <span className="text-[0.71rem] font-semibold text-[#9CA3AF]">Avg Confidence</span>
          </div>
          <p className="text-[1.4rem] font-bold text-[#111827]">{((decisions.summary?.avg_confidence as number ?? 0) * 100).toFixed(0)}%</p>
        </div>
        <div className="rounded-[18px] border border-[#E8EDF3] bg-white p-4">
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle className="h-4 w-4 text-[#F59E0B]" />
            <span className="text-[0.71rem] font-semibold text-[#9CA3AF]">Total Tokens</span>
          </div>
          <p className="text-[1.4rem] font-bold text-[#111827]">{(decisions.summary?.total_tokens as number ?? 0).toLocaleString()}</p>
        </div>
      </div>

      {/* Decision chain */}
      <div className="rounded-[18px] border border-[#E8EDF3] bg-white p-5">
        <h3 className="text-[0.95rem] font-bold text-[#111827] mb-4">Reasoning Chain</h3>
        <div className="space-y-2 max-h-[500px] overflow-y-auto">
          {(decisions.chain ?? []).map((d, i) => (
            <button key={d.decision_id} onClick={() => setSelectedDecision(selectedDecision === i ? null : i)}
              className="w-full text-left p-3 rounded-[12px] border border-[#E8EDF3] hover:bg-[#F8FAFC] transition-colors">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-[0.7rem] font-bold text-[#9CA3AF] font-mono">#{i + 1}</span>
                <span className="text-[0.75rem] font-semibold text-[#111827]">{d.step}</span>
                <Badge tone={d.confidence_score && d.confidence_score >= 0.8 ? "completed" : "warning"} label={d.confidence_score ? `${(d.confidence_score * 100).toFixed(0)}%` : "—"} />
              </div>
              <p className="text-[0.72rem] text-[#6B7280]">{d.agent}: {d.reasoning?.slice(0, 120)}{(d.reasoning?.length ?? 0) > 120 ? "..." : ""}</p>

              {/* Expanded LLM details */}
              {selectedDecision === i && d.llm_requests.length > 0 && (
                <div className="mt-3 space-y-2 pl-4 border-l-2 border-[#E8EDF3]">
                  {d.llm_requests.map((llm) => (
                    <div key={llm.request_id} className="p-2 rounded-[8px] bg-[#F8FAFC]">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-[0.68rem] font-semibold text-[#3B82F6]">{llm.provider}/{llm.model}</span>
                        <span className="text-[0.62rem] text-[#9CA3AF] font-mono">{llm.total_tokens} tokens</span>
                        {llm.cost != null && <span className="text-[0.62rem] text-[#9CA3AF]">${llm.cost.toFixed(6)}</span>}
                      </div>
                      {llm.prompt && <p className="text-[0.68rem] text-[#6B7280] truncate">Prompt: {llm.prompt}</p>}
                      {llm.response && <p className="text-[0.68rem] text-[#6B7280] truncate">Response: {llm.response}</p>}
                    </div>
                  ))}
                </div>
              )}

              {/* Governance */}
              {d.governance_action && (
                <div className="mt-2 flex items-center gap-1.5">
                  <ShieldCheck className="h-3 w-3 text-[#38B88A]" />
                  <span className="text-[0.66rem] text-[#6B7280]">Governance: {d.governance_action}</span>
                </div>
              )}
              {d.validation_result && (
                <div className="mt-1 flex items-center gap-1.5">
                  <CheckCircle2 className="h-3 w-3 text-[#38B88A]" />
                  <span className="text-[0.66rem] text-[#6B7280]">Validation: {d.validation_result}</span>
                </div>
              )}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}