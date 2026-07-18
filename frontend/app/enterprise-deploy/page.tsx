"use client"

import { useState } from "react"
import { motion } from "framer-motion"
import CortexShell from "@/components/layout/CortexShell"
import { stagger, variants } from "@/lib/motion-tokens"
import {
  useEnvironmentList,
  useDeploymentList,
  useCreateEnvironment,
  useCreateDeployment,
  useExecuteDeployment,
  useRollbackDeployment,
} from "@/hooks/queries/enterprise/useEnterpriseDeploy"
import {
  Activity,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Globe,
  Loader2,
  Play,
  Plus,
  RotateCcw,
  Server,
  Shield,
  Trash2,
  XCircle,
} from "lucide-react"

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    pending: "bg-gray-100 text-gray-600",
    deploying: "bg-blue-50 text-blue-600",
    deployed: "bg-[#F0FDF4] text-[#38B88A]",
    failed: "bg-red-50 text-red-600",
    rolled_back: "bg-amber-50 text-amber-600",
  }
  return (
    <span className={`rounded-full px-2 py-0.5 text-[0.55rem] font-medium capitalize ${colors[status] || "bg-gray-100 text-gray-600"}`}>
      {status}
    </span>
  )
}

function HealthDot({ health }: { health: string }) {
  const colors: Record<string, string> = {
    healthy: "bg-[#38B88A]",
    degraded: "bg-amber-400",
    down: "bg-red-500",
    unknown: "bg-gray-300",
  }
  return <span className={`inline-block h-2 w-2 rounded-full ${colors[health] || "bg-gray-300"}`} />
}

export default function EnterpriseDeployCenter() {
  const [activeTab, setActiveTab] = useState("deployments")
  const [showCreateDeploy, setShowCreateDeploy] = useState(false)
  const [newDepWs, setNewDepWs] = useState("")
  const [newDepEnv, setNewDepEnv] = useState("")
  const [newDepVer, setNewDepVer] = useState("1.0.0")
  const [showCreateEnv, setShowCreateEnv] = useState(false)
  const [newEnvName, setNewEnvName] = useState("")
  const [newEnvType, setNewEnvType] = useState("development")

  const { data: environments } = useEnvironmentList()
  const { data: deployments } = useDeploymentList()
  const createEnvMutation = useCreateEnvironment()
  const createDepMutation = useCreateDeployment()
  const executeMutation = useExecuteDeployment()
  const rollbackMutation = useRollbackDeployment()

  const handleCreateEnv = async () => {
    if (!newEnvName) return
    try {
      await createEnvMutation.mutateAsync({ name: newEnvName, env_type: newEnvType })
      setNewEnvName("")
      setShowCreateEnv(false)
    } catch (err) { console.error(err) }
  }

  const handleCreateDeploy = async () => {
    if (!newDepWs || !newDepEnv) return
    try {
      const dep = await createDepMutation.mutateAsync({
        workspace_id: newDepWs,
        environment_id: newDepEnv,
        version: newDepVer,
      })
      await executeMutation.mutateAsync(dep.id)
      setNewDepWs("")
      setNewDepEnv("")
      setShowCreateDeploy(false)
    } catch (err) { console.error(err) }
  }

  const tabs = [
    { id: "deployments", label: "Deployments", icon: Activity },
    { id: "environments", label: "Environments", icon: Globe },
  ]

  return (
    <CortexShell title="Deployment Engine" subtitle="Deploy artifacts to environments with rollback support">
      <div className="relative z-10 mx-auto max-w-7xl space-y-6">
        {/* Summary Cards */}
        <motion.div initial="hidden" animate="visible" variants={stagger(0.04, 0.01)} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[
            { icon: Activity, label: "Total Deployments", value: deployments?.length ?? "-", color: "bg-blue-500" },
            { icon: CheckCircle2, label: "Deployed", value: deployments?.filter(d => d.status === "deployed").length ?? "-", color: "bg-[#38B88A]" },
            { icon: Globe, label: "Environments", value: environments?.length ?? "-", color: "bg-purple-500" },
            { icon: RotateCcw, label: "Rolled Back", value: deployments?.filter(d => d.status === "rolled_back").length ?? "-", color: "bg-amber-500" },
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

        {/* Tab Nav */}
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[#E8EDF3] bg-white p-1">
          <div className="flex flex-wrap gap-1">
            {tabs.map((tab) => {
              const TabIcon = tab.icon
              const isActive = activeTab === tab.id
              return (
                <button key={tab.id} onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center gap-2 rounded-lg px-3.5 py-2 text-[0.75rem] font-medium transition-all ${
                    isActive ? "bg-[#38B88A] text-white shadow-sm" : "text-[#6B7280] hover:bg-[#F4F7FA]"
                  }`}>
                  <TabIcon className="h-3.5 w-3.5" /> {tab.label}
                </button>
              )
            })}
          </div>
          <div className="flex items-center gap-2">
            <button onClick={() => setShowCreateEnv(!showCreateEnv)}
              className="flex items-center gap-1.5 rounded-lg border border-gray-300 px-3 py-1.5 text-[0.65rem] font-medium text-gray-600 hover:bg-[#F4F7FA]">
              <Plus className="h-3.5 w-3.5" /> New Env
            </button>
            <button onClick={() => setShowCreateDeploy(!showCreateDeploy)}
              className="flex items-center gap-1.5 rounded-lg border border-[#38B88A]/30 px-3 py-1.5 text-[0.65rem] font-medium text-[#38B88A] hover:bg-[#F0FDF4]">
              <Play className="h-3.5 w-3.5" /> New Deploy
            </button>
          </div>
        </div>

        {/* Create Forms */}
        {showCreateEnv && (
          <div className="rounded-xl border border-purple-200 bg-purple-50 p-4">
            <h3 className="mb-3 text-sm font-bold text-[#111827]">Create Environment</h3>
            <div className="grid gap-3 sm:grid-cols-3">
              <input value={newEnvName} onChange={e => setNewEnvName(e.target.value)} placeholder="Environment name" className="rounded-lg border border-[#E8EDF3] px-3 py-2 text-[0.78rem] outline-none" />
              <select value={newEnvType} onChange={e => setNewEnvType(e.target.value)} className="rounded-lg border border-[#E8EDF3] px-3 py-2 text-[0.78rem] outline-none">
                {["development", "staging", "production", "qa", "demo"].map(t => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
              <button onClick={handleCreateEnv} disabled={!newEnvName || createEnvMutation.isPending}
                className="rounded-lg bg-purple-500 px-4 py-2 text-[0.72rem] font-bold text-white disabled:opacity-50">
                {createEnvMutation.isPending ? <Loader2 className="inline h-3.5 w-3.5 animate-spin" /> : "Create"}
              </button>
            </div>
          </div>
        )}

        {showCreateDeploy && (
          <div className="rounded-xl border border-[#38B88A]/30 bg-[#F0FDF4] p-4">
            <h3 className="mb-3 text-sm font-bold text-[#111827]">Create Deployment</h3>
            <div className="grid gap-3 sm:grid-cols-3">
              <select value={newDepWs} onChange={e => setNewDepWs(e.target.value)} className="rounded-lg border border-[#E8EDF3] px-3 py-2 text-[0.78rem] outline-none">
                <option value="">Workspace</option>
              </select>
              <select value={newDepEnv} onChange={e => setNewDepEnv(e.target.value)} className="rounded-lg border border-[#E8EDF3] px-3 py-2 text-[0.78rem] outline-none">
                <option value="">Environment...</option>
                {environments?.map(env => (
                  <option key={env.id} value={env.id}>{env.name} ({env.type})</option>
                ))}
              </select>
              <input value={newDepVer} onChange={e => setNewDepVer(e.target.value)} placeholder="Version" className="rounded-lg border border-[#E8EDF3] px-3 py-2 text-[0.78rem] outline-none" />
            </div>
            <button onClick={handleCreateDeploy} disabled={!newDepWs || !newDepEnv || createDepMutation.isPending}
              className="mt-3 flex items-center gap-2 rounded-lg bg-[#38B88A] px-4 py-2 text-[0.72rem] font-bold text-white disabled:opacity-50">
              {createDepMutation.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
              Deploy
            </button>
          </div>
        )}

        {/* Deployments Tab */}
        {activeTab === "deployments" && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-3">
            {deployments?.map((dep) => (
              <div key={dep.id} className={`rounded-xl border-l-4 p-4 ${
                dep.status === "deployed" ? "border-l-[#38B88A]" :
                dep.status === "failed" ? "border-l-red-400" :
                dep.status === "rolled_back" ? "border-l-amber-400" :
                "border-l-blue-400"
              } bg-white`}>
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0 flex-1">
                    <div className="mb-1 flex items-center gap-2">
                      <StatusBadge status={dep.status} />
                      <span className="text-[0.55rem] text-[#9CA3AF]">{dep.id}</span>
                    </div>
                    <p className="text-[0.78rem] font-medium text-[#111827]">{dep.environment_name} <span className="text-[#6B7280]">v{dep.version}</span></p>
                    <div className="mt-1 flex flex-wrap items-center gap-3 text-[0.55rem] text-[#6B7280]">
                      <span className="flex items-center gap-1"><Server className="h-3 w-3" />{dep.strategy}</span>
                      <span className="flex items-center gap-1"><Shield className="h-3 w-3" />{dep.approvals_granted?.length ?? 0}/{dep.approvals_required ?? 0} approvals</span>
                    </div>
                    {dep.log?.length > 0 && dep.status === "deploying" && (
                      <div className="mt-2 max-h-16 overflow-y-auto rounded-lg bg-[#1E293B] p-2 font-mono text-[0.5rem] text-[#94A3B8]">
                        {dep.log.slice(-3).map((entry: any, i: number) => (
                          <div key={i}>{entry.message}</div>
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    {dep.status === "pending" && (
                      <button onClick={() => executeMutation.mutate(dep.id)} className="rounded-lg p-1.5 text-[#38B88A] hover:bg-[#F0FDF4]">
                        <Play className="h-4 w-4" />
                      </button>
                    )}
                    {(dep.status === "deployed" || dep.status === "failed") && (
                      <button onClick={() => rollbackMutation.mutate(dep.id)} className="rounded-lg p-1.5 text-amber-500 hover:bg-amber-50">
                        <RotateCcw className="h-4 w-4" />
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))}
            {(!deployments || deployments.length === 0) && (
              <div className="flex flex-col items-center rounded-xl border border-[#E8EDF3] bg-white py-16 text-[#9CA3AF]">
                <Activity className="mb-3 h-10 w-10 opacity-30" />
                <p className="text-sm">No deployments yet.</p>
              </div>
            )}
          </motion.div>
        )}

        {/* Environments Tab */}
        {activeTab === "environments" && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {environments?.map((env) => (
              <div key={env.id} className="rounded-xl border border-[#E8EDF3] bg-white p-4">
                <div className="mb-3 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <HealthDot health={env.health} />
                    <h3 className="text-[0.82rem] font-bold text-[#111827]">{env.name}</h3>
                  </div>
                  <span className="rounded bg-[#F4F7FA] px-2 py-0.5 text-[0.5rem] text-[#6B7280]">{env.type}</span>
                </div>
                <div className="space-y-1 text-[0.6rem] text-[#6B7280]">
                  <p>Region: {env.region}</p>
                  <p>Health: <span className="capitalize">{env.health}</span></p>
                  {env.url && <p className="truncate">URL: {env.url}</p>}
                  <p>Deployments: {env.deployment_history?.length ?? 0}</p>
                </div>
              </div>
            ))}
            {(!environments || environments.length === 0) && (
              <div className="col-span-full flex flex-col items-center rounded-xl border border-[#E8EDF3] bg-white py-16 text-[#9CA3AF]">
                <Globe className="mb-3 h-10 w-10 opacity-30" />
                <p className="text-sm">No environments configured.</p>
              </div>
            )}
          </motion.div>
        )}
      </div>
    </CortexShell>
  )
}
