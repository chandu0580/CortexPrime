"use client"
import { useState } from "react"
import { motion } from "framer-motion"
import CortexShell from "@/components/layout/CortexShell"
import { stagger, variants } from "@/lib/motion-tokens"
import {
  useInfraDashboard,
  useInfraTimeline,
  useInfraClusters,
  useInfraPods,
  useInfraPodHealth,
  useInfraNodes,
  useInfraNodeUtilization,
  useInfraDeployments,
  useInfraDeploymentHealth,
  useInfraPvcs,
  useInfraNetworkFailures,
  useInfraDockerContainers,
  useInfraDockerHealth,
  useInfraDockerImages,
  useInfraDockerVolumes,
  useInfraDockerNetworks,
  useInfraHelmReleases,
  useInfraHelmHealth,
  useInfraPrometheusAlerts,
  useInfraPrometheusStats,
  useInfraCorrelatedAlerts,
  useInfraGrafanaDashboards,
  useInfraLokiAnalyses,
  useInfraTraces,
  useInfraTraceHealth,
  useInfraTraceGraph,
  useInfraServiceGraphHealth,
  useOtelServices,
  useInfraPlatforms,
  useInfraSync,
  useDockerSync,
  usePrometheusTargets,
  usePrometheusLiveAlerts,
  usePrometheusMetricsSnapshot,
  usePrometheusCollect,
  usePrometheusSyncAlerts,
  useLokiLabels,
  useLokiStreams,
  useLokiTargetLogs,
  useLokiQuery,
  useLokiAnalyze,
  useLokiCorrelate,
  useObservability,
  useGrafanaDashboardsReal,
  useGrafanaDatasources,
  useGrafanaFolders,
  useGrafanaAlerts,
  useGrafanaAnnotations,
  useCorrelateFromAlert,
} from "@/hooks/queries/enterprise/useEnterpriseInfrastructure"
import { enterpriseInfraApi } from "@/services/enterprise/infrastructure"
import {
  Activity, CheckCircle, XCircle, Clock, Loader2, AlertTriangle, RefreshCw,
  Server, Container, Box, Hexagon, Shield, BarChart3, Radio,
  Layers, GitBranch, HardDrive, Network, Cpu, Search, Database, Monitor,
  LineChart, FileText, ExternalLink, TrendingUp, TrendingDown, Minus, Folder,
} from "lucide-react"

const tabs = ["Observability", "Cluster", "Pods", "Deployments", "Docker", "Helm", "Metrics", "Logs", "Traces", "Dashboards", "Alerts", "Health"]

function StatusBadge({ status }: { status?: string }) {
  const s = (status || "").toLowerCase()
  if (s === "healthy" || s === "ready" || s === "running" || s === "available" || s === "bound" || s === "deployed" || s === "ok" || s === "completed" || s === "passed")
    return <span className="inline-flex items-center gap-1 text-xs font-medium text-green-600 dark:text-green-400"><CheckCircle size={12} />{status}</span>
  if (s === "degraded" || s === "unavailable" || s === "failed" || s === "error" || s === "crashloop" || s === "oom" || s === "firing")
    return <span className="inline-flex items-center gap-1 text-xs font-medium text-red-600 dark:text-red-400"><XCircle size={12} />{status}</span>
  if (s === "pending" || s === "progressing" || s === "rollback")
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

function SyncSection() {
  const syncMut = useInfraSync()
  const [syncResult, setSyncResult] = useState<string | null>(null)

  return (
    <SectionCard title="Live Kubernetes Sync" icon={RefreshCw} iconColor="text-blue-500">
      <p className="text-sm text-gray-500 dark:text-gray-400 mb-3">
        Pull real-time data from connected Kubernetes clusters.
      </p>
      <div className="flex items-center gap-3">
        <button
          onClick={async () => {
            setSyncResult(null)
            try {
              const res = await syncMut.mutateAsync(undefined)
              const r = res as any
              setSyncResult(`Synced ${r.clusters || 0} clusters, ${r.nodes || 0} nodes, ${r.pods || 0} pods, ${r.deployments || 0} deployments, ${r.pvcs || 0} PVCs`)
            } catch (e: any) {
              setSyncResult(`Sync failed: ${e?.message || "unknown error"}`)
            }
          }}
          disabled={syncMut.isPending}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
        >
          {syncMut.isPending ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
          {syncMut.isPending ? "Syncing..." : "Sync from Cluster"}
        </button>
        {syncResult && (
          <span className={`text-xs ${syncResult.startsWith("Synced") ? "text-green-600" : "text-red-600"}`}>
            {syncResult}
          </span>
        )}
      </div>
    </SectionCard>
  )
}

function DockerSyncSection() {
  const syncMut = useDockerSync()
  const [syncResult, setSyncResult] = useState<string | null>(null)

  return (
    <SectionCard title="Live Docker Sync" icon={RefreshCw} iconColor="text-cyan-500">
      <p className="text-sm text-gray-500 dark:text-gray-400 mb-3">
        Pull real-time containers, images, volumes, and networks from the local Docker engine.
      </p>
      <div className="flex items-center gap-3">
        <button
          onClick={async () => {
            setSyncResult(null)
            try {
              const res = await syncMut.mutateAsync(undefined)
              const r = res as any
              setSyncResult(`Synced ${r.containers || 0} containers, ${r.images || 0} images, ${r.volumes || 0} volumes, ${r.networks || 0} networks`)
            } catch (e: any) {
              setSyncResult(`Sync failed: ${e?.message || "unknown error"}`)
            }
          }}
          disabled={syncMut.isPending}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-cyan-600 text-white text-sm font-medium hover:bg-cyan-700 disabled:opacity-50"
        >
          {syncMut.isPending ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
          {syncMut.isPending ? "Syncing..." : "Sync from Docker Engine"}
        </button>
        {syncResult && (
          <span className={`text-xs ${syncResult.startsWith("Synced") ? "text-green-600" : "text-red-600"}`}>
            {syncResult}
          </span>
        )}
      </div>
    </SectionCard>
  )
}

export default function EnterpriseInfrastructureCenter() {
  const [activeTab, setActiveTab] = useState("Cluster")
  const [lokiQueryStr, setLokiQueryStr] = useState("{namespace!=\"\"}")
  const [lokiQueryResults, setLokiQueryResults] = useState<any[] | null>(null)
  const [lokiAnalyzeResults, setLokiAnalyzeResults] = useState<any | null>(null)
  const [lokiCorrelateResults, setLokiCorrelateResults] = useState<any | null>(null)
  const [lokiTargetType, setLokiTargetType] = useState("pod")
  const [lokiTargetName, setLokiTargetName] = useState("")
  const [lokiTargetMinutes, setLokiTargetMinutes] = useState(15)
  const [lokiAnalyzing, setLokiAnalyzing] = useState(false)

  const { data: dashboard } = useInfraDashboard()
  const { data: timeline } = useInfraTimeline(20)
  const { data: infraPods } = useInfraPods()
  const { data: podHealth } = useInfraPodHealth()
  const { data: infraNodes } = useInfraNodes()
  const { data: nodeUtil } = useInfraNodeUtilization()
  const { data: infraDeployments } = useInfraDeployments()
  const { data: depHealth } = useInfraDeploymentHealth()
  const { data: infraPvcs } = useInfraPvcs()
  const { data: infraNetFailures } = useInfraNetworkFailures()
  const { data: dockerContainers } = useInfraDockerContainers()
  const { data: dockerHealth } = useInfraDockerHealth()
  const { data: dockerImages } = useInfraDockerImages()
  const { data: dockerVolumes } = useInfraDockerVolumes()
  const { data: dockerNetworks } = useInfraDockerNetworks()
  const { data: helmReleases } = useInfraHelmReleases()
  const { data: helmHealth } = useInfraHelmHealth()
  const { data: prometheusStats } = useInfraPrometheusStats()
  const { data: promMetricsSnap } = usePrometheusMetricsSnapshot()
  const { data: promTargets } = usePrometheusTargets()
  const { data: promLiveAlerts } = usePrometheusLiveAlerts()
  const { data: correlAlerts } = useInfraCorrelatedAlerts()
  const { data: grafanaDashboards } = useInfraGrafanaDashboards()
  const { data: lokiAnalyses } = useInfraLokiAnalyses()
  const { data: lokiLabelsData } = useLokiLabels()
  const { data: lokiStreamsData } = useLokiStreams()
  const { data: lokiTargetData } = useLokiTargetLogs(lokiTargetType, lokiTargetName, lokiTargetMinutes)
  const lokiAnalyzeMut = useLokiAnalyze()
  const lokiCorrelateMut = useLokiCorrelate()
  const { data: infraTraces } = useInfraTraces()
  const { data: traceHealth } = useInfraTraceHealth()
  const { data: traceGraph } = useInfraTraceGraph()
  const { data: graphHealth } = useInfraServiceGraphHealth()
  const { data: otelServices } = useOtelServices()
  const { data: infraPlatforms } = useInfraPlatforms()
  const { data: observability } = useObservability()
  const { data: grafanaDsReal } = useGrafanaDatasources()
  const { data: grafanaFolders } = useGrafanaFolders()
  const { data: grafanaAlertsData } = useGrafanaAlerts()
  const { data: grafanaAnnotationsData } = useGrafanaAnnotations()
  const [grafanaDashQuery, setGrafanaDashQuery] = useState("")
  const { data: grafanaDashboardsReal } = useGrafanaDashboardsReal(grafanaDashQuery)
  const correlateMut = useCorrelateFromAlert()
  const [correlateAlertName, setCorrelateAlertName] = useState("")
  const [correlateResult, setCorrelateResult] = useState<any | null>(null)

  const ds = dashboard || {} as any
  const tlEntries = timeline?.timeline || []

  return (
    <CortexShell
      title="Enterprise Infrastructure Center"
      subtitle="Kubernetes · Docker · Helm · Prometheus · Grafana · Loki · OpenTelemetry"
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

        {/* OBSERVABILITY TAB */}
        {activeTab === "Observability" && (
          <div className="space-y-4">
            {/* Overview KPIs */}
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
              <KpiCard icon={BarChart3} label="Dashboards" value={observability?.dashboards?.total || 0} color="text-orange-600" />
              <KpiCard icon={Database} label="Datasources" value={observability?.datasources?.total || 0} color="text-blue-600" sub={`types: ${(observability?.datasources?.known_types || []).join(", ")}`} />
              <KpiCard icon={Activity} label="Alerts" value={observability?.alerts?.alerts?.length || 0} color="text-red-600" />
              <KpiCard icon={Cpu} label="Pod Health" value={`${observability?.health?.pods?.running || 0}/${observability?.health?.pods?.total || 0}`} color="text-green-600" />
              <KpiCard icon={Network} label="Traces" value={observability?.traces?.total_traces || 0} color="text-purple-600" />
              <KpiCard icon={Hexagon} label="KG Nodes" value={observability?.knowledge_graph?.nodes || 0} color="text-cyan-600" sub={`${observability?.knowledge_graph?.edges || 0} edges`} />
            </div>

            {/* Unified Health */}
            <SectionCard title="Unified Observability Health" icon={Shield} iconColor="text-green-500">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {[
                  { label: "Grafana Org", value: observability?.dashboards?.status === "error" ? "Disconnected" : "Connected", color: observability?.dashboards?.status === "error" ? "text-red-600" : "text-green-600" },
                  { label: "Active Runtime Executions", value: observability?.runtime?.active_executions || 0, color: "text-blue-600" },
                  { label: "Learning Patterns", value: observability?.learning?.patterns || 0, color: "text-purple-600" },
                  { label: "Recommendations", value: observability?.recommendations?.length || 0, color: "text-orange-600" },
                ].map((item, i) => (
                  <div key={i} className="p-4 rounded-lg bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 text-center">
                    <p className="text-xs text-gray-500 uppercase">{item.label}</p>
                    <p className={`text-2xl font-bold mt-1 ${item.color}`}>{item.value}</p>
                  </div>
                ))}
              </div>
            </SectionCard>

            {/* Data Source Types */}
            {observability?.datasources?.datasources && (
              <SectionCard title="Datasource Composition" icon={Database} iconColor="text-blue-500">
                <div className="flex flex-wrap gap-2">
                  {Object.entries(observability.datasources.type_counts || {}).map(([type, count]) => (
                    <span key={type} className="px-3 py-1 rounded-lg text-sm font-medium bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300">
                      {type} <span className="font-bold">({String(count)})</span>
                    </span>
                  ))}
                </div>
              </SectionCard>
            )}

            {/* Dashboard List */}
            {observability?.dashboards?.dashboards && (
              <SectionCard title="Discovered Dashboards" icon={BarChart3} iconColor="text-orange-500">
                <div className="overflow-x-auto max-h-60 overflow-y-auto">
                  <table className="w-full text-sm">
                    <thead><tr className="border-b border-gray-200 dark:border-gray-700">
                      <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Title</th>
                      <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Folder</th>
                      <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Panels</th>
                      <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Variables</th>
                      <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Version</th>
                    </tr></thead>
                    <tbody>
                      {(observability.dashboards.dashboards || []).slice(0, 30).map((d: any, i: number) => (
                        <tr key={d.uid || i} className="border-b border-gray-100 dark:border-gray-700/50 hover:bg-gray-50 dark:hover:bg-gray-700/30">
                          <td className="py-2 px-3 font-medium text-gray-900 dark:text-white">{d.title}</td>
                          <td className="py-2 px-3 text-gray-600 dark:text-gray-400">{d.folder}</td>
                          <td className="py-2 px-3 text-gray-600 dark:text-gray-400">{d.panel_count}</td>
                          <td className="py-2 px-3 text-gray-600 dark:text-gray-400">{d.variable_count}</td>
                          <td className="py-2 px-3 text-gray-600 dark:text-gray-400">v{d.version}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </SectionCard>
            )}

            {/* Correlation Card */}
            <SectionCard title="Alert Correlation Chain" icon={Activity} iconColor="text-red-500">
              <p className="text-xs text-gray-500 dark:text-gray-400 mb-3">Drill down from an alert through metrics, traces, logs, deployments, pods, Knowledge Graph, learning, and recommendations</p>
              <div className="flex gap-2 mb-3">
                <input
                  type="text"
                  value={correlateAlertName}
                  onChange={(e) => setCorrelateAlertName(e.target.value)}
                  placeholder="Alert name (e.g. HighCpuUsage)"
                  className="flex-1 px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm text-gray-900 dark:text-white"
                />
                <button
                  onClick={async () => {
                    setCorrelateResult(null)
                    try {
                      const res: any = await correlateMut.mutateAsync(correlateAlertName)
                      setCorrelateResult(res)
                    } catch {}
                  }}
                  disabled={correlateMut.isPending || !correlateAlertName}
                  className="px-4 py-2 rounded-lg bg-red-600 text-white text-sm font-medium hover:bg-red-700 disabled:opacity-50"
                >Correlate</button>
              </div>
              {correlateResult && (
                <div className="space-y-1">
                  <p className="text-xs font-medium text-gray-500">Correlation Chain Steps</p>
                  <div className="flex flex-wrap gap-1">
                    {(correlateResult.steps || []).map((s: any, i: number) => (
                      <span key={i} className="px-2 py-0.5 rounded text-xs bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 font-mono">
                        {i > 0 && <span className="text-gray-400 mr-1">→</span>}{s.step}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </SectionCard>
          </div>
        )}

        {/* CLUSTER TAB */}
        {activeTab === "Cluster" && (
          <div className="space-y-6">
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
              <KpiCard icon={Server} label="Clusters" value={ds.clusters?.total || 0} color="text-blue-600" sub={`${ds.clusters?.healthy || 0} healthy`} />
              <KpiCard icon={Box} label="Pods" value={ds.pods?.total || 0} color="text-green-600" sub={`${ds.pods?.running || 0} running`} />
              <KpiCard icon={Layers} label="Deployments" value={ds.deployments?.total || 0} color="text-purple-600" sub={`${ds.deployments?.available || 0} available`} />
              <KpiCard icon={Cpu} label="Nodes" value={ds.nodes?.node_count || 0} color="text-cyan-600" sub={`${ds.nodes?.avg_cpu || 0}% avg CPU`} />
              <KpiCard icon={AlertTriangle} label="Critical Alerts" value={ds.alerts?.critical || 0} color="text-red-600" />
              <KpiCard icon={Activity} label="Network Failures" value={ds.active_network_failures || 0} color="text-orange-600" />
            </div>

            <SyncSection />

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <SectionCard title="Pod Health" icon={Box} iconColor="text-green-500">
                <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                  {["total", "running", "pending", "failed", "crashloop"].map((k) => (
                    <div key={k} className="p-3 rounded-lg bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 text-center">
                      <p className="text-xs text-gray-500 uppercase">{k}</p>
                      <p className={`text-xl font-bold mt-1 ${k === "failed" || k === "crashloop" ? "text-red-600" : k === "running" ? "text-green-600" : k === "pending" ? "text-yellow-600" : ""}`}>
                        {ds.pods?.[k] || 0}
                      </p>
                    </div>
                  ))}
                </div>
              </SectionCard>

              <SectionCard title="Deployment Health" icon={Layers} iconColor="text-purple-500">
                <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                  {["total", "available", "degraded", "unavailable", "rollouts_in_progress", "rollbacks"].map((k) => (
                    <div key={k} className="p-3 rounded-lg bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700">
                      <p className="text-xs text-gray-500 uppercase">{k.replace(/_/g, " ")}</p>
                      <p className={`text-xl font-bold mt-1 ${k === "rollbacks" || k === "unavailable" ? "text-red-600" : k === "available" ? "text-green-600" : k === "rollouts_in_progress" ? "text-yellow-600" : ""}`}>
                        {ds.deployments?.[k] || 0}
                      </p>
                    </div>
                  ))}
                </div>
              </SectionCard>
            </div>

            {/* Timeline */}
            <SectionCard title="Recent Activity" icon={Activity} iconColor="text-blue-500">
              <div className="space-y-1 max-h-60 overflow-y-auto">
                {tlEntries.length === 0 ? (
                  <p className="text-sm text-gray-500 dark:text-gray-400 text-center py-8">No activity yet</p>
                ) : (
                  tlEntries.map((entry: any, i: number) => (
                    <div key={i} className="flex items-center gap-3 p-2 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700/50">
                      <div className={`p-1.5 rounded-full ${
                        entry.source === "pod" ? "bg-green-100 dark:bg-green-900/30" :
                        entry.source === "deployment" ? "bg-purple-100 dark:bg-purple-900/30" :
                        entry.source === "node" ? "bg-cyan-100 dark:bg-cyan-900/30" :
                        entry.source === "helm" ? "bg-indigo-100 dark:bg-indigo-900/30" :
                        entry.source === "docker" ? "bg-blue-100 dark:bg-blue-900/30" :
                        "bg-gray-100 dark:bg-gray-700"
                      }`}>
                        {entry.source === "pod" ? <Box size={12} className="text-green-600" /> :
                         entry.source === "deployment" ? <Layers size={12} className="text-purple-600" /> :
                         entry.source === "node" ? <Cpu size={12} className="text-cyan-600" /> :
                         entry.source === "helm" ? <Hexagon size={12} className="text-indigo-600" /> :
                         entry.source === "docker" ? <Container size={12} className="text-blue-600" /> :
                         <Activity size={12} />}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-900 dark:text-white truncate">{entry.name}</p>
                        <p className="text-xs text-gray-500 dark:text-gray-400">{entry.source} · {entry.namespace || "—"}</p>
                      </div>
                      <StatusBadge status={entry.status} />
                      <span className="text-xs text-gray-400 dark:text-gray-500 shrink-0">{new Date(entry.timestamp || Date.now()).toLocaleTimeString()}</span>
                    </div>
                  ))
                )}
              </div>
            </SectionCard>
          </div>
        )}

        {/* PODS TAB */}
        {activeTab === "Pods" && (
          <div className="space-y-4">
            {podHealth ? (
              <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-3">
                {Object.entries(podHealth as Record<string, unknown>).map(([k, v]) => (
                  <div key={k} className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4 text-center">
                    <p className="text-xs text-gray-500 uppercase">{k}</p>
                    <p className={`text-2xl font-bold mt-1 ${k === "failed" || k === "oom" || k === "crashloop" ? "text-red-600" : k === "running" ? "text-green-600" : k === "pending" ? "text-yellow-600" : ""}`}>{String(v)}</p>
                  </div>
                ))}
              </div>
            ) : null}
            <SectionCard title="Pod List" icon={Box} iconColor="text-green-500">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead><tr className="border-b border-gray-200 dark:border-gray-700">
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Name</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Namespace</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Status</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Phase</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Restarts</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Node</th>
                  </tr></thead>
                  <tbody>{(infraPods?.pods || []).length === 0 ? (
                    <tr><td colSpan={6} className="text-center py-8 text-sm text-gray-500">No pods tracked</td></tr>
                  ) : (
                    (infraPods?.pods || []).map((p: any) => (
                      <tr key={p.pod_id} className="border-b border-gray-100 dark:border-gray-700/50 hover:bg-gray-50 dark:hover:bg-gray-700/30">
                        <td className="py-2 px-3 font-medium text-gray-900 dark:text-white">{p.name}</td>
                        <td className="py-2 px-3 text-gray-600 dark:text-gray-400">{p.namespace}</td>
                        <td className="py-2 px-3"><StatusBadge status={p.status} />{p.oom_detected && <span className="ml-1 text-xs text-red-500">OOM</span>}{p.crashloop_detected && <span className="ml-1 text-xs text-red-500">CL</span>}</td>
                        <td className="py-2 px-3 text-gray-600 dark:text-gray-400">{p.phase}</td>
                        <td className="py-2 px-3 text-gray-600 dark:text-gray-400">{p.restarts}</td>
                        <td className="py-2 px-3 text-gray-600 dark:text-gray-400">{p.node_name || "-"}</td>
                      </tr>
                    ))
                  )}</tbody>
                </table>
              </div>
            </SectionCard>
          </div>
        )}

        {/* DEPLOYMENTS TAB */}
        {activeTab === "Deployments" && (
          <div className="space-y-4">
            {depHealth ? (
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
                {Object.entries(depHealth as Record<string, unknown>).map(([k, v]) => (
                  <div key={k} className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4 text-center">
                    <p className="text-xs text-gray-500 uppercase">{k.replace(/_/g, " ")}</p>
                    <p className={`text-2xl font-bold mt-1 ${k === "rollbacks" || k === "unavailable" ? "text-red-600" : k === "available" ? "text-green-600" : ""}`}>{String(v)}</p>
                  </div>
                ))}
              </div>
            ) : null}
            <SectionCard title="Deployment List" icon={Layers} iconColor="text-purple-500">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead><tr className="border-b border-gray-200 dark:border-gray-700">
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Name</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Namespace</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Replicas</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Available</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Status</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Rollout</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Image</th>
                  </tr></thead>
                  <tbody>{(infraDeployments?.deployments || []).length === 0 ? (
                    <tr><td colSpan={7} className="text-center py-8 text-sm text-gray-500">No deployments tracked</td></tr>
                  ) : (
                    (infraDeployments?.deployments || []).map((d: any) => (
                      <tr key={d.deployment_id} className="border-b border-gray-100 dark:border-gray-700/50 hover:bg-gray-50 dark:hover:bg-gray-700/30">
                        <td className="py-2 px-3 font-medium text-gray-900 dark:text-white">{d.name}</td>
                        <td className="py-2 px-3 text-gray-600 dark:text-gray-400">{d.namespace}</td>
                        <td className="py-2 px-3 text-gray-600 dark:text-gray-400">{d.replicas}</td>
                        <td className="py-2 px-3 text-gray-600 dark:text-gray-400">{d.available}/{d.replicas}</td>
                        <td className="py-2 px-3"><StatusBadge status={d.status} /></td>
                        <td className="py-2 px-3"><StatusBadge status={d.rollout_status} /></td>
                        <td className="py-2 px-3 text-gray-600 dark:text-gray-400 font-mono text-xs">{d.image || "-"}</td>
                      </tr>
                    ))
                  )}</tbody>
                </table>
              </div>
            </SectionCard>
          </div>
        )}

        {/* DOCKER TAB */}
        {activeTab === "Docker" && (
          <div className="space-y-4">
            <DockerSyncSection />
            {dockerHealth ? (
              <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                {Object.entries(dockerHealth as Record<string, unknown>).map(([k, v]) => (
                  <div key={k} className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4 text-center">
                    <p className="text-xs text-gray-500 uppercase">{k}</p>
                    <p className={`text-2xl font-bold mt-1 ${k === "unhealthy" || k === "error" ? "text-red-600" : k === "running" ? "text-green-600" : k === "stopped" || k === "paused" ? "text-yellow-600" : ""}`}>{String(v)}</p>
                  </div>
                ))}
              </div>
            ) : null}
            <SectionCard title="Docker Containers" icon={Container} iconColor="text-blue-500">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead><tr className="border-b border-gray-200 dark:border-gray-700">
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Name</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Image</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Status</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Health</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Restarts</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Host</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Ports</th>
                  </tr></thead>
                  <tbody>{(dockerContainers?.containers || []).length === 0 ? (
                    <tr><td colSpan={7} className="text-center py-8 text-sm text-gray-500">No containers — sync from Docker engine</td></tr>
                  ) : (
                    (dockerContainers?.containers || []).map((c: any) => (
                      <tr key={c.docker_id} className="border-b border-gray-100 dark:border-gray-700/50 hover:bg-gray-50 dark:hover:bg-gray-700/30">
                        <td className="py-2 px-3 font-medium text-gray-900 dark:text-white">{c.name}</td>
                        <td className="py-2 px-3 font-mono text-xs text-gray-600 dark:text-gray-400">{c.image}</td>
                        <td className="py-2 px-3"><StatusBadge status={c.status} /></td>
                        <td className="py-2 px-3">{c.health && c.health !== "none" && c.health !== "" ? <StatusBadge status={c.health === "healthy" ? "ready" : "unhealthy"} /> : <span className="text-xs text-gray-400">&mdash;</span>}</td>
                        <td className="py-2 px-3 text-gray-600 dark:text-gray-400">{c.restart_count}</td>
                        <td className="py-2 px-3 text-gray-600 dark:text-gray-400">{c.host}</td>
                        <td className="py-2 px-3 text-gray-600 dark:text-gray-400 font-mono text-xs">{(c.ports || []).join(", ") || "-"}</td>
                      </tr>
                    ))
                  )}</tbody>
                </table>
              </div>
            </SectionCard>
            <SectionCard title="Docker Images" icon={Layers} iconColor="text-purple-500">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead><tr className="border-b border-gray-200 dark:border-gray-700">
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Tags</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Size</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Digest</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Repository</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Arch</th>
                  </tr></thead>
                  <tbody>{(dockerImages?.images || []).length === 0 ? (
                    <tr><td colSpan={5} className="text-center py-8 text-sm text-gray-500">No images — sync from Docker engine</td></tr>
                  ) : (
                    (dockerImages?.images || []).map((i: any) => (
                      <tr key={i.image_entry_id} className="border-b border-gray-100 dark:border-gray-700/50 hover:bg-gray-50 dark:hover:bg-gray-700/30">
                        <td className="py-2 px-3 font-medium text-gray-900 dark:text-white font-mono text-xs">{(i.tags || []).join(", ") || i.image_id?.slice(0, 16) || "-"}</td>
                        <td className="py-2 px-3 text-gray-600 dark:text-gray-400">{i.size_bytes ? `${(i.size_bytes / 1048576).toFixed(1)} MB` : "-"}</td>
                        <td className="py-2 px-3 font-mono text-xs text-gray-600 dark:text-gray-400">{(i.digest || "").slice(0, 16) || "-"}</td>
                        <td className="py-2 px-3 text-gray-600 dark:text-gray-400 font-mono text-xs">{i.repository || "-"}</td>
                        <td className="py-2 px-3 text-gray-600 dark:text-gray-400">{i.architecture || "-"}</td>
                      </tr>
                    ))
                  )}</tbody>
                </table>
              </div>
            </SectionCard>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <SectionCard title="Volumes" icon={Database} iconColor="text-cyan-500">
                {(dockerVolumes?.volumes || []).length === 0 ? (
                  <p className="text-sm text-gray-500 text-center py-4">No volumes tracked</p>
                ) : (
                  <div className="space-y-2">
                    {(dockerVolumes?.volumes || []).map((v: any) => (
                      <div key={v.volume_id} className="p-3 rounded-lg bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700">
                        <p className="text-sm font-medium text-gray-900 dark:text-white">{v.name}</p>
                        <p className="text-xs text-gray-500">{v.driver} &middot; {v.mountpoint || "-"}</p>
                      </div>
                    ))}
                  </div>
                )}
              </SectionCard>
              <SectionCard title="Networks" icon={Network} iconColor="text-green-500">
                {(dockerNetworks?.networks || []).length === 0 ? (
                  <p className="text-sm text-gray-500 text-center py-4">No networks tracked</p>
                ) : (
                  <div className="space-y-2">
                    {(dockerNetworks?.networks || []).map((n: any) => (
                      <div key={n.network_id} className="p-3 rounded-lg bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700">
                        <p className="text-sm font-medium text-gray-900 dark:text-white">{n.name}</p>
                        <p className="text-xs text-gray-500">{n.driver} &middot; {n.scope}{n.subnet ? ` &middot; ${n.subnet}` : ""}</p>
                      </div>
                    ))}
                  </div>
                )}
              </SectionCard>
            </div>
          </div>
        )}

        {/* HELM TAB */}
        {activeTab === "Helm" && (
          <div className="space-y-4">
            {helmHealth ? (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {Object.entries(helmHealth as Record<string, unknown>).map(([k, v]) => (
                  <div key={k} className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4 text-center">
                    <p className="text-xs text-gray-500 uppercase">{k}</p>
                    <p className={`text-2xl font-bold mt-1 ${k === "failed" ? "text-red-600" : k === "deployed" ? "text-green-600" : k === "pending" ? "text-yellow-600" : ""}`}>{String(v)}</p>
                  </div>
                ))}
              </div>
            ) : null}
            <SectionCard title="Helm Releases" icon={Hexagon} iconColor="text-indigo-500">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead><tr className="border-b border-gray-200 dark:border-gray-700">
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Name</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Namespace</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Chart</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Version</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Revision</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Status</th>
                  </tr></thead>
                  <tbody>{(helmReleases?.releases || []).length === 0 ? (
                    <tr><td colSpan={6} className="text-center py-8 text-sm text-gray-500">No releases tracked</td></tr>
                  ) : (
                    (helmReleases?.releases || []).map((r: any) => (
                      <tr key={r.release_id} className="border-b border-gray-100 dark:border-gray-700/50 hover:bg-gray-50 dark:hover:bg-gray-700/30">
                        <td className="py-2 px-3 font-medium text-gray-900 dark:text-white">{r.name}</td>
                        <td className="py-2 px-3 text-gray-600 dark:text-gray-400">{r.namespace}</td>
                        <td className="py-2 px-3 text-gray-600 dark:text-gray-400 font-mono text-xs">{r.chart}</td>
                        <td className="py-2 px-3 text-gray-600 dark:text-gray-400">{r.version}</td>
                        <td className="py-2 px-3 text-gray-600 dark:text-gray-400">v{r.revision}</td>
                        <td className="py-2 px-3"><StatusBadge status={r.status} /></td>
                      </tr>
                    ))
                  )}</tbody>
                </table>
              </div>
            </SectionCard>
          </div>
        )}

        {/* METRICS TAB */}
        {activeTab === "Metrics" && (
          <div className="space-y-4">
            {nodeUtil ? (
              <SectionCard title="Node Utilization (Kubernetes)" icon={Cpu} iconColor="text-cyan-500">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {(["avg_cpu", "avg_memory", "avg_disk"] as const).map((k) => {
                    const nu = nodeUtil as Record<string, number>
                    const val = nu[k] || 0
                    const pct = (typeof val === "number" ? val : 0) * 100
                    return (
                      <div key={k} className="p-4 rounded-lg bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700">
                        <p className="text-xs text-gray-500 uppercase mb-2">{k.replace("avg_", "Avg ")}</p>
                        <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-3">
                          <div className={`h-3 rounded-full ${pct > 80 ? "bg-red-500" : pct > 60 ? "bg-yellow-500" : "bg-green-500"}`}
                            style={{ width: `${Math.min(pct, 100)}%` }} />
                        </div>
                        <p className="text-sm font-bold text-gray-900 dark:text-white mt-2">{pct.toFixed(1)}%</p>
                      </div>
                    )
                  })}
                </div>
                <p className="text-xs text-gray-500 mt-3">{(nodeUtil as Record<string, number>)?.node_count || 0} nodes tracked</p>
              </SectionCard>
            ) : null}

            {promMetricsSnap ? (
              <SectionCard title="Live Prometheus Metrics" icon={BarChart3} iconColor="text-orange-500">
                {(() => {
                  const pms = promMetricsSnap as Record<string, unknown>
                  const metrics = pms.metrics as Record<string, number> | undefined
                  if (!metrics || Object.keys(metrics).length === 0) return null
                  return (
                    <>
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                  {Object.entries(metrics).map(([k, v]) => (
                    <div key={k} className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4 text-center">
                      <p className="text-xs text-gray-500 uppercase">{k.replace(/_/g, " ")}</p>
                      <p className="text-xl font-bold mt-1 text-gray-900 dark:text-white">{typeof v === "number" ? v.toFixed(2) : String(v)}</p>
                    </div>
                  ))}
                </div>
                <p className="text-xs text-gray-500 mt-3">Collected at: {pms.collected_at ? new Date(pms.collected_at as string).toLocaleString() : "-"}</p>
                </>
                  )
                })()}
              </SectionCard>
            ) : null}

            <SectionCard title="Prometheus Scrape Targets" icon={Radio} iconColor="text-red-500">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead><tr className="border-b border-gray-200 dark:border-gray-700">
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Job</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Instance</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Health</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Last Scrape</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Scrape Duration</th>
                  </tr></thead>
                  <tbody>{(promTargets ? (promTargets as Record<string, unknown>).targets as unknown[] : []).length === 0 ? (
                    <tr><td colSpan={5} className="text-center py-8 text-sm text-gray-500">No targets — connect to Prometheus or sync from the Alerts tab</td></tr>
                  ) : (
                    ((promTargets as Record<string, unknown>).targets as any[]).map((t: any, i: number) => (
                      <tr key={i} className="border-b border-gray-100 dark:border-gray-700/50 hover:bg-gray-50 dark:hover:bg-gray-700/30">
                        <td className="py-2 px-3 font-medium text-gray-900 dark:text-white">{t.labels?.job || t.scrapePool || "-"}</td>
                        <td className="py-2 px-3 font-mono text-xs text-gray-600 dark:text-gray-400">{t.discoveredLabels?.__address__ || t.labels?.instance || "-"}</td>
                        <td className="py-2 px-3"><StatusBadge status={t.health} /></td>
                        <td className="py-2 px-3 text-xs text-gray-500">{t.lastScrape ? new Date(t.lastScrape).toLocaleString() : "-"}</td>
                        <td className="py-2 px-3 text-xs text-gray-600 dark:text-gray-400">{t.lastScrapeDuration ? `${(t.lastScrapeDuration * 1000).toFixed(0)}ms` : "-"}</td>
                      </tr>
                    ))
                  )}</tbody>
                </table>
              </div>
            </SectionCard>

            {prometheusStats ? (
              <SectionCard title="Alert Stats (Legacy)" icon={AlertTriangle} iconColor="text-yellow-500">
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
                  {Object.entries(prometheusStats as Record<string, unknown>).map(([k, v]) => (
                    <div key={k} className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4 text-center">
                      <p className="text-xs text-gray-500 uppercase">{k}</p>
                      <p className={`text-2xl font-bold mt-1 ${k === "critical" || k === "firing" ? "text-red-600" : k === "warning" ? "text-yellow-600" : ""}`}>{String(v)}</p>
                    </div>
                  ))}
                </div>
              </SectionCard>
            ) : null}
          </div>
        )}

        {/* LOGS TAB */}
        {activeTab === "Logs" && (
          <div className="space-y-4">
            {/* LogQL Query */}
            <SectionCard title="Live Log Query" icon={Search} iconColor="text-green-500">
              <p className="text-xs text-gray-500 dark:text-gray-400 mb-3">
                Query real logs from Loki using LogQL. Connected to {lokiLabelsData?.labels?.length || 0} available labels.
              </p>
              <div className="flex gap-2 mb-3">
                <input
                  type="text"
                  value={lokiQueryStr}
                  onChange={(e) => setLokiQueryStr(e.target.value)}
                  placeholder='{namespace!=""} |= "error"'
                  className="flex-1 px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm font-mono text-gray-900 dark:text-white"
                />
                <button
                  onClick={async () => {
                    const res = await enterpriseInfraApi.lokiQuery(lokiQueryStr, 100) as any
                    setLokiQueryResults(res?.streams || [])
                  }}
                  className="px-4 py-2 rounded-lg bg-green-600 text-white text-sm font-medium hover:bg-green-700"
                >Query</button>
              </div>
              {lokiQueryResults && lokiQueryResults.length > 0 && (
                <div className="bg-gray-900 rounded-lg p-3 max-h-60 overflow-y-auto font-mono text-xs">
                  {lokiQueryResults.map((s: any, i: number) => (
                    <div key={i} className="mb-2">
                      <div className="text-gray-500 mb-1">{JSON.stringify(s.labels)}</div>
                      {(s.entries || []).slice(0, 20).map((e: any, j: number) => (
                        <div key={j} className={`${e.line?.toLowerCase().includes("error") ? "text-red-400" : e.line?.toLowerCase().includes("warn") ? "text-yellow-400" : "text-green-400"}`}>
                          {e.timestamp ? new Date(e.timestamp).toLocaleTimeString() : ""} {e.line}
                        </div>
                      ))}
                      {(s.entries || []).length > 20 && <div className="text-gray-500 mt-1">... and {s.entries.length - 20} more</div>}
                    </div>
                  ))}
                </div>
              )}
              {lokiQueryResults && lokiQueryResults.length === 0 && (
                <p className="text-sm text-gray-500 text-center py-4">No log entries matched your query</p>
              )}
            </SectionCard>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {/* Target Logs */}
              <SectionCard title="Target Logs" icon={FileText} iconColor="text-blue-500">
                <p className="text-xs text-gray-500 dark:text-gray-400 mb-3">Tail logs for a specific infrastructure entity</p>
                <div className="flex gap-2 mb-3">
                  <select value={lokiTargetType} onChange={(e) => setLokiTargetType(e.target.value)}
                    className="px-2 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm text-gray-900 dark:text-white">
                    {["pod","container","deployment","service","namespace","node","app","ingress","job","cronjob"].map(t => (
                      <option key={t} value={t}>{t}</option>
                    ))}
                  </select>
                  <input
                    type="text"
                    value={lokiTargetName}
                    onChange={(e) => setLokiTargetName(e.target.value)}
                    placeholder="target name"
                    className="flex-1 px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm text-gray-900 dark:text-white"
                  />
                </div>
                {(() => {
                  const ltd = lokiTargetData as Record<string, unknown> | undefined
                  const streams = ltd?.streams as unknown[] | undefined
                  return streams && streams.length > 0 ? (
                  <div className="bg-gray-900 rounded-lg p-3 max-h-40 overflow-y-auto font-mono text-xs">
                    {streams.map((s: any, i: number) => (
                      <div key={i}>
                        {(s.entries || []).slice(0, 30).map((e: any, j: number) => (
                          <div key={j} className={`${e.line?.toLowerCase().includes("error") ? "text-red-400" : e.line?.toLowerCase().includes("warn") ? "text-yellow-400" : "text-green-400"}`}>
                            {e.timestamp ? new Date(e.timestamp).toLocaleTimeString() : ""} {e.line}
                          </div>
                        ))}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-gray-500 text-center py-4">{lokiTargetName ? "No logs for this target" : "Enter a target name above"}</p>
                )})()}
              </SectionCard>

              {/* Log Analysis */}
              <SectionCard title="Log Analysis" icon={Activity} iconColor="text-purple-500">
                <p className="text-xs text-gray-500 dark:text-gray-400 mb-3">Detect error patterns, exceptions, and log storms</p>
                <div className="flex gap-2 mb-3">
                  <input
                    type="text"
                    value={lokiQueryStr}
                    onChange={(e) => setLokiQueryStr(e.target.value)}
                    placeholder="LogQL for analysis"
                    className="flex-1 px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm font-mono text-gray-900 dark:text-white"
                  />
                  <button
                    onClick={async () => {
                      setLokiAnalyzing(true)
                      setLokiAnalyzeResults(null)
                      try {
                        const res: any = await lokiAnalyzeMut.mutateAsync({ logql: lokiQueryStr })
                        setLokiAnalyzeResults(res?.analysis || res)
                      } finally {
                        setLokiAnalyzing(false)
                      }
                    }}
                    disabled={lokiAnalyzing}
                    className="px-4 py-2 rounded-lg bg-purple-600 text-white text-sm font-medium hover:bg-purple-700 disabled:opacity-50"
                  >{lokiAnalyzing ? "Analyzing..." : "Analyze"}</button>
                </div>
                {lokiAnalyzeResults && (
                  <div className="space-y-2">
                    <div className="grid grid-cols-3 gap-2">
                      <div className="p-2 rounded bg-gray-50 dark:bg-gray-900 border text-center">
                        <p className="text-xs text-gray-500">Lines</p>
                        <p className="text-lg font-bold">{lokiAnalyzeResults.total_lines || 0}</p>
                      </div>
                      <div className="p-2 rounded bg-gray-50 dark:bg-gray-900 border text-center">
                        <p className="text-xs text-gray-500">Errors</p>
                        <p className={`text-lg font-bold ${(lokiAnalyzeResults.total_errors || 0) > 0 ? "text-red-600" : "text-green-600"}`}>{lokiAnalyzeResults.total_errors || 0}</p>
                      </div>
                      <div className="p-2 rounded bg-gray-50 dark:bg-gray-900 border text-center">
                        <p className="text-xs text-gray-500">Rate</p>
                        <p className="text-lg font-bold">{(lokiAnalyzeResults.error_rate * 100 || 0).toFixed(1)}%</p>
                      </div>
                    </div>
                    {lokiAnalyzeResults.log_storm_detected && (
                      <div className="p-2 rounded bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 text-sm font-medium text-center">
                        ⚡ Log Storm Detected — {lokiAnalyzeResults.total_errors} errors in window
                      </div>
                    )}
                    {lokiAnalyzeResults.global_patterns?.length > 0 && (
                      <div>
                        <p className="text-xs font-medium text-gray-500 uppercase mb-1">Error Patterns</p>
                        <div className="flex flex-wrap gap-1">
                          {lokiAnalyzeResults.global_patterns.map((p: any, i: number) => (
                            <span key={i} className="px-2 py-0.5 rounded text-xs bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300">
                              {p.pattern} ({p.count})
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                    {lokiAnalyzeResults.top_errors?.length > 0 && (
                      <div>
                        <p className="text-xs font-medium text-gray-500 uppercase mb-1">Top Errors</p>
                        <div className="bg-gray-900 rounded p-2 max-h-24 overflow-y-auto font-mono text-xs text-red-400 space-y-0.5">
                          {lokiAnalyzeResults.top_errors.map((e: any, i: number) => (
                            <div key={i}>{e.error?.slice(0, 120)}{e.error?.length > 120 ? "..." : ""} <span className="text-gray-500">(x{e.count})</span></div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </SectionCard>
            </div>

            {/* Labels & Streams */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <SectionCard title="Available Labels" icon={Database} iconColor="text-cyan-500">
                {(() => {
                  const lld = lokiLabelsData as { labels: string[] } | undefined
                  return lld?.labels?.length ? (
                    <div className="flex flex-wrap gap-1">
                      {lld.labels.map((l: string) => (
                        <span key={l} className="px-2 py-0.5 rounded text-xs bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 font-mono">{l}</span>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-gray-500 text-center py-4">No labels — Loki connector may not be connected</p>
                  )
                })()}
              </SectionCard>

              <SectionCard title="Log Streams" icon={Layers} iconColor="text-indigo-500">
                {(() => {
                  const lsd = lokiStreamsData as { streams: unknown[] } | undefined
                  const streams = lsd?.streams
                  return streams?.length ? (
                    <div className="max-h-40 overflow-y-auto space-y-1">
                      {streams.slice(0, 30).map((s: any, i: number) => (
                        <div key={i} className="text-xs font-mono text-gray-600 dark:text-gray-400 truncate">
                          {JSON.stringify(s)}
                        </div>
                      ))}
                      {streams.length > 30 && (
                        <p className="text-xs text-gray-500">... and {streams.length - 30} more</p>
                      )}
                    </div>
                  ) : (
                    <p className="text-sm text-gray-500 text-center py-4">No streams discovered</p>
                  )
                })()}
              </SectionCard>
            </div>

            {/* Legacy Log Analyses */}
            <SectionCard title="Legacy Log Analyses" icon={FileText} iconColor="text-gray-500">
              <p className="text-xs text-gray-500 dark:text-gray-400 mb-3">Backward-compatible analyses from the JSON store</p>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead><tr className="border-b border-gray-200 dark:border-gray-700">
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Stream</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Total Lines</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Errors</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Warns</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Info</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Analyzed</th>
                  </tr></thead>
                  <tbody>{(lokiAnalyses?.analyses || []).length === 0 ? (
                    <tr><td colSpan={6} className="text-center py-8 text-sm text-gray-500">No legacy log analyses</td></tr>
                  ) : (
                    (lokiAnalyses?.analyses || []).slice(0, 10).map((a: any) => (
                      <tr key={a.analysis_id} className="border-b border-gray-100 dark:border-gray-700/50 hover:bg-gray-50 dark:hover:bg-gray-700/30">
                        <td className="py-2 px-3 font-medium text-gray-900 dark:text-white">{a.stream}</td>
                        <td className="py-2 px-3 text-gray-600 dark:text-gray-400">{a.total_lines}</td>
                        <td className="py-2 px-3"><span className={`font-medium ${a.error_count > 0 ? "text-red-600" : "text-green-600"}`}>{a.error_count}</span></td>
                        <td className="py-2 px-3 text-yellow-600">{a.warn_count}</td>
                        <td className="py-2 px-3 text-gray-600 dark:text-gray-400">{a.info_count}</td>
                        <td className="py-2 px-3 text-xs text-gray-500">{new Date(a.analyzed_at || Date.now()).toLocaleString()}</td>
                      </tr>
                    ))
                  )}</tbody>
                </table>
              </div>
            </SectionCard>
          </div>
        )}

        {/* TRACES TAB */}
        {activeTab === "Traces" && (
          <div className="space-y-4">
            {/* Trace Health KPIs */}
            {traceHealth ? (
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
                {Object.entries(traceHealth as Record<string, unknown>).map(([k, v]) => (
                  <div key={k} className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4 text-center">
                    <p className="text-xs text-gray-500 uppercase">{k.replace(/_/g, " ")}</p>
                    <p className={`text-2xl font-bold mt-1 ${k === "error" ? "text-red-600" : k === "ok" ? "text-green-600" : ""}`}>{typeof v === "number" ? v.toLocaleString() : String(v)}</p>
                  </div>
                ))}
              </div>
            ) : null}

            {/* Service Graph KPIs */}
            {graphHealth && (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4 text-center">
                  <p className="text-xs text-gray-500 uppercase">Services</p>
                  <p className="text-2xl font-bold mt-1 text-blue-600">{graphHealth.total_services}</p>
                </div>
                <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4 text-center">
                  <p className="text-xs text-gray-500 uppercase">Healthy</p>
                  <p className="text-2xl font-bold mt-1 text-green-600">{graphHealth.healthy_services}</p>
                </div>
                <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4 text-center">
                  <p className="text-xs text-gray-500 uppercase">With Errors</p>
                  <p className={`text-2xl font-bold mt-1 ${graphHealth.services_with_errors > 0 ? "text-red-600" : "text-gray-400"}`}>{graphHealth.services_with_errors}</p>
                </div>
                <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4 text-center">
                  <p className="text-xs text-gray-500 uppercase">Dependencies</p>
                  <p className="text-2xl font-bold mt-1 text-purple-600">{graphHealth.total_edges}</p>
                </div>
              </div>
            )}

            {/* Service Dependency Graph */}
            <SectionCard title="Service Dependency Graph" icon={Network} iconColor="text-blue-500">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead><tr className="border-b border-gray-200 dark:border-gray-700">
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Service</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Version</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Environment</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Spans</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Errors</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Edges</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Last Seen</th>
                  </tr></thead>
                  <tbody>{(otelServices?.services || []).length === 0 ? (
                    <tr><td colSpan={7} className="text-center py-8 text-sm text-gray-500">No services discovered — send OTLP traces to /api/infrastructure/otel/v1/traces</td></tr>
                  ) : (
                    (otelServices?.services || []).map((s: any) => (
                      <tr key={s.id} className="border-b border-gray-100 dark:border-gray-700/50 hover:bg-gray-50 dark:hover:bg-gray-700/30">
                        <td className="py-2 px-3 font-medium text-gray-900 dark:text-white">{s.name}</td>
                        <td className="py-2 px-3 text-gray-600 dark:text-gray-400">{s.version || "-"}</td>
                        <td className="py-2 px-3 text-gray-600 dark:text-gray-400">{s.environment || "-"}</td>
                        <td className="py-2 px-3 text-gray-600 dark:text-gray-400">{s.span_count}</td>
                        <td className="py-2 px-3"><span className={s.error_count > 0 ? "text-red-600 font-medium" : "text-green-600"}>{s.error_count}</span></td>
                        <td className="py-2 px-3 text-gray-600 dark:text-gray-400">{s.edge_count}</td>
                        <td className="py-2 px-3 text-xs text-gray-500">{s.last_seen ? new Date(s.last_seen).toLocaleString() : "-"}</td>
                      </tr>
                    ))
                  )}</tbody>
                </table>
              </div>
              {traceGraph && traceGraph.edges && traceGraph.edges.length > 0 && (
                <div className="mt-4 p-3 rounded-lg bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700">
                  <p className="text-xs font-medium text-gray-500 uppercase mb-2">Service Dependencies</p>
                  <div className="flex flex-wrap gap-2">
                    {traceGraph.edges.map((e: any, i: number) => (
                      <span key={i} className="inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-mono bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300">
                        {e.source} <span className="text-gray-400">→</span> {e.target}
                        <span className="text-gray-400 ml-1">({e.operation})</span>
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </SectionCard>

            {/* Live Traces */}
            <SectionCard title="Distributed Traces" icon={Radio} iconColor="text-purple-500">
              <p className="text-xs text-gray-500 dark:text-gray-400 mb-3">
                Traces are ingested via the OTLP HTTP endpoint at POST /api/infrastructure/otel/v1/traces
              </p>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead><tr className="border-b border-gray-200 dark:border-gray-700">
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Trace ID</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Service</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Spans</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Duration</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">P95</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Status</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Operation</th>
                  </tr></thead>
                  <tbody>{(infraTraces?.traces || []).length === 0 ? (
                    <tr><td colSpan={7} className="text-center py-8 text-sm text-gray-500">No traces tracked — OTLP endpoint ready at /api/infrastructure/otel/v1/traces</td></tr>
                  ) : (
                    (infraTraces?.traces || []).map((t: any) => (
                      <tr key={t.trace_entry_id} className="border-b border-gray-100 dark:border-gray-700/50 hover:bg-gray-50 dark:hover:bg-gray-700/30">
                        <td className="py-2 px-3 font-mono text-xs text-gray-900 dark:text-white">{t.trace_id?.slice(0, 16)}…</td>
                        <td className="py-2 px-3 font-medium text-gray-900 dark:text-white">{t.service_name}</td>
                        <td className="py-2 px-3 text-gray-600 dark:text-gray-400">{t.total_spans} ({t.error_spans > 0 ? `${t.error_spans} err` : "ok"})</td>
                        <td className="py-2 px-3 font-mono text-xs text-gray-600 dark:text-gray-400">{t.duration_ms?.toFixed(0)}ms</td>
                        <td className="py-2 px-3 font-mono text-xs text-gray-600 dark:text-gray-400">{t.latency_p95?.toFixed(0)}ms</td>
                        <td className="py-2 px-3"><StatusBadge status={t.status} /></td>
                        <td className="py-2 px-3 text-gray-600 dark:text-gray-400">{t.root_operation || "-"}</td>
                      </tr>
                    ))
                  )}</tbody>
                </table>
              </div>
            </SectionCard>
          </div>
        )}

        {/* DASHBOARDS TAB */}
        {activeTab === "Dashboards" && (
          <div className="space-y-4">
            {/* Real Grafana Dashboards */}
            <SectionCard title="Grafana Dashboards" icon={BarChart3} iconColor="text-orange-500">
              <div className="flex gap-2 mb-3">
                <input
                  type="text"
                  value={grafanaDashQuery}
                  onChange={(e) => setGrafanaDashQuery(e.target.value)}
                  placeholder="Filter by title or folder..."
                  className="flex-1 px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm text-gray-900 dark:text-white"
                />
                <span className="text-xs text-gray-500 self-center">{grafanaDashboardsReal?.total || 0} dashboards</span>
              </div>
              <div className="overflow-x-auto max-h-72 overflow-y-auto">
                <table className="w-full text-sm">
                  <thead><tr className="border-b border-gray-200 dark:border-gray-700">
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Title</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Folder</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Panels</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Variables</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Datasources</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Version</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Tags</th>
                  </tr></thead>
                  <tbody>{(grafanaDashboardsReal?.dashboards || []).length === 0 ? (
                    <tr><td colSpan={7} className="text-center py-8 text-sm text-gray-500">No dashboards — Grafana connector may not be connected</td></tr>
                  ) : (
                    (grafanaDashboardsReal?.dashboards || []).map((d: any, i: number) => (
                      <tr key={d.uid || i} className="border-b border-gray-100 dark:border-gray-700/50 hover:bg-gray-50 dark:hover:bg-gray-700/30">
                        <td className="py-2 px-3 font-medium text-gray-900 dark:text-white">{d.title}</td>
                        <td className="py-2 px-3 text-gray-600 dark:text-gray-400">{d.folder}</td>
                        <td className="py-2 px-3 text-gray-600 dark:text-gray-400">{d.panel_count}</td>
                        <td className="py-2 px-3 text-gray-600 dark:text-gray-400">{d.variable_count}</td>
                        <td className="py-2 px-3">
                          <div className="flex flex-wrap gap-1">
                            {(d.datasources || []).slice(0, 3).map((ds: string, j: number) => (
                              <span key={j} className="px-1.5 py-0.5 rounded text-xs bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 font-mono">{ds.slice(0, 8)}…</span>
                            ))}
                            {(d.datasources || []).length > 3 && <span className="text-xs text-gray-500">+{d.datasources.length - 3}</span>}
                          </div>
                        </td>
                        <td className="py-2 px-3 text-gray-600 dark:text-gray-400">v{d.version}</td>
                        <td className="py-2 px-3">
                          <div className="flex flex-wrap gap-1">
                            {(d.tags || []).slice(0, 3).map((t: string, j: number) => (
                              <span key={j} className="px-1.5 py-0.5 rounded text-xs bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300">{t}</span>
                            ))}
                          </div>
                        </td>
                      </tr>
                    ))
                  )}</tbody>
                </table>
              </div>
            </SectionCard>

            {/* Grafana Datasources */}
            <SectionCard title="Datasources" icon={Database} iconColor="text-blue-500">
              <div className="overflow-x-auto max-h-60 overflow-y-auto">
                <table className="w-full text-sm">
                  <thead><tr className="border-b border-gray-200 dark:border-gray-700">
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Name</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Type</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">URL</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Default</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Version</th>
                  </tr></thead>
                  <tbody>{(grafanaDsReal?.datasources || []).length === 0 ? (
                    <tr><td colSpan={5} className="text-center py-8 text-sm text-gray-500">No datasources — Grafana connector may not be connected</td></tr>
                  ) : (
                    (grafanaDsReal?.datasources || []).map((ds: any) => (
                      <tr key={ds.id} className="border-b border-gray-100 dark:border-gray-700/50 hover:bg-gray-50 dark:hover:bg-gray-700/30">
                        <td className="py-2 px-3 font-medium text-gray-900 dark:text-white">{ds.name}</td>
                        <td className="py-2 px-3"><span className="px-2 py-0.5 rounded text-xs font-medium bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300">{ds.type}</span></td>
                        <td className="py-2 px-3 font-mono text-xs text-gray-600 dark:text-gray-400">{ds.url || "-"}</td>
                        <td className="py-2 px-3">{ds.is_default ? <CheckCircle size={14} className="text-green-500" /> : <Minus size={14} className="text-gray-400" />}</td>
                        <td className="py-2 px-3 text-gray-600 dark:text-gray-400">v{ds.version}</td>
                      </tr>
                    ))
                  )}</tbody>
                </table>
              </div>
              {grafanaDsReal?.type_counts && (
                <div className="mt-3 flex flex-wrap gap-1">
                  {Object.entries(grafanaDsReal.type_counts).map(([type, count]) => (
                    <span key={type} className="px-2 py-0.5 rounded text-xs bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300 font-medium">{type} ({String(count)})</span>
                    ))}
                  </div>
              )}
              </SectionCard>

            {/* Grafana Folders & Annotations */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <SectionCard title="Folders" icon={Folder} iconColor="text-yellow-500">
                {(() => {
                  const gf = grafanaFolders as { folders: unknown[] } | undefined
                  const folders = gf?.folders
                  return folders?.length ? (
                  <div className="space-y-1 max-h-40 overflow-y-auto">
                    {(folders || []).map((f: any) => (
                      <div key={f.uid} className="flex items-center justify-between p-2 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700/50">
                        <span className="text-sm font-medium text-gray-900 dark:text-white">{f.title}</span>
                        <span className="text-xs text-gray-500">{f.uid}</span>
                      </div>
                    ))}
                  </div>
                  ) : (
                    <p className="text-sm text-gray-500 text-center py-4">No folders found</p>
                  )
                })()}
              </SectionCard>

              <SectionCard title="Annotations" icon={Activity} iconColor="text-blue-500">
                {(() => {
                  const gad = grafanaAnnotationsData as { annotations: unknown[] } | undefined
                  const anns = gad?.annotations
                  return anns?.length ? (
                  <div className="space-y-1 max-h-40 overflow-y-auto">
                    {(anns || []).slice(0, 20).map((a: any, i: number) => (
                      <div key={i} className="p-2 rounded-lg bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700">
                        <p className="text-xs font-medium text-gray-900 dark:text-white">{a.text || a.alertName || "-"}</p>
                        <p className="text-xs text-gray-500">{a.tags?.join(", ") || ""} &middot; {a.created ? new Date(a.created).toLocaleString() : "-"}</p>
                      </div>
                    ))}
                  </div>
                  ) : (
                    <p className="text-sm text-gray-500 text-center py-4">No annotations found</p>
                  )
                })()}
              </SectionCard>
            </div>
          </div>
        )}

        {/* ALERTS TAB */}
        {activeTab === "Alerts" && (
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <SectionCard title="Alert Severity" icon={AlertTriangle} iconColor="text-red-500">
                <div className="grid grid-cols-3 gap-3">
                  {["critical", "warning", "info"].map((sev) => (
                    <div key={sev} className="p-3 rounded-lg bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 text-center">
                      <p className="text-xs text-gray-500 uppercase">{sev}</p>
                      <p className={`text-2xl font-bold mt-1 ${sev === "critical" ? "text-red-600" : sev === "warning" ? "text-yellow-600" : ""}`}>{(prometheusStats as Record<string, number> | undefined)?.[sev] || 0}</p>
                    </div>
                  ))}
                </div>
              </SectionCard>

              <SectionCard title="Correlated Alerts" icon={Activity} iconColor="text-orange-500">
                {(() => {
                  const ca = correlAlerts as { correlated: unknown[] } | undefined
                  const corr = ca?.correlated
                  return corr?.length ? (
                  <div className="space-y-2">
                    {corr.map((g: any, i: number) => (
                      <div key={i} className="p-3 rounded-lg bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700">
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-sm font-medium text-gray-900 dark:text-white">{g.correlation_key}</span>
                          <span className="text-xs font-medium text-red-600">{g.alert_count} alerts</span>
                        </div>
                        <div className="flex flex-wrap gap-1">
                          {(g.alerts || []).map((a: any, j: number) => (
                            <span key={j} className="px-2 py-0.5 rounded text-xs bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300">{a.alert_name}</span>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                  ) : (
                    <p className="text-sm text-gray-500 text-center py-4">No correlated alert groups</p>
                  )
                })()}
              </SectionCard>
            </div>

            <SectionCard title="Live Prometheus Alerts" icon={Activity} iconColor="text-red-500">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead><tr className="border-b border-gray-200 dark:border-gray-700">
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Alert</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Severity</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">State</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Active Since</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Correlated</th>
                  </tr></thead>
                  <tbody>{(() => {
                    const pla = promLiveAlerts as { alerts: unknown[] } | undefined
                    const alerts = pla?.alerts
                    return alerts?.length ? (
                    alerts.slice(0, 50).map((a: any, i: number) => (
                      <tr key={i} className="border-b border-gray-100 dark:border-gray-700/50 hover:bg-gray-50 dark:hover:bg-gray-700/30">
                        <td className="py-2 px-3 font-medium text-gray-900 dark:text-white">{a.alert_name}</td>
                        <td className="py-2 px-3"><span className={`px-2 py-0.5 rounded text-xs font-medium ${a.severity === "critical" ? "bg-red-100 dark:bg-red-900/30 text-red-700" : a.severity === "warning" ? "bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700" : "bg-blue-100 dark:bg-blue-900/30 text-blue-700"}`}>{a.severity}</span></td>
                        <td className="py-2 px-3"><StatusBadge status={a.state} /></td>
                        <td className="py-2 px-3 text-xs text-gray-500">{a.active_at ? new Date(a.active_at).toLocaleString() : "-"}</td>
                        <td className="py-2 px-3 text-xs text-gray-600 dark:text-gray-400">
                          {a.correlated && (a.correlated.pods?.length > 0 || a.correlated.containers?.length > 0 || a.correlated.services?.length > 0)
                            ? `${(a.correlated.pods?.length || 0)} pods, ${(a.correlated.containers?.length || 0)} containers, ${(a.correlated.services?.length || 0)} services`
                            : "-"}
                        </td>
                      </tr>
                    ))
                    ) : (
                      <tr><td colSpan={5} className="text-center py-8 text-sm text-gray-500">No live alerts — Prometheus connector may not be connected</td></tr>
                    )
                  })()}</tbody>
                </table>
              </div>
            </SectionCard>

            <SectionCard title="Legacy Alert Tracking" icon={Activity} iconColor="text-gray-500">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead><tr className="border-b border-gray-200 dark:border-gray-700">
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Alert</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Severity</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Status</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Value</th>
                  </tr></thead>
                  <tbody>{(() => {
                    const firing = (dashboard?.alerts as Record<string, unknown> | undefined)?.firing as unknown[] | undefined
                    return !firing?.length ? (
                    <tr><td colSpan={4} className="text-center py-8 text-sm text-gray-500">No legacy alerts tracked</td></tr>
                  ) : (
                    firing.slice(0, 30).map((a: any, i: number) => (
                      <tr key={i} className="border-b border-gray-100 dark:border-gray-700/50 hover:bg-gray-50 dark:hover:bg-gray-700/30">
                        <td className="py-2 px-3 font-medium text-gray-900 dark:text-white">{a.alert_name}</td>
                        <td className="py-2 px-3"><span className={`px-2 py-0.5 rounded text-xs font-medium ${a.severity === "critical" ? "bg-red-100 dark:bg-red-900/30 text-red-700" : a.severity === "warning" ? "bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700" : "bg-blue-100 dark:bg-blue-900/30 text-blue-700"}`}>{a.severity}</span></td>
                        <td className="py-2 px-3"><StatusBadge status={a.status} /></td>
                        <td className="py-2 px-3 font-mono text-xs text-gray-600 dark:text-gray-400">{a.value}</td>
                      </tr>
                    ))
                  )
                })()}
                  </tbody>
                </table>
              </div>
            </SectionCard>
          </div>
        )}

        {/* HEALTH TAB */}
        {activeTab === "Health" && (
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-5">
                <div className="flex items-center justify-between mb-3">
                  <h4 className="text-sm font-semibold text-gray-900 dark:text-white">Clusters</h4>
                  <Server size={18} className={ds.clusters?.healthy === ds.clusters?.total ? "text-green-500" : "text-yellow-500"} />
                </div>
                <div className="text-3xl font-bold text-gray-900 dark:text-white">{ds.clusters?.healthy || 0}/{ds.clusters?.total || 0}</div>
                <p className="text-xs text-gray-500 mt-1">Healthy clusters</p>
              </div>
              <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-5">
                <div className="flex items-center justify-between mb-3">
                  <h4 className="text-sm font-semibold text-gray-900 dark:text-white">Pods</h4>
                  <Box size={18} className={ds.pods?.failed === 0 ? "text-green-500" : "text-red-500"} />
                </div>
                <div className="text-3xl font-bold text-gray-900 dark:text-white">{ds.pods?.running || 0}/{ds.pods?.total || 0}</div>
                <p className="text-xs text-gray-500 mt-1">Running pods</p>
              </div>
              <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-5">
                <div className="flex items-center justify-between mb-3">
                  <h4 className="text-sm font-semibold text-gray-900 dark:text-white">Deployments</h4>
                  <Layers size={18} className={ds.deployments?.unavailable === 0 ? "text-green-500" : "text-red-500"} />
                </div>
                <div className="text-3xl font-bold text-gray-900 dark:text-white">{ds.deployments?.available || 0}/{ds.deployments?.total || 0}</div>
                <p className="text-xs text-gray-500 mt-1">Available deployments</p>
              </div>
              <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-5">
                <div className="flex items-center justify-between mb-3">
                  <h4 className="text-sm font-semibold text-gray-900 dark:text-white">Incidents</h4>
                  <AlertTriangle size={18} className={(ds.active_network_failures || 0) + (ds.alerts?.critical || 0) > 0 ? "text-red-500" : "text-green-500"} />
                </div>
                <div className="text-3xl font-bold text-gray-900 dark:text-white">{(ds.active_network_failures || 0) + (ds.alerts?.critical || 0)}</div>
                <p className="text-xs text-gray-500 mt-1">Active incidents</p>
              </div>
            </div>

            <SectionCard title="All Health Checks" icon={Shield} iconColor="text-green-500">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead><tr className="border-b border-gray-200 dark:border-gray-700">
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Component</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Status</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Details</th>
                  </tr></thead>
                  <tbody>
                    {[
                      { name: "Kubernetes Clusters", status: ds.clusters?.degraded === 0 ? "healthy" : "degraded", detail: `${ds.clusters?.healthy || 0} healthy, ${ds.clusters?.degraded || 0} degraded` },
                      { name: "Pods", status: ds.pods?.failed === 0 && ds.pods?.crashloop === 0 ? "healthy" : "degraded", detail: `${ds.pods?.running || 0} running, ${ds.pods?.failed || 0} failed, ${ds.pods?.crashloop || 0} crashloop` },
                      { name: "Deployments", status: ds.deployments?.unavailable === 0 ? "healthy" : "degraded", detail: `${ds.deployments?.available || 0} available, ${ds.deployments?.unavailable || 0} unavailable` },
                      { name: "Docker Containers", status: ds.containers?.error === 0 ? "healthy" : "degraded", detail: `${ds.containers?.running || 0} running, ${ds.containers?.error || 0} error` },
                      { name: "Helm Releases", status: ds.helm_releases?.failed === 0 ? "healthy" : "degraded", detail: `${ds.helm_releases?.deployed || 0} deployed, ${ds.helm_releases?.failed || 0} failed` },
                      { name: "Prometheus Alerts", status: ds.alerts?.critical === 0 && ds.alerts?.firing === 0 ? "healthy" : "degraded", detail: `${ds.alerts?.firing || 0} firing, ${ds.alerts?.critical || 0} critical` },
                      { name: "Traces", status: ds.traces?.error === 0 ? "healthy" : "degraded", detail: `${ds.traces?.ok || 0} ok, ${ds.traces?.error || 0} error` },
                      { name: "Network", status: (ds.active_network_failures || 0) === 0 ? "healthy" : "degraded", detail: `${ds.active_network_failures || 0} active failures` },
                    ].map((check, i) => (
                      <tr key={i} className="border-b border-gray-100 dark:border-gray-700/50 hover:bg-gray-50 dark:hover:bg-gray-700/30">
                        <td className="py-2 px-3 font-medium text-gray-900 dark:text-white">{check.name}</td>
                        <td className="py-2 px-3"><StatusBadge status={check.status} /></td>
                        <td className="py-2 px-3 text-gray-600 dark:text-gray-400 text-xs">{check.detail}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </SectionCard>

            {infraPvcs && infraPvcs.pvcs && infraPvcs.pvcs.length > 0 && (
              <SectionCard title="PVC Health" icon={Database} iconColor="text-blue-500">
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead><tr className="border-b border-gray-200 dark:border-gray-700">
                      <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Name</th>
                      <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Namespace</th>
                      <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Status</th>
                      <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Capacity</th>
                      <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Volume</th>
                    </tr></thead>
                    <tbody>
                      {(infraPvcs?.pvcs || []).map((p: any) => (
                        <tr key={p.pvc_id} className="border-b border-gray-100 dark:border-gray-700/50 hover:bg-gray-50 dark:hover:bg-gray-700/30">
                          <td className="py-2 px-3 font-medium text-gray-900 dark:text-white">{p.name}</td>
                          <td className="py-2 px-3 text-gray-600 dark:text-gray-400">{p.namespace}</td>
                          <td className="py-2 px-3"><StatusBadge status={p.status} /></td>
                          <td className="py-2 px-3 text-gray-600 dark:text-gray-400">{p.capacity_bytes ? `${(p.capacity_bytes / 1073741824).toFixed(1)} GB` : "-"}</td>
                          <td className="py-2 px-3 text-gray-600 dark:text-gray-400">{p.volume_name || "-"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </SectionCard>
            )}

            {infraNetFailures && infraNetFailures.network_failures && infraNetFailures.network_failures.length > 0 && (
              <SectionCard title="Network Failures" icon={Network} iconColor="text-red-500">
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead><tr className="border-b border-gray-200 dark:border-gray-700">
                      <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Source</th>
                      <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Destination</th>
                      <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Reason</th>
                      <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Protocol</th>
                      <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Detected</th>
                      <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Resolved</th>
                    </tr></thead>
                    <tbody>
                      {(infraNetFailures?.network_failures || []).map((f: any) => (
                        <tr key={f.failure_id} className="border-b border-gray-100 dark:border-gray-700/50 hover:bg-gray-50 dark:hover:bg-gray-700/30">
                          <td className="py-2 px-3 font-medium text-gray-900 dark:text-white">{f.source}</td>
                          <td className="py-2 px-3 text-gray-600 dark:text-gray-400">{f.destination}</td>
                          <td className="py-2 px-3 text-red-600">{f.reason}</td>
                          <td className="py-2 px-3 font-mono text-xs text-gray-600 dark:text-gray-400">{f.protocol}/{f.port}</td>
                          <td className="py-2 px-3 text-xs text-gray-500">{new Date(f.detected_at || Date.now()).toLocaleString()}</td>
                          <td className="py-2 px-3">{f.resolved ? <CheckCircle size={14} className="text-green-500" /> : <XCircle size={14} className="text-red-500" />}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </SectionCard>
            )}
          </div>
        )}
      </motion.div>
    </CortexShell>
  )
}
