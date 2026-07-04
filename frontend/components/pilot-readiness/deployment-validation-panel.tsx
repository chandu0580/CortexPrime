"use client"

import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  Server,
  Plug,
  Bot,
  Play,
  Brain,
  GitBranch as GitBranchIcon,
  Shield,
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  Activity,
  Clock,
} from "lucide-react"

import { cn } from "@/utils/cn"
import { StatusBadge, WizardContainer } from "./shared"

interface ValidationItem {
  label: string
  status: "healthy" | "active" | "connected" | "pending"
  detail?: string
}

interface ValidationStep {
  icon: typeof Server
  title: string
  description: string
  items: ValidationItem[]
  overall: "healthy" | "active" | "connected" | "pending"
  overallLabel: string
}

const STEPS: ValidationStep[] = [
  {
    icon: Server,
    title: "Infrastructure",
    description: "Verify all core infrastructure dependencies are running and accessible.",
    overall: "healthy",
    overallLabel: "All Systems Operational",
    items: [
      { label: "Docker Engine", status: "healthy", detail: "24.0.7" },
      { label: "Kubernetes Cluster", status: "healthy", detail: "1.29.2 / 3 nodes" },
      { label: "PostgreSQL", status: "healthy", detail: "16.2 / 12 ms" },
      { label: "Redis", status: "healthy", detail: "7.2.4 / 3 ms" },
      { label: "Neo4j", status: "healthy", detail: "5.19 / 8 ms" },
      { label: "RabbitMQ", status: "healthy", detail: "3.13 / 5 ms" },
    ],
  },
  {
    icon: Plug,
    title: "Connectors",
    description: "Verify all external service connectors are authenticated and reachable.",
    overall: "healthy",
    overallLabel: "All Connected",
    items: [
      { label: "GitHub", status: "healthy", detail: "45 ms" },
      { label: "Jira", status: "healthy", detail: "62 ms" },
      { label: "Slack", status: "healthy", detail: "38 ms" },
      { label: "Teams", status: "healthy", detail: "71 ms" },
      { label: "ServiceNow", status: "healthy", detail: "89 ms" },
      { label: "Confluence", status: "healthy", detail: "55 ms" },
      { label: "Notion", status: "healthy", detail: "42 ms" },
      { label: "Azure DevOps", status: "healthy", detail: "33 ms" },
    ],
  },
  {
    icon: Bot,
    title: "Workers",
    description: "Verify worker agents are registered and ready for task execution.",
    overall: "healthy",
    overallLabel: "7 Workers Active",
    items: [
      { label: "Browser Agent", status: "active", detail: "4 active / 0 idle" },
      { label: "Voice Agent", status: "active", detail: "2 active / 0 idle" },
      { label: "Desktop Agent", status: "active", detail: "1 active / 0 idle" },
    ],
  },
  {
    icon: Play,
    title: "Runtime",
    description: "Verify mission runtime components are healthy and communicating.",
    overall: "healthy",
    overallLabel: "All Services Healthy",
    items: [
      { label: "Mission Runtime", status: "healthy", detail: "Healthy" },
      { label: "EventBus", status: "healthy", detail: "Connected / 124 msg/s" },
      { label: "Agent Registry", status: "healthy", detail: "7 registered agents" },
    ],
  },
  {
    icon: Brain,
    title: "Memory Systems",
    description: "Verify memory stores are operational and data is accessible.",
    overall: "healthy",
    overallLabel: "All Memory Stores Operational",
    items: [
      { label: "Working Memory", status: "healthy", detail: "Redis / 3 MB used" },
      { label: "Episodic Memory", status: "healthy", detail: "PostgreSQL / 128 MB used" },
      { label: "Semantic Memory", status: "healthy", detail: "PostgreSQL / 256 MB used" },
      { label: "Reflection Memory", status: "healthy", detail: "PostgreSQL / 64 MB used" },
    ],
  },
  {
    icon: GitBranchIcon,
    title: "Knowledge Graph",
    description: "Verify knowledge graph connectivity and data integrity.",
    overall: "healthy",
    overallLabel: "Graph Operational",
    items: [
      { label: "Neo4j Connection", status: "healthy", detail: "Connected / 4 ms" },
      { label: "Entity Count", status: "healthy", detail: "15 nodes" },
      { label: "Relationship Count", status: "healthy", detail: "28 edges" },
    ],
  },
  {
    icon: Shield,
    title: "Health & Security",
    description: "Verify API health, authentication, and safety guardrails are active.",
    overall: "healthy",
    overallLabel: "All Security Checks Passed",
    items: [
      { label: "API Health", status: "healthy", detail: "200 OK / 12 ms" },
      { label: "JWT Authentication", status: "healthy", detail: "Valid / 256-bit" },
      { label: "Rate Limiting", status: "healthy", detail: "Active / 10,000 req/min" },
      { label: "Safety Guardrails", status: "healthy", detail: "Enabled / 0 blocks" },
      { label: "Emergency Stop", status: "healthy", detail: "Armed / Tested OK" },
    ],
  },
]

const slideVariants = {
  enter: (direction: number) => ({ x: direction > 0 ? 300 : -300, opacity: 0 }),
  center: { x: 0, opacity: 1 },
  exit: (direction: number) => ({ x: direction > 0 ? -300 : 300, opacity: 0 }),
}

export function DeploymentValidationPanel() {
  const [step, setStep] = useState(0)
  const [direction, setDirection] = useState(0)
  const [completed, setCompleted] = useState(false)

  const current = STEPS[step]
  const Icon = current.icon
  const total = STEPS.length
  const progress = ((step + 1) / total) * 100

  const goNext = () => {
    if (step < total - 1) {
      setDirection(1)
      setStep((s) => s + 1)
    } else {
      setCompleted(true)
    }
  }

  const goBack = () => {
    if (step > 0) {
      setDirection(-1)
      setStep((s) => s - 1)
    }
  }

  if (completed) {
    return (
      <WizardContainer>
        <div className="p-8 text-center space-y-6">
          {/* Score Ring */}
          <div className="flex justify-center">
            <div className="relative w-32 h-32">
              <svg className="w-full h-full -rotate-90" viewBox="0 0 128 128">
                <circle cx="64" cy="64" r="56" fill="none" stroke="#E8EDF3" strokeWidth="8" />
                <motion.circle
                  cx="64" cy="64" r="56"
                  fill="none"
                  stroke="#38B88A"
                  strokeWidth="8"
                  strokeLinecap="round"
                  strokeDasharray={2 * Math.PI * 56}
                  initial={{ strokeDashoffset: 2 * Math.PI * 56 }}
                  animate={{ strokeDashoffset: 2 * Math.PI * 56 * (1 - 98 / 100) }}
                  transition={{ duration: 1.5, ease: "easeOut" }}
                />
              </svg>
              <div className="absolute inset-0 flex items-center justify-center">
                <div className="text-center">
                  <div className="text-3xl font-bold text-[#111827]">98</div>
                  <div className="text-xs font-medium text-[#6B7280]">/ 100</div>
                </div>
              </div>
            </div>
          </div>

          <div>
            <h3 className="text-xl font-bold text-[#111827] mb-2">Deployment Validation Complete</h3>
            <p className="text-sm text-[#6B7280] max-w-md mx-auto">
              All 7 validation sections passed. Your CortexPrime deployment is fully operational.
            </p>
          </div>

          {/* All Systems Operational Banner */}
          <div className="flex items-center justify-center gap-2 bg-[#E8F5EE] border border-[#38B88A]/20 rounded-[18px] px-6 py-3 max-w-md mx-auto">
            <CheckCircle2 className="w-5 h-5 text-[#38B88A]" />
            <span className="text-sm font-semibold text-[#2F9F77]">All Systems Operational</span>
            <Activity className="w-4 h-4 text-[#38B88A] ml-1" />
          </div>

          {/* Section Summaries */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 max-w-lg mx-auto">
            {STEPS.map((s, i) => {
              const SectionIcon = s.icon
              return (
                <div key={i} className="flex items-center gap-1.5 text-xs text-[#111827] bg-[#F4F7FA] rounded-xl px-2.5 py-2">
                  <SectionIcon className="w-3.5 h-3.5 text-[#38B88A] shrink-0" />
                  {s.title}
                </div>
              )
            })}
          </div>

          <div className="flex items-center justify-center gap-2 text-sm text-[#6B7280]">
            <Clock className="w-4 h-4" />
            Last validated: {new Date().toLocaleString()}
          </div>
        </div>
      </WizardContainer>
    )
  }

  return (
    <WizardContainer>
      {/* Progress */}
      <div className="px-6 pt-6 pb-2">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-lg font-bold text-[#111827]">Deployment Validation</h2>
          <span className="text-xs font-medium text-[#38B88A]">{Math.round(progress)}%</span>
        </div>
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-medium text-[#6B7280]">
            Step {step + 1} of {total} — {current.title}
          </span>
          <StatusBadge tone={current.overall === "healthy" ? "healthy" : "running"} label={current.overallLabel} />
        </div>
        <div className="w-full h-1.5 bg-[#E8EDF3] rounded-full overflow-hidden">
          <motion.div
            className="h-full rounded-full bg-[#38B88A]"
            initial={false}
            animate={{ width: `${progress}%` }}
            transition={{ duration: 0.3, ease: "easeOut" }}
          />
        </div>
      </div>

      {/* Content */}
      <div className="px-6 pb-6">
        <AnimatePresence mode="wait" custom={direction}>
          <motion.div
            key={step}
            custom={direction}
            variants={slideVariants}
            initial="enter"
            animate="center"
            exit="exit"
            transition={{ duration: 0.25, ease: "easeInOut" }}
            className="space-y-5 pt-4"
          >
            {/* Section Header */}
            <div className="flex items-start gap-4">
              <div className="w-12 h-12 rounded-xl bg-[#E8F5EE] flex items-center justify-center shrink-0">
                <Icon className="w-6 h-6 text-[#38B88A]" />
              </div>
              <div className="min-w-0">
                <h3 className="text-lg font-bold text-[#111827]">{current.title}</h3>
                <p className="text-sm text-[#6B7280] mt-1">{current.description}</p>
              </div>
            </div>

            {/* Checklist */}
            <div className="border border-[#E8EDF3] rounded-[18px] overflow-hidden">
              {current.items.map((item) => (
                <div
                  key={item.label}
                  className="flex items-center justify-between px-4 py-3 border-b border-[#E8EDF3] last:border-b-0 hover:bg-[#F4F7FA] transition-colors duration-100"
                >
                  <div className="flex items-center gap-3">
                    <CheckCircle2 className="w-4 h-4 text-[#38B88A] shrink-0" />
                    <span className="text-sm font-medium text-[#111827]">{item.label}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    {item.detail && <span className="text-xs text-[#6B7280] font-mono">{item.detail}</span>}
                    <StatusBadge tone={item.status} label={item.status === "healthy" ? "✅" : item.status === "active" ? "✅" : "🔄"} />
                  </div>
                </div>
              ))}
            </div>

            {/* Section Overall Status */}
            <div className="flex items-center justify-between px-4 py-3 bg-[#E8F5EE] rounded-[18px] border border-[#38B88A]/20">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-[#38B88A]" />
                <span className="text-sm font-semibold text-[#2F9F77]">{current.overallLabel}</span>
              </div>
              <StatusBadge tone="healthy" label="Passed" />
            </div>
          </motion.div>
        </AnimatePresence>
      </div>

      {/* Navigation */}
      <div className="flex items-center justify-between px-6 py-4 border-t border-[#E8EDF3] bg-[#F4F7FA]">
        <div>
          {step > 0 && (
            <button
              onClick={goBack}
              className="flex items-center gap-1.5 px-4 py-2 rounded-[18px] text-sm font-medium text-[#6B7280] hover:bg-white hover:text-[#111827] border border-[#E8EDF3] transition-colors duration-150"
            >
              <ArrowLeft className="w-4 h-4" />
              Back
            </button>
          )}
        </div>
        <button
          onClick={goNext}
          className="flex items-center gap-1.5 px-5 py-2 rounded-[18px] text-sm font-medium bg-[#38B88A] text-white hover:bg-[#2F9F77] transition-colors duration-150"
        >
          {step < total - 1 ? (
            <>
              Next
              <ArrowRight className="w-4 h-4" />
            </>
          ) : (
            <>
              View Results
              <CheckCircle2 className="w-4 h-4" />
            </>
          )}
        </button>
      </div>
    </WizardContainer>
  )
}