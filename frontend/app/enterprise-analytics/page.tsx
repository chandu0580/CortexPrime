"use client"

import { useState } from "react"
import { motion } from "framer-motion"
import CortexShell from "@/components/layout/CortexShell"
import { stagger, variants } from "@/lib/motion-tokens"
import {
  useAnalyticsDashboard,
  useMetrics,
  useMetricSummary,
  useTrends,
  useReportList,
  useGenerateReport,
} from "@/hooks/queries/enterprise/useEnterpriseAnalytics"
import {
  Activity,
  BarChart3,
  ChevronDown,
  ChevronRight,
  FileText,
  Loader2,
  Plus,
  TrendingDown,
  TrendingUp,
  Zap,
} from "lucide-react"
import { TrendItem } from "@/services/enterprise/analytics"

function TrendIcon({ direction }: { direction: string }) {
  if (direction === "improving") return <TrendingUp className="h-3.5 w-3.5 text-[#38B88A]" />
  if (direction === "declining") return <TrendingDown className="h-3.5 w-3.5 text-red-500" />
  return <Activity className="h-3.5 w-3.5 text-gray-400" />
}

export default function EnterpriseAnalyticsCenter() {
  const [activeTab, setActiveTab] = useState("dashboard")
  const [showGenerate, setShowGenerate] = useState(false)
  const [reportTitle, setReportTitle] = useState("")
  const [reportTimeRange, setReportTimeRange] = useState("7d")

  const { data: dashboard } = useAnalyticsDashboard()
  const { data: summaries } = useMetricSummary()
  const { data: trends } = useTrends()
  const { data: reports } = useReportList()
  const generateMutation = useGenerateReport()

  const handleGenerate = async () => {
    if (!reportTitle) return
    try {
      await generateMutation.mutateAsync({ title: reportTitle, time_range: reportTimeRange })
      setReportTitle("")
      setShowGenerate(false)
    } catch (err) { console.error(err) }
  }

  const tabs = [
    { id: "dashboard", label: "Dashboard", icon: BarChart3 },
    { id: "metrics", label: "Metrics", icon: Activity },
    { id: "trends", label: "Trends", icon: TrendingUp },
    { id: "reports", label: "Reports", icon: FileText },
  ]

  return (
    <CortexShell title="Advanced Analytics" subtitle="Engineering velocity, quality trends, and failure pattern analysis">
      <div className="relative z-10 mx-auto max-w-7xl space-y-6">
        {/* Dashboard Tab */}
        {activeTab === "dashboard" && (
          <motion.div initial="hidden" animate="visible" variants={stagger(0.04, 0.01)} className="space-y-6">
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {[
                { icon: BarChart3, label: "Total Metrics", value: dashboard?.total_metrics ?? "-", color: "bg-blue-500" },
                { icon: FileText, label: "Reports", value: dashboard?.total_reports ?? "-", color: "bg-[#38B88A]" },
                { icon: TrendingUp, label: "Trends Detected", value: dashboard?.recent_trends?.length ?? "-", color: "bg-purple-500" },
                { icon: Zap, label: "Metric Types", value: Object.keys(dashboard?.metrics_by_type ?? {}).length ?? "-", color: "bg-amber-500" },
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
            </div>

            {dashboard?.metrics_by_type && Object.keys(dashboard.metrics_by_type).length > 0 && (
              <div className="rounded-xl border border-[#E8EDF3] bg-white p-5">
                <h3 className="mb-3 text-sm font-bold text-[#111827]">Metrics by Type</h3>
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {Object.entries(dashboard.metrics_by_type).map(([type, count]) => (
                    <div key={type} className="flex items-center justify-between rounded-lg bg-[#FAFBFC] px-3 py-2">
                      <span className="text-[0.65rem] font-medium text-[#6B7280] capitalize">{type}</span>
                      <span className="text-sm font-bold text-[#111827]">{count}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {dashboard?.latest_metrics && dashboard.latest_metrics.length > 0 && (
              <div className="rounded-xl border border-[#E8EDF3] bg-white p-5">
                <h3 className="mb-3 text-sm font-bold text-[#111827]">Latest Metrics</h3>
                <div className="space-y-2">
                  {dashboard.latest_metrics.slice(-5).reverse().map((m) => (
                    <div key={m.id} className="flex items-center justify-between rounded-lg border border-[#E8EDF3] px-3 py-2">
                      <div>
                        <span className="text-[0.6rem] font-medium text-[#111827]">{m.name}</span>
                        <span className="ml-2 text-[0.5rem] text-[#9CA3AF]">({m.metric_type})</span>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className="text-sm font-bold text-[#111827]">{m.value}</span>
                        <span className="text-[0.5rem] text-[#9CA3AF]">{m.unit}</span>
                        <span className="text-[0.5rem] text-[#9CA3AF]">{new Date(m.timestamp).toLocaleTimeString()}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </motion.div>
        )}

        {/* Metrics Tab */}
        {activeTab === "metrics" && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {summaries && Object.entries(summaries).map(([name, summary]) => (
              <div key={name} className="rounded-xl border border-[#E8EDF3] bg-white p-4">
                <h3 className="mb-1 text-[0.78rem] font-bold text-[#111827] capitalize">{name.replace(/_/g, " ")}</h3>
                <div className="space-y-1 text-[0.6rem] text-[#6B7280]">
                  <div className="flex justify-between"><span>Count</span><span className="font-medium text-[#111827]">{summary.count}</span></div>
                  <div className="flex justify-between"><span>Average</span><span className="font-medium text-[#111827]">{summary.avg}</span></div>
                  <div className="flex justify-between"><span>Min</span><span className="font-medium text-[#111827]">{summary.min}</span></div>
                  <div className="flex justify-between"><span>Max</span><span className="font-medium text-[#111827]">{summary.max}</span></div>
                  <div className="flex justify-between"><span>Latest</span><span className="font-medium text-[#111827]">{summary.latest}</span></div>
                </div>
              </div>
            ))}
            {(!summaries || Object.keys(summaries).length === 0) && (
              <div className="col-span-full flex flex-col items-center rounded-xl border border-[#E8EDF3] bg-white py-16 text-[#9CA3AF]">
                <Activity className="mb-3 h-10 w-10 opacity-30" />
                <p className="text-sm">No metrics recorded yet.</p>
              </div>
            )}
          </motion.div>
        )}

        {/* Trends Tab */}
        {activeTab === "trends" && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-3">
            {trends?.map((trend, i) => (
              <div key={i} className="flex items-center gap-4 rounded-xl border border-[#E8EDF3] bg-white p-4">
                <TrendIcon direction={trend.direction} />
                <div className="min-w-0 flex-1">
                  <p className="text-[0.72rem] font-medium text-[#111827] capitalize">{trend.metric_name.replace(/_/g, " ")}</p>
                  <p className="text-[0.55rem] text-[#6B7280]">{trend.metric_type} &middot; Window: {trend.window}</p>
                </div>
                <div className="text-right">
                  <p className={`text-sm font-bold ${trend.direction === "improving" ? "text-[#38B88A]" : trend.direction === "declining" ? "text-red-500" : "text-gray-400"}`}>
                    {trend.change_pct > 0 ? "+" : ""}{trend.change_pct}%
                  </p>
                  <p className="text-[0.5rem] text-[#9CA3AF] capitalize">{trend.direction}</p>
                </div>
              </div>
            ))}
            {(!trends || trends.length === 0) && (
              <div className="flex flex-col items-center rounded-xl border border-[#E8EDF3] bg-white py-16 text-[#9CA3AF]">
                <TrendingUp className="mb-3 h-10 w-10 opacity-30" />
                <p className="text-sm">No trends detected yet. More data needed.</p>
              </div>
            )}
          </motion.div>
        )}

        {/* Reports Tab */}
        {activeTab === "reports" && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
            <div className="flex justify-end">
              <button onClick={() => setShowGenerate(!showGenerate)}
                className="flex items-center gap-1.5 rounded-lg border border-[#38B88A]/30 px-3 py-1.5 text-[0.65rem] font-medium text-[#38B88A] hover:bg-[#F0FDF4]">
                <Plus className="h-3.5 w-3.5" /> Generate Report
              </button>
            </div>
            {showGenerate && (
              <div className="rounded-xl border border-[#38B88A]/30 bg-[#F0FDF4] p-4">
                <h3 className="mb-3 text-sm font-bold text-[#111827]">Generate Analytics Report</h3>
                <div className="flex flex-wrap gap-3">
                  <input value={reportTitle} onChange={e => setReportTitle(e.target.value)} placeholder="Report title"
                    className="min-w-[200px] rounded-lg border border-[#E8EDF3] px-3 py-2 text-[0.78rem] outline-none" />
                  <select value={reportTimeRange} onChange={e => setReportTimeRange(e.target.value)}
                    className="rounded-lg border border-[#E8EDF3] px-3 py-2 text-[0.78rem] outline-none">
                    <option value="24h">Last 24 hours</option>
                    <option value="7d">Last 7 days</option>
                    <option value="30d">Last 30 days</option>
                    <option value="90d">Last 90 days</option>
                  </select>
                  <button onClick={handleGenerate} disabled={!reportTitle || generateMutation.isPending}
                    className="flex items-center gap-2 rounded-lg bg-[#38B88A] px-4 py-2 text-[0.72rem] font-bold text-white disabled:opacity-50">
                    {generateMutation.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />}
                    Generate
                  </button>
                </div>
              </div>
            )}
            <div className="space-y-3">
              {reports?.map((report) => (
                <div key={report.id} className="rounded-xl border border-[#E8EDF3] bg-white p-4">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <h3 className="text-[0.82rem] font-bold text-[#111827]">{report.title}</h3>
                      <div className="mt-1 flex flex-wrap items-center gap-3 text-[0.55rem] text-[#6B7280]">
                        <span className="rounded bg-[#F4F7FA] px-1.5 py-0.5">{report.type}</span>
                        <span>Range: {report.time_range}</span>
                        <span>Metrics: {report.metrics_count}</span>
                        <span>Sections: {Object.keys(report.sections).length}</span>
                      </div>
                    </div>
                    <span className="shrink-0 text-[0.5rem] text-[#9CA3AF]">{new Date(report.generated_at).toLocaleDateString()}</span>
                  </div>
                </div>
              ))}
              {(!reports || reports.length === 0) && (
                <div className="flex flex-col items-center rounded-xl border border-[#E8EDF3] bg-white py-16 text-[#9CA3AF]">
                  <FileText className="mb-3 h-10 w-10 opacity-30" />
                  <p className="text-sm">No reports generated yet.</p>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </div>
    </CortexShell>
  )
}
