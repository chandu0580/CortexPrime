"use client"

import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  Monitor,
  Target,
  Repeat,
  Building2,
  ShieldCheck,
  BookOpen,
  Scale,
  ArrowLeft,
  ArrowRight,
  X,
  ExternalLink,
} from "lucide-react"
import Link from "next/link"

import { cn } from "@/utils/cn"

const STEPS = [
  {
    icon: Monitor,
    title: "Executive Platform",
    description:
      "Monitor and control all AI operations from a single command center. View real-time metrics, manage missions, and oversee agent activity across your entire CortexPrime deployment.",
    gradient: "from-[#38B88A]/20 to-[#38B88A]/5",
    mockContent: "Executive Dashboard mockup",
    learnMore: "/developer-portal/executive-platform",
  },
  {
    icon: Target,
    title: "Mission Control",
    description:
      "Define, execute, and monitor autonomous AI missions. CortexPrime orchestrates multiple agents to research, analyze, and generate insights from complex workflows.",
    gradient: "from-[#3B82F6]/20 to-[#3B82F6]/5",
    mockContent: "Mission Control interface mockup",
    learnMore: "/developer-portal/mission-control",
  },
  {
    icon: Repeat,
    title: "Replay Center",
    description:
      "Review every action taken during any mission. Play back executions step-by-step, analyze decisions made by each agent, and export replay data for compliance audits.",
    gradient: "from-[#8B5CF6]/20 to-[#8B5CF6]/5",
    mockContent: "Replay timeline mockup",
    learnMore: "/developer-portal/replay-center",
  },
  {
    icon: Building2,
    title: "Enterprise Operations",
    description:
      "Manage users, roles, connectors, secrets, and platform settings from a unified operations console. Maintain full control over your enterprise AI infrastructure.",
    gradient: "from-[#F59E0B]/20 to-[#F59E0B]/5",
    mockContent: "Operations dashboard mockup",
    learnMore: "/developer-portal/enterprise-operations",
  },
  {
    icon: ShieldCheck,
    title: "Certification",
    description:
      "Validate system health, security posture, and mission success rates with automated certification suites. Ensure your deployment meets enterprise readiness standards.",
    gradient: "from-[#10B981]/20 to-[#10B981]/5",
    mockContent: "Certification scorecard mockup",
    learnMore: "/developer-portal/certification",
  },
  {
    icon: BookOpen,
    title: "Developer Portal",
    description:
      "Access comprehensive SDK documentation, interactive API explorer, WebSocket examples, and code playground. Build custom integrations and extend platform capabilities.",
    gradient: "from-[#6366F1]/20 to-[#6366F1]/5",
    mockContent: "Developer Portal interface mockup",
    learnMore: "/developer-portal",
  },
  {
    icon: Scale,
    title: "Scale & Reliability",
    description:
      "Validate platform performance under load, plan capacity requirements, inject controlled failures, and monitor reliability metrics to ensure production-grade stability.",
    gradient: "from-[#EC4899]/20 to-[#EC4899]/5",
    mockContent: "Scale & Reliability dashboard mockup",
    learnMore: "/developer-portal/scale-reliability",
  },
]

const slideVariants = {
  enter: (direction: number) => ({
    x: direction > 0 ? 300 : -300,
    opacity: 0,
  }),
  center: {
    x: 0,
    opacity: 1,
  },
  exit: (direction: number) => ({
    x: direction > 0 ? -300 : 300,
    opacity: 0,
  }),
}

export function ProductTourPanel() {
  const [step, setStep] = useState(0)
  const [direction, setDirection] = useState(0)
  const [dismissed, setDismissed] = useState(false)

  if (dismissed) return null

  const current = STEPS[step]
  const Icon = current.icon
  const total = STEPS.length
  const progress = ((step + 1) / total) * 100

  const goNext = () => {
    if (step < total - 1) {
      setDirection(1)
      setStep((s) => s + 1)
    }
  }

  const goBack = () => {
    if (step > 0) {
      setDirection(-1)
      setStep((s) => s - 1)
    }
  }

  return (
    <div className="border border-[#E8EDF3] bg-white rounded-[18px] shadow-sm overflow-hidden">
      {/* Header / Progress */}
      <div className="px-6 pt-6 pb-4">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold text-[#111827]">Guided Product Tour</h2>
          <button
            onClick={() => setDismissed(true)}
            className="p-1.5 rounded-lg text-[#6B7280] hover:bg-[#F4F7FA] hover:text-[#111827] transition-colors duration-150"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-medium text-[#6B7280]">
            Step {step + 1} of {total}
          </span>
          <span className="text-xs font-medium text-[#38B88A]">{Math.round(progress)}% complete</span>
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

      {/* Step Content */}
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
            className="space-y-5"
          >
            {/* Icon */}
            <div className="flex justify-center">
              <div className="w-16 h-16 rounded-2xl bg-[#E8F5EE] flex items-center justify-center">
                <Icon className="w-8 h-8 text-[#38B88A]" />
              </div>
            </div>

            {/* Title & Description */}
            <div className="text-center max-w-lg mx-auto">
              <h3 className="text-xl font-bold text-[#111827] mb-2">{current.title}</h3>
              <p className="text-sm text-[#6B7280] leading-relaxed">{current.description}</p>
            </div>

            {/* Screenshot Placeholder */}
            <div
              className={cn(
                "relative rounded-[18px] border border-[#E8EDF3] overflow-hidden h-48 bg-gradient-to-br flex items-center justify-center",
                current.gradient,
              )}
            >
              <div className="text-center">
                <div className="w-24 h-16 mx-auto rounded-lg bg-white/60 border border-white/80 flex items-center justify-center mb-2 shadow-sm">
                  <Icon className="w-8 h-8 text-[#38B88A]/40" />
                </div>
                <span className="text-xs font-medium text-[#6B7280]/60">{current.mockContent}</span>
              </div>
            </div>

            {/* Learn More */}
            <div className="text-center">
              <Link
                href={current.learnMore}
                className="inline-flex items-center gap-1.5 text-sm font-medium text-[#38B88A] hover:text-[#2F9F77] transition-colors duration-150"
              >
                <ExternalLink className="w-3.5 h-3.5" />
                Learn More in Developer Portal
              </Link>
            </div>
          </motion.div>
        </AnimatePresence>
      </div>

      {/* Navigation */}
      <div className="flex items-center justify-between px-6 py-4 border-t border-[#E8EDF3] bg-[#F4F7FA]">
        <div className="flex items-center gap-2">
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
        <div className="flex items-center gap-2">
          <button
            onClick={() => setDismissed(true)}
            className="px-4 py-2 rounded-[18px] text-sm font-medium text-[#6B7280] hover:bg-white hover:text-[#111827] border border-[#E8EDF3] transition-colors duration-150"
          >
            Skip Tour
          </button>
          {step < total - 1 ? (
            <button
              onClick={goNext}
              className="flex items-center gap-1.5 px-4 py-2 rounded-[18px] text-sm font-medium bg-[#38B88A] text-white hover:bg-[#2F9F77] transition-colors duration-150"
            >
              Next
              <ArrowRight className="w-4 h-4" />
            </button>
          ) : (
            <button
              onClick={() => setDismissed(true)}
              className="px-4 py-2 rounded-[18px] text-sm font-medium bg-[#38B88A] text-white hover:bg-[#2F9F77] transition-colors duration-150"
            >
              Complete Tour
            </button>
          )}
        </div>
      </div>
    </div>
  )
}