"use client"

import { motion, AnimatePresence } from "framer-motion"
import {
  Activity, RotateCcw, CheckCircle, AlertCircle, Loader2,
  XCircle, RefreshCw, Shield, ArrowRight,
} from "lucide-react"
import { useAdaptiveExecutionStore } from "@/store/adaptiveExecutionStore"
import { useMissionStore } from "@/store/missionStore"
import { cn } from "@/utils/cn"
import { dur, ease } from "@/lib/motion-tokens"

function HealthBar({ score }: { score: number }) {
  const color =
    score >= 80 ? "bg-[#38B88A]" :
    score >= 50 ? "bg-amber-500" :
    "bg-red-500"
  return (
    <div className="flex items-center gap-2">
      <div className="h-2 w-20 rounded-full bg-gray-100 overflow-hidden">
        <div
          className={cn("h-full rounded-full transition-all duration-500", color)}
          style={{ width: `${score}%` }}
        />
      </div>
      <span className={cn(
        "text-[11px] font-bold font-mono",
        score >= 80 ? "text-[#38B88A]" :
        score >= 50 ? "text-amber-500" : "text-red-500"
      )}>
        {score}%
      </span>
    </div>
  )
}

export function AdaptiveExecutionPanel() {
  const goal = useMissionStore((s) => s.goal)
  const stage = useMissionStore((s) => s.stage)
  const {
    activeRecoveries, completedRecoveries, failedRecoveries,
    adaptiveMode, healthScore, isHealing,
    setAdaptiveMode, addRecovery,
  } = useAdaptiveExecutionStore()

  const totalRecoveries = completedRecoveries.length + failedRecoveries.length
  const successRate = totalRecoveries > 0
    ? Math.round((completedRecoveries.length / totalRecoveries) * 100)
    : 100

  return (
    <div className="flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity size={16} className="text-[#38B88A]" />
          <h3 className="text-[0.9rem] font-bold text-[#111827]">Adaptive Execution</h3>
          {isHealing && (
            <span className="flex items-center gap-1 text-[10px] text-amber-500 font-semibold">
              <Loader2 size={10} className="animate-spin" />
              Recovering...
            </span>
          )}
        </div>
        {goal && (
          <div className="flex items-center gap-2">
            <label className="flex items-center gap-1.5 cursor-pointer">
              <span className="text-[0.7rem] text-[#6B7280] font-medium">Auto-heal</span>
              <button
                onClick={() => setAdaptiveMode(!adaptiveMode)}
                className={cn(
                  "relative h-4 w-8 rounded-full transition-colors",
                  adaptiveMode ? "bg-[#38B88A]" : "bg-gray-200"
                )}
              >
                <span className={cn(
                  "absolute left-0.5 top-0.5 h-3 w-3 rounded-full bg-white transition-transform shadow-sm",
                  adaptiveMode && "translate-x-4"
                )} />
              </button>
            </label>
          </div>
        )}
      </div>

      {!goal && (
        <div className="rounded-[12px] border border-dashed border-[#D1D9E6] bg-white py-8 text-center">
          <div className="mx-auto mb-2 flex h-10 w-10 items-center justify-center rounded-[10px] bg-[#F8FAFC]">
            <Activity size={18} className="text-[#D1D5DB]" />
          </div>
          <p className="text-[0.84rem] font-medium text-[#9CA3AF]">No active mission</p>
          <p className="mt-1 text-[0.74rem] text-[#B0B7C3]">Start a mission to view adaptive execution</p>
        </div>
      )}

      {goal && (
        <>
          {/* Status cards */}
          <div className="grid grid-cols-4 gap-3">
            <div className="rounded-[10px] border border-[#E8EDF3] bg-white p-3 text-center">
              <p className="text-[0.65rem] text-[#6B7280] font-medium">Health</p>
              <HealthBar score={healthScore} />
            </div>
            <div className="rounded-[10px] border border-[#E8EDF3] bg-white p-3 text-center">
              <p className="text-[0.65rem] text-[#6B7280] font-medium">Active</p>
              <p className="text-[1rem] font-extrabold text-[#111827] mt-1">{activeRecoveries.length}</p>
            </div>
            <div className="rounded-[10px] border border-[#E8EDF3] bg-white p-3 text-center">
              <p className="text-[0.65rem] text-[#6B7280] font-medium">Recovered</p>
              <p className="text-[1rem] font-extrabold text-[#38B88A] mt-1">{completedRecoveries.length}</p>
            </div>
            <div className="rounded-[10px] border border-[#E8EDF3] bg-white p-3 text-center">
              <p className="text-[0.65rem] text-[#6B7280] font-medium">Success Rate</p>
              <p className={cn(
                "text-[1rem] font-extrabold mt-1",
                successRate >= 80 ? "text-[#38B88A]" : "text-amber-500"
              )}>{successRate}%</p>
            </div>
          </div>

          {/* Active recoveries */}
          {activeRecoveries.length > 0 && (
            <div>
              <p className="mb-2 text-[0.78rem] font-bold text-[#111827]">Active Recoveries</p>
              <div className="space-y-1.5">
                {activeRecoveries.map((rec) => (
                  <motion.div
                    key={rec.id}
                    initial={{ opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    className="flex items-start gap-3 rounded-[10px] border border-amber-200 bg-amber-50 px-4 py-3"
                  >
                    <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-[6px] bg-amber-500 text-white">
                      <RefreshCw size={12} className="animate-spin" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-[0.78rem] font-semibold text-amber-800">
                          {rec.failureType}
                        </span>
                        <span className="text-[10px] text-amber-600 font-mono">
                          Attempt {rec.attemptCount}/{rec.maxAttempts}
                        </span>
                      </div>
                      <p className="mt-0.5 text-[0.72rem] text-amber-700">{rec.failureMessage}</p>
                      <p className="text-[0.7rem] text-amber-600 mt-0.5">
                        Strategy: {rec.strategy}
                      </p>
                    </div>
                  </motion.div>
                ))}
              </div>
            </div>
          )}

          {/* Completed recoveries */}
          {completedRecoveries.length > 0 && (
            <div>
              <p className="mb-2 text-[0.78rem] font-bold text-[#111827]">Recovery History</p>
              <div className="space-y-1">
                {completedRecoveries.slice(-5).reverse().map((rec) => (
                  <div
                    key={rec.id}
                    className="flex items-center gap-3 rounded-[8px] border border-[#D1FAE5] bg-[#ECFBF4] px-3 py-2"
                  >
                    <CheckCircle size={12} className="text-[#38B88A] shrink-0" />
                    <span className="text-[0.72rem] text-[#374151] flex-1">{rec.failureType}</span>
                    <span className="text-[10px] text-[#6B7280]">{rec.strategy}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Failed recoveries */}
          {failedRecoveries.length > 0 && (
            <div>
              <p className="mb-2 text-[0.78rem] font-bold text-[#111827] text-red-700">Failed Recoveries</p>
              <div className="space-y-1">
                {failedRecoveries.slice(-3).reverse().map((rec) => (
                  <div
                    key={rec.id}
                    className="flex items-center gap-3 rounded-[8px] border border-red-200 bg-red-50 px-3 py-2"
                  >
                    <XCircle size={12} className="text-red-500 shrink-0" />
                    <span className="text-[0.72rem] text-[#374151] flex-1">{rec.failureType}</span>
                    <span className="text-[10px] text-red-500 font-medium">{rec.failureMessage.slice(0, 30)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeRecoveries.length === 0 && completedRecoveries.length === 0 && failedRecoveries.length === 0 && (
            <div className="rounded-[10px] border border-[#E8EDF3] bg-[#FAFCFB] px-4 py-5 text-center">
              <Shield size={16} className="mx-auto mb-1.5 text-[#38B88A]" />
              <p className="text-[0.78rem] text-[#6B7280]">No recovery events</p>
              <p className="text-[0.7rem] text-[#9CA3AF] mt-0.5">All systems operating normally</p>
            </div>
          )}

          {/* Stage information */}
          <div className="rounded-[8px] border border-[#E8EDF3] bg-[#FAFCFB] px-3 py-2">
            <div className="flex items-center gap-2">
              <ArrowRight size={12} className="text-[#38B88A]" />
              <span className="text-[0.7rem] text-[#6B7280]">
                Current stage: <strong className="text-[#374151]">{stage}</strong>
              </span>
              {adaptiveMode && (
                <span className="ml-auto text-[10px] text-[#38B88A] font-semibold">
                  Auto-heal enabled
                </span>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
