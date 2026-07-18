"use client"

import { useEffect, useRef } from "react"
import { motion } from "framer-motion"
import { Brain, Eye, BookOpen, Beaker, Activity, LayoutDashboard } from "lucide-react"
import CortexShell from "@/components/layout/CortexShell"
import { ExecutiveReasoningPanel } from "@/components/executive/ExecutiveReasoningPanel"
import { SimulationPanel } from "@/components/executive/SimulationPanel"
import { AdaptiveExecutionPanel } from "@/components/executive/AdaptiveExecutionPanel"
import { ObservationEngine } from "@/components/executive/ObservationEngine"
import { DecisionMemoryPanel } from "@/components/executive/DecisionMemoryPanel"
import { useExecutiveDashboard } from "@/hooks/queries/dashboard"
import { useDashboardWebSocket } from "@/hooks/queries/dashboard"
import { useExecutiveStore } from "@/store/executiveStore"
import { useExecutiveReasoningStore } from "@/store/executiveReasoningStore"
import type { ReasoningStep } from "@/store/executiveReasoningStore"
import { useSimulationStore } from "@/store/simulationStore"
import type { SimulationResult } from "@/store/simulationStore"
import { useAdaptiveExecutionStore } from "@/store/adaptiveExecutionStore"
import { useObservationStore } from "@/store/observationStore"
import { useDecisionMemoryStore } from "@/store/decisionMemoryStore"

function Panel({
  title,
  icon,
  children,
  delay = 0,
}: {
  title: string
  icon?: React.ReactNode
  children: React.ReactNode
  delay?: number
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.35 }}
      className="rounded-[16px] border border-[#E8EDF3] bg-white shadow-sm"
    >
      <div className="flex items-center gap-2 border-b border-[#E8EDF3] px-5 py-3.5">
        {icon && <span className="text-[#38B88A]">{icon}</span>}
        <h3 className="text-[0.82rem] font-bold text-[#111827] tracking-tight">{title}</h3>
      </div>
      <div className="p-5">
        {children}
      </div>
    </motion.div>
  )
}

export default function ExecutiveDashboardPage() {
  const { data, isSuccess } = useExecutiveDashboard()
  const prevDataRef = useRef(data)

  useDashboardWebSocket()

  useEffect(() => {
    void useExecutiveStore.getState().refreshAll()
    const id = setInterval(() => {
      void useExecutiveStore.getState().refreshAll()
    }, 30000)
    return () => clearInterval(id)
  }, [])

  useEffect(() => {
    if (!isSuccess || !data) return
    if (data === prevDataRef.current) return
    prevDataRef.current = data

    const r = data.reasoning
    useExecutiveReasoningStore.setState({
      sessions: r.sessions.map((s) => ({
        id: s.id,
        missionId: s.missionId,
        goal: s.goal,
        context: s.context,
        constraints: s.constraints,
        dependencies: s.dependencies,
        assumptions: s.assumptions,
        expectedOutcome: s.expectedOutcome,
        strategies: s.strategies.map((st) => ({
          name: st.name,
          description: st.description,
          confidence: st.confidence,
          risk: st.risk as "low" | "medium" | "high",
        })),
        overallConfidence: s.overallConfidence,
        riskLevel: s.riskLevel as "low" | "medium" | "high" | "critical",
        recommendation: s.recommendation,
        steps: s.steps.map((st) => ({
          id: st.id,
          type: st.type as ReasoningStep["type"],
          title: st.title,
          description: st.description,
          status: st.status as "pending" | "in_progress" | "completed" | "failed",
          confidence: st.confidence,
        })),
        status: s.status as "idle" | "reasoning" | "completed" | "failed",
        startedAt: s.startedAt ?? undefined,
        completedAt: s.completedAt ?? undefined,
      })),
      activeSessionId: r.activeSessionId,
      isReasoning: r.isReasoning,
      error: r.error,
    })

    const sim = data.simulation
    useSimulationStore.setState({
      simulations: sim.simulations.map((s) => ({
        id: s.id,
        missionId: s.missionId,
        type: s.type as SimulationResult["type"],
        status: s.status as "pending" | "running" | "completed" | "failed",
        scenarios: s.scenarios.map((sc) => ({
          id: sc.id,
          name: sc.name,
          description: sc.description,
          predictedOutcome: sc.predictedOutcome as "success" | "failure" | "degraded",
          confidence: sc.confidence,
          metrics: sc.metrics,
          risks: sc.risks.map((r) => ({
            description: r.description,
            severity: r.severity as "low" | "medium" | "high",
          })),
          recommendation: sc.recommendation,
        })),
        startedAt: s.startedAt ?? undefined,
        completedAt: s.completedAt ?? undefined,
      })),
      activeSimulationId: sim.activeSimulationId,
      isSimulating: sim.isSimulating,
      error: sim.error,
    })

    const ae = data.adaptiveExecution
    useAdaptiveExecutionStore.setState({
      missionId: ae.missionId,
      activeRecoveries: ae.activeRecoveries.map((r) => ({
        id: r.id,
        missionId: r.missionId,
        stepId: r.stepId,
        failureType: r.failureType,
        failureMessage: r.failureMessage,
        attemptCount: r.attemptCount,
        maxAttempts: r.maxAttempts,
        strategy: r.strategy,
        status: r.status as "pending" | "recovering" | "recovered" | "failed",
        startedAt: r.startedAt ?? undefined,
      })),
      completedRecoveries: ae.completedRecoveries.map((r) => ({
        id: r.id,
        missionId: r.missionId,
        stepId: r.stepId,
        failureType: r.failureType,
        failureMessage: r.failureMessage,
        attemptCount: r.attemptCount,
        maxAttempts: r.maxAttempts,
        strategy: r.strategy,
        status: r.status as "pending" | "recovering" | "recovered" | "failed",
        startedAt: r.startedAt ?? undefined,
      })),
      failedRecoveries: ae.failedRecoveries.map((r) => ({
        id: r.id,
        missionId: r.missionId,
        stepId: r.stepId,
        failureType: r.failureType,
        failureMessage: r.failureMessage,
        attemptCount: r.attemptCount,
        maxAttempts: r.maxAttempts,
        strategy: r.strategy,
        status: r.status as "pending" | "recovering" | "recovered" | "failed",
        startedAt: r.startedAt ?? undefined,
      })),
      adaptiveMode: ae.adaptiveMode,
      healthScore: ae.healthScore,
      isHealing: ae.isHealing,
    })

    const obs = data.observation
    useObservationStore.setState({
      categories: obs.categories.map((c) => ({
        id: c.id,
        label: c.label,
        metrics: c.metrics.map((m) => ({
          label: m.label,
          value: m.value,
          status: m.status as "healthy" | "warning" | "critical",
          trend: m.trend as "up" | "down" | "stable",
          timestamp: m.timestamp,
        })),
        alerts: c.alerts.map((a) => ({
          id: a.id,
          severity: a.severity as "info" | "warning" | "critical",
          source: a.source,
          message: a.message,
          timestamp: a.timestamp,
          acknowledged: a.acknowledged,
        })),
      })),
      metrics: obs.metrics.map((m) => ({
        label: m.label,
        value: m.value,
        status: m.status as "healthy" | "warning" | "critical",
        trend: m.trend as "up" | "down" | "stable",
        timestamp: m.timestamp,
      })),
      alerts: obs.alerts.map((a) => ({
        id: a.id,
        severity: a.severity as "info" | "warning" | "critical",
        source: a.source,
        message: a.message,
        timestamp: a.timestamp,
        acknowledged: a.acknowledged,
      })),
      isObserving: obs.isObserving,
      lastUpdate: obs.lastUpdate,
    })

    const dm = data.decisionMemory
    useDecisionMemoryStore.setState({
      decisions: dm.decisions.map((d) => ({
        id: d.id,
        missionId: d.missionId,
        decision: d.decision,
        rationale: d.rationale,
        alternatives: d.alternatives,
        outcome: d.outcome as "success" | "failure" | "partial" | "pending",
        confidence: d.confidence,
        riskLevel: d.riskLevel,
        timestamp: d.timestamp,
        metrics: d.metrics,
      })),
      isLoading: dm.isLoading,
      error: dm.error,
    })
  }, [data, isSuccess])

  return (
    <CortexShell title="Executive Dashboard">
      <div className="mx-auto max-w-[1600px] space-y-6 p-6">
        {/* Page header */}
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-center justify-between"
        >
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-[10px] bg-[#ECFBF4]">
              <LayoutDashboard size={18} className="text-[#38B88A]" />
            </div>
            <div>
              <h1 className="text-[1.3rem] font-extrabold text-[#111827] tracking-tight">Executive Decision Dashboard</h1>
              <p className="text-[0.75rem] text-[#6B7280]">Autonomous decision engine — reasoning, simulation, adaptive execution &amp; observation</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="flex items-center gap-1.5 rounded-full bg-[#ECFBF4] px-3 py-1.5 text-[11px] font-semibold text-[#38B88A]">
              <span className="h-1.5 w-1.5 rounded-full bg-[#38B88A] animate-pulse" />
              Autonomous
            </span>
          </div>
        </motion.div>

        {/* Row 1: Reasoning + Simulation */}
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <Panel title="Executive Reasoning Engine" icon={<Brain size={16} />} delay={0.05}>
            <ExecutiveReasoningPanel />
          </Panel>
          <Panel title="Simulation Engine" icon={<Beaker size={16} />} delay={0.1}>
            <SimulationPanel />
          </Panel>
        </div>

        {/* Row 2: Adaptive Execution + Observation */}
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <Panel title="Adaptive Execution" icon={<Activity size={16} />} delay={0.15}>
            <AdaptiveExecutionPanel />
          </Panel>
          <Panel title="Observation Engine" icon={<Eye size={16} />} delay={0.2}>
            <ObservationEngine />
          </Panel>
        </div>

        {/* Row 3: Decision Memory (full width) */}
        <Panel title="Executive Decision Memory" icon={<BookOpen size={16} />} delay={0.25}>
          <DecisionMemoryPanel />
        </Panel>
      </div>
    </CortexShell>
  )
}
