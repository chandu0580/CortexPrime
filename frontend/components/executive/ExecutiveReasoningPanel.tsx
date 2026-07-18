"use client"

import { motion, AnimatePresence } from "framer-motion"
import {
  Brain, CheckCircle, AlertCircle, Loader2, Lightbulb,
  Target, Shield, ArrowRight, GitBranch, FileText,
} from "lucide-react"
import { useExecutiveReasoningStore } from "@/store/executiveReasoningStore"
import { useMissionStore } from "@/store/missionStore"
import { cn } from "@/utils/cn"
import { dur, ease } from "@/lib/motion-tokens"

const STEP_ICONS: Record<string, React.ReactNode> = {
  goal_analysis: <Target size={14} />,
  context_evaluation: <FileText size={14} />,
  constraint_identification: <Shield size={14} />,
  dependency_mapping: <GitBranch size={14} />,
  assumption_check: <AlertCircle size={14} />,
  outcome_projection: <Lightbulb size={14} />,
  strategy_formulation: <Brain size={14} />,
  confidence_assessment: <Target size={14} />,
  risk_evaluation: <Shield size={14} />,
  recommendation: <ArrowRight size={14} />,
}

const STEP_LABELS: Record<string, string> = {
  goal_analysis: "Goal Analysis",
  context_evaluation: "Context Evaluation",
  constraint_identification: "Constraint Identification",
  dependency_mapping: "Dependency Mapping",
  assumption_check: "Assumption Check",
  outcome_projection: "Outcome Projection",
  strategy_formulation: "Strategy Formulation",
  confidence_assessment: "Confidence Assessment",
  risk_evaluation: "Risk Evaluation",
  recommendation: "Recommendation",
}

function RiskBadge({ level }: { level: string }) {
  const color =
    level === "low" ? "text-emerald-600 bg-emerald-50 border-emerald-200" :
    level === "medium" ? "text-amber-600 bg-amber-50 border-amber-200" :
    level === "high" ? "text-orange-600 bg-orange-50 border-orange-200" :
    "text-red-600 bg-red-50 border-red-200"
  return (
    <span className={cn("rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider", color)}>
      {level}
    </span>
  )
}

export function ExecutiveReasoningPanel() {
  const goal = useMissionStore((s) => s.goal)
  const sessions = useExecutiveReasoningStore((s) => s.sessions)
  const activeSessionId = useExecutiveReasoningStore((s) => s.activeSessionId)
  const isReasoning = useExecutiveReasoningStore((s) => s.isReasoning)
  const error = useExecutiveReasoningStore((s) => s.error)
  const startReasoning = useExecutiveReasoningStore((s) => s.startReasoning)
  const completeReasoning = useExecutiveReasoningStore((s) => s.completeReasoning)
  const activeSession = sessions.find((s) => s.id === activeSessionId)

  const handleStartReasoning = () => {
    if (!goal) return
    startReasoning(goal)
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Brain size={16} className="text-[#38B88A]" />
          <h3 className="text-[0.9rem] font-bold text-[#111827]">Executive Reasoning Engine</h3>
          {isReasoning && (
            <span className="flex items-center gap-1 text-[10px] text-[#38B88A] font-semibold">
              <Loader2 size={10} className="animate-spin" />
              Reasoning...
            </span>
          )}
        </div>
        {goal && !isReasoning && (
          <button
            onClick={handleStartReasoning}
            className="flex items-center gap-1.5 rounded-[8px] bg-[#38B88A] px-3 py-1.5 text-[11px] font-bold text-white hover:bg-[#2F9F77] transition-colors"
          >
            <Brain size={12} />
            Run Reasoning
          </button>
        )}
      </div>

      {!goal && (
        <div className="rounded-[12px] border border-dashed border-[#D1D9E6] bg-white py-8 text-center">
          <div className="mx-auto mb-2 flex h-10 w-10 items-center justify-center rounded-[10px] bg-[#F8FAFC]">
            <Brain size={18} className="text-[#D1D5DB]" />
          </div>
          <p className="text-[0.84rem] font-medium text-[#9CA3AF]">No mission active</p>
          <p className="mt-1 text-[0.74rem] text-[#B0B7C3]">Start a mission to begin reasoning</p>
        </div>
      )}

      {error && (
        <div className="rounded-[10px] border border-red-200 bg-red-50 px-4 py-3">
          <div className="flex items-center gap-2">
            <AlertCircle size={14} className="text-red-500 shrink-0" />
            <p className="text-[0.78rem] text-red-700">{error}</p>
          </div>
        </div>
      )}

      {activeSession && (
        <AnimatePresence mode="wait">
          <motion.div
            key={activeSession.id}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: dur.base, ease: ease.out }}
            className="space-y-4"
          >
            {/* Reasoning steps */}
            <div className="space-y-1.5">
              {activeSession.steps.length === 0 && isReasoning && (
                <div className="rounded-[10px] border border-[#E8EDF3] bg-[#FAFCFB] px-4 py-6 text-center">
                  <Loader2 size={16} className="mx-auto mb-2 animate-spin text-[#38B88A]" />
                  <p className="text-[0.78rem] text-[#6B7280]">Initializing reasoning pipeline...</p>
                </div>
              )}
              {activeSession.steps.map((step, i) => (
                <motion.div
                  key={step.id}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.05 }}
                  className={cn(
                    "flex items-start gap-3 rounded-[10px] border px-4 py-3 transition-all",
                    step.status === "completed"
                      ? "border-[#D1FAE5] bg-[#ECFBF4]"
                      : step.status === "in_progress"
                      ? "border-[#DBEAFE] bg-[#EFF6FF]"
                      : step.status === "failed"
                      ? "border-[#FECACA] bg-[#FEF2F2]"
                      : "border-[#E8EDF3] bg-white"
                  )}
                >
                  <div className={cn(
                    "flex h-7 w-7 shrink-0 items-center justify-center rounded-[6px]",
                    step.status === "completed" ? "bg-[#38B88A] text-white" :
                    step.status === "in_progress" ? "bg-blue-500 text-white" :
                    step.status === "failed" ? "bg-red-500 text-white" :
                    "bg-[#F0F4F8] text-[#9CA3AF]"
                  )}>
                    {step.status === "completed" ? <CheckCircle size={12} /> :
                     step.status === "in_progress" ? <Loader2 size={12} className="animate-spin" /> :
                     step.status === "failed" ? <AlertCircle size={12} /> :
                     STEP_ICONS[step.type] || <FileText size={12} />}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className={cn(
                        "text-[0.78rem] font-semibold",
                        step.status === "completed" ? "text-[#2F9F77]" :
                        step.status === "in_progress" ? "text-blue-700" :
                        step.status === "failed" ? "text-red-700" :
                        "text-[#374151]"
                      )}>
                        {STEP_LABELS[step.type] || step.title}
                      </span>
                      {step.confidence != null && (
                        <span className="text-[10px] text-[#9CA3AF] font-mono">
                          {(step.confidence * 100).toFixed(0)}%
                        </span>
                      )}
                    </div>
                    <p className="mt-0.5 text-[0.72rem] text-[#6B7280] leading-relaxed">
                      {step.description}
                    </p>
                    {step.details && Object.keys(step.details).length > 0 && (
                      <div className="mt-1.5 flex flex-wrap gap-1">
                        {Object.entries(step.details).map(([k, v]) => (
                          <span key={k} className="rounded-[4px] bg-white/60 px-1.5 py-0.5 text-[10px] text-[#6B7280] font-mono border border-[#E8EDF3]">
                            {k}: {String(v)}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </motion.div>
              ))}
            </div>

            {/* Summary */}
            {activeSession.status === "completed" && (
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className="rounded-[12px] border border-[#D1FAE5] bg-[#ECFBF4] p-5"
              >
                <div className="mb-4 flex items-center justify-between">
                  <h4 className="text-[0.82rem] font-bold text-[#111827]">Reasoning Summary</h4>
                  <RiskBadge level={activeSession.riskLevel} />
                </div>

                <div className="mb-3 grid grid-cols-3 gap-3">
                  <div className="rounded-[8px] bg-white px-3 py-2 text-center">
                    <p className="text-[0.65rem] text-[#6B7280] font-medium">Confidence</p>
                    <p className="text-[1rem] font-extrabold text-[#111827]">
                      {(activeSession.overallConfidence * 100).toFixed(0)}%
                    </p>
                  </div>
                  <div className="rounded-[8px] bg-white px-3 py-2 text-center">
                    <p className="text-[0.65rem] text-[#6B7280] font-medium">Strategies</p>
                    <p className="text-[1rem] font-extrabold text-[#111827]">
                      {activeSession.strategies.length}
                    </p>
                  </div>
                  <div className="rounded-[8px] bg-white px-3 py-2 text-center">
                    <p className="text-[0.65rem] text-[#6B7280] font-medium">Constraints</p>
                    <p className="text-[1rem] font-extrabold text-[#111827]">
                      {activeSession.constraints.length}
                    </p>
                  </div>
                </div>

                {activeSession.recommendation && (
                  <div className="rounded-[8px] bg-white px-4 py-3">
                    <div className="flex items-start gap-2">
                      <ArrowRight size={14} className="mt-0.5 shrink-0 text-[#38B88A]" />
                      <div>
                        <p className="text-[0.7rem] font-bold text-[#374151] mb-0.5">Recommendation</p>
                        <p className="text-[0.78rem] text-[#6B7280] leading-relaxed">
                          {activeSession.recommendation}
                        </p>
                      </div>
                    </div>
                  </div>
                )}

                {/* Strategies */}
                {activeSession.strategies.length > 0 && (
                  <div className="mt-3 space-y-1.5">
                    <p className="text-[0.7rem] font-bold text-[#374151]">Strategies Considered</p>
                    {activeSession.strategies.map((strat, i) => (
                      <div key={i} className="flex items-center justify-between rounded-[8px] bg-white px-3 py-2">
                        <div className="flex items-center gap-2">
                          <span className="text-[0.72rem] font-semibold text-[#374151]">{strat.name}</span>
                          <RiskBadge level={strat.risk} />
                        </div>
                        <span className="text-[0.7rem] text-[#6B7280] font-mono">
                          {(strat.confidence * 100).toFixed(0)}% confidence
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </motion.div>
            )}
          </motion.div>
        </AnimatePresence>
      )}
    </div>
  )
}
