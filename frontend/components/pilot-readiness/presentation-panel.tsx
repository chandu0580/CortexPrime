"use client"

import { useState, useCallback, useEffect, useRef, useMemo } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { cn } from "@/utils/cn"
import { ease, dur } from "@/lib/motion-tokens"
import {
  Monitor,
  MonitorOff,
  ChevronLeft,
  ChevronRight,
  Maximize2,
  Minimize2,
  Play,
  Pause,
  Download,
  LayoutGrid,
  Sparkles,
  Shield,
  Cpu,
  Eye,
  Code2,
  Settings,
  BarChart3,
  Lock,
  Puzzle,
  Database,
  Cloud,
  ThumbsUp,
  CheckCircle2,
  ArrowRight,
  SkipForward,
  SkipBack,
  Timer,
} from "lucide-react"

interface Slide {
  id: number
  title: string
  subtitle?: string
  icon: React.ReactNode
  content: React.ReactNode
}

const SLIDE_DURATION = 8

const slidesData: Slide[] = [
  {
    id: 1,
    title: "CortexPrime",
    subtitle: "Autonomous AI Operating System",
    icon: <Sparkles className="h-10 w-10 text-[#38B88A]" />,
    content: (
      <div className="flex flex-col items-center gap-6 text-center">
        <div className="flex items-center gap-4">
          <Sparkles className="h-16 w-16 text-[#38B88A]" />
          <div>
            <h2 className="text-5xl font-bold tracking-tight text-white">CortexPrime</h2>
            <p className="mt-2 text-2xl text-[#94A3B8]">Autonomous AI Operating System</p>
          </div>
        </div>
        <div className="mt-4 flex gap-8 text-sm text-[#64748B]">
          <span>Version 2.4.0</span>
          <span>|</span>
          <span>July 2026</span>
        </div>
        <p className="mt-4 max-w-2xl text-lg text-[#CBD5E1]">
          Enterprise-grade autonomous AI operations platform purpose-built for mission-critical
          workloads at scale.
        </p>
      </div>
    ),
  },
  {
    id: 2,
    title: "Platform Overview",
    subtitle: "Enterprise-Grade AI Operations",
    icon: <Cpu className="h-10 w-10 text-[#38B88A]" />,
    content: (
      <div className="grid grid-cols-2 gap-6">
        {[
          { label: "Missions Completed", value: "248", sub: "+12% vs last quarter" },
          { label: "System Uptime", value: "99.97%", sub: "SLA-compliant" },
          { label: "Active Workers", value: "12", sub: "Across 4 environments" },
          { label: "Enterprise Connectors", value: "8", sub: "All major platforms" },
        ].map((stat) => (
          <div
            key={stat.label}
            className="rounded-xl border border-[#1E293B] bg-[#0F172A] p-6 text-center"
          >
            <p className="text-4xl font-bold text-[#38B88A]">{stat.value}</p>
            <p className="mt-2 text-lg font-semibold text-white">{stat.label}</p>
            <p className="mt-1 text-sm text-[#64748B]">{stat.sub}</p>
          </div>
        ))}
      </div>
    ),
  },
  {
    id: 3,
    title: "Mission Control",
    subtitle: "Autonomous Multi-Agent Execution",
    icon: <Cpu className="h-10 w-10 text-[#38B88A]" />,
    content: (
      <div className="space-y-4">
        <p className="text-lg text-[#CBD5E1]">
          End-to-end autonomous mission pipeline orchestrating specialized AI agents across
          discovery, planning, execution, and verification.
        </p>
        <div className="grid grid-cols-2 gap-3">
          {[
            { step: "01", emoji: "🔍", label: "Discovery", desc: "Intent parsing & context gathering" },
            { step: "02", emoji: "🧠", label: "Planning", desc: "Multi-agent task decomposition" },
            { step: "03", emoji: "⚡", label: "Execution", desc: "Parallel agent orchestration" },
            { step: "04", emoji: "✅", label: "Verification", desc: "Automated quality assurance" },
          ].map((item) => (
            <div
              key={item.step}
              className="flex items-center gap-3 rounded-lg border border-[#1E293B] bg-[#0F172A] p-4"
            >
              <span className="text-2xl">{item.emoji}</span>
              <div>
                <p className="font-semibold text-white">
                  {item.step}. {item.label}
                </p>
                <p className="text-sm text-[#64748B]">{item.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    ),
  },
  {
    id: 4,
    title: "Enterprise Replay",
    subtitle: "Complete Execution Visibility",
    icon: <Eye className="h-10 w-10 text-[#38B88A]" />,
    content: (
      <div className="space-y-4">
        <p className="text-lg text-[#CBD5E1]">
          Full forensic visibility into every mission execution with frame-by-frame replay
          capability.
        </p>
        <ul className="space-y-3">
          {[
            "Step-by-step execution timeline with millisecond precision",
            "Agent decision logs with reasoning traces for every action",
            "Tool call inspection with input/output payload review",
            "Memory state snapshots at each checkpoint",
            "Side-by-side diff view across mission runs",
            "Export replay as JSON, PDF, or compliance report",
          ].map((item) => (
            <li key={item} className="flex items-start gap-3 text-[#CBD5E1]">
              <CheckCircle2 className="mt-0.5 h-5 w-5 flex-shrink-0 text-[#38B88A]" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </div>
    ),
  },
  {
    id: 5,
    title: "Developer Portal",
    subtitle: "Extensible SDK & API Platform",
    icon: <Code2 className="h-10 w-10 text-[#38B88A]" />,
    content: (
      <div className="space-y-4">
        <p className="text-lg text-[#CBD5E1]">
          Rich SDK ecosystem with interactive API documentation, playground environments, and
          CI/CD integration.
        </p>
        <div className="grid grid-cols-2 gap-3">
          {[
            { label: "REST API", desc: "Full CRUD operations" },
            { label: "WebSocket", desc: "Real-time event streams" },
            { label: "TypeScript SDK", desc: "Type-safe client" },
            { label: "Python SDK", desc: "Data science native" },
            { label: "CLI Tools", desc: "Pipeline automation" },
            { label: "Webhooks", desc: "Event-driven integration" },
          ].map((item) => (
            <div
              key={item.label}
              className="rounded-lg border border-[#1E293B] bg-[#0F172A] p-3"
            >
              <p className="font-semibold text-white">{item.label}</p>
              <p className="text-sm text-[#64748B]">{item.desc}</p>
            </div>
          ))}
        </div>
      </div>
    ),
  },
  {
    id: 6,
    title: "Operations Center",
    subtitle: "Unified Administrative Control",
    icon: <Settings className="h-10 w-10 text-[#38B88A]" />,
    content: (
      <div className="space-y-4">
        <p className="text-lg text-[#CBD5E1]">
          Centralized command center for managing users, workers, missions, and system health
          across the entire deployment.
        </p>
        <ul className="space-y-3">
          {[
            "Real-time system health dashboard with live metrics",
            "User & role management with granular permission controls",
            "Worker fleet management — deploy, scale, monitor",
            "Mission queue oversight with priority-based scheduling",
            "Audit logging with searchable event history",
            "Alerting & notification engine with PagerDuty/Slack integration",
          ].map((item) => (
            <li key={item} className="flex items-start gap-3 text-[#CBD5E1]">
              <ArrowRight className="mt-0.5 h-5 w-5 flex-shrink-0 text-[#38B88A]" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </div>
    ),
  },
  {
    id: 7,
    title: "Scale & Reliability",
    subtitle: "Enterprise-Grade Performance",
    icon: <BarChart3 className="h-10 w-10 text-[#38B88A]" />,
    content: (
      <div className="space-y-4">
        <p className="text-lg text-[#CBD5E1]">
          Battle-tested infrastructure designed for extreme scale with zero-downtime operations.
        </p>
        <div className="grid grid-cols-2 gap-3">
          {[
            { label: "Load Testing", value: "50K+", desc: "Concurrent missions" },
            { label: "Latency", value: "&lt;50ms", desc: "P95 response time" },
            { label: "Capacity", value: "Unlimited", desc: "Horizontal scaling" },
            { label: "Reliability", value: "99.997%", desc: "Monthly uptime" },
          ].map((item) => (
            <div
              key={item.label}
              className="rounded-lg border border-[#1E293B] bg-[#0F172A] p-4"
            >
              <p className="text-2xl font-bold text-[#38B88A]">{item.value}</p>
              <p className="font-semibold text-white">{item.label}</p>
              <p className="text-sm text-[#64748B]">{item.desc}</p>
            </div>
          ))}
        </div>
      </div>
    ),
  },
  {
    id: 8,
    title: "Security & Governance",
    subtitle: "Defense in Depth",
    icon: <Lock className="h-10 w-10 text-[#38B88A]" />,
    content: (
      <div className="space-y-4">
        <p className="text-lg text-[#CBD5E1]">
          Comprehensive security architecture with multi-layered controls and enterprise compliance
          certifications.
        </p>
        <div className="grid grid-cols-2 gap-3">
          {[
            { label: "RBAC / ABAC", desc: "Fine-grained access control" },
            { label: "Approval Workflows", desc: "Multi-step approval chains" },
            { label: "Guardrails", desc: "Policy-as-code enforcement" },
            { label: "Encryption", desc: "AES-256 at rest, TLS 1.3 in transit" },
            { label: "Audit Trail", desc: "Immutable event logging" },
            { label: "Compliance", desc: "SOC 2, ISO 27001, GDPR" },
          ].map((item) => (
            <div
              key={item.label}
              className="rounded-lg border border-[#1E293B] bg-[#0F172A] p-3"
            >
              <Shield className="mb-2 h-5 w-5 text-[#38B88A]" />
              <p className="font-semibold text-white">{item.label}</p>
              <p className="text-sm text-[#64748B]">{item.desc}</p>
            </div>
          ))}
        </div>
      </div>
    ),
  },
  {
    id: 9,
    title: "Connectors & Integrations",
    subtitle: "8 Enterprise Connectors",
    icon: <Puzzle className="h-10 w-10 text-[#38B88A]" />,
    content: (
      <div className="grid grid-cols-4 gap-3">
        {[
          { emoji: "💬", label: "Slack" },
          { emoji: "📧", label: "Microsoft Teams" },
          { emoji: "📄", label: "Google Workspace" },
          { emoji: "🗄️", label: "Jira" },
          { emoji: "📊", label: "ServiceNow" },
          { emoji: "🔐", label: "Okta" },
          { emoji: "☁️", label: "AWS" },
          { emoji: "🐙", label: "GitHub" },
        ].map((connector) => (
          <div
            key={connector.label}
            className="flex flex-col items-center gap-2 rounded-lg border border-[#1E293B] bg-[#0F172A] p-4 text-center"
          >
            <span className="text-3xl">{connector.emoji}</span>
            <p className="font-semibold text-white">{connector.label}</p>
          </div>
        ))}
      </div>
    ),
  },
  {
    id: 10,
    title: "Memory & Knowledge",
    subtitle: "Persistent Intelligence",
    icon: <Database className="h-10 w-10 text-[#38B88A]" />,
    content: (
      <div className="space-y-4">
        <p className="text-lg text-[#CBD5E1]">
          Multi-tier memory architecture that persists, indexes, and retrieves knowledge across
          sessions and missions.
        </p>
        <div className="grid grid-cols-2 gap-3">
          {[
            { label: "Working Memory", desc: "Session-scoped context with automatic eviction" },
            { label: "Episodic Memory", desc: "Mission history with full replay capability" },
            { label: "Semantic Memory", desc: "Vector-embedded knowledge graph" },
            { label: "Procedural Memory", desc: "Learned workflows & optimization patterns" },
          ].map((item) => (
            <div
              key={item.label}
              className="rounded-lg border border-[#1E293B] bg-[#0F172A] p-4"
            >
              <p className="font-semibold text-white">{item.label}</p>
              <p className="text-sm text-[#64748B]">{item.desc}</p>
            </div>
          ))}
        </div>
      </div>
    ),
  },
  {
    id: 11,
    title: "Deployment Flexibility",
    subtitle: "Any Environment, Any Scale",
    icon: <Cloud className="h-10 w-10 text-[#38B88A]" />,
    content: (
      <div className="grid grid-cols-2 gap-4">
        {[
          { emoji: "🐳", label: "Docker", desc: "Containerized deployment" },
          { emoji: "⚓", label: "Kubernetes", desc: "Orchestrated scaling" },
          { emoji: "☁️", label: "Cloud Native", desc: "AWS, Azure, GCP" },
          { emoji: "🔒", label: "Air-Gapped", desc: "Fully offline capable" },
        ].map((item) => (
          <div
            key={item.label}
            className="flex items-center gap-4 rounded-lg border border-[#1E293B] bg-[#0F172A] p-5"
          >
            <span className="text-4xl">{item.emoji}</span>
            <div>
              <p className="text-xl font-bold text-white">{item.label}</p>
              <p className="text-[#64748B]">{item.desc}</p>
            </div>
          </div>
        ))}
        <div className="col-span-2 mt-2 rounded-lg border border-[#1E293B] bg-[#0F172A] p-4 text-center">
          <p className="text-[#94A3B8]">
            Single-tenant, hybrid, or multi-cloud — CortexPrime adapts to your infrastructure.
          </p>
        </div>
      </div>
    ),
  },
  {
    id: 12,
    title: "Ready for Your Enterprise",
    subtitle: "Next Steps",
    icon: <ThumbsUp className="h-10 w-10 text-[#38B88A]" />,
    content: (
      <div className="flex flex-col items-center gap-6 text-center">
        <CheckCircle2 className="h-16 w-16 text-[#38B88A]" />
        <p className="max-w-xl text-xl text-[#CBD5E1]">
          Thank you for exploring CortexPrime. We are ready to partner with your enterprise team
          for a guided proof of concept.
        </p>
        <div className="grid grid-cols-2 gap-6">
          <div className="rounded-lg border border-[#1E293B] bg-[#0F172A] p-5">
            <p className="font-semibold text-white">Contact</p>
            <p className="mt-1 text-sm text-[#38B88A]">enterprise@cortexprime.io</p>
          </div>
          <div className="rounded-lg border border-[#1E293B] bg-[#0F172A] p-5">
            <p className="font-semibold text-white">Documentation</p>
            <p className="mt-1 text-sm text-[#38B88A]">docs.cortexprime.io</p>
          </div>
        </div>
        <p className="text-sm text-[#64748B]">
          Schedule your enterprise deep-dive: enterprise@cortexprime.io
        </p>
      </div>
    ),
  },
]

function exportAsMarkdown(slides: Slide[]): string {
  return slides
    .map((slide, i) => {
      return `# Slide ${i + 1}: ${slide.title}${slide.subtitle ? `\n## ${slide.subtitle}` : ""}\n\n[Content placeholder — icon-based slide rendered in Presentation Mode]\n\n---\n`
    })
    .join("\n")
}

function SlideThumbnail({
  slide,
  index,
  onClick,
}: {
  slide: Slide
  index: number
  onClick: () => void
}) {
  return (
    <motion.button
      whileHover={{ y: -4, scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
      transition={{ duration: dur.fast, ease: ease.out }}
      onClick={onClick}
      className="flex flex-col items-center gap-2 rounded-xl border border-[#1E293B] bg-[#0F172A] p-5 text-center transition-colors hover:border-[#38B88A]/50"
    >
      <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-[#38B88A]/10">
        {slide.icon}
      </div>
      <p className="text-xs text-[#64748B]">Slide {index + 1}</p>
      <p className="text-sm font-semibold text-white leading-tight">{slide.title}</p>
      {slide.subtitle && (
        <p className="text-xs text-[#64748B] line-clamp-1">{slide.subtitle}</p>
      )}
    </motion.button>
  )
}

export default function PresentationPanel() {
  const [presentationMode, setPresentationMode] = useState(false)
  const [currentSlide, setCurrentSlide] = useState(0)
  const [autoAdvance, setAutoAdvance] = useState(false)
  const [autoAdvanceInterval, setAutoAdvanceInterval] = useState(SLIDE_DURATION)
  const [fullscreen, setFullscreen] = useState(false)
  const [showGrid, setShowGrid] = useState(true)
  const containerRef = useRef<HTMLDivElement>(null)
  const autoAdvanceRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const totalSlides = slidesData.length

  const goToSlide = useCallback((index: number) => {
    setCurrentSlide(Math.max(0, Math.min(index, slidesData.length - 1)))
  }, [])

  const goNext = useCallback(() => {
    setCurrentSlide((prev) => Math.min(prev + 1, slidesData.length - 1))
  }, [])

  const goPrev = useCallback(() => {
    setCurrentSlide((prev) => Math.max(prev - 1, 0))
  }, [])

  const toggleFullscreen = useCallback(async () => {
    if (!document.fullscreenElement) {
      await document.documentElement.requestFullscreen()
      setFullscreen(true)
    } else {
      await document.exitFullscreen()
      setFullscreen(false)
    }
  }, [])

  const togglePresentation = useCallback(() => {
    setPresentationMode((prev) => {
      if (prev) {
        setAutoAdvance(false)
        if (document.fullscreenElement) {
          document.exitFullscreen()
          setFullscreen(false)
        }
      }
      return !prev
    })
    setCurrentSlide(0)
    setShowGrid(false)
  }, [])

  const handleExport = useCallback(() => {
    const markdown = exportAsMarkdown(slidesData)
    const blob = new Blob([markdown], { type: "text/markdown" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = "cortexprime-presentation.md"
    a.click()
    URL.revokeObjectURL(url)
  }, [])

  const progressPercent = ((currentSlide + 1) / totalSlides) * 100

  const estimatedTimeRemaining = useMemo(() => {
    const remaining = totalSlides - currentSlide - 1
    const minutes = Math.floor((remaining * autoAdvanceInterval) / 60)
    const seconds = (remaining * autoAdvanceInterval) % 60
    if (minutes > 0) return `${minutes}m ${seconds}s`
    return `${seconds}s`
  }, [currentSlide, totalSlides, autoAdvanceInterval])

  useEffect(() => {
    if (autoAdvance) {
      autoAdvanceRef.current = setInterval(() => {
        setCurrentSlide((prev) => {
          if (prev >= slidesData.length - 1) {
            setAutoAdvance(false)
            return prev
          }
          return prev + 1
        })
      }, autoAdvanceInterval * 1000)
    }
    return () => {
      if (autoAdvanceRef.current) {
        clearInterval(autoAdvanceRef.current)
        autoAdvanceRef.current = null
      }
    }
  }, [autoAdvance, autoAdvanceInterval])

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!presentationMode) return
      if (e.key === "ArrowRight" || e.key === " ") {
        e.preventDefault()
        goNext()
      } else if (e.key === "ArrowLeft") {
        e.preventDefault()
        goPrev()
      } else if (e.key === "Escape") {
        setPresentationMode(false)
        setAutoAdvance(false)
        if (document.fullscreenElement) {
          document.exitFullscreen()
          setFullscreen(false)
        }
      } else if (e.key === "f") {
        toggleFullscreen()
      }
    }
    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [presentationMode, goNext, goPrev, toggleFullscreen])

  return (
    <div
      ref={containerRef}
      className={cn(
        "relative min-h-screen transition-all duration-500",
        presentationMode && "bg-[#020617]",
      )}
    >
      <div
        className={cn(
          "transition-all duration-500",
          presentationMode && "opacity-30 pointer-events-none",
        )}
      >
        <div className="mx-auto max-w-7xl px-6 py-8">
          <div className="mb-6 flex items-center justify-between">
            <h2 className="text-2xl font-bold text-white">Pilot Readiness</h2>
            <div className="flex items-center gap-3">
              <button
                onClick={handleExport}
                className="flex items-center gap-2 rounded-lg border border-[#1E293B] bg-[#0F172A] px-4 py-2 text-sm text-[#94A3B8] transition-colors hover:border-[#38B88A]/50 hover:text-white"
              >
                <Download className="h-4 w-4" />
                Export as Markdown
              </button>
              <button
                onClick={togglePresentation}
                className="flex items-center gap-2 rounded-lg border border-[#38B88A] bg-[#38B88A] px-5 py-2.5 text-sm font-semibold text-white shadow-lg shadow-[#38B88A]/20 transition-all hover:bg-[#2F9F77]"
              >
                <Monitor className="h-4 w-4" />
                Enter Presentation Mode
              </button>
            </div>
          </div>

          {showGrid && (
            <div className="grid grid-cols-3 gap-4">
              {slidesData.map((slide, index) => (
                <SlideThumbnail
                  key={slide.id}
                  slide={slide}
                  index={index}
                  onClick={() => {
                    setPresentationMode(true)
                    setCurrentSlide(index)
                    setShowGrid(false)
                  }}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      <AnimatePresence>
        {presentationMode && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: dur.medium, ease: ease.inOut }}
            className="fixed inset-0 z-50 flex flex-col bg-[#020617]"
          >
            <div className="flex flex-1 flex-col items-center justify-center overflow-y-auto px-8 py-12">
              <AnimatePresence mode="wait">
                <motion.div
                  key={currentSlide}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -20 }}
                  transition={{ duration: dur.base, ease: ease.out }}
                  className="w-full max-w-4xl"
                >
                  <div className="mb-8 flex items-center gap-4">
                    <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-[#38B88A]/10">
                      {slidesData[currentSlide].icon}
                    </div>
                    <div>
                      <h1 className="text-4xl font-bold text-white">
                        {slidesData[currentSlide].title}
                      </h1>
                      {slidesData[currentSlide].subtitle && (
                        <p className="mt-1 text-xl text-[#38B88A]">
                          {slidesData[currentSlide].subtitle}
                        </p>
                      )}
                    </div>
                  </div>
                  <div className="rounded-xl border border-[#1E293B] bg-[#0A0F1E] p-8">
                    {slidesData[currentSlide].content}
                  </div>
                </motion.div>
              </AnimatePresence>
            </div>

            <div className="flex-shrink-0 border-t border-[#1E293B] bg-[#0A0F1E]">
              <div className="h-1 w-full bg-[#1E293B]">
                <div
                  className="h-full bg-[#38B88A] transition-all duration-300"
                  style={{ width: `${progressPercent}%` }}
                />
              </div>
              <div className="flex items-center justify-between px-6 py-3">
                <div className="flex items-center gap-4">
                  <span className="text-sm font-semibold text-[#94A3B8]">
                    {currentSlide + 1} / {totalSlides}
                  </span>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => goToSlide(0)}
                      disabled={currentSlide === 0}
                      className="rounded-lg p-2 text-[#64748B] transition-colors hover:bg-[#1E293B] hover:text-white disabled:opacity-30"
                    >
                      <SkipBack className="h-4 w-4" />
                    </button>
                    <button
                      onClick={goPrev}
                      disabled={currentSlide === 0}
                      className="rounded-lg p-2 text-[#64748B] transition-colors hover:bg-[#1E293B] hover:text-white disabled:opacity-30"
                    >
                      <ChevronLeft className="h-5 w-5" />
                    </button>
                    <button
                      onClick={goNext}
                      disabled={currentSlide >= totalSlides - 1}
                      className="rounded-lg p-2 text-[#64748B] transition-colors hover:bg-[#1E293B] hover:text-white disabled:opacity-30"
                    >
                      <ChevronRight className="h-5 w-5" />
                    </button>
                    <button
                      onClick={() => goToSlide(totalSlides - 1)}
                      disabled={currentSlide >= totalSlides - 1}
                      className="rounded-lg p-2 text-[#64748B] transition-colors hover:bg-[#1E293B] hover:text-white disabled:opacity-30"
                    >
                      <SkipForward className="h-4 w-4" />
                    </button>
                  </div>
                </div>

                <div className="flex items-center gap-4">
                  <div className="flex items-center gap-2 text-sm text-[#64748B]">
                    <Timer className="h-4 w-4" />
                    <span>{estimatedTimeRemaining} remaining</span>
                  </div>

                  <button
                    onClick={() => setAutoAdvance((prev) => !prev)}
                    className={cn(
                      "flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm transition-colors",
                      autoAdvance
                        ? "bg-[#38B88A]/20 text-[#38B88A]"
                        : "text-[#64748B] hover:bg-[#1E293B] hover:text-white",
                    )}
                  >
                    {autoAdvance ? (
                      <Pause className="h-4 w-4" />
                    ) : (
                      <Play className="h-4 w-4" />
                    )}
                    Auto
                  </button>

                  <button
                    onClick={toggleFullscreen}
                    className="rounded-lg p-2 text-[#64748B] transition-colors hover:bg-[#1E293B] hover:text-white"
                  >
                    {fullscreen ? (
                      <Minimize2 className="h-4 w-4" />
                    ) : (
                      <Maximize2 className="h-4 w-4" />
                    )}
                  </button>

                  <button
                    onClick={togglePresentation}
                    className="flex items-center gap-2 rounded-lg border border-[#1E293B] px-4 py-1.5 text-sm text-[#94A3B8] transition-colors hover:border-red-500/50 hover:text-red-400"
                  >
                    <MonitorOff className="h-4 w-4" />
                    Exit
                  </button>
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {presentationMode && (
        <div className="fixed bottom-24 right-6 z-[60] flex flex-col gap-2">
          <button
            onClick={() => setShowGrid((prev) => !prev)}
            className="rounded-lg border border-[#1E293B] bg-[#0F172A] p-2 text-[#64748B] transition-colors hover:border-[#38B88A]/50 hover:text-white"
            title="Slide overview"
          >
            <LayoutGrid className="h-4 w-4" />
          </button>
        </div>
      )}

      {presentationMode && showGrid && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 20 }}
          transition={{ duration: dur.fast, ease: ease.out }}
          className="fixed bottom-32 right-6 z-[60] w-64 rounded-xl border border-[#1E293B] bg-[#0A0F1E] p-3 shadow-2xl"
        >
          <p className="mb-2 text-xs font-semibold text-[#64748B] uppercase tracking-wider">
            Jump to slide
          </p>
          <div className="grid grid-cols-3 gap-1.5">
            {slidesData.map((slide, index) => (
              <button
                key={slide.id}
                onClick={() => goToSlide(index)}
                className={cn(
                  "rounded-md p-2 text-center text-xs transition-colors",
                  index === currentSlide
                    ? "bg-[#38B88A]/20 text-[#38B88A] border border-[#38B88A]/50"
                    : "text-[#64748B] hover:bg-[#1E293B] hover:text-white",
                )}
              >
                {index + 1}
              </button>
            ))}
          </div>
        </motion.div>
      )}
    </div>
  )
}