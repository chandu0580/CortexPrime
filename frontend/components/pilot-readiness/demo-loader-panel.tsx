"use client"

import { useCallback, useMemo, useRef, useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Rocket, Check, Download, RotateCcw, X, Loader2 } from "lucide-react"
import { cn } from "@/utils/cn"
import {
  DEMO_ORGANIZATION,
  DEMO_DEPARTMENTS,
  DEMO_USERS,
  DEMO_PROJECTS,
  DEMO_REPOSITORIES,
  DEMO_JIRA_ISSUES,
  DEMO_MISSIONS,
  DEMO_KNOWLEDGE_GRAPH,
  DEMO_MEMORY_RECORDS,
  DEMO_APPROVALS,
  DEMO_CONNECTOR_ACTIVITY,
  DEMO_AUDIT_LOGS,
  DEMO_DASHBOARD_METRICS,
} from "./demo-data"

type Phase = "idle" | "loading" | "loaded"

interface DatasetStatus {
  key: string
  label: string
  count: number
}

const datasets: DatasetStatus[] = [
  { key: "org", label: "Organization", count: 1 },
  { key: "depts", label: "Departments", count: DEMO_DEPARTMENTS.length },
  { key: "users", label: "Users", count: DEMO_USERS.length },
  { key: "projects", label: "Projects", count: DEMO_PROJECTS.length },
  { key: "repos", label: "Repos", count: DEMO_REPOSITORIES.length },
  { key: "jira", label: "Jira Issues", count: DEMO_JIRA_ISSUES.length },
  { key: "missions", label: "Missions", count: DEMO_MISSIONS.length },
  { key: "approvals", label: "Approvals", count: DEMO_APPROVALS.length },
  { key: "kg", label: "KG Entities", count: DEMO_KNOWLEDGE_GRAPH.length },
  { key: "memories", label: "Memory Records", count: DEMO_MEMORY_RECORDS.length },
  { key: "connectors", label: "Connector Activity", count: DEMO_CONNECTOR_ACTIVITY.length },
  { key: "audit", label: "Audit Logs", count: DEMO_AUDIT_LOGS.length },
]

const CONFETTI_COLORS = ["#38B88A", "#2F9F77", "#B7E5D3", "#F59E0B", "#3B82F6", "#EF4444", "#8B5CF6"]

interface ConfettiParticle {
  id: number
  x: number
  y: number
  rotation: number
  color: string
  scale: number
}

export default function DemoLoaderPanel() {
  const [phase, setPhase] = useState<Phase>("idle")
  const [progress, setProgress] = useState(0)
  const [loadedKeys, setLoadedKeys] = useState<Set<string>>(new Set())
  const [confetti, setConfetti] = useState<ConfettiParticle[]>([])
  const [dataCopy, setDataCopy] = useState<Record<string, unknown> | null>(null)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const allLoaded = loadedKeys.size === datasets.length

  const fireConfetti = useCallback(() => {
    const particles: ConfettiParticle[] = Array.from({ length: 60 }, (_, i) => ({
      id: i,
      x: Math.random() * 100,
      y: -10 - Math.random() * 20,
      rotation: Math.random() * 720 - 360,
      color: CONFETTI_COLORS[Math.floor(Math.random() * CONFETTI_COLORS.length)],
      scale: 0.4 + Math.random() * 0.8,
    }))
    setConfetti(particles)
    setTimeout(() => setConfetti([]), 2500)
  }, [])

  const load = useCallback(() => {
    setPhase("loading")
    setProgress(0)
    setLoadedKeys(new Set())
    setDataCopy(null)
    setConfetti([])

    const perStep = 100 / datasets.length
    let idx = 0

    const tick = () => {
      if (idx >= datasets.length) {
        setPhase("loaded")
        setProgress(100)
        setLoadedKeys(new Set(datasets.map((d) => d.key)))
        fireConfetti()
        return
      }
      setLoadedKeys((prev) => new Set(prev).add(datasets[idx].key))
      setProgress(Math.min(100, Math.round((idx + 1) * perStep)))
      idx++
      timerRef.current = setTimeout(tick, Math.round(1000 / datasets.length))
    }

    timerRef.current = setTimeout(tick, 100)
  }, [fireConfetti])

  const reset = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current)
    setPhase("idle")
    setProgress(0)
    setLoadedKeys(new Set())
    setDataCopy(null)
    setConfetti([])
  }, [])

  const exportData = useCallback(() => {
    const payload = {
      exportedAt: new Date().toISOString(),
      organization: DEMO_ORGANIZATION,
      departments: DEMO_DEPARTMENTS,
      users: DEMO_USERS,
      projects: DEMO_PROJECTS,
      repositories: DEMO_REPOSITORIES,
      jiraIssues: DEMO_JIRA_ISSUES,
      missions: DEMO_MISSIONS,
      knowledgeGraph: DEMO_KNOWLEDGE_GRAPH,
      memoryRecords: DEMO_MEMORY_RECORDS,
      approvals: DEMO_APPROVALS,
      connectorActivity: DEMO_CONNECTOR_ACTIVITY,
      auditLogs: DEMO_AUDIT_LOGS,
      dashboardMetrics: DEMO_DASHBOARD_METRICS,
    }
    setDataCopy(payload)

    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = "acmecorp-demo-dataset.json"
    a.click()
    URL.revokeObjectURL(url)
  }, [])

  return (
    <div className="mx-auto max-w-2xl space-y-8 py-12">
      {/* Header */}
      <div className="text-center">
        <h1 className="text-2xl font-bold tracking-tight text-[#111827]">
          Pilot Customer Readiness
        </h1>
        <p className="mt-1.5 text-sm text-[#6B7280]">
          One-click enterprise demo for AcmeCorp Inc.
        </p>
      </div>

      {/* Load Button */}
      <AnimatePresence mode="wait">
        {phase === "idle" && (
          <motion.button
            key="load-btn"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -12 }}
            whileHover={{ y: -3, scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            onClick={load}
            className={cn(
              "mx-auto flex items-center justify-center gap-3 rounded-[20px] px-10 py-5 text-lg font-bold",
              "border border-[#38B88A] bg-[#38B88A] text-white",
              "shadow-[0_16px_40px_rgba(56,184,138,0.3)]",
              "hover:border-[#2F9F77] hover:bg-[#2F9F77]",
              "transition-colors duration-200",
            )}
          >
            <Rocket className="h-6 w-6" />
            Load Demo Enterprise
          </motion.button>
        )}
      </AnimatePresence>

      {/* Progress */}
      {phase === "loading" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between gap-3 text-sm text-[#6B7280]">
            <span className="flex items-center gap-2 font-medium text-[#111827]">
              <Loader2 className="h-4 w-4 animate-spin text-[#38B88A]" />
              Loading demo data...
            </span>
            <span className="font-semibold text-[#38B88A]">{progress}%</span>
          </div>
          <div className="h-2.5 w-full overflow-hidden rounded-full bg-[#E8EDF3]">
            <motion.div
              className="h-full rounded-full bg-[#38B88A]"
              initial={{ width: 0 }}
              animate={{ width: `${progress}%` }}
              transition={{ duration: 0.35, ease: "easeOut" }}
            />
          </div>
        </div>
      )}

      {/* Status Grid */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {datasets.map((ds) => {
          const loaded = loadedKeys.has(ds.key)
          return (
            <motion.div
              key={ds.key}
              layout
              className={cn(
                "flex items-center gap-3 rounded-[18px] border px-4 py-3.5 transition-colors duration-200",
                loaded
                  ? "border-[#D6F0E5] bg-[#E8F5EE]/50"
                  : "border-[#E8EDF3] bg-white",
              )}
            >
              <div
                className={cn(
                  "flex h-8 w-8 shrink-0 items-center justify-center rounded-full transition-all duration-300",
                  loaded
                    ? "bg-[#38B88A] text-white"
                    : "bg-[#F4F7FA] text-[#9CA3AF]",
                )}
              >
                {loaded ? (
                  <motion.div
                    initial={{ scale: 0, rotate: -90 }}
                    animate={{ scale: 1, rotate: 0 }}
                    transition={{ type: "spring" as const, stiffness: 300, damping: 20 }}
                  >
                    <Check className="h-4 w-4" />
                  </motion.div>
                ) : (
                  <span className="text-xs font-bold">{ds.count}</span>
                )}
              </div>
              <div className="min-w-0">
                <p
                  className={cn(
                    "truncate text-sm font-medium transition-colors duration-200",
                    loaded ? "text-[#2F9F77]" : "text-[#6B7280]",
                  )}
                >
                  {ds.label}
                </p>
                <p
                  className={cn(
                    "text-xs transition-colors duration-200",
                    loaded ? "text-[#38B88A]/70" : "text-[#9CA3AF]",
                  )}
                >
                  {loaded ? `${ds.count} loaded` : `${ds.count} items`}
                </p>
              </div>
            </motion.div>
          )
        })}
      </div>

      {/* Success Banner */}
      <AnimatePresence>
        {phase === "loaded" && (
          <motion.div
            initial={{ opacity: 0, y: 16, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -16, scale: 0.95 }}
            className="rounded-[24px] border border-[#D6F0E5] bg-gradient-to-b from-[#E8F5EE] to-white p-6 text-center shadow-[0_8px_32px_rgba(56,184,138,0.12)]"
          >
            <motion.div
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ type: "spring" as const, stiffness: 200, damping: 15, delay: 0.1 }}
              className="mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-full bg-[#38B88A]"
            >
              <Check className="h-7 w-7 text-white" />
            </motion.div>
            <h3 className="text-lg font-bold text-[#111827]">Demo Data Loaded</h3>
            <p className="mt-1 text-sm text-[#6B7280]">
              AcmeCorp enterprise dataset is ready for exploration — 97 records across 12 datasets.
            </p>
            <div className="mt-5 flex items-center justify-center gap-3">
              <button
                onClick={reset}
                className="inline-flex items-center gap-2 rounded-[14px] border border-[#EF4444]/30 px-5 py-2.5 text-sm font-semibold text-[#EF4444] transition-colors hover:border-[#EF4444]/60 hover:bg-red-50"
              >
                <RotateCcw className="h-4 w-4" />
                Reset Demo Data
              </button>
              <button
                onClick={exportData}
                className="inline-flex items-center gap-2 rounded-[14px] border border-[#E8EDF3] bg-white px-5 py-2.5 text-sm font-semibold text-[#111827] shadow-sm transition-colors hover:border-[#D1D5DB] hover:bg-[#F9FAFB]"
              >
                <Download className="h-4 w-4" />
                Export Demo Dataset
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Confetti Particles */}
      <AnimatePresence>
        {confetti.length > 0 && (
          <div className="pointer-events-none fixed inset-0 z-50 overflow-hidden">
            {confetti.map((p) => (
              <motion.div
                key={p.id}
                initial={{
                  x: `${p.x}vw`,
                  y: `${p.y}vh`,
                  rotate: 0,
                  opacity: 1,
                }}
                animate={{
                  y: "110vh",
                  rotate: p.rotation,
                  opacity: [1, 1, 0],
                }}
                exit={{ opacity: 0 }}
                transition={{
                  duration: 2.2,
                  ease: [0.25, 0.46, 0.45, 0.94],
                  delay: Math.random() * 0.3,
                }}
                className="absolute h-3 w-2 rounded-sm"
                style={{ backgroundColor: p.color, scale: p.scale }}
              />
            ))}
          </div>
        )}
      </AnimatePresence>

      {/* Empty state */}
      {phase === "idle" && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="rounded-[24px] border border-dashed border-[#E8EDF3] bg-white/50 p-10 text-center"
        >
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-[#F4F7FA]">
            <Rocket className="h-7 w-7 text-[#9CA3AF]" />
          </div>
          <h3 className="text-base font-semibold text-[#111827]">No Demo Data Loaded</h3>
          <p className="mt-1 text-sm text-[#6B7280]">
            Click the button above to inject the full AcmeCorp enterprise demo dataset.
          </p>
        </motion.div>
      )}
    </div>
  )
}