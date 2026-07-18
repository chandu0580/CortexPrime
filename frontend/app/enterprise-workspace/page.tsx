"use client"

import { useState } from "react"
import { motion } from "framer-motion"
import CortexShell from "@/components/layout/CortexShell"
import { stagger, variants } from "@/lib/motion-tokens"
import {
  useWorkspaceList,
  useWorkspaceDetail,
  useWorkspaceStatus,
  useWorkspaceArtifacts,
  useRepositories,
  useRepositoryIntelligence,
  useCreateWorkspace,
  useDestroyWorkspace,
  useCheckoutBranch,
} from "@/hooks/queries/enterprise/useEnterpriseWorkspace"
import {
  Activity,
  AlertTriangle,
  BarChart3,
  BookOpen,
  Box,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Code2,
  Cpu,
  Eye,
  FileCode,
  GitBranch,
  Globe,
  Layers,
  Loader2,
  Lock,
  Package,
  Plus,
  Search,
  Shield,
  Terminal,
  Trash2,
  Wrench,
  Zap,
} from "lucide-react"

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    ready: "bg-[#F0FDF4] text-[#38B88A]",
    creating: "bg-blue-50 text-blue-600",
    active: "bg-amber-50 text-amber-600",
    closing: "bg-gray-100 text-gray-600",
    destroyed: "bg-red-50 text-red-500",
  }
  return (
    <span className={`rounded-full px-2 py-0.5 text-[0.55rem] font-medium capitalize ${colors[status] || "bg-gray-100 text-gray-600"}`}>
      {status}
    </span>
  )
}

function LanguageBar({ languages }: { languages: Record<string, number> }) {
  const total = Object.values(languages).reduce((a, b) => a + b, 0) || 1
  const colors = ["bg-blue-400", "bg-[#38B88A]", "bg-amber-400", "bg-purple-400", "bg-red-400", "bg-teal-400"]
  return (
    <div className="flex h-2 overflow-hidden rounded-full bg-[#F3F4F6]">
      {Object.entries(languages).slice(0, 6).map(([lang, count], i) => (
        <div key={lang} className={colors[i % colors.length]} style={{ width: `${(count / total) * 100}%` }}
          title={`${lang}: ${count}`} />
      ))}
    </div>
  )
}

export default function EngineeringWorkspaceCenter() {
  const [activeTab, setActiveTab] = useState("workspaces")
  const [selectedWs, setSelectedWs] = useState("")
  const [wsName, setWsName] = useState("")
  const [wsRepo, setWsRepo] = useState("")
  const [wsBranch, setWsBranch] = useState("main")
  const [repoUrl, setRepoUrl] = useState("")
  const [showCreate, setShowCreate] = useState(false)

  const { data: workspaces, isLoading: wsLoading } = useWorkspaceList()
  const { data: wsDetail } = useWorkspaceDetail(selectedWs)
  const { data: wsStatus } = useWorkspaceStatus(selectedWs)
  const { data: artifacts } = useWorkspaceArtifacts(selectedWs)
  const { data: repos } = useRepositories()
  const { data: repoIntel } = useRepositoryIntelligence(repoUrl)
  const createMutation = useCreateWorkspace()
  const destroyMutation = useDestroyWorkspace()
  const checkoutMutation = useCheckoutBranch()

  const handleCreate = async () => {
    if (!wsName) return
    try {
      await createMutation.mutateAsync({ name: wsName, repoUrl: wsRepo || undefined, branch: wsBranch })
      setWsName("")
      setWsRepo("")
      setWsBranch("main")
      setShowCreate(false)
    } catch (err) {
      console.error("Create workspace failed:", err)
    }
  }

  const tabs = [
    { id: "workspaces", label: "Workspaces", icon: Box },
    { id: "repositories", label: "Repositories", icon: Globe },
    { id: "intelligence", label: "Repository Intelligence", icon: Cpu },
  ]

  return (
    <CortexShell title="Engineering Workspace Center" subtitle="Managed workspaces for every engineering task — isolated, tracked, and replayable">
      <div className="relative z-10 mx-auto max-w-7xl space-y-6">
        {/* Tab Navigation */}
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[#E8EDF3] bg-white p-1">
          <div className="flex flex-wrap gap-1">
            {tabs.map((tab) => {
              const TabIcon = tab.icon
              const isActive = activeTab === tab.id
              return (
                <button
                  key={tab.id}
                  onClick={() => { setActiveTab(tab.id); setSelectedWs("") }}
                  className={`flex items-center gap-2 rounded-lg px-3.5 py-2 text-[0.75rem] font-medium transition-all ${
                    isActive ? "bg-[#38B88A] text-white shadow-sm" : "text-[#6B7280] hover:bg-[#F4F7FA]"
                  }`}
                >
                  <TabIcon className="h-3.5 w-3.5" />
                  {tab.label}
                </button>
              )
            })}
          </div>
          {activeTab === "workspaces" && (
            <button onClick={() => setShowCreate(!showCreate)}
              className="flex items-center gap-1.5 rounded-lg border border-[#38B88A]/30 px-3 py-1.5 text-[0.65rem] font-medium text-[#38B88A] hover:bg-[#F0FDF4]">
              <Plus className="h-3.5 w-3.5" /> New Workspace
            </button>
          )}
        </div>

        {/* Workspaces Tab */}
        {activeTab === "workspaces" && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
            {/* Create Form */}
            {showCreate && (
              <div className="rounded-xl border border-[#38B88A]/30 bg-[#F0FDF4] p-4">
                <h3 className="mb-3 text-sm font-bold text-[#111827]">Create Workspace</h3>
                <div className="grid gap-3 sm:grid-cols-3">
                  <input type="text" value={wsName} onChange={e => setWsName(e.target.value)}
                    placeholder="Workspace name" className="rounded-lg border border-[#E8EDF3] px-3 py-2 text-[0.78rem] outline-none" />
                  <input type="text" value={wsRepo} onChange={e => setWsRepo(e.target.value)}
                    placeholder="Repository URL (optional)" className="rounded-lg border border-[#E8EDF3] px-3 py-2 text-[0.78rem] outline-none" />
                  <input type="text" value={wsBranch} onChange={e => setWsBranch(e.target.value)}
                    placeholder="Branch" className="rounded-lg border border-[#E8EDF3] px-3 py-2 text-[0.78rem] outline-none" />
                </div>
                <button onClick={handleCreate} disabled={!wsName || createMutation.isPending}
                  className="mt-3 flex items-center gap-2 rounded-lg bg-[#38B88A] px-4 py-2 text-[0.72rem] font-bold text-white disabled:opacity-50">
                  {createMutation.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />}
                  Create Workspace
                </button>
              </div>
            )}

            {/* Workspace List */}
            <div className="grid gap-4 lg:grid-cols-3">
              <div className="lg:col-span-1">
                <div className="rounded-xl border border-[#E8EDF3] bg-white p-4">
                  <h3 className="mb-3 text-sm font-bold text-[#111827]">All Workspaces ({workspaces?.length ?? 0})</h3>
                  {wsLoading ? (
                    <div className="flex justify-center py-4"><Loader2 className="h-4 w-4 animate-spin text-[#6B7280]" /></div>
                  ) : workspaces?.length === 0 ? (
                    <p className="text-center text-[0.7rem] text-[#9CA3AF] py-4">No workspaces yet.</p>
                  ) : (
                    <div className="space-y-1.5">
                      {workspaces?.map((ws) => (
                        <button key={ws.id} onClick={() => setSelectedWs(ws.id)}
                          className={`w-full rounded-lg border px-3 py-2 text-left transition-all ${
                            selectedWs === ws.id ? "border-[#38B88A] bg-[#F0FDF4]" : "border-[#E8EDF3] hover:bg-[#FAFBFC]"
                          }`}>
                          <div className="flex items-center justify-between">
                            <p className="text-[0.72rem] font-medium text-[#111827] truncate">{ws.name}</p>
                            <StatusBadge status={ws.status} />
                          </div>
                          <p className="mt-0.5 text-[0.55rem] text-[#9CA3AF] truncate">
                            {ws.repo_url ? ws.repo_url.split("/").slice(-2).join("/") : "no repo"} @ {ws.branch}
                            {ws.locked && " \u{1F512}"}
                          </p>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* Workspace Detail */}
              <div className="lg:col-span-2">
                {selectedWs && wsDetail ? (
                  <div className="rounded-xl border border-[#E8EDF3] bg-white p-5">
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <h2 className="text-lg font-bold text-[#111827]">{wsDetail.name}</h2>
                        <p className="mt-0.5 text-[0.7rem] text-[#6B7280]">{wsDetail.id}</p>
                      </div>
                      <div className="flex items-center gap-2">
                        <StatusBadge status={wsDetail.status} />
                        {wsDetail.locked && <Lock className="h-3.5 w-3.5 text-amber-500" />}
                        <button onClick={() => destroyMutation.mutate(wsDetail.id)}
                          className="rounded-lg p-1.5 text-red-400 hover:bg-red-50">
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </div>

                    {/* Quick Info */}
                    <div className="mt-4 grid gap-3 sm:grid-cols-3">
                      <div className="rounded-lg bg-[#FAFBFC] px-3 py-2">
                        <p className="text-[0.55rem] font-medium text-[#9CA3AF]">Repository</p>
                        <p className="text-[0.72rem] font-medium text-[#111827] truncate">{wsDetail.repo_url || "None"}</p>
                      </div>
                      <div className="rounded-lg bg-[#FAFBFC] px-3 py-2">
                        <p className="text-[0.55rem] font-medium text-[#9CA3AF]">Branch</p>
                        <div className="flex items-center gap-1.5">
                          <GitBranch className="h-3 w-3 text-[#6B7280]" />
                          <input type="text" defaultValue={wsDetail.branch}
                            onBlur={(e) => checkoutMutation.mutate({ wsId: wsDetail.id, branch: e.target.value })}
                            className="flex-1 border-0 bg-transparent text-[0.72rem] font-medium text-[#111827] outline-none" />
                        </div>
                      </div>
                      <div className="rounded-lg bg-[#FAFBFC] px-3 py-2">
                        <p className="text-[0.55rem] font-medium text-[#9CA3AF]">Created</p>
                        <p className="text-[0.72rem] text-[#6B7280]">{new Date(wsDetail.created_at).toLocaleDateString()}</p>
                      </div>
                    </div>

                    {/* Repository Intelligence */}
                    {wsDetail.repository && (
                      <div className="mt-4">
                        <h4 className="mb-2 text-[0.7rem] font-bold text-[#6B7280]">Repository Intelligence</h4>
                        <div className="grid gap-3 sm:grid-cols-2">
                          <div className="rounded-lg border border-[#E8EDF3] p-3">
                            <p className="mb-1 text-[0.55rem] font-medium text-[#9CA3AF]">Languages</p>
                            <LanguageBar languages={wsDetail.repository.languages} />
                            <div className="mt-1.5 flex flex-wrap gap-1.5">
                              {Object.entries(wsDetail.repository.languages).slice(0, 5).map(([lang]) => (
                                <span key={lang} className="rounded bg-[#F4F7FA] px-1.5 py-0.5 text-[0.5rem] text-[#6B7280]">{lang}</span>
                              ))}
                            </div>
                          </div>
                          <div className="rounded-lg border border-[#E8EDF3] p-3">
                            <p className="mb-1 text-[0.55rem] font-medium text-[#9CA3AF]">Frameworks & Tools</p>
                            <div className="flex flex-wrap gap-1.5">
                              {wsDetail.repository.frameworks.map((fw) => (
                                <span key={fw} className="rounded bg-purple-50 px-1.5 py-0.5 text-[0.5rem] text-purple-600">{fw}</span>
                              ))}
                              {wsDetail.repository.package_managers.map((pm) => (
                                <span key={pm} className="rounded bg-blue-50 px-1.5 py-0.5 text-[0.5rem] text-blue-600">{pm}</span>
                              ))}
                            </div>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Artifacts */}
                    <div className="mt-4">
                      <h4 className="mb-2 text-[0.7rem] font-bold text-[#6B7280]">Artifacts ({wsDetail.artifacts?.length ?? 0})</h4>
                      {wsDetail.artifacts?.length > 0 ? (
                        <div className="grid gap-2 sm:grid-cols-2">
                          {wsDetail.artifacts.slice(0, 6).map((a) => (
                            <div key={a.id} className="flex items-center gap-2 rounded-lg border border-[#E8EDF3] px-3 py-2">
                              <FileCode className="h-3.5 w-3.5 text-[#6B7280]" />
                              <div className="min-w-0 flex-1">
                                <p className="text-[0.65rem] font-medium text-[#111827] truncate">{a.name}</p>
                                <p className="text-[0.5rem] text-[#9CA3AF]">{a.type}</p>
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <p className="text-[0.65rem] text-[#9CA3AF]">No artifacts yet.</p>
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center rounded-xl border border-[#E8EDF3] bg-white py-16 text-[#9CA3AF]">
                    <Box className="mb-3 h-10 w-10 opacity-30" />
                    <p className="text-sm">Select a workspace to view details.</p>
                  </div>
                )}
              </div>
            </div>
          </motion.div>
        )}

        {/* Repositories Tab */}
        {activeTab === "repositories" && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
            <div className="rounded-xl border border-[#E8EDF3] bg-white p-5">
              <h3 className="mb-4 text-sm font-bold text-[#111827]">Known Repositories ({repos?.length ?? 0})</h3>
              {repos?.length === 0 ? (
                <p className="text-center text-[0.7rem] text-[#9CA3AF] py-8">No repositories tracked yet. Create a workspace with a repo URL.</p>
              ) : (
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {repos?.map((repo) => (
                    <div key={repo.url} className="rounded-lg border border-[#E8EDF3] p-4 hover:border-[#38B88A]/30">
                      <div className="flex items-start gap-2">
                        <GitBranch className="mt-0.5 h-4 w-4 shrink-0 text-[#6B7280]" />
                        <div className="min-w-0 flex-1">
                          <p className="text-[0.7rem] font-bold text-[#111827] truncate">{repo.name}</p>
                          <p className="text-[0.55rem] text-[#9CA3AF] truncate">{repo.url}</p>
                        </div>
                      </div>
                      {repo.languages && Object.keys(repo.languages).length > 0 && (
                        <div className="mt-2">
                          <LanguageBar languages={repo.languages} />
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </motion.div>
        )}

        {/* Intelligence Tab */}
        {activeTab === "intelligence" && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
            <div className="rounded-xl border border-[#E8EDF3] bg-white p-4">
              <label className="mb-1 block text-[0.65rem] font-medium text-[#6B7280]">Repository URL</label>
              <div className="flex gap-2">
                <input type="text" value={repoUrl} onChange={e => setRepoUrl(e.target.value)}
                  placeholder="https://github.com/org/repo"
                  className="flex-1 rounded-lg border border-[#E8EDF3] px-3 py-2 text-[0.78rem] outline-none" />
              </div>
            </div>

            {repoUrl && repoIntel && (
              <div className="rounded-xl border border-[#E8EDF3] bg-white p-5">
                <h2 className="text-lg font-bold text-[#111827]">{repoIntel.name}</h2>
                <p className="mt-0.5 text-[0.7rem] text-[#6B7280]">{repoIntel.url}</p>

                <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  <div className="rounded-lg border border-[#E8EDF3] p-3">
                    <p className="mb-1 text-[0.55rem] font-medium text-[#9CA3AF]">Languages</p>
                    <LanguageBar languages={repoIntel.languages} />
                    <div className="mt-2 space-y-1">
                      {Object.entries(repoIntel.languages).slice(0, 6).map(([lang, count]) => (
                        <div key={lang} className="flex justify-between text-[0.6rem]">
                          <span className="text-[#6B7280]">{lang}</span>
                          <span className="font-medium text-[#111827]">{count}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="rounded-lg border border-[#E8EDF3] p-3">
                    <p className="mb-1 text-[0.55rem] font-medium text-[#9CA3AF]">Build & Tools</p>
                    <div className="space-y-2">
                      <div><p className="text-[0.55rem] text-[#9CA3AF]">Build System</p><p className="text-[0.7rem] font-medium text-[#111827]">{repoIntel.build_system}</p></div>
                      <div><p className="text-[0.55rem] text-[#9CA3AF]">Test Framework</p><p className="text-[0.7rem] font-medium text-[#111827]">{repoIntel.test_framework || "Not detected"}</p></div>
                      <div><p className="text-[0.55rem] text-[#9CA3AF]">Package Managers</p><p className="text-[0.7rem] font-medium text-[#111827]">{repoIntel.package_managers.join(", ") || "None"}</p></div>
                    </div>
                  </div>

                  <div className="rounded-lg border border-[#E8EDF3] p-3">
                    <p className="mb-1 text-[0.55rem] font-medium text-[#9CA3AF]">Infrastructure</p>
                    <div className="space-y-2">
                      <div className="flex items-center gap-2">
                        <CheckCircle2 className={`h-3 w-3 ${repoIntel.statistics.has_docker ? "text-[#38B88A]" : "text-[#9CA3AF]"}`} />
                        <span className="text-[0.65rem] text-[#6B7280]">Docker</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <CheckCircle2 className={`h-3 w-3 ${repoIntel.statistics.has_cicd ? "text-[#38B88A]" : "text-[#9CA3AF]"}`} />
                        <span className="text-[0.65rem] text-[#6B7280]">CI/CD</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <CheckCircle2 className={`h-3 w-3 ${repoIntel.statistics.has_tests ? "text-[#38B88A]" : "text-[#9CA3AF]"}`} />
                        <span className="text-[0.65rem] text-[#6B7280]">Tests</span>
                      </div>
                    </div>
                  </div>
                </div>

                {repoIntel.frameworks.length > 0 && (
                  <div className="mt-4">
                    <p className="mb-2 text-[0.7rem] font-bold text-[#6B7280]">Detected Frameworks</p>
                    <div className="flex flex-wrap gap-2">
                      {repoIntel.frameworks.map((fw) => (
                        <span key={fw} className="rounded-full bg-purple-50 px-3 py-1 text-[0.65rem] font-medium text-purple-600">{fw}</span>
                      ))}
                    </div>
                  </div>
                )}

                {repoIntel.modules.length > 0 && (
                  <div className="mt-4">
                    <p className="mb-2 text-[0.7rem] font-bold text-[#6B7280]">Module Structure</p>
                    <div className="flex flex-wrap gap-1.5">
                      {repoIntel.modules.slice(0, 15).map((mod) => (
                        <span key={mod} className="rounded bg-[#F4F7FA] px-2 py-0.5 text-[0.55rem] text-[#6B7280]">{mod}</span>
                      ))}
                    </div>
                  </div>
                )}

                {repoIntel.cicd_configs.length > 0 && (
                  <div className="mt-4">
                    <p className="mb-2 text-[0.7rem] font-bold text-[#6B7280]">CI/CD</p>
                    <div className="flex flex-wrap gap-2">
                      {repoIntel.cicd_configs.map((cicd) => (
                        <span key={cicd} className="rounded-full bg-blue-50 px-3 py-1 text-[0.65rem] font-medium text-blue-600">{cicd}</span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </motion.div>
        )}
      </div>
    </CortexShell>
  )
}
