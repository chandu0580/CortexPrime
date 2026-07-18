"use client"
import { useState } from "react"
import { motion } from "framer-motion"
import CortexShell from "@/components/layout/CortexShell"
import { stagger, variants } from "@/lib/motion-tokens"
import {
  useRcaDashboard,
  useRcaAnalyses,
  useRcaIncidents,
  useRunAnalysis,
} from "@/hooks/queries/enterprise/useEnterpriseRca"
import {
  Activity, CheckCircle, XCircle, Clock, Loader2, AlertTriangle, Zap,
  Search, TrendingUp, TrendingDown, Minus, Brain, GitBranch, Layers,
  Box, Server, FileText, Radio, Network, Shield, BarChart3, Cpu,
  ArrowRight, ExternalLink, BookOpen, Lightbulb,
} from "lucide-react"

const tabs = ["Incidents", "Timeline", "Evidence", "Correlations", "Root Cause", "Recommendations", "Story"]

function StatusBadge({ status }: { status?: string }) {
  const s = (status || "").toLowerCase()
  if (s === "passed" || s === "success" || s === "completed" || s === "healthy" || s === "ok" || s === "resolved" || s === "available" || s === "bound")
    return <span className="inline-flex items-center gap-1 text-xs font-medium text-green-600 dark:text-green-400"><CheckCircle size={12} />{status}</span>
  if (s === "failed" || s === "firing" || s === "error" || s === "crashloop" || s === "oom" || s === "unavailable" || s === "degraded" || s === "unresolved" || s === "rollback")
    return <span className="inline-flex items-center gap-1 text-xs font-medium text-red-600 dark:text-red-400"><XCircle size={12} />{status}</span>
  if (s === "running" || s === "pending" || s === "in_progress" || s === "progressing")
    return <span className="inline-flex items-center gap-1 text-xs font-medium text-yellow-600 dark:text-yellow-400"><Clock size={12} />{status}</span>
  return <span className="inline-flex items-center gap-1 text-xs font-medium text-gray-500 dark:text-gray-400"><Activity size={12} />{status || "unknown"}</span>
}

function KpiCard({ icon: Icon, label, value, color, sub }: { icon: any; label: string; value: number | string; color: string; sub?: string }) {
  return (
    <motion.div variants={variants.fadeIn} className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">{label}</p>
          <p className="text-2xl font-bold text-gray-900 dark:text-white mt-1">{value}</p>
          {sub && <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">{sub}</p>}
        </div>
        <div className="p-3 rounded-lg bg-gray-100 dark:bg-gray-700">
          <Icon size={24} className={color} />
        </div>
      </div>
    </motion.div>
  )
}

function SectionCard({ title, icon: Icon, iconColor, children }: { title: string; icon: any; iconColor: string; children: React.ReactNode }) {
  return (
    <motion.div variants={variants.fadeIn} className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-6">
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
        <Icon size={18} className={iconColor} />
        {title}
      </h3>
      {children}
    </motion.div>
  )
}

function ConfidenceBadge({ score }: { score: number }) {
  const label = score >= 0.8 ? "Very High" : score >= 0.6 ? "High" : score >= 0.4 ? "Medium" : score >= 0.2 ? "Low" : "Very Low"
  const color = score >= 0.8 ? "text-green-600 bg-green-100 dark:bg-green-900/30" :
                score >= 0.6 ? "text-blue-600 bg-blue-100 dark:bg-blue-900/30" :
                score >= 0.4 ? "text-yellow-600 bg-yellow-100 dark:bg-yellow-900/30" :
                "text-red-600 bg-red-100 dark:bg-red-900/30"
  return <span className={`px-2 py-0.5 rounded text-xs font-medium ${color}`}>{label} ({Math.round(score * 100)}%)</span>
}

export default function EnterpriseRcaCenter() {
  const [activeTab, setActiveTab] = useState("Incidents")
  const [simProblem, setSimProblem] = useState("Production incident — elevated error rate and pod crashes after deployment")
  const [simHours, setSimHours] = useState("24")

  const { data: dashboard } = useRcaDashboard()
  const { data: analyses } = useRcaAnalyses()
  const { data: incidents } = useRcaIncidents()
  const runAnalysisMut = useRunAnalysis()
  const [analysisResult, setAnalysisResult] = useState<any>(null)

  const ds = dashboard || {} as any
  const handleRunAnalysis = async () => {
    try {
      const result = await runAnalysisMut.mutateAsync({
        problem: simProblem,
        hours_back: parseInt(simHours) || 24,
      })
      setAnalysisResult(result)
    } catch {}
  }

  return (
    <CortexShell
      title="Enterprise RCA Center"
      subtitle="Root cause analysis — correlates GitHub, CI/CD, Kubernetes, Prometheus, Loki, and OpenTelemetry"
    >
      <motion.div initial="hidden" animate="visible" variants={stagger(0.04, 0.01)} className="space-y-6">
        {/* Tabs */}
        <div className="flex flex-wrap gap-2 border-b border-gray-200 dark:border-gray-700 pb-2">
          {tabs.map((tab) => (
            <button key={tab} onClick={() => setActiveTab(tab)}
              className={`px-4 py-2 text-sm font-medium rounded-t-lg transition-colors ${
                activeTab === tab
                  ? "text-blue-600 dark:text-blue-400 border-b-2 border-blue-600 dark:border-blue-400"
                  : "text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300"
              }`}>{tab}</button>
          ))}
        </div>

        {/* INCIDENTS TAB */}
        {activeTab === "Incidents" && (
          <div className="space-y-6">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <KpiCard icon={AlertTriangle} label="Analyses" value={ds.total_analyses || 0} color="text-red-600" />
              <KpiCard icon={Activity} label="Incidents" value={ds.total_incidents || 0} color="text-orange-600" />
              <KpiCard icon={BarChart3} label="Avg Confidence" value={ds.total_analyses ? `${Math.round((ds.avg_confidence || 0) * 100)}%` : "-"} color="text-blue-600" />
              <KpiCard icon={Brain} label="Top Causes" value={ds.top_root_causes?.length || 0} color="text-purple-600" />
            </div>

            {/* Simulator */}
            <SectionCard title="Run RCA Analysis" icon={Zap} iconColor="text-yellow-500">
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                <div className="lg:col-span-2">
                  <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Problem Description</label>
                  <textarea value={simProblem} onChange={(e) => setSimProblem(e.target.value)} rows={3}
                    className="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-900 p-3 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500" />
                </div>
                <div className="space-y-2">
                  <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Time Window (hours)</label>
                  <select value={simHours} onChange={(e) => setSimHours(e.target.value)}
                    className="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-900 p-2 text-sm text-gray-900 dark:text-gray-100">
                    <option value="1">1 hour</option>
                    <option value="6">6 hours</option>
                    <option value="12">12 hours</option>
                    <option value="24">24 hours</option>
                    <option value="48">48 hours</option>
                    <option value="168">7 days</option>
                  </select>
                  <button onClick={handleRunAnalysis} disabled={runAnalysisMut.isPending}
                    className="w-full flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
                    {runAnalysisMut.isPending ? <Loader2 size={16} className="animate-spin" /> : <Brain size={16} />}
                    Run Analysis
                  </button>
                </div>
              </div>
            </SectionCard>

            {analysisResult && (
              <SectionCard title="Latest Analysis Result" icon={Brain} iconColor="text-purple-500">
                <div className="space-y-3">
                  <div className="flex items-center gap-3 flex-wrap">
                    <span className="text-sm font-semibold text-gray-900 dark:text-white">{analysisResult.problem}</span>
                    <ConfidenceBadge score={analysisResult.summary?.confidence_score || 0} />
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    <div className="p-2 rounded bg-gray-50 dark:bg-gray-900 text-center">
                      <p className="text-xs text-gray-500">Timeline Events</p>
                      <p className="text-lg font-bold text-gray-900 dark:text-white">{analysisResult.summary?.total_events_in_timeline || 0}</p>
                    </div>
                    <div className="p-2 rounded bg-gray-50 dark:bg-gray-900 text-center">
                      <p className="text-xs text-gray-500">Hypotheses</p>
                      <p className="text-lg font-bold text-gray-900 dark:text-white">{analysisResult.summary?.total_hypotheses || 0}</p>
                    </div>
                    <div className="p-2 rounded bg-gray-50 dark:bg-gray-900 text-center">
                      <p className="text-xs text-gray-500">Services Affected</p>
                      <p className="text-lg font-bold text-gray-900 dark:text-white">{analysisResult.summary?.affected_services_count || 0}</p>
                    </div>
                    <div className="p-2 rounded bg-gray-50 dark:bg-gray-900 text-center">
                      <p className="text-xs text-gray-500">Deployments Affected</p>
                      <p className="text-lg font-bold text-gray-900 dark:text-white">{analysisResult.summary?.affected_deployments_count || 0}</p>
                    </div>
                  </div>
                  {analysisResult.top_hypothesis && (
                    <div className="p-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800">
                      <p className="text-sm font-semibold text-red-800 dark:text-red-200">Root Cause</p>
                      <p className="text-sm text-red-700 dark:text-red-300 mt-1">{analysisResult.top_hypothesis.root_cause}</p>
                    </div>
                  )}
                </div>
              </SectionCard>
            )}

            {/* Incidents table */}
            <SectionCard title="Incidents" icon={AlertTriangle} iconColor="text-red-500">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead><tr className="border-b border-gray-200 dark:border-gray-700">
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Problem</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Root Cause</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Confidence</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Time</th>
                  </tr></thead>
                  <tbody>{(incidents?.incidents || []).length === 0 && (analysisResult ? (() => {
                    const ar = analysisResult
                    return (
                      <tr key={ar.incident_id} className="border-b border-gray-100 dark:border-gray-700/50 hover:bg-gray-50 dark:hover:bg-gray-700/30">
                        <td className="py-2 px-3 font-medium text-gray-900 dark:text-white max-w-xs truncate">{ar.problem?.slice(0, 80)}</td>
                        <td className="py-2 px-3 text-gray-600 dark:text-gray-400 max-w-xs truncate">{ar.summary?.top_root_cause || "-"}</td>
                        <td className="py-2 px-3"><ConfidenceBadge score={ar.summary?.confidence_score || 0} /></td>
                        <td className="py-2 px-3 text-xs text-gray-500">{new Date(ar.timestamp || Date.now()).toLocaleString()}</td>
                      </tr>
                    )
                  })() : (
                    <tr><td colSpan={4} className="text-center py-8 text-sm text-gray-500">No incidents yet — run an analysis</td></tr>
                  ))}
                  {(incidents?.incidents || []).slice(0, analysisResult ? 19 : 20).map((inc: any) => (
                    <tr key={inc.incident_id} className="border-b border-gray-100 dark:border-gray-700/50 hover:bg-gray-50 dark:hover:bg-gray-700/30">
                      <td className="py-2 px-3 font-medium text-gray-900 dark:text-white max-w-xs truncate">{inc.problem?.slice(0, 80)}</td>
                      <td className="py-2 px-3 text-gray-600 dark:text-gray-400 max-w-xs truncate">{inc.root_cause || "-"}</td>
                      <td className="py-2 px-3"><ConfidenceBadge score={inc.confidence || 0} /></td>
                      <td className="py-2 px-3 text-xs text-gray-500">{new Date(inc.timestamp || Date.now()).toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
                </table>
              </div>
            </SectionCard>

            {/* Top root causes */}
            {ds.top_root_causes?.length > 0 && (
              <SectionCard title="Top Root Causes" icon={BarChart3} iconColor="text-purple-500">
                <div className="flex flex-wrap gap-3">
                  {ds.top_root_causes.map((c: any, i: number) => (
                    <div key={i} className="px-3 py-2 rounded-lg bg-purple-50 dark:bg-purple-900/20 border border-purple-200 dark:border-purple-800">
                      <span className="text-xs font-medium text-purple-700 dark:text-purple-300">{c.cause?.slice(0, 60)}</span>
                      <span className="ml-2 text-sm font-bold text-purple-600 dark:text-purple-400">{c.count}</span>
                    </div>
                  ))}
                </div>
              </SectionCard>
            )}
          </div>
        )}

        {/* TIMELINE TAB */}
        {activeTab === "Timeline" && (
          <div className="space-y-4">
            <SectionCard title="Event Timeline" icon={Activity} iconColor="text-blue-500">
              {(analysisResult?.timeline || []).length === 0 ? (
                <p className="text-sm text-gray-500 dark:text-gray-400 text-center py-8">Run an analysis to see the timeline</p>
              ) : (
                <div className="space-y-1 max-h-[600px] overflow-y-auto">
                  {(analysisResult?.timeline || []).map((entry: any, i: number) => (
                    <div key={i} className="flex items-center gap-3 p-2 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700/50">
                      <div className={`p-1.5 rounded-full ${
                        entry.source === "github" ? "bg-gray-100 dark:bg-gray-700" :
                        entry.source === "cicd" ? "bg-blue-100 dark:bg-blue-900/30" :
                        entry.source === "infrastructure" ? "bg-green-100 dark:bg-green-900/30" :
                        entry.source === "prometheus" ? "bg-red-100 dark:bg-red-900/30" :
                        entry.source === "loki" ? "bg-yellow-100 dark:bg-yellow-900/30" :
                        entry.source === "opentelemetry" ? "bg-purple-100 dark:bg-purple-900/30" :
                        "bg-gray-100 dark:bg-gray-700"
                      }`}>
                        {entry.source === "github" ? <GitBranch size={12} /> :
                         entry.source === "cicd" ? <Layers size={12} /> :
                         entry.source === "infrastructure" ? <Server size={12} /> :
                         entry.source === "prometheus" ? <Activity size={12} /> :
                         entry.source === "loki" ? <FileText size={12} /> :
                         entry.source === "opentelemetry" ? <Radio size={12} /> :
                         <Activity size={12} />}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-900 dark:text-white truncate">{entry.name}</p>
                        <p className="text-xs text-gray-500 dark:text-gray-400">{entry.source} · {entry.type}</p>
                      </div>
                      <StatusBadge status={entry.status} />
                      <span className="text-xs text-gray-400 dark:text-gray-500 shrink-0">{new Date(entry.timestamp || Date.now()).toLocaleTimeString()}</span>
                    </div>
                  ))}
                </div>
              )}
            </SectionCard>
          </div>
        )}

        {/* EVIDENCE TAB */}
        {activeTab === "Evidence" && (
          <div className="space-y-4">
            {(!analysisResult?.evidence || Object.keys(analysisResult.evidence).length === 0) ? (
              <p className="text-sm text-gray-500 dark:text-gray-400 text-center py-8">Run an analysis to collect evidence</p>
            ) : (
              Object.entries(analysisResult.evidence).map(([key, val]: [string, any]) => (
                <SectionCard key={key} title={key.charAt(0).toUpperCase() + key.slice(1)} icon={Shield} iconColor="text-green-500">
                  {key === "pods" && (
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
                      <div className="text-center p-2 rounded bg-gray-50 dark:bg-gray-900"><span className="text-xs text-gray-500">Error</span><p className="text-lg font-bold text-red-600">{val.error_pods}</p></div>
                      <div className="text-center p-2 rounded bg-gray-50 dark:bg-gray-900"><span className="text-xs text-gray-500">OOM</span><p className="text-lg font-bold text-red-600">{val.oom_pods}</p></div>
                      <div className="text-center p-2 rounded bg-gray-50 dark:bg-gray-900"><span className="text-xs text-gray-500">CrashLoop</span><p className="text-lg font-bold text-red-600">{val.crashloop_pods}</p></div>
                      <div className="text-center p-2 rounded bg-gray-50 dark:bg-gray-900"><span className="text-xs text-gray-500">Total</span><p className="text-lg font-bold">{val.total_pods}</p></div>
                    </div>
                  )}
                  {key === "deployments" && (
                    <div className="grid grid-cols-3 gap-3 mb-3">
                      <div className="text-center p-2 rounded bg-gray-50 dark:bg-gray-900"><span className="text-xs text-gray-500">Rollbacks</span><p className="text-lg font-bold text-red-600">{val.rollbacks}</p></div>
                      <div className="text-center p-2 rounded bg-gray-50 dark:bg-gray-900"><span className="text-xs text-gray-500">Unavailable</span><p className="text-lg font-bold text-red-600">{val.unavailable}</p></div>
                      <div className="text-center p-2 rounded bg-gray-50 dark:bg-gray-900"><span className="text-xs text-gray-500">Total</span><p className="text-lg font-bold">{val.total_deployments}</p></div>
                    </div>
                  )}
                  {key === "alerts" && (
                    <div><p className="text-lg font-bold text-red-600">{val.total_firing_alerts} firing alerts</p></div>
                  )}
                  {key === "logs" && (
                    <div><p className="text-lg font-bold text-yellow-600">{val.total_log_streams_with_errors} streams with errors</p></div>
                  )}
                  {key === "traces" && (
                    <div><p className="text-lg font-bold text-purple-600">{val.total_traces_with_errors} traces with errors</p></div>
                  )}
                  {key === "network" && (
                    <div><p className="text-lg font-bold text-orange-600">{val.total_unresolved_failures} unresolved failures</p></div>
                  )}
                </SectionCard>
              ))
            )}
          </div>
        )}

        {/* CORRELATIONS TAB */}
        {activeTab === "Correlations" && (
          <div className="space-y-4">
            {(!analysisResult?.correlations || Object.keys(analysisResult.correlations).length === 0) ? (
              <p className="text-sm text-gray-500 dark:text-gray-400 text-center py-8">Run an analysis to see correlations</p>
            ) : (
              Object.entries(analysisResult.correlations).map(([key, val]: [string, any]) => (
                <SectionCard key={key} title={key.replace(/_/g, " ").replace("loki", "Loki").replace("k8s", "Kubernetes").replace("cicd", "CI/CD").replace("prometheus", "Prometheus")} icon={Network} iconColor="text-blue-500">
                  {(val || []).length === 0 ? (
                    <p className="text-sm text-gray-500">No correlations found</p>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead><tr className="border-b border-gray-200 dark:border-gray-700">
                          {Object.keys(val[0] || {}).map((k) => (
                            <th key={k} className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">{k.replace(/_/g, " ")}</th>
                          ))}
                        </tr></thead>
                        <tbody>
                          {(val || []).slice(0, 10).map((item: any, i: number) => (
                            <tr key={i} className="border-b border-gray-100 dark:border-gray-700/50 hover:bg-gray-50 dark:hover:bg-gray-700/30">
                              {Object.values(item).slice(0, 6).map((v: any, j: number) => (
                                <td key={j} className="py-2 px-3 text-gray-600 dark:text-gray-400 text-xs">{typeof v === 'boolean' ? String(v) : typeof v === 'object' ? JSON.stringify(v).slice(0, 40) : String(v).slice(0, 30)}</td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </SectionCard>
              ))
            )}
          </div>
        )}

        {/* ROOT CAUSE TAB */}
        {activeTab === "Root Cause" && (
          <div className="space-y-4">
            {!analysisResult?.top_hypothesis ? (
              <p className="text-sm text-gray-500 dark:text-gray-400 text-center py-8">Run an analysis to identify root cause</p>
            ) : (
              <>
                <SectionCard title="Top Hypothesis" icon={Brain} iconColor="text-purple-500">
                  <div className="p-4 rounded-lg bg-purple-50 dark:bg-purple-900/20 border border-purple-200 dark:border-purple-800">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-semibold text-purple-800 dark:text-purple-200">{analysisResult.top_hypothesis.pattern_id}</span>
                      <ConfidenceBadge score={analysisResult.top_hypothesis.confidence || 0} />
                    </div>
                    <p className="text-lg font-bold text-purple-700 dark:text-purple-300 mb-2">{analysisResult.top_hypothesis.root_cause}</p>
                    <p className="text-sm text-purple-600 dark:text-purple-400">{analysisResult.top_hypothesis.description}</p>
                    <div className="mt-3 flex gap-2">
                      <span className="px-2 py-0.5 rounded text-xs font-medium bg-purple-200 dark:bg-purple-800 text-purple-700 dark:text-purple-300">{analysisResult.top_hypothesis.category}</span>
                      <span className="px-2 py-0.5 rounded text-xs font-medium bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300">{analysisResult.top_hypothesis.matching_event_count} matching events</span>
                    </div>
                  </div>
                </SectionCard>

                <SectionCard title="All Hypotheses" icon={BarChart3} iconColor="text-blue-500">
                  <div className="space-y-3">
                    {(analysisResult.hypotheses || []).map((h: any, i: number) => (
                      <div key={h.hypothesis_id} className={`p-3 rounded-lg border ${i === 0 ? 'border-purple-300 dark:border-purple-700 bg-purple-50 dark:bg-purple-900/20' : 'border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900'}`}>
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-sm font-medium text-gray-900 dark:text-white">{h.root_cause}</span>
                          {h.confidence != null && <ConfidenceBadge score={h.confidence} />}
                        </div>
                        <p className="text-xs text-gray-500 dark:text-gray-400">{h.description}</p>
                        <div className="flex gap-2 mt-2">
                          <span className="px-2 py-0.5 rounded text-xs bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300">{h.category}</span>
                          <span className="px-2 py-0.5 rounded text-xs bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-400">{h.matching_event_count} events</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </SectionCard>
              </>
            )}
          </div>
        )}

        {/* RECOMMENDATIONS TAB */}
        {activeTab === "Recommendations" && (
          <div className="space-y-4">
            {!analysisResult ? (
              <p className="text-sm text-gray-500 dark:text-gray-400 text-center py-8">Run an analysis to get recommendations</p>
            ) : (
              <>
                <SectionCard title="Recovery Actions" icon={Lightbulb} iconColor="text-yellow-500">
                  {(analysisResult.recovery_actions || []).length === 0 ? (
                    <p className="text-sm text-gray-500">No recovery actions identified</p>
                  ) : (
                    <ul className="space-y-2">
                      {(analysisResult.recovery_actions || []).map((action: string, i: number) => (
                        <li key={i} className="flex items-start gap-3 p-3 rounded-lg bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700">
                          <ArrowRight size={16} className="text-blue-500 mt-0.5 shrink-0" />
                          <span className="text-sm text-gray-900 dark:text-white">{action}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </SectionCard>

                {analysisResult.impact && (
                  <SectionCard title="Impact Analysis" icon={AlertTriangle} iconColor="text-orange-500">
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                      {Object.entries(analysisResult.impact).map(([key, val]: [string, any]) => (
                        <div key={key} className="p-3 rounded-lg bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700">
                          <p className="text-xs text-gray-500 uppercase mb-1">{key.replace("affected_", "").replace(/_/g, " ")}</p>
                          <p className="text-xl font-bold text-gray-900 dark:text-white">{(val || []).length}</p>
                          {(val || []).length > 0 && (
                            <div className="mt-1 text-xs text-gray-600 dark:text-gray-400 truncate">
                              {(val || []).slice(0, 3).join(", ")}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </SectionCard>
                )}
              </>
            )}
          </div>
        )}

        {/* STORY TAB */}
        {activeTab === "Story" && (
          <div className="space-y-4">
            {!analysisResult?.story ? (
              <p className="text-sm text-gray-500 dark:text-gray-400 text-center py-8">Run an analysis to generate an engineering story</p>
            ) : (
              <SectionCard title="Engineering Story" icon={BookOpen} iconColor="text-green-500">
                <div className="bg-gray-900 rounded-lg p-6 max-h-[600px] overflow-y-auto">
                  <div className="prose prose-sm prose-invert max-w-none text-gray-300 whitespace-pre-wrap font-mono text-xs leading-relaxed">
                    {analysisResult.story.story}
                  </div>
                </div>
                <div className="flex items-center gap-3 mt-4">
                  <span className="text-xs text-gray-500">Confidence: </span>
                  <ConfidenceBadge score={analysisResult.story.confidence_score || 0} />
                  <span className="text-xs text-gray-500 ml-2">Generated: {new Date(analysisResult.story.generated_at || Date.now()).toLocaleString()}</span>
                </div>
              </SectionCard>
            )}
          </div>
        )}
      </motion.div>
    </CortexShell>
  )
}
