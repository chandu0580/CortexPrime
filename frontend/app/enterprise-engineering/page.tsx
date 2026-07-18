"use client"

import { useState } from "react"
import { motion } from "framer-motion"
import CortexShell from "@/components/layout/CortexShell"
import { stagger, variants } from "@/lib/motion-tokens"
import {
  useEngineeringAgents,
  useEngineeringEcosystems,
  useExecuteEngineeringTask,
  useAnalyzeRepository,
  useBuildPlan,
  useInvestigate,
  useGenerateEngineeringPlan,
} from "@/hooks/queries/enterprise/useEnterpriseEngineering"
import {
  Activity,
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Code2,
  Cpu,
  Eye,
  FileCode,
  GitBranch,
  Loader2,
  ScrollText,
  Search,
  Shield,
  Target,
  Terminal,
  Users,
  Wrench,
  Zap,
} from "lucide-react"

const AGENT_ICONS: Record<string, any> = {
  engineering_executive: Users,
  repository_analyst: GitBranch,
  build_engineer: Terminal,
  qa_engineer: CheckCircle2,
  security_engineer: Shield,
  software_architect: Code2,
  bug_investigator: Search,
  engineering_planner: ScrollText,
  code_generator: FileCode,
  code_reviewer: Eye,
  test_validator: Activity,
  devops_engineer: Wrench,
  sre_engineer: Cpu,
}

function AgentCard({ agent, result }: { agent: { name: string; title: string; responsibility: string }; result?: any }) {
  const Icon = AGENT_ICONS[agent.name] || Users
  const hasError = result?.error
  const hasData = result && !hasError
  return (
    <div className={`rounded-xl border p-4 ${hasError ? "border-red-300 bg-red-50" : hasData ? "border-[#38B88A]/30 bg-[#F0FDF4]" : "border-[#E8EDF3] bg-white"}`}>
      <div className="flex items-start gap-3">
        <div className={`rounded-lg p-2 ${hasError ? "bg-red-100" : hasData ? "bg-[#38B88A]/10" : "bg-[#F4F7FA]"}`}>
          <Icon className={`h-4 w-4 ${hasError ? "text-red-500" : hasData ? "text-[#38B88A]" : "text-[#6B7280]"}`} />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-[0.78rem] font-bold text-[#111827]">{agent.title}</p>
          <p className="text-[0.6rem] text-[#6B7280]">{agent.responsibility}</p>
          {hasError && <p className="mt-1 text-[0.6rem] text-red-500">{hasError}</p>}
          {hasData && (
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              {Object.entries(result).filter(([k]) => !["agent"].includes(k)).slice(0, 4).map(([k, v]) => (
                <span key={k} className="rounded bg-white/60 px-1.5 py-0.5 text-[0.5rem] text-[#6B7280]">
                  {k}: {Array.isArray(v) ? v.length : String(v).slice(0, 40)}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default function EnterpriseEngineeringDepartment() {
  const [objective, setObjective] = useState("")
  const [repoUrl, setRepoUrl] = useState("")
  const [ecosystem, setEcosystem] = useState("python")
  const [branch, setBranch] = useState("main")
  const [activeTab, setActiveTab] = useState("agents")
  const [report, setReport] = useState<any>(null)

  const { data: agents } = useEngineeringAgents()
  const { data: ecosystems } = useEngineeringEcosystems()
  const executeMutation = useExecuteEngineeringTask()
  const analyzeMutation = useAnalyzeRepository()
  const buildMutation = useBuildPlan()
  const investigateMutation = useInvestigate()
  const planMutation = useGenerateEngineeringPlan()

  const handleExecute = async () => {
    if (!objective && !repoUrl) return
    try {
      const result = await executeMutation.mutateAsync({
        objective: objective || "Automated engineering task",
        repo_url: repoUrl,
        ecosystem,
        branch,
      })
      setReport(result)
    } catch (err) {
      console.error("Engineering task failed:", err)
    }
  }

  const tabs = [
    { id: "agents", label: "Engineering Organization", icon: Users },
    { id: "execute", label: "Execute Task", icon: Zap },
    { id: "report", label: "Latest Report", icon: ScrollText, disabled: !report },
  ]

  return (
    <CortexShell title="Engineering Department" subtitle="Coordinated organization of 13 specialized engineering agents working through Mission Runtime">
      <div className="relative z-10 mx-auto max-w-7xl space-y-6">
        {/* Tab Navigation */}
        <div className="flex flex-wrap gap-1 rounded-xl border border-[#E8EDF3] bg-white p-1">
          {tabs.map((tab) => {
            const TabIcon = tab.icon
            const isActive = activeTab === tab.id
            return (
              <button
                key={tab.id}
                onClick={() => !tab.disabled && setActiveTab(tab.id)}
                className={`flex items-center gap-2 rounded-lg px-4 py-2 text-[0.78rem] font-medium transition-all ${
                  tab.disabled ? "cursor-not-allowed opacity-40" :
                  isActive ? "bg-[#38B88A] text-white shadow-sm" : "text-[#6B7280] hover:bg-[#F4F7FA]"
                }`}
              >
                <TabIcon className="h-4 w-4" />
                {tab.label}
              </button>
            )
          })}
        </div>

        {/* Agents Tab */}
        {activeTab === "agents" && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
            <div className="rounded-xl border border-[#E8EDF3] bg-white p-5">
              <h3 className="mb-1 text-sm font-bold text-[#111827]">Engineering Organization</h3>
              <p className="mb-4 text-[0.7rem] text-[#6B7280]">
                {agents?.length ?? 0} specialized agents coordinated through Mission Runtime — no monolithic coding agent.
              </p>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {agents?.map((agent) => {
                  const result = report?.agents?.[agent.name]
                  return <AgentCard key={agent.name} agent={agent} result={result} />
                })}
              </div>
            </div>

            {/* Ecosystems */}
            <div className="mt-5 rounded-xl border border-[#E8EDF3] bg-white p-5">
              <h3 className="mb-3 text-sm font-bold text-[#111827]">Supported Build Ecosystems</h3>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {ecosystems?.map((eco) => (
                  <div key={eco.id} className="rounded-lg border border-[#E8EDF3] p-3">
                    <p className="text-[0.72rem] font-bold text-[#111827]">{eco.name}</p>
                    <div className="mt-2 space-y-1 text-[0.6rem] text-[#6B7280]">
                      <p className="flex items-center gap-1"><Terminal className="h-3 w-3" /> Build: {eco.build}</p>
                      <p className="flex items-center gap-1"><Code2 className="h-3 w-3" /> Lint: {eco.lint}</p>
                      {eco.test && <p className="flex items-center gap-1"><CheckCircle2 className="h-3 w-3" /> Test: {eco.test}</p>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </motion.div>
        )}

        {/* Execute Tab */}
        {activeTab === "execute" && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-5">
            <div className="rounded-xl border border-[#E8EDF3] bg-white p-5">
              <h3 className="mb-4 text-sm font-bold text-[#111827]">Run Engineering Task</h3>
              <div className="space-y-4">
                <div>
                  <label className="mb-1 block text-[0.65rem] font-medium text-[#6B7280]">Objective</label>
                  <textarea
                    value={objective}
                    onChange={(e) => setObjective(e.target.value)}
                    placeholder="Describe the engineering task..."
                    className="w-full rounded-lg border border-[#E8EDF3] px-3 py-2 text-[0.78rem] text-[#111827] outline-none placeholder-[#9CA3AF]"
                    rows={3}
                  />
                </div>
                <div className="grid gap-4 sm:grid-cols-3">
                  <div>
                    <label className="mb-1 block text-[0.65rem] font-medium text-[#6B7280]">Repository URL</label>
                    <input
                      type="text"
                      value={repoUrl}
                      onChange={(e) => setRepoUrl(e.target.value)}
                      placeholder="https://github.com/org/repo"
                      className="w-full rounded-lg border border-[#E8EDF3] px-3 py-2 text-[0.78rem] text-[#111827] outline-none placeholder-[#9CA3AF]"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-[0.65rem] font-medium text-[#6B7280]">Branch</label>
                    <input
                      type="text"
                      value={branch}
                      onChange={(e) => setBranch(e.target.value)}
                      className="w-full rounded-lg border border-[#E8EDF3] px-3 py-2 text-[0.78rem] text-[#111827] outline-none"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-[0.65rem] font-medium text-[#6B7280]">Ecosystem</label>
                    <select
                      value={ecosystem}
                      onChange={(e) => setEcosystem(e.target.value)}
                      className="w-full rounded-lg border border-[#E8EDF3] px-3 py-2 text-[0.78rem] text-[#111827] outline-none"
                    >
                      {ecosystems?.map((eco) => (
                        <option key={eco.id} value={eco.id}>{eco.name}</option>
                      ))}
                    </select>
                  </div>
                </div>
                <button
                  onClick={handleExecute}
                  disabled={executeMutation.isPending || (!objective && !repoUrl)}
                  className="flex items-center gap-2 rounded-lg bg-[#38B88A] px-5 py-2.5 text-[0.78rem] font-bold text-white hover:bg-[#2DA978] disabled:opacity-50"
                >
                  {executeMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Zap className="h-4 w-4" />}
                  {executeMutation.isPending ? "Coordinating engineering agents..." : "Execute Engineering Task"}
                </button>
              </div>
            </div>
          </motion.div>
        )}

        {/* Report Tab */}
        {activeTab === "report" && report && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-5">
            <div className="rounded-xl border border-[#E8EDF3] bg-white p-5">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h2 className="text-lg font-bold text-[#111827]">{report.objective || "Engineering Task"}</h2>
                  <p className="mt-0.5 text-[0.7rem] text-[#6B7280]">
                    Execution {report.execution_id.slice(0, 12)}... — {report.status}
                  </p>
                </div>
                <span className={`rounded-full px-3 py-1 text-[0.7rem] font-medium capitalize ${
                  report.status === "completed" ? "bg-[#F0FDF4] text-[#38B88A]" : "bg-amber-50 text-amber-600"
                }`}>{report.status}</span>
              </div>
            </div>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {agents?.map((agent) => {
                const result = report.agents?.[agent.name]
                return <AgentCard key={agent.name} agent={agent} result={result} />
              })}
            </div>
          </motion.div>
        )}

        {/* Empty state when no tab content */}
        {activeTab === "report" && !report && (
          <div className="flex flex-col items-center justify-center py-16 text-[#9CA3AF]">
            <ScrollText className="mb-3 h-10 w-10 opacity-30" />
            <p className="text-sm">Execute an engineering task to see the report.</p>
          </div>
        )}
      </div>
    </CortexShell>
  )
}
