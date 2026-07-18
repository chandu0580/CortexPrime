"use client"

import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Play, Pause, RotateCcw, BarChart3, TrendingUp, TrendingDown, AlertTriangle, CheckCircle2, Loader2 } from "lucide-react"
import { cn } from "@/utils/cn"
import { stagger, variants } from "@/lib/motion-tokens"

interface SimulationScenario {
  id: string
  name: string
  description: string
  predictedOutcome: "success" | "failure" | "degraded"
  confidence: number
  metrics: Record<string, number>
  risks: string[]
  recommendation: string
}

interface Simulation {
  id: string
  missionId: string
  type: string
  scenarios: SimulationScenario[]
  status: "pending" | "running" | "completed" | "failed"
}

const simulationTemplates = [
  { id: "execution", label: "Execution Path", description: "Simulate optimal mission execution paths" },
  { id: "failure", label: "Failure Mode", description: "Identify potential failure points and cascading impacts" },
  { id: "resource", label: "Resource Loading", description: "Simulate resource allocation and bottlenecks" },
  { id: "approval", label: "Approval Flow", description: "Test governance approval chains and timing" },
  { id: "rollback", label: "Rollback Plan", description: "Validate rollback procedures and data integrity" },
]

const mockSimulations: Simulation[] = [
  {
    id: "sim-1",
    missionId: "m-1",
    type: "execution",
    status: "completed",
    scenarios: [
      {
        id: "s-1",
        name: "Optimal Path",
        description: "Standard execution with all agents available",
        predictedOutcome: "success",
        confidence: 0.94,
        metrics: { duration_min: 18, tokens: 45000, cost: 0.32 },
        risks: ["Memory retrieval latency may spike under load"],
        recommendation: "Proceed with standard allocation",
      },
      {
        id: "s-2",
        name: "Degraded Mode",
        description: "Research agent unavailable, fallback to cached data",
        predictedOutcome: "degraded",
        confidence: 0.78,
        metrics: { duration_min: 32, tokens: 62000, cost: 0.48 },
        risks: ["Reduced accuracy without live research", "Slower response time"],
        recommendation: "Queue research agent or preload cache",
      },
    ],
  },
]

const outcomeConfig = {
  success: { icon: CheckCircle2, color: "text-[var(--success)]", bg: "bg-[var(--success-muted)]" },
  degraded: { icon: AlertTriangle, color: "text-[var(--warning)]", bg: "bg-[var(--warning-muted)]" },
  failure: { icon: TrendingDown, color: "text-[var(--danger)]", bg: "bg-[var(--danger-muted)]" },
}

export default function SimulationPanel() {
  const [simulations, setSimulations] = useState<Simulation[]>(mockSimulations)
  const [activeSim, setActiveSim] = useState<string | null>(null)
  const [running, setRunning] = useState(false)

  function handleRunSimulation(typeId: string) {
    setRunning(true)
    const newSim: Simulation = {
      id: `sim-${Date.now()}`,
      missionId: "m-current",
      type: typeId,
      status: "running",
      scenarios: [],
    }
    setSimulations((prev) => [newSim, ...prev])
    setTimeout(() => {
      setSimulations((prev) =>
        prev.map((s) =>
          s.id === newSim.id
            ? {
                ...s,
                status: "completed" as const,
                scenarios: [
                  {
                    id: `s-${Date.now()}`,
                    name: "Simulated Result",
                    description: "Auto-generated simulation result",
                    predictedOutcome: "success" as const,
                    confidence: 0.88,
                    metrics: { duration_min: 22, tokens: 51000, cost: 0.38 },
                    risks: ["Standard operational risks apply"],
                    recommendation: "Proceed with monitoring",
                  },
                ],
              }
            : s
        )
      )
      setRunning(false)
    }, 2500)
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
        {simulationTemplates.map((template) => (
          <motion.button
            key={template.id}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.97 }}
            onClick={() => handleRunSimulation(template.id)}
            disabled={running}
            aria-label={`Run ${template.label} simulation`}
            className={cn(
              "rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-3 text-left transition-all hover:shadow-sm hover:border-[var(--success)]/30",
              running && "opacity-50 cursor-not-allowed"
            )}
          >
            <p className="text-[0.7rem] font-bold text-[var(--text-primary)]">{template.label}</p>
            <p className="mt-0.5 text-[0.6rem] text-[var(--text-muted)] leading-tight">{template.description}</p>
          </motion.button>
        ))}
      </div>

      <AnimatePresence>
        {simulations.length === 0 && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex flex-col items-center py-8 text-center">
            <BarChart3 className="h-10 w-10 text-[var(--text-muted)] mb-3" />
            <p className="text-[0.85rem] font-semibold text-[var(--text-secondary)]">No simulations yet</p>
            <p className="text-[0.7rem] text-[var(--text-muted)]">Run a simulation to see results</p>
          </motion.div>
        )}

        <div aria-live="polite" aria-atomic="false" className="space-y-3">
          {simulations.map((sim) => (
            <motion.div
              key={sim.id}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, height: 0 }}
              className={cn(
                "rounded-[12px] border p-4",
                sim.status === "running" ? "border-[var(--success)] bg-[var(--success-muted)]" : "border-[var(--border)] bg-[var(--surface)]"
              )}
            >
              <div className="flex items-center justify-between mb-3">
                <div>
                  <span className="text-[0.7rem] font-semibold text-[var(--text-secondary)] uppercase tracking-wider">
                    {simulationTemplates.find((t) => t.id === sim.type)?.label ?? sim.type}
                  </span>
                  <span className={cn(
                    "ml-2 inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[0.6rem] font-semibold",
                    sim.status === "running" ? "bg-[var(--success)] text-white" :
                    sim.status === "completed" ? "bg-[var(--success-muted)] text-[var(--success)]" :
                    "bg-[var(--danger-muted)] text-[var(--danger)]"
                  )}>
                    {sim.status === "running" && <Loader2 className="h-3 w-3 animate-spin" />}
                    {sim.status}
                  </span>
                </div>
                <button
                  onClick={() => setSimulations((prev) => prev.filter((s) => s.id !== sim.id))}
                  aria-label={`Dismiss ${simulationTemplates.find((t) => t.id === sim.type)?.label ?? sim.type} simulation`}
                  className="text-[0.65rem] font-semibold text-[var(--text-muted)] hover:text-[var(--danger)]"
                >
                  Dismiss
                </button>
              </div>

              {sim.status === "running" && (
                <div className="flex items-center gap-2 text-[0.75rem] text-[var(--success)]">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Simulating...
                </div>
              )}

              {sim.status === "completed" && sim.scenarios.length > 0 && (
                <div className="space-y-3">
                  {sim.scenarios.map((sc) => {
                    const cfg = outcomeConfig[sc.predictedOutcome]
                    const Icon = cfg.icon
                    return (
                      <div key={sc.id} className="rounded-[10px] border border-[var(--border)] bg-[var(--surface-raised)] p-3">
                        <div className="flex items-start justify-between gap-3">
                          <div className="flex items-start gap-2.5">
                            <div className={cn("flex h-7 w-7 shrink-0 items-center justify-center rounded-[8px]", cfg.bg)}>
                              <Icon className={cn("h-4 w-4", cfg.color)} />
                            </div>
                            <div>
                              <p className="text-[0.8rem] font-bold text-[var(--text-primary)]">{sc.name}</p>
                              <p className="text-[0.68rem] text-[var(--text-secondary)]">{sc.description}</p>
                            </div>
                          </div>
                          <div className="shrink-0 text-right">
                            <div className={cn("text-[0.85rem] font-bold", cfg.color)}>
                              {(sc.confidence * 100).toFixed(0)}%
                            </div>
                            <span className="text-[0.6rem] text-[var(--text-muted)]">confidence</span>
                          </div>
                        </div>

                        <div className="mt-3 flex flex-wrap gap-3">
                          {Object.entries(sc.metrics).map(([k, v]) => (
                            <div key={k} className="rounded-[6px] bg-[var(--surface)] border border-[var(--border)] px-2.5 py-1">
                              <span className="text-[0.55rem] font-semibold uppercase text-[var(--text-muted)]">{k}</span>
                              <p className="text-[0.75rem] font-bold text-[var(--text-primary)]">
                                {k.includes("cost") ? "$" : ""}{typeof v === "number" ? v.toLocaleString() : v}
                              </p>
                            </div>
                          ))}
                        </div>

                        {sc.risks.length > 0 && (
                          <div className="mt-2.5 space-y-1">
                            {sc.risks.map((r, i) => (
                              <div key={i} className="flex items-start gap-1.5 text-[0.68rem] text-[var(--warning)]">
                                <AlertTriangle className="h-3 w-3 mt-0.5 shrink-0" />
                                <span>{r}</span>
                              </div>
                            ))}
                          </div>
                        )}

                        <div className="mt-2 rounded-[6px] bg-[var(--success-muted)] px-3 py-1.5 text-[0.68rem] font-medium text-[var(--success)]">
                          Recommendation: {sc.recommendation}
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </motion.div>
          ))}
        </div>
      </AnimatePresence>
    </div>
  )
}
