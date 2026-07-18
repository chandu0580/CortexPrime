"use client"

import { useState } from "react"
import { motion } from "framer-motion"
import CortexShell from "@/components/layout/CortexShell"
import { stagger, variants } from "@/lib/motion-tokens"
import {
  useGitBranches,
  useGitPullRequests,
  useGitHistory,
  usePRSummary,
  useCreateBranch,
  useCreateCommit,
  useCreatePullRequest,
  useMergePullRequest,
  useSyncIssue,
  useGenerateContext,
} from "@/hooks/queries/enterprise/useEnterpriseGitOperations"
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  Code2,
  ExternalLink,
  FileCode,
  GitBranch,
  GitCommit,
  GitCompare,
  GitMerge,
  GitPullRequest,
  Globe,
  Loader2,
  MessageSquare,
  Plus,
  RefreshCw,
  Shield,
  Star,
  Terminal,
  XCircle,
  Zap,
} from "lucide-react"

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    open: "bg-green-50 text-green-600",
    closed: "bg-gray-100 text-gray-500",
    merged: "bg-purple-50 text-purple-600",
    success: "bg-[#F0FDF4] text-[#38B88A]",
    failed: "bg-red-50 text-red-600",
    linked: "bg-blue-50 text-blue-600",
    synced: "bg-teal-50 text-teal-600",
  }
  return (
    <span className={`rounded-full px-2 py-0.5 text-[0.55rem] font-medium capitalize ${colors[status] || "bg-gray-100 text-gray-600"}`}>
      {status}
    </span>
  )
}

export default function EnterpriseGitCenter() {
  const [activeTab, setActiveTab] = useState("dashboard")
  const [repoUrl, setRepoUrl] = useState("https://github.com/org/repo")
  const [showCreateBranch, setShowCreateBranch] = useState(false)
  const [showCreatePR, setShowCreatePR] = useState(false)
  const [branchName, setBranchName] = useState("")
  const [sourceBranch, setSourceBranch] = useState("main")
  const [prTitle, setPrTitle] = useState("")
  const [prHead, setPrHead] = useState("")
  const [prBase, setPrBase] = useState("main")
  const [commitDesc, setCommitDesc] = useState("")
  const [commitBranch, setCommitBranch] = useState("")
  const [issueNumber, setIssueNumber] = useState("")
  const [issueComment, setIssueComment] = useState("")

  const { data: branches } = useGitBranches(repoUrl)
  const { data: pullRequests } = useGitPullRequests(repoUrl)
  const { data: history } = useGitHistory(20)
  const { data: prSummary } = usePRSummary()
  const createBranchMut = useCreateBranch()
  const createCommitMut = useCreateCommit()
  const createPRMut = useCreatePullRequest()
  const mergePRMut = useMergePullRequest()
  const syncIssueMut = useSyncIssue()
  const contextMut = useGenerateContext()

  const tabs = [
    { id: "dashboard", label: "Dashboard", icon: Activity },
    { id: "branches", label: "Branches", icon: GitBranch },
    { id: "pull-requests", label: "Pull Requests", icon: GitPullRequest },
    { id: "history", label: "History", icon: RefreshCw },
  ]

  return (
    <CortexShell title="Enterprise Git Center" subtitle="Autonomous branch, commit, PR, and issue orchestration">
      <div className="relative z-10 mx-auto max-w-7xl space-y-6">
        {/* Summary Cards */}
        <motion.div initial="hidden" animate="visible" variants={stagger(0.04, 0.01)} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[
            { icon: GitBranch, label: "Branches", value: branches?.length ?? "-", color: "bg-blue-500" },
            { icon: GitPullRequest, label: "Open PRs", value: pullRequests?.length ?? (prSummary as any)?.total_open ?? "-", color: "bg-purple-500" },
            { icon: GitCommit, label: "Commits", value: history?.filter(h => h.action === "commit_created").length ?? "-", color: "bg-[#38B88A]" },
            { icon: Activity, label: "Total Ops", value: history?.length ?? "-", color: "bg-amber-500" },
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

        {/* Repo URL Input */}
        <div className="flex items-center gap-3 rounded-xl border border-[#E8EDF3] bg-white p-3">
          <Globe className="h-4 w-4 text-[#6B7280]" />
          <input type="text" value={repoUrl} onChange={e => setRepoUrl(e.target.value)}
            placeholder="https://github.com/owner/repo"
            className="flex-1 border-0 bg-transparent text-[0.78rem] outline-none" />
        </div>

        {/* Tab Nav */}
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[#E8EDF3] bg-white p-1">
          <div className="flex flex-wrap gap-1">
            {tabs.map((tab) => {
              const TabIcon = tab.icon
              const isActive = activeTab === tab.id
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
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
        </div>

        {/* Dashboard */}
        {activeTab === "dashboard" && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-5">
            {/* Quick Actions */}
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <button onClick={() => setShowCreateBranch(!showCreateBranch)}
                className="flex items-center gap-3 rounded-xl border border-[#E8EDF3] bg-white p-4 text-left hover:shadow-sm">
                <div className="rounded-lg bg-blue-50 p-2.5"><GitBranch className="h-5 w-5 text-blue-500" /></div>
                <div>
                  <p className="text-[0.72rem] font-bold text-[#111827]">Create Branch</p>
                  <p className="text-[0.55rem] text-[#6B7280]">From source branch</p>
                </div>
              </button>
              <button onClick={() => setActiveTab("branches")}
                className="flex items-center gap-3 rounded-xl border border-[#E8EDF3] bg-white p-4 text-left hover:shadow-sm">
                <div className="rounded-lg bg-green-50 p-2.5"><GitCommit className="h-5 w-5 text-[#38B88A]" /></div>
                <div>
                  <p className="text-[0.72rem] font-bold text-[#111827]">Create Commit</p>
                  <p className="text-[0.55rem] text-[#6B7280]">Stage and commit changes</p>
                </div>
              </button>
              <button onClick={() => setShowCreatePR(!showCreatePR)}
                className="flex items-center gap-3 rounded-xl border border-[#E8EDF3] bg-white p-4 text-left hover:shadow-sm">
                <div className="rounded-lg bg-purple-50 p-2.5"><GitPullRequest className="h-5 w-5 text-purple-500" /></div>
                <div>
                  <p className="text-[0.72rem] font-bold text-[#111827]">Create PR</p>
                  <p className="text-[0.55rem] text-[#6B7280]">With auto-generated context</p>
                </div>
              </button>
              <button onClick={() => setActiveTab("history")}
                className="flex items-center gap-3 rounded-xl border border-[#E8EDF3] bg-white p-4 text-left hover:shadow-sm">
                <div className="rounded-lg bg-amber-50 p-2.5"><Activity className="h-5 w-5 text-amber-500" /></div>
                <div>
                  <p className="text-[0.72rem] font-bold text-[#111827]">View History</p>
                  <p className="text-[0.55rem] text-[#6B7280]">All git operations log</p>
                </div>
              </button>
            </div>

            {/* Create Branch Quick Form */}
            {showCreateBranch && (
              <div className="rounded-xl border border-blue-200 bg-blue-50 p-4">
                <h3 className="mb-3 text-sm font-bold text-[#111827]">New Branch</h3>
                <div className="grid gap-3 sm:grid-cols-3">
                  <input type="text" value={branchName} onChange={e => setBranchName(e.target.value)}
                    placeholder="Branch name" className="rounded-lg border border-blue-200 px-3 py-2 text-[0.78rem] outline-none" />
                  <input type="text" value={sourceBranch} onChange={e => setSourceBranch(e.target.value)}
                    placeholder="Source branch" className="rounded-lg border border-blue-200 px-3 py-2 text-[0.78rem] outline-none" />
                  <button onClick={async () => {
                    await createBranchMut.mutateAsync({ repo_url: repoUrl, branch_name: branchName, source_branch: sourceBranch })
                    setBranchName(""); setShowCreateBranch(false)
                  }} disabled={!branchName || createBranchMut.isPending}
                    className="flex items-center justify-center gap-2 rounded-lg bg-blue-500 px-4 py-2 text-[0.72rem] font-bold text-white disabled:opacity-50">
                    {createBranchMut.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />}
                    Create
                  </button>
                </div>
              </div>
            )}

            {/* Create PR Quick Form */}
            {showCreatePR && (
              <div className="rounded-xl border border-purple-200 bg-purple-50 p-4">
                <h3 className="mb-3 text-sm font-bold text-[#111827]">New Pull Request</h3>
                <div className="grid gap-3 sm:grid-cols-2">
                  <input type="text" value={prTitle} onChange={e => setPrTitle(e.target.value)}
                    placeholder="PR title" className="rounded-lg border border-purple-200 px-3 py-2 text-[0.78rem] outline-none" />
                  <div className="flex gap-2">
                    <input type="text" value={prHead} onChange={e => setPrHead(e.target.value)}
                      placeholder="Head branch" className="flex-1 rounded-lg border border-purple-200 px-3 py-2 text-[0.78rem] outline-none" />
                    <input type="text" value={prBase} onChange={e => setPrBase(e.target.value)}
                      placeholder="Base branch" className="w-24 rounded-lg border border-purple-200 px-3 py-2 text-[0.78rem] outline-none" />
                  </div>
                </div>
                <button onClick={async () => {
                  await createPRMut.mutateAsync({ repo_url: repoUrl, title: prTitle, head: prHead, base: prBase })
                  setPrTitle(""); setPrHead(""); setShowCreatePR(false)
                }} disabled={!prTitle || !prHead || createPRMut.isPending}
                  className="mt-3 flex items-center gap-2 rounded-lg bg-purple-500 px-4 py-2 text-[0.72rem] font-bold text-white disabled:opacity-50">
                  {createPRMut.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <GitPullRequest className="h-3.5 w-3.5" />}
                  Create PR
                </button>
              </div>
            )}

            {/* Open PRs Summary */}
            {pullRequests && pullRequests.length > 0 && (
              <div className="rounded-xl border border-[#E8EDF3] bg-white p-5">
                <h3 className="mb-3 text-sm font-bold text-[#111827]">Open Pull Requests</h3>
                <div className="space-y-2">
                  {pullRequests.slice(0, 5).map((pr) => (
                    <div key={pr.pr_number} className="flex items-center justify-between rounded-lg border border-[#E8EDF3] p-3">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <GitPullRequest className="h-3.5 w-3.5 text-green-500" />
                          <span className="text-[0.72rem] font-medium text-[#111827]">{pr.title}</span>
                        </div>
                        <div className="mt-0.5 flex items-center gap-2 text-[0.5rem] text-[#9CA3AF]">
                          <span>#{pr.pr_number}</span>
                          <span>{pr.head} → {pr.base}</span>
                        </div>
                      </div>
                      {pr.html_url && (
                        <a href={pr.html_url} target="_blank" rel="noopener noreferrer"
                          className="shrink-0 text-[#9CA3AF] hover:text-[#38B88A]">
                          <ExternalLink className="h-3.5 w-3.5" />
                        </a>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Recent Activity */}
            {history && history.length > 0 && (
              <div className="rounded-xl border border-[#E8EDF3] bg-white p-5">
                <h3 className="mb-3 text-sm font-bold text-[#111827]">Recent Activity</h3>
                <div className="space-y-1">
                  {history.slice(0, 8).map((entry, i) => (
                    <div key={i} className="flex items-center gap-2 text-[0.6rem] text-[#6B7280] py-1">
                      <div className={`w-1.5 h-1.5 rounded-full ${
                        entry.action.includes("merged") ? "bg-purple-400" :
                        entry.action.includes("created") ? "bg-blue-400" :
                        entry.action.includes("opened") ? "bg-green-400" :
                        "bg-gray-300"
                      }`} />
                      <span className="font-medium text-[#111827] capitalize">{entry.action.replace(/_/g, " ")}</span>
                      <span className="text-[#9CA3AF] truncate">{entry.entity_id}</span>
                      <span className="ml-auto text-[#9CA3AF]">{new Date(entry.timestamp).toLocaleString()}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </motion.div>
        )}

        {/* Branches */}
        {activeTab === "branches" && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
            <div className="flex items-center gap-3">
              <input type="text" value={branchName} onChange={e => setBranchName(e.target.value)}
                placeholder="New branch name"
                className="flex-1 rounded-lg border border-[#E8EDF3] px-3 py-2 text-[0.78rem] outline-none" />
              <input type="text" value={sourceBranch} onChange={e => setSourceBranch(e.target.value)}
                placeholder="From branch"
                className="w-36 rounded-lg border border-[#E8EDF3] px-3 py-2 text-[0.78rem] outline-none" />
              <button onClick={async () => {
                await createBranchMut.mutateAsync({ repo_url: repoUrl, branch_name: branchName, source_branch: sourceBranch })
                setBranchName("")
              }} disabled={!branchName || createBranchMut.isPending}
                className="flex items-center gap-2 rounded-lg bg-blue-500 px-4 py-2 text-[0.72rem] font-bold text-white disabled:opacity-50">
                {createBranchMut.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />}
                Create
              </button>
            </div>

            <div className="rounded-xl border border-[#E8EDF3] bg-white">
              <div className="border-b border-[#E8EDF3] px-4 py-3">
                <h3 className="text-sm font-bold text-[#111827]">{branches?.length ?? 0} Branches</h3>
              </div>
              {branches?.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12 text-[#9CA3AF]">
                  <GitBranch className="mb-3 h-8 w-8 opacity-30" />
                  <p className="text-[0.72rem]">No branches found.</p>
                </div>
              ) : (
                <div className="divide-y divide-[#E8EDF3]">
                  {branches?.map((b) => (
                    <div key={b.name} className="flex items-center gap-3 px-4 py-3">
                      <GitBranch className="h-4 w-4 shrink-0 text-[#6B7280]" />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <span className="text-[0.72rem] font-medium text-[#111827]">{b.name}</span>
                          {b.protected && <Shield className="h-3 w-3 text-amber-500" />}
                        </div>
                        <p className="text-[0.5rem] text-[#9CA3AF]">{b.sha?.slice(0, 12)}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </motion.div>
        )}

        {/* Pull Requests */}
        {activeTab === "pull-requests" && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
            {pullRequests?.length === 0 ? (
              <div className="flex flex-col items-center justify-center rounded-xl border border-[#E8EDF3] bg-white py-16 text-[#9CA3AF]">
                <GitPullRequest className="mb-3 h-10 w-10 opacity-30" />
                <p className="text-[0.72rem]">No pull requests. Create one from the Dashboard.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {pullRequests?.map((pr) => (
                  <div key={pr.pr_number} className="rounded-xl border border-[#E8EDF3] bg-white p-4">
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <GitPullRequest className={`h-4 w-4 ${pr.state === "open" ? "text-green-500" : "text-gray-400"}`} />
                          <StatusBadge status={pr.state} />
                          <span className="text-[0.72rem] font-bold text-[#111827]">{pr.title}</span>
                        </div>
                        <div className="mt-1 flex flex-wrap items-center gap-2 text-[0.5rem] text-[#9CA3AF]">
                          <span>#{pr.pr_number}</span>
                          <span>{pr.head} → {pr.base}</span>
                          {pr.reviewers?.length > 0 && (
                            <span>Reviewers: {pr.reviewers.join(", ")}</span>
                          )}
                          {pr.labels?.length > 0 && pr.labels.map(l => (
                            <span key={l} className="rounded bg-[#F4F7FA] px-1.5 py-0.5 text-[0.45rem]">{l}</span>
                          ))}
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <button onClick={() => mergePRMut.mutate({ prNumber: pr.pr_number, repo_url: repoUrl })}
                          disabled={pr.state !== "open" || mergePRMut.isPending}
                          className="flex items-center gap-1 rounded-lg bg-purple-50 px-2 py-1 text-[0.55rem] font-medium text-purple-600 hover:bg-purple-100 disabled:opacity-40">
                          <GitMerge className="h-3 w-3" /> Merge
                        </button>
                        {pr.html_url && (
                          <a href={pr.html_url} target="_blank" rel="noopener noreferrer"
                            className="text-[#9CA3AF] hover:text-[#38B88A]">
                            <ExternalLink className="h-3.5 w-3.5" />
                          </a>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </motion.div>
        )}

        {/* History */}
        {activeTab === "history" && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
            <div className="rounded-xl border border-[#E8EDF3] bg-white">
              <div className="border-b border-[#E8EDF3] px-4 py-3">
                <h3 className="text-sm font-bold text-[#111827]">Operation History ({history?.length ?? 0})</h3>
              </div>
              {history?.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12 text-[#9CA3AF]">
                  <RefreshCw className="mb-3 h-8 w-8 opacity-30" />
                  <p className="text-[0.72rem]">No operations yet.</p>
                </div>
              ) : (
                <div className="divide-y divide-[#E8EDF3]">
                  {history?.map((entry, i) => (
                    <div key={i} className="flex items-center gap-3 px-4 py-2.5">
                      <div className={`w-2 h-2 rounded-full ${
                        entry.action.includes("merged") ? "bg-purple-400" :
                        entry.action.includes("created") ? "bg-blue-400" :
                        entry.action.includes("opened") ? "bg-green-400" :
                        entry.action.includes("synchronized") ? "bg-teal-400" :
                        "bg-gray-300"
                      }`} />
                      <div className="min-w-0 flex-1">
                        <p className="text-[0.65rem] font-medium text-[#111827] capitalize">{entry.action.replace(/_/g, " ")}</p>
                        <p className="text-[0.5rem] text-[#9CA3AF] truncate">{entry.entity_id}</p>
                      </div>
                      <p className="shrink-0 text-[0.5rem] text-[#9CA3AF]">{new Date(entry.timestamp).toLocaleString()}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </motion.div>
        )}
      </div>
    </CortexShell>
  )
}
