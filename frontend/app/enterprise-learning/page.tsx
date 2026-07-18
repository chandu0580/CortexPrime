"use client"

import { useState } from "react"
import { motion } from "framer-motion"
import CortexShell from "@/components/layout/CortexShell"
import { stagger, variants } from "@/lib/motion-tokens"
import {
  useEnterpriseLearningDashboard,
  useEnterpriseLessons,
  useEnterpriseFailurePatterns,
  useEnterpriseRecoveryPatterns,
  useEnterpriseRecommendations,
  useEnterpriseLearningConfidenceTrends,
  useEnterpriseLearningAnalyze,
} from "@/hooks/queries/enterprise/useEnterpriseLearning"
import {
  Lightbulb,
  AlertTriangle,
  CheckCircle2,
  RefreshCw,
  Shield,
  TrendingUp,
  Target,
  BookOpen,
  Zap,
  Loader2,
  Brain,
  ListChecks,
  BarChart3,
} from "lucide-react"

function StatCard({
  icon: Icon,
  label,
  value,
  color,
}: {
  icon: React.ElementType
  label: string
  value: string | number
  color: string
}) {
  return (
    <motion.div
      variants={variants.fadeUp}
      className="rounded-xl border border-[#E8EDF3] bg-white p-4"
    >
      <div className="flex items-center gap-3">
        <div className={`rounded-lg p-2.5 ${color}`}>
          <Icon className="h-4 w-4 text-white" />
        </div>
        <div>
          <p className="text-[0.7rem] font-medium text-[#6B7280]">{label}</p>
          <p className="text-xl font-bold text-[#111827]">{value}</p>
        </div>
      </div>
    </motion.div>
  )
}

function LessonsPanel() {
  const { data: lessons, isLoading } = useEnterpriseLessons(10)

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8 text-[0.78rem] text-[#6B7280]">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        Loading lessons...
      </div>
    )
  }

  if (!lessons || lessons.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-10 text-[#6B7280]">
        <BookOpen className="mb-2 h-8 w-8 opacity-30" />
        <p className="text-[0.78rem]">No lessons discovered yet. Missions will generate lessons automatically.</p>
      </div>
    )
  }

  return (
    <div className="max-h-96 space-y-2 overflow-y-auto">
      {lessons.map((lesson, i) => {
        const isSuccess = lesson.metadata?.outcome === "success"
        const isFailure = lesson.metadata?.outcome === "failure"
        return (
          <div
            key={lesson.id}
            className="rounded-lg border border-[#E8EDF3] bg-white p-3"
          >
            <div className="flex items-start gap-2.5">
              {isSuccess ? (
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-[#38B88A]" />
              ) : isFailure ? (
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-red-500" />
              ) : (
                <Lightbulb className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" />
              )}
              <div className="min-w-0 flex-1">
                <p className="text-[0.78rem] font-medium text-[#111827] line-clamp-2">
                  {lesson.content}
                </p>
                <div className="mt-1.5 flex items-center gap-2">
                  <span className={`rounded px-1.5 py-0.5 text-[0.6rem] font-medium ${
                    isSuccess
                      ? "bg-[#F0FDF4] text-[#38B88A]"
                      : isFailure
                      ? "bg-red-50 text-red-600"
                      : "bg-amber-50 text-amber-600"
                  }`}>
                    {lesson.metadata?.domain as string || "unknown"}
                  </span>
                  <span className="text-[0.6rem] text-[#9CA3AF]">
                    {(lesson.confidence * 100).toFixed(0)}% confidence
                  </span>
                </div>
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}

function FailurePatternsPanel() {
  const { data: patterns, isLoading } = useEnterpriseFailurePatterns(10)

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8 text-[0.78rem] text-[#6B7280]">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        Loading patterns...
      </div>
    )
  }

  if (!patterns || patterns.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-10 text-[#6B7280]">
        <AlertTriangle className="mb-2 h-8 w-8 opacity-30" />
        <p className="text-[0.78rem]">No failure patterns detected.</p>
      </div>
    )
  }

  const maxCount = Math.max(...patterns.map((p) => p.count))

  return (
    <div className="space-y-3">
      {patterns.map((p, i) => (
        <div key={p.signature || i}>
          <div className="mb-1 flex items-center justify-between">
            <div className="min-w-0 flex-1 truncate pr-2">
              <span className="text-[0.78rem] font-medium text-[#111827]">
                {p.signature || p.error || "Unknown error"}
              </span>
            </div>
            <span className="shrink-0 rounded bg-red-50 px-1.5 py-0.5 text-[0.6rem] font-medium text-red-600">
              {p.count}x
            </span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-[#F3F4F6]">
            <div
              className="h-full rounded-full bg-red-400 transition-all"
              style={{ width: `${(p.count / maxCount) * 100}%` }}
            />
          </div>
          {p.source && (
            <p className="mt-0.5 text-[0.6rem] text-[#9CA3AF]">Source: {p.source}</p>
          )}
        </div>
      ))}
    </div>
  )
}

function RecoveryPatternsPanel() {
  const { data: patterns, isLoading } = useEnterpriseRecoveryPatterns()

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8 text-[0.78rem] text-[#6B7280]">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        Loading patterns...
      </div>
    )
  }

  if (!patterns || patterns.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-10 text-[#6B7280]">
        <RefreshCw className="mb-2 h-8 w-8 opacity-30" />
        <p className="text-[0.78rem]">No recovery patterns recorded.</p>
      </div>
    )
  }

  const recoveryColors: Record<string, string> = {
    retry: "bg-blue-400",
    fallback: "bg-amber-400",
    rollback: "bg-purple-400",
    escalation: "bg-red-400",
  }

  return (
    <div className="space-y-3">
      {patterns.map((p, i) => {
        const rt = p.recovery_type || "unknown"
        return (
          <div
            key={rt}
            className="flex items-center gap-3 rounded-lg border border-[#E8EDF3] bg-white px-3 py-2.5"
          >
            <div className={`h-2.5 w-2.5 shrink-0 rounded-full ${recoveryColors[rt] || "bg-gray-400"}`} />
            <div className="min-w-0 flex-1">
              <p className="text-[0.78rem] font-medium text-[#111827] capitalize">{rt}</p>
              <p className="text-[0.65rem] text-[#6B7280]">
                Used {p.count || 0} time(s)
                {p.last_used && ` — last used ${new Date(p.last_used).toLocaleDateString()}`}
              </p>
            </div>
          </div>
        )
      })}
    </div>
  )
}

function RecommendationsPanel() {
  const { data: recommendations, isLoading } = useEnterpriseRecommendations(10)

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8 text-[0.78rem] text-[#6B7280]">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        Loading recommendations...
      </div>
    )
  }

  if (!recommendations || recommendations.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-10 text-[#6B7280]">
        <Zap className="mb-2 h-8 w-8 opacity-30" />
        <p className="text-[0.78rem]">No recommendations yet. Run analysis to generate them.</p>
      </div>
    )
  }

  const priorityColors: Record<string, string> = {
    high: "border-l-red-500 bg-red-50",
    medium: "border-l-amber-500 bg-amber-50",
    low: "border-l-blue-500 bg-blue-50",
  }

  return (
    <div className="space-y-2">
      {recommendations.map((r, i) => {
        const priority = (r.metadata?.priority as string) || "medium"
        return (
          <div
            key={r.id}
            className={`rounded-r-lg border border-l-4 border-[#E8EDF3] p-3 ${priorityColors[priority] || "bg-white"}`}
          >
            <p className="text-[0.78rem] font-medium text-[#111827]">{r.content}</p>
            <div className="mt-1.5 flex items-center gap-2">
              <span className={`rounded px-1.5 py-0.5 text-[0.6rem] font-medium capitalize ${
                priority === "high"
                  ? "bg-red-100 text-red-700"
                  : priority === "medium"
                  ? "bg-amber-100 text-amber-700"
                  : "bg-blue-100 text-blue-700"
              }`}>
                {priority}
              </span>
              <span className="text-[0.6rem] text-[#9CA3AF]">
                {(r.confidence * 100).toFixed(0)}% confidence
              </span>
            </div>
          </div>
        )
      })}
    </div>
  )
}

function ConfidenceSection() {
  const { data: trends, isLoading } = useEnterpriseLearningConfidenceTrends()

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-6 text-[0.78rem] text-[#6B7280]">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        Loading...
      </div>
    )
  }

  if (!trends) return null

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {[
        { label: "Avg Lesson Confidence", value: `${(trends.avg_lesson_confidence * 100).toFixed(0)}%`, icon: BookOpen, color: "bg-[#38B88A]" },
        { label: "Avg Pattern Confidence", value: `${(trends.avg_pattern_confidence * 100).toFixed(0)}%`, icon: Target, color: "bg-blue-500" },
        { label: "Avg Recommendation Confidence", value: `${(trends.avg_recommendation_confidence * 100).toFixed(0)}%`, icon: Zap, color: "bg-amber-500" },
        { label: "Total Intelligence Entries", value: trends.total_intelligence_entries, icon: Brain, color: "bg-purple-500" },
      ].map((stat, i) => {
        const Icon = stat.icon
        return (
          <div key={i} className="rounded-lg border border-[#E8EDF3] bg-[#FAFBFC] p-3">
            <div className="flex items-center gap-2">
              <Icon className="h-3.5 w-3.5 text-[#6B7280]" />
              <span className="text-[0.7rem] font-medium text-[#6B7280]">{stat.label}</span>
            </div>
            <p className="mt-1 text-lg font-bold text-[#111827]">{stat.value}</p>
          </div>
        )
      })}
    </div>
  )
}

export default function EnterpriseLearningDashboard() {
  const [selectedTab, setSelectedTab] = useState<string>("lessons")
  const { data: dashboard, isLoading: isDashboardLoading } = useEnterpriseLearningDashboard()
  const analyzeMutation = useEnterpriseLearningAnalyze()

  const handleAnalyze = () => {
    analyzeMutation.mutate({ limit: 50 })
  }

  const tabs = [
    { id: "lessons", label: "Lessons Learned", icon: BookOpen },
    { id: "failures", label: "Failure Patterns", icon: AlertTriangle },
    { id: "recoveries", label: "Recovery Patterns", icon: RefreshCw },
    { id: "recommendations", label: "Recommendations", icon: Zap },
  ]

  return (
    <CortexShell title="Executive Learning Dashboard" subtitle="Active intelligence that improves from every mission">
      <div className="relative z-10 mx-auto max-w-7xl space-y-6">
        {/* Summary Stats */}
        <motion.div initial="hidden" animate="visible" variants={stagger(0.04, 0.01)}>
          {isDashboardLoading ? (
            <div className="flex items-center justify-center py-8 text-sm text-[#6B7280]">
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Loading dashboard...
            </div>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
              <StatCard icon={BookOpen} label="Total Lessons" value={dashboard?.summary?.total_lessons ?? 0} color="bg-[#38B88A]" />
              <StatCard icon={CheckCircle2} label="Success Lessons" value={dashboard?.summary?.success_lessons ?? 0} color="bg-green-500" />
              <StatCard icon={AlertTriangle} label="Failure Lessons" value={dashboard?.summary?.failure_lessons ?? 0} color="bg-red-500" />
              <StatCard icon={Target} label="Failure Patterns" value={dashboard?.summary?.total_failure_patterns ?? 0} color="bg-blue-500" />
              <StatCard icon={RefreshCw} label="Recovery Patterns" value={dashboard?.summary?.total_recovery_patterns ?? 0} color="bg-amber-500" />
              <StatCard icon={Zap} label="Recommendations" value={dashboard?.summary?.total_recommendations ?? 0} color="bg-purple-500" />
            </div>
          )}
        </motion.div>

        {/* Action Bar */}
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-center justify-between rounded-xl border border-[#E8EDF3] bg-white p-4"
        >
          <div className="flex items-center gap-2">
            <Brain className="h-5 w-5 text-[#38B88A]" />
            <span className="text-sm font-medium text-[#111827]">
              The learning engine automatically extracts intelligence from every event. Trigger on-demand analysis to catch up on past missions.
            </span>
          </div>
          <button
            onClick={handleAnalyze}
            disabled={analyzeMutation.isPending}
            className="ml-4 flex shrink-0 items-center gap-2 rounded-lg bg-[#38B88A] px-4 py-2 text-sm font-medium text-white transition-all hover:bg-[#2EA07A] disabled:opacity-50"
          >
            {analyzeMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <BarChart3 className="h-4 w-4" />
            )}
            {analyzeMutation.isPending ? "Analyzing..." : "Analyze Now"}
          </button>
        </motion.div>

        {/* Tab Navigation */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="flex gap-1 rounded-xl border border-[#E8EDF3] bg-white p-1"
        >
          {tabs.map((tab) => {
            const TabIcon = tab.icon
            const isActive = selectedTab === tab.id
            return (
              <button
                key={tab.id}
                onClick={() => setSelectedTab(tab.id)}
                className={`flex items-center gap-2 rounded-lg px-4 py-2 text-[0.78rem] font-medium transition-all ${
                  isActive
                    ? "bg-[#38B88A] text-white shadow-sm"
                    : "text-[#6B7280] hover:bg-[#F4F7FA]"
                }`}
              >
                <TabIcon className="h-4 w-4" />
                {tab.label}
              </button>
            )
          })}
        </motion.div>

        {/* Tab Content */}
        <motion.div key={selectedTab} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-5">
          {/* Lessons Tab */}
          {selectedTab === "lessons" && (
            <motion.div variants={stagger(0.05, 0.03)} className="space-y-5">
              <motion.div variants={variants.fadeUp} className="rounded-xl border border-[#E8EDF3] bg-white p-5">
                <div className="mb-4 flex items-center gap-2">
                  <BookOpen className="h-4 w-4 text-[#38B88A]" />
                  <h2 className="text-sm font-bold text-[#111827]">Recent Lessons Learned</h2>
                </div>
                <LessonsPanel />
              </motion.div>

              <motion.div variants={variants.fadeUp} className="rounded-xl border border-[#E8EDF3] bg-white p-5">
                <div className="mb-4 flex items-center gap-2">
                  <TrendingUp className="h-4 w-4 text-[#38B88A]" />
                  <h2 className="text-sm font-bold text-[#111827]">Confidence Trends</h2>
                </div>
                <ConfidenceSection />
              </motion.div>
            </motion.div>
          )}

          {/* Failure Patterns Tab */}
          {selectedTab === "failures" && (
            <motion.div variants={variants.fadeUp} className="rounded-xl border border-[#E8EDF3] bg-white p-5">
              <div className="mb-4 flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-red-500" />
                <h2 className="text-sm font-bold text-[#111827]">Failure Patterns by Frequency</h2>
              </div>
              <FailurePatternsPanel />
            </motion.div>
          )}

          {/* Recovery Patterns Tab */}
          {selectedTab === "recoveries" && (
            <motion.div variants={variants.fadeUp} className="rounded-xl border border-[#E8EDF3] bg-white p-5">
              <div className="mb-4 flex items-center gap-2">
                <RefreshCw className="h-4 w-4 text-amber-500" />
                <h2 className="text-sm font-bold text-[#111827]">Recovery Strategy Patterns</h2>
              </div>
              <RecoveryPatternsPanel />
            </motion.div>
          )}

          {/* Recommendations Tab */}
          {selectedTab === "recommendations" && (
            <motion.div variants={variants.fadeUp} className="rounded-xl border border-[#E8EDF3] bg-white p-5">
              <div className="mb-4 flex items-center gap-2">
                <ListChecks className="h-4 w-4 text-purple-500" />
                <h2 className="text-sm font-bold text-[#111827]">Actionable Recommendations</h2>
                <span className="ml-auto rounded bg-[#F0FDF4] px-2 py-0.5 text-[0.65rem] font-medium text-[#38B88A]">
                  Generated from accumulated intelligence
                </span>
              </div>
              <RecommendationsPanel />
            </motion.div>
          )}
        </motion.div>

        {/* Top Failure Patterns Summary (always visible) */}
        {dashboard?.top_failure_patterns && dashboard.top_failure_patterns.length > 0 && selectedTab !== "failures" && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="rounded-xl border border-[#E8EDF3] bg-white p-5"
          >
            <div className="mb-3 flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-red-500" />
              <h2 className="text-sm font-bold text-[#111827]">Top Failure Signals</h2>
            </div>
            <div className="flex flex-wrap gap-2">
              {dashboard.top_failure_patterns.slice(0, 5).map((p, i) => (
                <span
                  key={i}
                  className="inline-flex items-center gap-1.5 rounded-full border border-red-200 bg-red-50 px-3 py-1 text-[0.7rem] font-medium text-red-700"
                >
                  <AlertTriangle className="h-3 w-3" />
                  {p.signature ? p.signature.length > 30 ? `${p.signature.slice(0, 30)}...` : p.signature : p.error?.slice(0, 30)}
                  <span className="ml-0.5 rounded-full bg-red-200 px-1.5 text-[0.55rem] font-bold text-red-800">
                    {p.count}
                  </span>
                </span>
              ))}
            </div>
          </motion.div>
        )}
      </div>
    </CortexShell>
  )
}
