"use client"

import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  Beaker, CheckCircle, AlertCircle, Loader2, TrendingUp,
  TrendingDown, Minus, AlertTriangle, ArrowRight, FlaskConical,
} from "lucide-react"
import { useSimulationStore, type SimulationType } from "@/store/simulationStore"
import { useMissionStore } from "@/store/missionStore"
import { cn } from "@/utils/cn"
import { dur, ease } from "@/lib/motion-tokens"

const SIMULATION_TYPES: { id: SimulationType; label: string }[] = [
  { id: "execution", label: "Execution" },
  { id: "path", label: "Path" },
  { id: "failure", label: "Failure" },
  { id: "approval", label: "Approval" },
  { id: "rollback", label: "Rollback" },
]

function MetricCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-[8px] border border-[#E8EDF3] bg-[#FAFCFB] px-3 py-2 text-center">
      <p className="text-[0.65rem] text-[#6B7280] font-medium">{label}</p>
      <p className="text-[0.85rem] font-extrabold text-[#111827]">{value}</p>
    </div>
  )
}

function OutcomeBadge({ outcome }: { outcome: string }) {
  const color =
    outcome === "success" ? "text-emerald-600 bg-emerald-50 border-emerald-200" :
    outcome === "failure" ? "text-red-600 bg-red-50 border-red-200" :
    "text-amber-600 bg-amber-50 border-amber-200"
  return (
    <span className={cn("rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider", color)}>
      {outcome}
    </span>
  )
}

export function SimulationPanel() {
  const [selectedType, setSelectedType] = useState<SimulationType>("execution")
  const goal = useMissionStore((s) => s.goal)
  const { simulations, activeSimulationId, isSimulating, error, startSimulation, completeSimulation, addScenario } =
    useSimulationStore()
  const activeSimulation = simulations.find((s) => s.id === activeSimulationId)

  const handleRunSimulation = () => {
    if (!goal) return
    startSimulation(`mission_${Date.now()}`, selectedType)
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Beaker size={16} className="text-[#38B88A]" />
          <h3 className="text-[0.9rem] font-bold text-[#111827]">Simulation Engine</h3>
          {isSimulating && (
            <span className="flex items-center gap-1 text-[10px] text-[#38B88A] font-semibold">
              <Loader2 size={10} className="animate-spin" />
              Simulating...
            </span>
          )}
        </div>
        {goal && !isSimulating && (
          <button
            onClick={handleRunSimulation}
            className="flex items-center gap-1.5 rounded-[8px] bg-[#38B88A] px-3 py-1.5 text-[11px] font-bold text-white hover:bg-[#2F9F77] transition-colors"
          >
            <FlaskConical size={12} />
            Run Simulation
          </button>
        )}
      </div>

      {!goal && (
        <div className="rounded-[12px] border border-dashed border-[#D1D9E6] bg-white py-8 text-center">
          <div className="mx-auto mb-2 flex h-10 w-10 items-center justify-center rounded-[10px] bg-[#F8FAFC]">
            <Beaker size={18} className="text-[#D1D5DB]" />
          </div>
          <p className="text-[0.84rem] font-medium text-[#9CA3AF]">No mission active</p>
          <p className="mt-1 text-[0.74rem] text-[#B0B7C3]">Start a mission to run simulations</p>
        </div>
      )}

      {/* Simulation type selector */}
      {goal && (
        <div className="flex flex-wrap gap-1.5">
          {SIMULATION_TYPES.map((type) => (
            <button
              key={type.id}
              onClick={() => setSelectedType(type.id)}
              className={cn(
                "rounded-[8px] px-3 py-1.5 text-[0.72rem] font-semibold transition-all border",
                selectedType === type.id
                  ? "bg-[#ECFBF4] text-[#2F9F77] border-[#38B88A]"
                  : "bg-white text-[#6B7280] border-[#E8EDF3] hover:bg-gray-50"
              )}
            >
              {type.label}
            </button>
          ))}
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

      {activeSimulation && (
        <AnimatePresence mode="wait">
          <motion.div
            key={activeSimulation.id}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: dur.base, ease: ease.out }}
            className="space-y-3"
          >
            {/* Scenarios */}
            {activeSimulation.scenarios.length === 0 && isSimulating && (
              <div className="rounded-[10px] border border-[#E8EDF3] bg-[#FAFCFB] px-4 py-6 text-center">
                <Loader2 size={16} className="mx-auto mb-2 animate-spin text-[#38B88A]" />
                <p className="text-[0.78rem] text-[#6B7280]">Generating simulation scenarios...</p>
              </div>
            )}

            {activeSimulation.scenarios.map((scenario, i) => (
              <motion.div
                key={scenario.id}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.08 }}
                className="rounded-[10px] border border-[#E8EDF3] bg-white p-4"
              >
                <div className="mb-3 flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className="text-[0.82rem] font-bold text-[#111827]">{scenario.name}</span>
                      <OutcomeBadge outcome={scenario.predictedOutcome} />
                    </div>
                    <p className="text-[0.72rem] text-[#6B7280]">{scenario.description}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-[0.65rem] text-[#6B7280]">Confidence</p>
                    <p className="text-[0.85rem] font-extrabold text-[#111827] font-mono">
                      {(scenario.confidence * 100).toFixed(0)}%
                    </p>
                  </div>
                </div>

                {/* Metrics */}
                <div className="mb-3 grid grid-cols-3 gap-2">
                  {scenario.metrics.map((m, j) => (
                    <MetricCard key={j} label={m.label} value={m.value} />
                  ))}
                </div>

                {/* Risks */}
                {scenario.risks.length > 0 && (
                  <div className="mb-3 space-y-1">
                    <p className="text-[0.7rem] font-bold text-[#374151]">Identified Risks</p>
                    {scenario.risks.map((risk, j) => (
                      <div key={j} className="flex items-center gap-2 rounded-[6px] bg-[#FFF7ED] px-3 py-1.5">
                        <AlertTriangle size={10} className="text-amber-500 shrink-0" />
                        <span className="text-[0.7rem] text-[#6B7280] flex-1">{risk.description}</span>
                        <span className={cn(
                          "text-[10px] font-bold uppercase",
                          risk.severity === "high" ? "text-red-500" :
                          risk.severity === "medium" ? "text-amber-500" : "text-yellow-600"
                        )}>{risk.severity}</span>
                      </div>
                    ))}
                  </div>
                )}

                {scenario.recommendation && (
                  <div className="flex items-start gap-2 rounded-[8px] bg-[#ECFBF4] px-3 py-2">
                    <ArrowRight size={12} className="mt-0.5 shrink-0 text-[#38B88A]" />
                    <p className="text-[0.72rem] text-[#6B7280]">{scenario.recommendation}</p>
                  </div>
                )}
              </motion.div>
            ))}
          </motion.div>
        </AnimatePresence>
      )}
    </div>
  )
}
