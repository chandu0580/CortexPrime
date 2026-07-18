"use client"
import { useState } from "react"
import { motion } from "framer-motion"
import CortexShell from "@/components/layout/CortexShell"
import { stagger, variants } from "@/lib/motion-tokens"
import {
  useArgoCDApplications,
  useArgoCDApplication,
  useArgoCDProjects,
  useArgoCDRepositories,
  useArgoCDClusters,
  useArgoCDDrift,
  useArgoCDSync,
  useArgoCDRefresh,
  useArgoCDRollback,
  useArgoCDCorrelate,
  useArgoCDRevisions,
} from "@/hooks/queries/enterprise/useEnterpriseInfrastructure"
import {
  Activity, CheckCircle, XCircle, Clock, Loader2, AlertTriangle, RefreshCw,
  GitBranch, Box, Server, Layers, Shield, ExternalLink, ArrowRight,
  TrendingUp, TrendingDown, Minus, PlayCircle, RotateCcw, Search,
} from "lucide-react"

const tabs = ["Dashboard", "Applications", "Projects", "Repositories", "Clusters", "Drift", "Correlation"]

function StatusBadge({ status }: { status?: string }) {
  const s = (status || "").toLowerCase()
  if (s === "healthy" || s === "synced" || s === "ready" || s === "running" || s === "available")
    return <span className="inline-flex items-center gap-1 text-xs font-medium text-green-600 dark:text-green-400"><CheckCircle size={12} />{status}</span>
  if (s === "degraded" || s === "outofsync" || s === "failed" || s === "error" || s === "missing")
    return <span className="inline-flex items-center gap-1 text-xs font-medium text-red-600 dark:text-red-400"><XCircle size={12} />{status}</span>
  if (s === "progressing" || s === "pending" || s === "syncing")
    return <span className="inline-flex items-center gap-1 text-xs font-medium text-yellow-600 dark:text-yellow-400"><Clock size={12} />{status}</span>
  return <span className="inline-flex items-center gap-1 text-xs font-medium text-gray-500 dark:text-gray-400"><Activity size={12} />{status || "unknown"}</span>
}

function KpiCard({ icon: Icon, label, value, color }: { icon: any; label: string; value: number | string; color: string }) {
  return (
    <motion.div variants={variants.fadeIn} className={`rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4 ${color}`}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">{label}</p>
          <p className="text-2xl font-bold text-gray-900 dark:text-white mt-1">{value}</p>
        </div>
        <div className={`p-3 rounded-lg ${color.replace('text-', 'bg-').replace('600', '100').replace('500', '100')} dark:bg-gray-700`}>
          <Icon size={24} className={color} />
        </div>
      </div>
    </motion.div>
  )
}

function HealthBar({ label, ok, total }: { label: string; ok: number; total: number }) {
  const pct = total > 0 ? Math.round((ok / total) * 100) : 0
  return (
    <div className="flex items-center gap-3 text-sm">
      <span className="w-24 text-gray-600 dark:text-gray-400">{label}</span>
      <div className="flex-1 h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-all ${pct >= 90 ? 'bg-green-500' : pct >= 70 ? 'bg-yellow-500' : 'bg-red-500'}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-gray-500 dark:text-gray-400 w-16 text-right">{ok}/{total}</span>
    </div>
  )
}

export default function EnterpriseGitopsCenter() {
  const [activeTab, setActiveTab] = useState("Dashboard")
  const [selectedApp, setSelectedApp] = useState("")
  const [searchQuery, setSearchQuery] = useState("")

  const { data: apps, isLoading: appsLoading } = useArgoCDApplications()
  const { data: appDetail, isLoading: appDetailLoading } = useArgoCDApplication(selectedApp)
  const { data: revisions } = useArgoCDRevisions(selectedApp)
  const { data: projects } = useArgoCDProjects()
  const { data: repos } = useArgoCDRepositories()
  const { data: clusters } = useArgoCDClusters()
  const { data: drift } = useArgoCDDrift()

  const syncMut = useArgoCDSync()
  const refreshMut = useArgoCDRefresh()
  const rollbackMut = useArgoCDRollback()
  const correlateMut = useArgoCDCorrelate()

  const filteredApps = (apps?.applications || []).filter((a: any) =>
    !searchQuery || a.name?.toLowerCase().includes(searchQuery.toLowerCase()) || a.project?.toLowerCase().includes(searchQuery.toLowerCase())
  )

  const appsCount = apps?.total || 0
  const syncedCount = apps?.sync_counts?.Synced || 0
  const healthyCount = apps?.health_counts?.Healthy || 0
  const outOfSync = apps?.out_of_sync || 0
  const degraded = apps?.degraded || 0
  const projectsCount = projects?.total || 0
  const reposCount = repos?.total || 0
  const clustersCount = clusters?.total || 0
  const driftCount = drift?.drift_count || 0

  return (
    <CortexShell>
      <motion.div variants={stagger()} initial="hidden" animate="visible" className="p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Enterprise GitOps Center</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">ArgoCD — Application lifecycle, drift detection, and GitOps correlation</p>
          </div>
          <div className="flex items-center gap-2">
            <Search size={16} className="text-gray-400" />
            <input
              type="text"
              placeholder="Search applications..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              className="text-sm border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-1.5 bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 border-b border-gray-200 dark:border-gray-700">
          {tabs.map(t => (
            <button key={t} onClick={() => setActiveTab(t)}
              className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${activeTab === t ? 'border-blue-600 text-blue-600 dark:text-blue-400 dark:border-blue-400' : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'}`}>
              {t}
            </button>
          ))}
        </div>

        {activeTab === "Dashboard" && (
          <motion.div variants={stagger()} initial="hidden" animate="visible" className="space-y-6">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <KpiCard icon={GitBranch} label="Applications" value={appsCount} color="text-blue-600" />
              <KpiCard icon={Shield} label="Synced" value={syncedCount} color="text-green-600" />
              <KpiCard icon={AlertTriangle} label="Out of Sync" value={outOfSync} color="text-red-600" />
              <KpiCard icon={AlertTriangle} label="Degraded" value={degraded} color="text-orange-600" />
              <KpiCard icon={Layers} label="Projects" value={projectsCount} color="text-purple-600" />
              <KpiCard icon={Server} label="Repositories" value={reposCount} color="text-indigo-600" />
              <KpiCard icon={Box} label="Clusters" value={clustersCount} color="text-teal-600" />
              <KpiCard icon={AlertTriangle} label="Drifts" value={driftCount} color="text-red-600" />
            </div>
          </motion.div>
        )}

        {activeTab === "Applications" && (
          <motion.div variants={stagger()} initial="hidden" animate="visible" className="space-y-4">
            {/* Summary */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
              <div className="rounded-lg bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 p-3">
                <p className="text-xs text-green-600 dark:text-green-400">Synced</p>
                <p className="text-xl font-bold text-green-700 dark:text-green-300">{syncedCount}</p>
              </div>
              <div className="rounded-lg bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 p-3">
                <p className="text-xs text-yellow-600 dark:text-yellow-400">Progressing</p>
                <p className="text-xl font-bold text-yellow-700 dark:text-yellow-300">{apps?.sync_counts?.Progressing || 0}</p>
              </div>
              <div className="rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 p-3">
                <p className="text-xs text-red-600 dark:text-red-400">Out of Sync</p>
                <p className="text-xl font-bold text-red-700 dark:text-red-300">{outOfSync}</p>
              </div>
              <div className="rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 p-3">
                <p className="text-xs text-red-600 dark:text-red-400">Degraded</p>
                <p className="text-xl font-bold text-red-700 dark:text-red-300">{degraded}</p>
              </div>
            </div>

            {appsLoading ? (
              <div className="flex items-center justify-center py-12"><Loader2 size={32} className="animate-spin text-gray-400" /></div>
            ) : filteredApps.length === 0 ? (
              <div className="text-center py-12 text-gray-500 dark:text-gray-400">No applications found</div>
            ) : (
              <div className="overflow-x-auto rounded-xl border border-gray-200 dark:border-gray-700">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 dark:bg-gray-800">
                    <tr>
                      <th className="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400">Name</th>
                      <th className="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400">Project</th>
                      <th className="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400">Sync Status</th>
                      <th className="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400">Health</th>
                      <th className="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400">Namespace</th>
                      <th className="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                    {filteredApps.map((app: any) => (
                      <tr key={app.name} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                        <td className="px-4 py-3">
                          <button onClick={() => { setSelectedApp(app.name); setActiveTab("Correlation") }} className="font-medium text-blue-600 dark:text-blue-400 hover:underline">{app.name}</button>
                        </td>
                        <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{app.project || "-"}</td>
                        <td className="px-4 py-3"><StatusBadge status={app.sync_status} /></td>
                        <td className="px-4 py-3"><StatusBadge status={app.health_status} /></td>
                        <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{app.dest_namespace || "-"}</td>
                        <td className="px-4 py-3">
                          <div className="flex gap-2">
                            <button onClick={() => syncMut.mutate({ name: app.name })} className="text-xs px-2 py-1 rounded bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 hover:bg-blue-100 dark:hover:bg-blue-900/50" title="Sync"><RefreshCw size={14} /></button>
                            <button onClick={() => refreshMut.mutate(app.name)} className="text-xs px-2 py-1 rounded bg-green-50 dark:bg-green-900/30 text-green-600 dark:text-green-400 hover:bg-green-100 dark:hover:bg-green-900/50" title="Refresh"><RotateCcw size={14} /></button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </motion.div>
        )}

        {activeTab === "Projects" && (
          <motion.div variants={stagger()} initial="hidden" animate="visible" className="space-y-4">
            {projects?.projects?.length ? (
              <div className="overflow-x-auto rounded-xl border border-gray-200 dark:border-gray-700">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 dark:bg-gray-800">
                    <tr>
                      <th className="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400">Project</th>
                      <th className="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400">Source Repos</th>
                      <th className="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400">Destinations</th>
                      <th className="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400">Description</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                    {projects.projects.map((p: any) => (
                      <tr key={p.name} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                        <td className="px-4 py-3 font-medium text-gray-900 dark:text-white">{p.name}</td>
                        <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{(p.source_repos || []).length} repos</td>
                        <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{(p.destinations || []).length} clusters</td>
                        <td className="px-4 py-3 text-gray-500 dark:text-gray-400 max-w-xs truncate">{p.description || "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : <div className="text-center py-12 text-gray-500 dark:text-gray-400">No projects found</div>}
          </motion.div>
        )}

        {activeTab === "Repositories" && (
          <motion.div variants={stagger()} initial="hidden" animate="visible" className="space-y-4">
            {repos?.repos?.length ? (
              <div className="overflow-x-auto rounded-xl border border-gray-200 dark:border-gray-700">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 dark:bg-gray-800">
                    <tr>
                      <th className="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400">Repo</th>
                      <th className="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400">Type</th>
                      <th className="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400">Connection State</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                    {repos.repos.map((r: any) => (
                      <tr key={r.repo} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                        <td className="px-4 py-3 font-medium text-blue-600 dark:text-blue-400">{r.repo}</td>
                        <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{r.type || "git"}</td>
                        <td className="px-4 py-3"><StatusBadge status={r.connection_state || "active"} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : <div className="text-center py-12 text-gray-500 dark:text-gray-400">No repositories found</div>}
          </motion.div>
        )}

        {activeTab === "Clusters" && (
          <motion.div variants={stagger()} initial="hidden" animate="visible" className="space-y-4">
            {clusters?.clusters?.length ? (
              <div className="overflow-x-auto rounded-xl border border-gray-200 dark:border-gray-700">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 dark:bg-gray-800">
                    <tr>
                      <th className="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400">Name</th>
                      <th className="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400">Server</th>
                      <th className="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400">Namespaces</th>
                      <th className="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400">Connection State</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                    {clusters.clusters.map((c: any) => (
                      <tr key={c.name || c.server} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                        <td className="px-4 py-3 font-medium text-gray-900 dark:text-white">{c.name || c.server?.split("//")[1] || c.server}</td>
                        <td className="px-4 py-3 text-xs text-gray-500 dark:text-gray-400 max-w-[200px] truncate">{c.server}</td>
                        <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{(c.namespaces || []).length}</td>
                        <td className="px-4 py-3"><StatusBadge status={c.connection_state || "unknown"} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : <div className="text-center py-12 text-gray-500 dark:text-gray-400">No clusters found</div>}
          </motion.div>
        )}

        {activeTab === "Drift" && (
          <motion.div variants={stagger()} initial="hidden" animate="visible" className="space-y-4">
            {drift ? (
              <div className="space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  <KpiCard icon={AlertTriangle} label="Drift Count" value={drift.drift_count || 0} color="text-red-600" />
                  <KpiCard icon={Activity} label="Risk Score" value={drift.risk_score || 0} color={drift.risk_score > 50 ? "text-red-600" : drift.risk_score > 20 ? "text-yellow-600" : "text-green-600"} />
                  <KpiCard icon={Shield} label="Healthy" value={(drift.drifts || []).filter((d: any) => d.type === "healthy").length} color="text-green-600" />
                </div>
                {(drift.drifts || []).length > 0 && (
                  <div className="overflow-x-auto rounded-xl border border-gray-200 dark:border-gray-700">
                    <table className="w-full text-sm">
                      <thead className="bg-gray-50 dark:bg-gray-800">
                        <tr>
                          <th className="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400">Application</th>
                          <th className="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400">Type</th>
                          <th className="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400">Status</th>
                          <th className="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400">Risk</th>
                          <th className="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400">Detail</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                        {drift.drifts.map((d: any, i: number) => (
                          <tr key={i} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                            <td className="px-4 py-3 font-medium text-gray-900 dark:text-white">{d.application || "-"}</td>
                            <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{d.type || "-"}</td>
                            <td className="px-4 py-3"><StatusBadge status={d.status || d.type} /></td>
                            <td className="px-4 py-3">
                              <span className={`px-2 py-0.5 rounded text-xs font-medium ${(d.risk_score || d.risk || 0) > 50 ? 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300' : (d.risk_score || d.risk || 0) > 20 ? 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-300' : 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300'}`}>
                                {d.risk_score || d.risk || 0}
                              </span>
                            </td>
                            <td className="px-4 py-3 text-xs text-gray-500 dark:text-gray-400 max-w-xs truncate">{d.message || d.detail || ""}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            ) : <div className="text-center py-12 text-gray-500 dark:text-gray-400">Loading drift data...</div>}
          </motion.div>
        )}

        {activeTab === "Correlation" && (
          <motion.div variants={stagger()} initial="hidden" animate="visible" className="space-y-4">
            <div className="flex items-center gap-4 mb-4">
              <input
                type="text"
                placeholder="Application name"
                value={selectedApp}
                onChange={e => setSelectedApp(e.target.value)}
                className="flex-1 border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <button onClick={() => correlateMut.mutate(selectedApp)} disabled={!selectedApp || correlateMut.isPending}
                className="px-4 py-2 text-sm font-medium bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed">
                {correlateMut.isPending ? <Loader2 size={14} className="animate-spin" /> : "Correlate"}
              </button>
            </div>
            {correlateMut.data && (
              <pre className="text-xs text-gray-600 dark:text-gray-400 bg-gray-50 dark:bg-gray-800/50 rounded-xl p-4 max-h-[600px] overflow-auto">
                {JSON.stringify(correlateMut.data, null, 2)}
              </pre>
            )}
            {selectedApp && appDetail && (
              <div className="space-y-4">
                <div className="rounded-xl border border-gray-200 dark:border-gray-700 p-4">
                  <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3">{selectedApp} — Detail</h3>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                    <div><span className="text-xs text-gray-500 dark:text-gray-400">Project:</span><p className="text-sm font-medium">{appDetail.project || "-"}</p></div>
                    <div><span className="text-xs text-gray-500 dark:text-gray-400">Sync:</span><p className="text-sm font-medium"><StatusBadge status={appDetail.sync_status} /></p></div>
                    <div><span className="text-xs text-gray-500 dark:text-gray-400">Health:</span><p className="text-sm font-medium"><StatusBadge status={appDetail.health_status} /></p></div>
                    <div><span className="text-xs text-gray-500 dark:text-gray-400">Namespace:</span><p className="text-sm font-medium">{appDetail.dest_namespace || "-"}</p></div>
                    <div><span className="text-xs text-gray-500 dark:text-gray-400">Server:</span><p className="text-sm font-medium truncate">{appDetail.dest_server || "-"}</p></div>
                    <div><span className="text-xs text-gray-500 dark:text-gray-400">Repo URL:</span><p className="text-sm font-medium truncate">{appDetail.repo_url || appDetail.source?.repo_url || "-"}</p></div>
                  </div>
                </div>
                {revisions && (
                  <div className="rounded-xl border border-gray-200 dark:border-gray-700 p-4">
                    <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3">Revision History</h3>
                    <div className="space-y-2 max-h-[300px] overflow-auto">
                      {(revisions.revisions || revisions.revision_history || revisions.history || []).slice(0, 10).map((r: any, i: number) => (
                        <div key={i} className="flex items-center justify-between text-xs bg-gray-50 dark:bg-gray-800/50 rounded-lg p-2">
                          <span className="font-mono text-gray-900 dark:text-white">{r.revision?.substring(0, 12) || r.id || `rev-${i}`}</span>
                          <span className="text-gray-500 dark:text-gray-400">{new Date(r.deployed_at || r.deployedAt || r.timestamp || r.deployed_at || "").toLocaleString()}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </motion.div>
        )}
      </motion.div>
    </CortexShell>
  )
}
