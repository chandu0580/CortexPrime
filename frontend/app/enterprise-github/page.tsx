"use client"
import { useState } from "react"
import { motion } from "framer-motion"
import CortexShell from "@/components/layout/CortexShell"
import { stagger, variants } from "@/lib/motion-tokens"
import {
  useGithubDashboard,
  useGithubWebhooks,
  useGithubWorkflowRuns,
  useGithubPullRequests,
  useGithubIssues,
  useGithubReleases,
  useGithubDeployments,
  useGithubBranches,
  useReceiveWebhook,
  useTranslateEvent,
  useLaunchMission,
  useSyncRepositories,
} from "@/hooks/queries/enterprise/useEnterpriseGithubOperations"
import {
  Activity,
  GitBranch,
  GitPullRequest,
  AlertCircle,
  CheckCircle,
  XCircle,
  Clock,
  Webhook,
  PlayCircle,
  ExternalLink,
  Tag,
  Layers,
  Box,
  Loader2,
  MessageSquare,
  Rocket,
  RefreshCw,
  ArrowRight,
  Search,
} from "lucide-react"

const tabs = ["Dashboard", "Webhooks", "Workflow Runs", "Pull Requests", "Issues", "Releases", "Deployments", "Branches"]

function StatusBadge({ status, conclusion }: { status?: string; conclusion?: string }) {
  const s = (status || conclusion || "").toLowerCase()
  const display = status || conclusion || "";
  const ds = display.toLowerCase();
  if (ds === "success" || ds === "completed" || ds === "merged" || ds === "open")
    return <span className="inline-flex items-center gap-1 text-xs font-medium text-green-600 dark:text-green-400"><CheckCircle size={12} />{display}</span>
  if (ds === "failure" || ds === "failed" || ds === "error" || ds === "cancelled" || ds === "timed_out" || ds === "closed")
    return <span className="inline-flex items-center gap-1 text-xs font-medium text-red-600 dark:text-red-400"><XCircle size={12} />{display}</span>
  if (ds === "in_progress" || ds === "queued" || ds === "pending" || ds === "running")
    return <span className="inline-flex items-center gap-1 text-xs font-medium text-yellow-600 dark:text-yellow-400"><Clock size={12} />{display}</span>
  return <span className="inline-flex items-center gap-1 text-xs font-medium text-gray-500 dark:text-gray-400"><Activity size={12} />{status || conclusion || "unknown"}</span>
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

export default function EnterpriseGithubCenter() {
  const [activeTab, setActiveTab] = useState("Dashboard")
  const [ownerInput, setOwnerInput] = useState("")
  const [repoInput, setRepoInput] = useState("")
  const [connectedOwner, setConnectedOwner] = useState("")
  const [connectedRepo, setConnectedRepo] = useState("")

  const owner = connectedOwner
  const repo = connectedRepo

  const { data: dashboard, isLoading: dashLoading } = useGithubDashboard(owner, repo)
  const { data: webhooks } = useGithubWebhooks(10)
  const { data: workflowRuns } = useGithubWorkflowRuns(owner, repo)
  const { data: pullRequests } = useGithubPullRequests(owner, repo)
  const { data: issues } = useGithubIssues(owner, repo)
  const { data: releases } = useGithubReleases(owner, repo)
  const { data: deployments } = useGithubDeployments(owner, repo)
  const { data: branches } = useGithubBranches(owner, repo)

  const receiveWebhookMut = useReceiveWebhook()
  const translateMut = useTranslateEvent()
  const launchMissionMut = useLaunchMission()
  const syncMut = useSyncRepositories()

  const [webhookEventType, setWebhookEventType] = useState("push")
  const [sendResult, setSendResult] = useState<string | null>(null)

  const handleConnect = () => {
    setConnectedOwner(ownerInput.trim())
    setConnectedRepo(repoInput.trim())
  }

  const handleSendWebhook = async () => {
    setSendResult(null)
    try {
      const payload: Record<string, any> = {
        ref: `refs/heads/main`,
        repository: {
          full_name: `${owner}/${repo}`,
          clone_url: `https://github.com/${owner}/${repo}.git`,
          html_url: `https://github.com/${owner}/${repo}`,
        },
        sender: { login: "developer" },
        commits: [{ id: "abc123", message: "test webhook", author: { name: "Dev" }, timestamp: new Date().toISOString(), url: `https://github.com/${owner}/${repo}/commit/abc123` }],
      }
      await receiveWebhookMut.mutateAsync({ payload, eventType: webhookEventType })
      setSendResult("Webhook sent successfully")
    } catch {
      setSendResult("Failed to send webhook")
    }
  }

  const handleSync = async () => {
    try {
      await syncMut.mutateAsync({ owner })
    } catch {}
  }

  const handleTranslateAndMission = async () => {
    setSendResult(null)
    try {
      const payload: Record<string, any> = {
        ref: `refs/heads/main`,
        repository: {
          full_name: `${owner}/${repo}`,
          clone_url: `https://github.com/${owner}/${repo}.git`,
          html_url: `https://github.com/${owner}/${repo}`,
        },
        sender: { login: "developer" },
        commits: [{ id: "abc123", message: "test translate", author: { name: "Dev" }, timestamp: new Date().toISOString(), url: `https://github.com/${owner}/${repo}/commit/abc123` }],
      }
      await translateMut.mutateAsync({ eventType: webhookEventType, payload })
      await launchMissionMut.mutateAsync({ eventType: webhookEventType, payload })
      setSendResult("Translate + Mission launched")
    } catch {
      setSendResult("Translate/Mission failed")
    }
  }

  const stats = dashboard || {
    total_webhooks: 0, total_workflow_runs: 0, total_prs: 0,
    total_issues: 0, total_releases: 0, total_deployments: 0, total_branches: 0,
    recent_activity: [],
  }

  return (
    <CortexShell
      title="GitHub Engineering Integration"
      subtitle="Live repository intelligence — webhooks, workflows, PRs, issues, releases, deployments, branches"
    >
      <motion.div initial="hidden" animate="visible" variants={stagger(0.04, 0.01)} className="space-y-6">
        {/* Owner/Repo Connection Bar */}
        <motion.div variants={variants.fadeIn} className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4">
          <div className="flex flex-wrap items-end gap-3">
            <div className="flex-1 min-w-[160px]">
              <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Owner</label>
              <input
                type="text"
                value={ownerInput}
                onChange={(e) => setOwnerInput(e.target.value)}
                placeholder="e.g. vercel"
                className="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-900 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div className="flex-1 min-w-[160px]">
              <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Repository</label>
              <input
                type="text"
                value={repoInput}
                onChange={(e) => setRepoInput(e.target.value)}
                placeholder="e.g. next.js"
                className="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-900 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <button
              onClick={handleConnect}
              disabled={!ownerInput.trim() || !repoInput.trim()}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 transition-colors disabled:opacity-50"
            >
              <Search size={16} />
              Connect
            </button>
            {owner && repo && (
              <button
                onClick={handleSync}
                disabled={syncMut.isPending}
                className="flex items-center gap-2 px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 text-sm font-medium hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors disabled:opacity-50"
              >
                <RefreshCw size={16} className={syncMut.isPending ? "animate-spin" : ""} />
                Sync
              </button>
            )}
          </div>
          {owner && repo && (
            <p className="mt-2 text-xs text-green-600 dark:text-green-400">
              Connected to <span className="font-mono font-medium">{owner}/{repo}</span>
            </p>
          )}
        </motion.div>

        {/* Tabs */}
        <div className="flex flex-wrap gap-2 border-b border-gray-200 dark:border-gray-700 pb-2">
          {tabs.map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-4 py-2 text-sm font-medium rounded-t-lg transition-colors ${
                activeTab === tab
                  ? "text-blue-600 dark:text-blue-400 border-b-2 border-blue-600 dark:border-blue-400"
                  : "text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300"
              }`}
            >
              {tab}
            </button>
          ))}
        </div>

        {/* DASHBOARD TAB */}
        {activeTab === "Dashboard" && (
          <div className="space-y-6">
            {!owner || !repo ? (
              <motion.div variants={variants.fadeIn} className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-12 text-center">
                <Search size={48} className="mx-auto text-gray-300 dark:text-gray-600 mb-4" />
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">Connect to a Repository</h3>
                <p className="text-sm text-gray-500 dark:text-gray-400">Enter an owner and repository name above to view live GitHub data.</p>
              </motion.div>
            ) : (
              <>
                {/* KPI Cards */}
                <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-4">
                  <KpiCard icon={Webhook} label="Webhooks" value={stats.total_webhooks} color="text-purple-600" />
                  <KpiCard icon={PlayCircle} label="Workflow Runs" value={stats.total_workflow_runs} color="text-blue-600" />
                  <KpiCard icon={GitPullRequest} label="Pull Requests" value={stats.total_prs} color="text-green-600" />
                  <KpiCard icon={MessageSquare} label="Issues" value={stats.total_issues} color="text-orange-600" />
                  <KpiCard icon={Tag} label="Releases" value={stats.total_releases} color="text-pink-600" />
                  <KpiCard icon={Rocket} label="Deployments" value={stats.total_deployments} color="text-cyan-600" />
                  <KpiCard icon={GitBranch} label="Branches" value={stats.total_branches} color="text-indigo-600" />
                </div>

                {/* Webhook Test */}
                <motion.div variants={variants.fadeIn} className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-6">
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
                    <Webhook size={18} className="text-purple-500" />
                    Test Webhook
                  </h3>
                  <div className="flex flex-wrap items-end gap-3">
                    <div className="w-48">
                      <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Event Type</label>
                      <select
                        value={webhookEventType}
                        onChange={(e) => setWebhookEventType(e.target.value)}
                        className="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-900 p-2 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
                      >
                        <option value="push">push</option>
                        <option value="pull_request">pull_request</option>
                        <option value="pull_request_review">pull_request_review</option>
                        <option value="issues">issues</option>
                        <option value="workflow_run">workflow_run</option>
                        <option value="release">release</option>
                        <option value="deployment">deployment</option>
                        <option value="deployment_status">deployment_status</option>
                        <option value="create">create (branch)</option>
                        <option value="delete">delete (branch)</option>
                      </select>
                    </div>
                    <button
                      onClick={handleSendWebhook}
                      disabled={receiveWebhookMut.isPending}
                      className="flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-purple-600 text-white text-sm font-medium hover:bg-purple-700 transition-colors disabled:opacity-50"
                    >
                      {receiveWebhookMut.isPending ? <Loader2 size={16} className="animate-spin" /> : <Webhook size={16} />}
                      Send Webhook
                    </button>
                    <button
                      onClick={handleTranslateAndMission}
                      disabled={translateMut.isPending || launchMissionMut.isPending}
                      className="flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 transition-colors disabled:opacity-50"
                    >
                      {(translateMut.isPending || launchMissionMut.isPending) ? <Loader2 size={16} className="animate-spin" /> : <Rocket size={16} />}
                      Translate + Launch Mission
                    </button>
                    {sendResult && (
                      <span className="text-xs text-gray-500 dark:text-gray-400">{sendResult}</span>
                    )}
                  </div>
                </motion.div>

                {/* Recent Activity */}
                <motion.div variants={variants.fadeIn} className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-6">
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
                    <Activity size={18} className="text-blue-500" />
                    Recent Activity
                  </h3>
                  <div className="space-y-2 max-h-80 overflow-y-auto">
                    {(stats.recent_activity || []).length === 0 ? (
                      <p className="text-sm text-gray-500 dark:text-gray-400 text-center py-8">No activity yet.</p>
                    ) : (
                      stats.recent_activity.map((act: any, i: number) => (
                        <div key={i} className="flex items-center gap-3 p-2 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700/50">
                          <div className={`p-1.5 rounded-full ${
                            act.type === "webhook" ? "bg-purple-100 dark:bg-purple-900/30" :
                            act.type === "pr" ? "bg-green-100 dark:bg-green-900/30" :
                            "bg-blue-100 dark:bg-blue-900/30"
                          }`}>
                            {act.type === "webhook" ? <Webhook size={12} className="text-purple-600" /> :
                             act.type === "pr" ? <GitPullRequest size={12} className="text-green-600" /> :
                             <PlayCircle size={12} className="text-blue-600" />}
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-gray-900 dark:text-white truncate">
                              {act.data?.event_type || act.data?.title || act.data?.name || act.type}
                            </p>
                            <p className="text-xs text-gray-500 dark:text-gray-400">{act.data?.repository || act.data?.repo || ""}</p>
                          </div>
                          <span className="text-xs text-gray-400 dark:text-gray-500 shrink-0">
                            {new Date(act.timestamp || Date.now()).toLocaleTimeString()}
                          </span>
                        </div>
                      ))
                    )}
                  </div>
                </motion.div>

                {/* Flow Diagram */}
                <motion.div variants={variants.fadeIn} className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-6">
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Engineering Flow</h3>
                  <div className="flex flex-wrap items-center gap-2 text-xs">
                    {["Webhook", "Executive", "Repo Intel", "Code Intel", "Arch Intel", "Patch Pipeline", "Sandbox", "Actions", "Tests", "PR", "Approval", "Deploy", "Monitor", "Learn", "Graph"].map((step, i) => (
                      <span key={step} className="inline-flex items-center gap-2">
                        <span className="px-3 py-1.5 rounded-full bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 font-medium border border-blue-200 dark:border-blue-800">
                          {step}
                        </span>
                        {i < 14 && <ArrowRight size={14} className="text-gray-400" />}
                      </span>
                    ))}
                  </div>
                </motion.div>
              </>
            )}
          </div>
        )}

        {/* WEBHOOKS TAB */}
        {activeTab === "Webhooks" && (
          <motion.div variants={variants.fadeIn} className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-6">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Webhook Activity</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200 dark:border-gray-700">
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Event</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Repository</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Sender</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Verified</th>
                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Time</th>
                  </tr>
                </thead>
                <tbody>
                  {(webhooks?.webhooks || []).length === 0 ? (
                    <tr><td colSpan={5} className="text-center py-8 text-sm text-gray-500 dark:text-gray-400">No webhooks received</td></tr>
                  ) : (
                    (webhooks?.webhooks || []).map((wh: any) => (
                      <tr key={wh.event_id} className="border-b border-gray-100 dark:border-gray-700/50 hover:bg-gray-50 dark:hover:bg-gray-700/30">
                        <td className="py-2 px-3 font-medium text-gray-900 dark:text-white">{wh.event_type}</td>
                        <td className="py-2 px-3 text-gray-600 dark:text-gray-400">{wh.repository}</td>
                        <td className="py-2 px-3 text-gray-600 dark:text-gray-400">{wh.sender}</td>
                        <td className="py-2 px-3">{wh.verified ? <CheckCircle size={14} className="text-green-500" /> : <XCircle size={14} className="text-red-500" />}</td>
                        <td className="py-2 px-3 text-xs text-gray-500 dark:text-gray-400">{new Date(wh.received_at || Date.now()).toLocaleString()}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </motion.div>
        )}

        {/* WORKFLOW RUNS TAB */}
        {activeTab === "Workflow Runs" && (
          <motion.div variants={variants.fadeIn} className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-6">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">GitHub Actions Workflow Runs</h3>
            {!owner || !repo ? (
              <p className="text-sm text-gray-500 dark:text-gray-400 text-center py-8">Connect to a repository above.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-200 dark:border-gray-700">
                      <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Name</th>
                      <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Branch</th>
                      <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Status</th>
                      <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Conclusion</th>
                      <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Actor</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(workflowRuns?.workflow_runs || []).length === 0 ? (
                      <tr><td colSpan={5} className="text-center py-8 text-sm text-gray-500 dark:text-gray-400">No workflow runs found</td></tr>
                    ) : (
                      (workflowRuns?.workflow_runs || []).map((run: any) => (
                        <tr key={run.id || run.run_id} className="border-b border-gray-100 dark:border-gray-700/50 hover:bg-gray-50 dark:hover:bg-gray-700/30">
                          <td className="py-2 px-3 font-medium text-gray-900 dark:text-white">{run.name}</td>
                          <td className="py-2 px-3 text-gray-600 dark:text-gray-400">{run.head_branch}</td>
                          <td className="py-2 px-3"><StatusBadge status={run.status} /></td>
                          <td className="py-2 px-3"><StatusBadge status={run.conclusion} /></td>
                          <td className="py-2 px-3 text-gray-600 dark:text-gray-400">{run.actor || "-"}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </motion.div>
        )}

        {/* PULL REQUESTS TAB */}
        {activeTab === "Pull Requests" && (
          <motion.div variants={variants.fadeIn} className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-6">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Pull Requests</h3>
            {!owner || !repo ? (
              <p className="text-sm text-gray-500 dark:text-gray-400 text-center py-8">Connect to a repository above.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-200 dark:border-gray-700">
                      <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">#</th>
                      <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Title</th>
                      <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">State</th>
                      <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Branch</th>
                      <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Author</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(pullRequests?.pull_requests || []).length === 0 ? (
                      <tr><td colSpan={5} className="text-center py-8 text-sm text-gray-500 dark:text-gray-400">No pull requests found</td></tr>
                    ) : (
                      (pullRequests?.pull_requests || []).map((pr: any) => (
                        <tr key={pr.number} className="border-b border-gray-100 dark:border-gray-700/50 hover:bg-gray-50 dark:hover:bg-gray-700/30">
                          <td className="py-2 px-3 font-medium text-gray-900 dark:text-white">#{pr.number}</td>
                          <td className="py-2 px-3 text-gray-900 dark:text-white max-w-xs truncate">{pr.title}</td>
                          <td className="py-2 px-3"><StatusBadge status={pr.state} /></td>
                          <td className="py-2 px-3 text-gray-600 dark:text-gray-400">{pr.head_branch}</td>
                          <td className="py-2 px-3 text-gray-600 dark:text-gray-400">{pr.author}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </motion.div>
        )}

        {/* ISSUES TAB */}
        {activeTab === "Issues" && (
          <motion.div variants={variants.fadeIn} className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-6">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Issues</h3>
            {!owner || !repo ? (
              <p className="text-sm text-gray-500 dark:text-gray-400 text-center py-8">Connect to a repository above.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-200 dark:border-gray-700">
                      <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">#</th>
                      <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Title</th>
                      <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">State</th>
                      <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Labels</th>
                      <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Author</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(issues?.issues || []).length === 0 ? (
                      <tr><td colSpan={5} className="text-center py-8 text-sm text-gray-500 dark:text-gray-400">No issues found</td></tr>
                    ) : (
                      (issues?.issues || []).map((iss: any) => (
                        <tr key={iss.number} className="border-b border-gray-100 dark:border-gray-700/50 hover:bg-gray-50 dark:hover:bg-gray-700/30">
                          <td className="py-2 px-3 font-medium text-gray-900 dark:text-white">#{iss.number}</td>
                          <td className="py-2 px-3 text-gray-900 dark:text-white max-w-xs truncate">{iss.title}</td>
                          <td className="py-2 px-3"><StatusBadge status={iss.state} /></td>
                          <td className="py-2 px-3">
                            <div className="flex flex-wrap gap-1">
                              {(iss.labels || []).map((l: string) => (
                                <span key={l} className="px-2 py-0.5 rounded-full text-xs bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300">{l}</span>
                              ))}
                            </div>
                          </td>
                          <td className="py-2 px-3 text-gray-600 dark:text-gray-400">{iss.author}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </motion.div>
        )}

        {/* RELEASES TAB */}
        {activeTab === "Releases" && (
          <motion.div variants={variants.fadeIn} className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-6">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Releases</h3>
            {!owner || !repo ? (
              <p className="text-sm text-gray-500 dark:text-gray-400 text-center py-8">Connect to a repository above.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-200 dark:border-gray-700">
                      <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Tag</th>
                      <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Name</th>
                      <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Prerelease</th>
                      <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Author</th>
                      <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Published</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(releases?.releases || []).length === 0 ? (
                      <tr><td colSpan={5} className="text-center py-8 text-sm text-gray-500 dark:text-gray-400">No releases found</td></tr>
                    ) : (
                      (releases?.releases || []).map((rel: any) => (
                        <tr key={rel.tag_name} className="border-b border-gray-100 dark:border-gray-700/50 hover:bg-gray-50 dark:hover:bg-gray-700/30">
                          <td className="py-2 px-3 font-mono text-sm font-medium text-gray-900 dark:text-white">{rel.tag_name}</td>
                          <td className="py-2 px-3 text-gray-900 dark:text-white">{rel.name}</td>
                          <td className="py-2 px-3">{rel.prerelease ? <Tag size={14} className="text-yellow-500" /> : <CheckCircle size={14} className="text-green-500" />}</td>
                          <td className="py-2 px-3 text-gray-600 dark:text-gray-400">{rel.author}</td>
                          <td className="py-2 px-3 text-xs text-gray-500 dark:text-gray-400">{new Date(rel.published_at || Date.now()).toLocaleDateString()}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </motion.div>
        )}

        {/* DEPLOYMENTS TAB */}
        {activeTab === "Deployments" && (
          <motion.div variants={variants.fadeIn} className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-6">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Deployments</h3>
            {!owner || !repo ? (
              <p className="text-sm text-gray-500 dark:text-gray-400 text-center py-8">Connect to a repository above.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-200 dark:border-gray-700">
                      <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">ID</th>
                      <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Environment</th>
                      <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">State</th>
                      <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Description</th>
                      <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Updated By</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(deployments?.deployments || []).length === 0 ? (
                      <tr><td colSpan={5} className="text-center py-8 text-sm text-gray-500 dark:text-gray-400">No deployments found</td></tr>
                    ) : (
                      (deployments?.deployments || []).map((dep: any) => (
                        <tr key={dep.deployment_id || dep.id} className="border-b border-gray-100 dark:border-gray-700/50 hover:bg-gray-50 dark:hover:bg-gray-700/30">
                          <td className="py-2 px-3 font-mono text-xs text-gray-900 dark:text-white">{dep.deployment_id || dep.id}</td>
                          <td className="py-2 px-3 font-medium text-gray-900 dark:text-white">{dep.environment}</td>
                          <td className="py-2 px-3"><StatusBadge status={dep.state} /></td>
                          <td className="py-2 px-3 text-gray-600 dark:text-gray-400 max-w-xs truncate">{dep.description}</td>
                          <td className="py-2 px-3 text-gray-600 dark:text-gray-400">{dep.updated_by || "-"}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </motion.div>
        )}

        {/* BRANCHES TAB */}
        {activeTab === "Branches" && (
          <motion.div variants={variants.fadeIn} className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-6">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Branch Intelligence</h3>
            {!owner || !repo ? (
              <p className="text-sm text-gray-500 dark:text-gray-400 text-center py-8">Connect to a repository above.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-200 dark:border-gray-700">
                      <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Name</th>
                      <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Last Commit</th>
                      <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Commits</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(branches?.branches || []).length === 0 ? (
                      <tr><td colSpan={3} className="text-center py-8 text-sm text-gray-500 dark:text-gray-400">No branches found</td></tr>
                    ) : (
                      (branches?.branches || []).map((b: any) => (
                        <tr key={b.name} className="border-b border-gray-100 dark:border-gray-700/50 hover:bg-gray-50 dark:hover:bg-gray-700/30">
                          <td className="py-2 px-3 font-mono text-sm font-medium text-gray-900 dark:text-white">{b.name}</td>
                          <td className="py-2 px-3 text-xs text-gray-600 dark:text-gray-400 max-w-xs truncate">{b.last_commit || "-"}</td>
                          <td className="py-2 px-3 text-gray-600 dark:text-gray-400">{b.commit_count || 0}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </motion.div>
        )}
      </motion.div>
    </CortexShell>
  )
}
