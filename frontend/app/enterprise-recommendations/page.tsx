"use client"

import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import CortexShell from "@/components/layout/CortexShell"
import { stagger, variants } from "@/lib/motion-tokens"
import {
  useRecommendations,
  useRecommendationDashboard,
  useRecommendationCategories,
  useRecommendationHistory,
  useDismissRecommendation,
  useExecuteRecommendation,
} from "@/hooks/queries/enterprise/useEnterpriseRecommendations"
import {
  Activity,
  AlertTriangle,
  Archive,
  ArrowUpRight,
  BarChart3,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  DollarSign,
  Eye,
  GitBranch,
  Lightbulb,
  Loader2,
  Target,
  ThumbsUp,
  Trash2,
  TrendingUp,
  Zap,
} from "lucide-react"

const CATEGORY_LABELS: Record<string, string> = {
  operations: "Operations",
  security: "Security",
  reliability: "Reliability",
  performance: "Performance",
  connector_health: "Connector Health",
  workflow_optimization: "Workflow Optimization",
  cost_optimization: "Cost Optimization",
  knowledge: "Knowledge",
  learning: "Learning",
  mission_recovery: "Mission Recovery",
  governance: "Governance",
  compliance: "Compliance",
  infrastructure: "Infrastructure",
  executive_strategy: "Executive Strategy",
}

const CATEGORY_COLORS: Record<string, string> = {
  operations: "bg-blue-500",
  security: "bg-red-500",
  reliability: "bg-teal-500",
  performance: "bg-amber-500",
  connector_health: "bg-purple-500",
  workflow_optimization: "bg-indigo-500",
  cost_optimization: "bg-green-500",
  knowledge: "bg-cyan-500",
  learning: "bg-pink-500",
  mission_recovery: "bg-orange-500",
  governance: "bg-gray-600",
  compliance: "bg-rose-500",
  infrastructure: "bg-sky-500",
  executive_strategy: "bg-violet-500",
}

const PRIORITY_ORDER = ["critical", "high", "medium", "low"] as const
const PRIORITY_COLORS: Record<string, string> = {
  critical: "border-red-500 bg-red-50",
  high: "border-orange-400 bg-orange-50",
  medium: "border-amber-300 bg-amber-50",
  low: "border-gray-200 bg-white",
}
const PRIORITY_BADGE: Record<string, string> = {
  critical: "bg-red-100 text-red-700",
  high: "bg-orange-100 text-orange-700",
  medium: "bg-amber-100 text-amber-700",
  low: "bg-gray-100 text-gray-600",
}
const RISK_COLORS: Record<string, string> = {
  critical: "text-red-600 bg-red-50 border-red-400",
  high: "text-orange-600 bg-orange-50 border-orange-400",
  medium: "text-amber-600 bg-amber-50 border-amber-300",
  low: "text-gray-600 bg-gray-50 border-gray-300",
}

function PriorityBadge({ priority }: { priority: string }) {
  return (
    <span className={`rounded-full px-2 py-0.5 text-[0.55rem] font-medium uppercase ${PRIORITY_BADGE[priority] || "bg-gray-100 text-gray-600"}`}>
      {priority}
    </span>
  )
}

function RiskBadge({ risk }: { risk: string }) {
  return (
    <span className={`rounded-full border px-2 py-0.5 text-[0.55rem] font-medium capitalize ${RISK_COLORS[risk] || "text-gray-600 bg-gray-50 border-gray-300"}`}>
      {risk} risk
    </span>
  )
}

function CategoryBadge({ category }: { category: string }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[0.55rem] font-medium text-white ${CATEGORY_COLORS[category] || "bg-gray-500"}`}>
      {CATEGORY_LABELS[category] || category}
    </span>
  )
}

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100)
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-[#F3F4F6]">
        <div className={`h-full rounded-full ${pct >= 80 ? "bg-[#38B88A]" : pct >= 50 ? "bg-amber-400" : "bg-red-400"}`}
          style={{ width: `${pct}%` }} />
      </div>
      <span className="text-[0.6rem] font-medium text-[#6B7280]">{pct}%</span>
    </div>
  )
}

function RecommendationCard({
  rec,
  onDismiss,
  onExecute,
  expanded,
  onToggle,
}: {
  rec: any
  onDismiss: (id: string) => void
  onExecute: (id: string) => void
  expanded: boolean
  onToggle: () => void
}) {
  return (
    <motion.div layout className={`rounded-xl border-l-4 ${PRIORITY_COLORS[rec.priority] || "border-gray-200 bg-white"} overflow-hidden`}>
      <button onClick={onToggle} className="flex w-full items-start gap-3 p-4 text-left">
        <div className="min-w-0 flex-1">
          <div className="mb-1 flex items-center gap-2">
            <CategoryBadge category={rec.category} />
            <PriorityBadge priority={rec.priority} />
            <RiskBadge risk={rec.risk} />
          </div>
          <h3 className="text-[0.82rem] font-bold text-[#111827]">{rec.title}</h3>
          <p className="mt-0.5 text-[0.7rem] text-[#6B7280] line-clamp-2">{rec.description}</p>
          <div className="mt-2 flex flex-wrap items-center gap-3 text-[0.6rem] text-[#9CA3AF]">
            <ConfidenceBar value={rec.confidence} />
            {rec.related_connector && <span className="flex items-center gap-1"><GitBranch className="h-3 w-3" />{rec.related_connector}</span>}
            {rec.related_mission && <span className="flex items-center gap-1"><Target className="h-3 w-3" />{rec.related_mission.slice(0, 10)}...</span>}
            {rec.estimated_cost_savings && <span className="flex items-center gap-1"><DollarSign className="h-3 w-3" />{rec.estimated_cost_savings}</span>}
            {rec.estimated_time_savings && <span className="flex items-center gap-1"><Activity className="h-3 w-3" />{rec.estimated_time_savings}</span>}
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          {!rec.dismissed && !rec.executed && (
            <>
              <span onClick={(e) => { e.stopPropagation(); onExecute(rec.id) }}
                className="rounded-lg bg-[#38B88A]/10 p-1.5 text-[#38B88A] hover:bg-[#38B88A]/20"
                title="Execute Action">
                <ThumbsUp className="h-3.5 w-3.5" />
              </span>
              <span onClick={(e) => { e.stopPropagation(); onDismiss(rec.id) }}
                className="rounded-lg bg-gray-100 p-1.5 text-[#6B7280] hover:bg-gray-200"
                title="Dismiss">
                <Trash2 className="h-3.5 w-3.5" />
              </span>
            </>
          )}
          {expanded ? <ChevronDown className="h-4 w-4 text-[#9CA3AF]" /> : <ChevronRight className="h-4 w-4 text-[#9CA3AF]" />}
        </div>
      </button>

      <AnimatePresence>
        {expanded && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }} className="border-t border-[#E8EDF3]">
            <div className="space-y-4 p-4">
              <div>
                <p className="mb-1 text-[0.65rem] font-medium text-[#6B7280]">Reason</p>
                <p className="text-[0.72rem] text-[#111827]">{rec.reason}</p>
              </div>

              {rec.evidence && rec.evidence.length > 0 && (
                <div>
                  <p className="mb-1 text-[0.65rem] font-medium text-[#6B7280]">Evidence ({rec.evidence.length})</p>
                  <div className="space-y-1">
                    {rec.evidence.map((ev: any, i: number) => (
                      <div key={i} className="flex items-start gap-2 rounded-lg bg-[#FAFBFC] px-3 py-2">
                        <Eye className="mt-0.5 h-3 w-3 shrink-0 text-[#9CA3AF]" />
                        <div className="min-w-0 flex-1">
                          <p className="text-[0.65rem] font-medium text-[#6B7280]">{ev.source}</p>
                          <p className="text-[0.6rem] text-[#111827]">{ev.detail || JSON.stringify(ev).slice(0, 120)}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {rec.actions && rec.actions.length > 0 && (
                <div>
                  <p className="mb-1 text-[0.65rem] font-medium text-[#6B7280]">Actions</p>
                  <div className="flex flex-wrap gap-1.5">
                    {rec.actions.map((a: any, i: number) => (
                      <span key={i} className="inline-flex items-center gap-1 rounded-full bg-[#F0FDF4] px-2.5 py-1 text-[0.6rem] font-medium text-[#38B88A]">
                        <Zap className="h-3 w-3" />
                        {a.label}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {(rec.learning_references?.length > 0 || rec.replay_references?.length > 0 || rec.verification_references?.length > 0) && (
                <div className="flex flex-wrap gap-3 text-[0.55rem] text-[#9CA3AF]">
                  {rec.learning_references?.length > 0 && <span>{rec.learning_references.length} learning refs</span>}
                  {rec.replay_references?.length > 0 && <span>{rec.replay_references.length} replay refs</span>}
                  {rec.verification_references?.length > 0 && <span>{rec.verification_references.length} verification refs</span>}
                </div>
              )}

              <p className="text-[0.55rem] text-[#9CA3AF]">Created: {new Date(rec.created_at).toLocaleString()}</p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

export default function EnterpriseRecommendationCenter() {
  const [activeTab, setActiveTab] = useState("overview")
  const [filterCategory, setFilterCategory] = useState("")
  const [filterPriority, setFilterPriority] = useState("")
  const [expandedCard, setExpandedCard] = useState<string | null>(null)
  const [showHistory, setShowHistory] = useState(false)

  const { data: dashboard } = useRecommendationDashboard()
  const { data: activeRecs, isLoading: recsLoading } = useRecommendations(
    filterCategory || undefined,
    filterPriority || undefined,
  )
  const { data: categories } = useRecommendationCategories()
  const { data: history } = useRecommendationHistory(100)
  const dismissMutation = useDismissRecommendation()
  const executeMutation = useExecuteRecommendation()

  const handleDismiss = (id: string) => dismissMutation.mutate(id)
  const handleExecute = (id: string) => executeMutation.mutate(id)

  const tabs = [
    { id: "overview", label: "Overview", icon: BarChart3 },
    { id: "critical", label: "Critical", icon: AlertTriangle, count: dashboard?.critical_count },
    { id: "high", label: "High", icon: TrendingUp, count: dashboard?.high_count },
    { id: "medium", label: "Medium", icon: Activity, count: dashboard?.medium_count },
    { id: "low", label: "Low", icon: ArrowUpRight, count: dashboard?.low_count },
  ]

  const currentPriority = activeTab === "overview" ? "" : activeTab

  const filteredRecs = currentPriority
    ? activeRecs?.filter(r => r.priority === currentPriority) ?? []
    : activeRecs ?? []

  return (
    <CortexShell title="Executive Recommendation Center" subtitle="Proactive intelligence for every platform signal — continuously analyzed, prioritized, and actionable">
      <div className="relative z-10 mx-auto max-w-7xl space-y-6">
        {/* Dashboard Summary */}
        <motion.div initial="hidden" animate="visible" variants={stagger(0.04, 0.01)} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {[
            { icon: Lightbulb, label: "Active Recs", value: dashboard?.active_recommendations ?? "-", color: "bg-blue-500" },
            { icon: AlertTriangle, label: "Critical", value: dashboard?.critical_count ?? "-", color: "bg-red-500" },
            { icon: TrendingUp, label: "High Priority", value: dashboard?.high_count ?? "-", color: "bg-orange-500" },
            { icon: CheckCircle2, label: "Executed", value: dashboard?.executed_recommendations ?? "-", color: "bg-[#38B88A]" },
            { icon: Archive, label: "Dismissed", value: dashboard?.dismissed_recommendations ?? "-", color: "bg-gray-500" },
          ].map((stat, i) => {
            const Icon = stat.icon
            return (
              <motion.div key={i} variants={variants.fadeUp} className="rounded-xl border border-[#E8EDF3] bg-white p-4">
                <div className="flex items-center gap-3">
                  <div className={`rounded-lg p-2.5 ${stat.color}`}><Icon className="h-4 w-4 text-white" /></div>
                  <div>
                    <p className="text-[0.7rem] font-medium text-[#6B7280]">{stat.label}</p>
                    <p className="text-xl font-bold text-[#111827]">{stat.value}</p>
                  </div>
                </div>
              </motion.div>
            )
          })}
        </motion.div>

        {/* Tab Navigation */}
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[#E8EDF3] bg-white p-1">
          <div className="flex flex-wrap gap-1">
            {tabs.map((tab) => {
              const TabIcon = tab.icon
              const isActive = activeTab === tab.id
              return (
                <button
                  key={tab.id}
                  onClick={() => { setActiveTab(tab.id); setExpandedCard(null) }}
                  className={`flex items-center gap-2 rounded-lg px-3.5 py-2 text-[0.75rem] font-medium transition-all ${
                    isActive ? "bg-[#38B88A] text-white shadow-sm" : "text-[#6B7280] hover:bg-[#F4F7FA]"
                  }`}
                >
                  <TabIcon className="h-3.5 w-3.5" />
                  {tab.label}
                  {tab.count !== undefined && tab.count > 0 && (
                    <span className={`rounded-full px-1.5 text-[0.5rem] font-bold ${
                      isActive ? "bg-white/20 text-white" : "bg-[#E8EDF3] text-[#6B7280]"
                    }`}>{tab.count}</span>
                  )}
                </button>
              )
            })}
          </div>
          <div className="flex items-center gap-2">
            <select
              value={filterCategory}
              onChange={(e) => setFilterCategory(e.target.value)}
              className="rounded-lg border border-[#E8EDF3] px-2 py-1.5 text-[0.65rem] text-[#6B7280] outline-none"
            >
              <option value="">All Categories</option>
              {Object.entries(CATEGORY_LABELS).map(([key, label]) => (
                <option key={key} value={key}>{label}</option>
              ))}
            </select>
            <button
              onClick={() => setShowHistory(!showHistory)}
              className={`rounded-lg border px-3 py-1.5 text-[0.65rem] font-medium transition-all ${
                showHistory ? "border-[#38B88A] bg-[#F0FDF4] text-[#38B88A]" : "border-[#E8EDF3] text-[#6B7280] hover:bg-[#F4F7FA]"
              }`}
            >
              <Archive className="mr-1 inline h-3 w-3" />
              History
            </button>
          </div>
        </div>

        {/* Top Risks & Opportunities (overview only) */}
        {activeTab === "overview" && !showHistory && dashboard && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="grid gap-4 lg:grid-cols-2">
            {dashboard.top_risks?.length > 0 && (
              <div className="rounded-xl border border-[#E8EDF3] bg-white p-4">
                <h3 className="mb-3 flex items-center gap-2 text-sm font-bold text-red-600">
                  <AlertTriangle className="h-4 w-4" /> Top Risks
                </h3>
                <div className="space-y-2">
                  {dashboard.top_risks.map((r: any) => (
                    <div key={r.id} className="flex items-start gap-2 rounded-lg bg-red-50 px-3 py-2">
                      <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0 text-red-500" />
                      <div className="min-w-0 flex-1">
                        <p className="text-[0.7rem] font-medium text-[#111827]">{r.title}</p>
                        <p className="text-[0.6rem] text-[#6B7280]">{r.reason}</p>
                      </div>
                      <PriorityBadge priority={r.priority} />
                    </div>
                  ))}
                </div>
              </div>
            )}
            {dashboard.top_opportunities?.length > 0 && (
              <div className="rounded-xl border border-[#E8EDF3] bg-white p-4">
                <h3 className="mb-3 flex items-center gap-2 text-sm font-bold text-[#38B88A]">
                  <TrendingUp className="h-4 w-4" /> Top Opportunities
                </h3>
                <div className="space-y-2">
                  {dashboard.top_opportunities.map((r: any) => (
                    <div key={r.id} className="flex items-start gap-2 rounded-lg bg-[#F0FDF4] px-3 py-2">
                      <TrendingUp className="mt-0.5 h-3 w-3 shrink-0 text-[#38B88A]" />
                      <div className="min-w-0 flex-1">
                        <p className="text-[0.7rem] font-medium text-[#111827]">{r.title}</p>
                        <p className="text-[0.6rem] text-[#6B7280]">
                          {r.estimated_cost_savings && `Cost: ${r.estimated_cost_savings}`}
                          {r.estimated_time_savings && r.estimated_cost_savings && " | "}
                          {r.estimated_time_savings && `Time: ${r.estimated_time_savings}`}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </motion.div>
        )}

        {/* Categories (overview only) */}
        {activeTab === "overview" && !showHistory && categories && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="rounded-xl border border-[#E8EDF3] bg-white p-4">
            <h3 className="mb-3 text-sm font-bold text-[#111827]">Recommendations by Category</h3>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {categories.filter(c => c.count > 0).map((cat) => (
                <button key={cat.category} onClick={() => setFilterCategory(cat.category)}
                  className={`flex items-center justify-between rounded-lg border px-3 py-2 text-left transition-all ${
                    filterCategory === cat.category ? "border-[#38B88A] bg-[#F0FDF4]" : "border-[#E8EDF3] hover:bg-[#FAFBFC]"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <div className={`h-2.5 w-2.5 rounded-full ${CATEGORY_COLORS[cat.category] || "bg-gray-400"}`} />
                    <span className="text-[0.7rem] font-medium text-[#111827]">{CATEGORY_LABELS[cat.category] || cat.category}</span>
                  </div>
                  <span className="text-sm font-bold text-[#6B7280]">{cat.count}</span>
                </button>
              ))}
            </div>
          </motion.div>
        )}

        {/* Recommendations / History List */}
        {showHistory ? (
          <div className="space-y-3">
            <h3 className="text-sm font-bold text-[#6B7280]">Historical Recommendations ({history?.length ?? 0})</h3>
            {history?.length === 0 && (
              <div className="flex flex-col items-center justify-center py-12 text-[#9CA3AF]">
                <Archive className="mb-2 h-8 w-8 opacity-30" />
                <p className="text-[0.78rem]">No dismissed or executed recommendations yet.</p>
              </div>
            )}
            {history?.map((rec) => (
              <RecommendationCard
                key={rec.id}
                rec={rec}
                onDismiss={handleDismiss}
                onExecute={handleExecute}
                expanded={expandedCard === rec.id}
                onToggle={() => setExpandedCard(expandedCard === rec.id ? null : rec.id)}
              />
            ))}
          </div>
        ) : (
          <div className="space-y-3">
            {recsLoading ? (
              <div className="flex items-center justify-center py-12 text-[#6B7280]">
                <Loader2 className="mr-2 h-5 w-5 animate-spin" /> Analyzing platform signals...
              </div>
            ) : filteredRecs.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-[#9CA3AF]">
                <Lightbulb className="mb-2 h-8 w-8 opacity-30" />
                <p className="text-[0.78rem]">No recommendations in this category.</p>
                <p className="text-[0.65rem]">The engine continuously scans — check back when new signals arrive.</p>
              </div>
            ) : (
              <>
                <div className="flex items-center justify-between">
                  <p className="text-[0.7rem] font-medium text-[#6B7280]">
                    {filteredRecs.length} recommendation{filteredRecs.length !== 1 ? "s" : ""}
                    {filterCategory && ` in ${CATEGORY_LABELS[filterCategory] || filterCategory}`}
                    {currentPriority && ` (${currentPriority} priority)`}
                  </p>
                  {dashboard?.last_full_scan && (
                    <p className="text-[0.55rem] text-[#9CA3AF]">Last scan: {new Date(dashboard.last_full_scan).toLocaleString()}</p>
                  )}
                </div>
                {filteredRecs.map((rec) => (
                  <RecommendationCard
                    key={rec.id}
                    rec={rec}
                    onDismiss={handleDismiss}
                    onExecute={handleExecute}
                    expanded={expandedCard === rec.id}
                    onToggle={() => setExpandedCard(expandedCard === rec.id ? null : rec.id)}
                  />
                ))}
              </>
            )}
          </div>
        )}
      </div>
    </CortexShell>
  )
}
