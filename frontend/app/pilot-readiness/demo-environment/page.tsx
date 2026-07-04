"use client"

import { useState } from "react"
import { motion } from "framer-motion"
import { PilotSidebar, PilotTopBar, StatusBadge, DataTable } from "@/components/pilot-readiness/shared"
import { stagger, variants } from "@/lib/motion-tokens"
import {
  ChevronLeft, Database, Building2, Users, FolderGit2, GitBranch,
  Bug, Target, ShieldCheck, Brain, Network, Activity
} from "lucide-react"
import Link from "next/link"
import {
  DEMO_ORGANIZATION, DEMO_DEPARTMENTS, DEMO_USERS, DEMO_PROJECTS,
  DEMO_REPOSITORIES, DEMO_JIRA_ISSUES, DEMO_MISSIONS, DEMO_APPROVALS,
  DEMO_KNOWLEDGE_GRAPH, DEMO_MEMORY_RECORDS, DEMO_CONNECTOR_ACTIVITY,
  DEMO_DASHBOARD_METRICS
} from "@/components/pilot-readiness/demo-data"
import { cn } from "@/utils/cn"

export default function DemoEnvironmentPage() {
  const [collapsed, setCollapsed] = useState(false)
  const [activeTab, setActiveTab] = useState("overview")
  const sidebarWidth = collapsed ? 60 : 220

  const tabs = [
    { id: "overview", label: "Overview", icon: Database },
    { id: "users", label: "Users", icon: Users },
    { id: "projects", label: "Projects", icon: FolderGit2 },
    { id: "missions", label: "Missions", icon: Target },
    { id: "graph", label: "Knowledge Graph", icon: Network },
    { id: "activity", label: "Activity", icon: Activity },
  ]

  const metrics = [
    { label: "Missions Completed", value: String(DEMO_DASHBOARD_METRICS.missionsCompleted), icon: Target, color: "#38B88A" },
    { label: "Active Users", value: String(DEMO_DASHBOARD_METRICS.activeUsers), icon: Users, color: "#3B82F6" },
    { label: "Workers Active", value: String(DEMO_DASHBOARD_METRICS.workersActive), icon: Activity, color: "#8B5CF6" },
    { label: "Uptime", value: `${DEMO_DASHBOARD_METRICS.uptime}%`, icon: ShieldCheck, color: "#38B88A" },
  ]

  return (
    <div className="min-h-screen bg-[#F4F7FA]">
      <PilotSidebar collapsed={collapsed} onCollapse={() => setCollapsed((v) => !v)} />
      <PilotTopBar sidebarWidth={sidebarWidth} />
      <div className="flex min-h-screen flex-col pt-[57px] transition-all duration-300" style={{ paddingLeft: sidebarWidth }}>
        <main className="flex-1 px-5 py-5">
          <motion.div initial="hidden" animate="visible" variants={stagger(0.04)} className="mx-auto max-w-[1500px]">
            <motion.div variants={variants.fadeUp} className="mb-4">
              <Link href="/pilot-readiness" className="inline-flex items-center gap-1 text-[0.72rem] font-semibold text-[#6B7280] hover:text-[#111827]"><ChevronLeft className="h-3.5 w-3.5" /> Back</Link>
              <div className="flex items-center gap-2 mt-2">
                <Building2 className="h-5 w-5 text-[#38B88A]" />
                <h1 className="text-[1.5rem] font-bold tracking-[-0.02em] text-[#111827]">Demo Enterprise: {DEMO_ORGANIZATION.name}</h1>
              </div>
              <p className="text-[0.82rem] text-[#6B7280]">{DEMO_ORGANIZATION.industry} &middot; {DEMO_ORGANIZATION.size} &middot; {DEMO_ORGANIZATION.location}</p>
            </motion.div>

            {/* Metric cards */}
            <motion.div variants={variants.fadeUp} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 mb-5">
              {metrics.map((m) => (
                <div key={m.label} className="rounded-[18px] border border-[#E8EDF3] bg-white p-4">
                  <div className="flex items-center gap-2 mb-1">
                    <m.icon className="h-4 w-4" style={{ color: m.color }} />
                    <span className="text-[0.71rem] font-semibold text-[#9CA3AF]">{m.label}</span>
                  </div>
                  <p className="text-[1.4rem] font-bold text-[#111827]">{m.value}</p>
                </div>
              ))}
            </motion.div>

            {/* Tabs */}
            <motion.div variants={variants.fadeUp} className="flex items-center gap-1 mb-5 p-1 rounded-[12px] bg-[#F8FAFC] w-fit">
              {tabs.map((tab) => (
                <button key={tab.id} onClick={() => setActiveTab(tab.id)}
                  className={cn(
                    "flex items-center gap-1.5 px-3 py-2 rounded-[8px] text-[0.75rem] font-semibold transition-colors",
                    activeTab === tab.id ? "bg-white text-[#111827] shadow-sm" : "text-[#6B7280] hover:text-[#111827]"
                  )}>
                  <tab.icon className="h-3.5 w-3.5" /> {tab.label}
                </button>
              ))}
            </motion.div>

            {/* Tab content */}
            <motion.div variants={variants.fadeUp}>
              {activeTab === "overview" && (
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  <div className="rounded-[18px] border border-[#E8EDF3] bg-white p-5">
                    <h3 className="text-[0.9rem] font-bold text-[#111827] mb-3">Organization</h3>
                    <div className="space-y-2 text-[0.78rem]">
                      <div className="flex justify-between"><span className="text-[#6B7280]">Name</span><span className="font-semibold">{DEMO_ORGANIZATION.name}</span></div>
                      <div className="flex justify-between"><span className="text-[#6B7280]">Industry</span><span className="font-semibold">{DEMO_ORGANIZATION.industry}</span></div>
                      <div className="flex justify-between"><span className="text-[#6B7280]">Departments</span><span className="font-semibold">{DEMO_DEPARTMENTS.length}</span></div>
                      <div className="flex justify-between"><span className="text-[#6B7280]">Tenants</span><span className="font-semibold">{DEMO_ORGANIZATION.tenants}</span></div>
                    </div>
                  </div>
                  <div className="rounded-[18px] border border-[#E8EDF3] bg-white p-5">
                    <h3 className="text-[0.9rem] font-bold text-[#111827] mb-3">Departments</h3>
                    <div className="space-y-2">
                      {DEMO_DEPARTMENTS.map((d) => (
                        <div key={d.id} className="flex items-center justify-between text-[0.75rem]">
                          <span className="font-semibold text-[#111827]">{d.name}</span>
                          <span className="text-[#6B7280]">{d.headCount} people</span>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div className="rounded-[18px] border border-[#E8EDF3] bg-white p-5">
                    <h3 className="text-[0.9rem] font-bold text-[#111827] mb-3">Quick Stats</h3>
                    <div className="space-y-2 text-[0.78rem]">
                      <div className="flex justify-between"><span className="text-[#6B7280]">Users</span><span className="font-semibold">{DEMO_USERS.length}</span></div>
                      <div className="flex justify-between"><span className="text-[#6B7280]">Projects</span><span className="font-semibold">{DEMO_PROJECTS.length}</span></div>
                      <div className="flex justify-between"><span className="text-[#6B7280]">Missions</span><span className="font-semibold">{DEMO_MISSIONS.length}</span></div>
                      <div className="flex justify-between"><span className="text-[#6B7280]">KG Entities</span><span className="font-semibold">{DEMO_KNOWLEDGE_GRAPH.length}</span></div>
                      <div className="flex justify-between"><span className="text-[#6B7280]">Approvals</span><span className="font-semibold">{DEMO_APPROVALS.length}</span></div>
                    </div>
                  </div>
                </div>
              )}

              {activeTab === "users" && (
                <div className="rounded-[18px] border border-[#E8EDF3] bg-white p-5">
                  <DataTable
                    columns={[
                      { label: "Name", key: "name" },
                      { label: "Email", key: "email" },
                      { label: "Role", key: "role" },
                      { label: "Department", key: "department" },
                      { label: "MFA", key: "mfaEnabled", render: (row: Record<string, unknown>) => (row.mfaEnabled as boolean) ? "✅" : "—" },
                      { label: "Status", key: "status" },
                    ]}
                    data={DEMO_USERS as unknown as Record<string, unknown>[]}
                  />
                </div>
              )}

              {activeTab === "projects" && (
                <div className="rounded-[18px] border border-[#E8EDF3] bg-white p-5">
                  <h3 className="text-[0.9rem] font-bold text-[#111827] mb-3">Projects</h3>
                  <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                    {DEMO_PROJECTS.map((p) => (
                      <div key={p.id} className="rounded-[12px] border border-[#E8EDF3] p-4">
                        <p className="text-[0.82rem] font-bold text-[#111827]">{p.name}</p>
                        <p className="text-[0.68rem] text-[#6B7280]">{p.department}</p>
                        <div className="mt-2 flex items-center gap-2">
                          <div className="flex-1 h-1.5 rounded-full bg-[#E8EDF3]">
                            <div className="h-full rounded-full bg-[#38B88A]" style={{ width: `${p.progress}%` }} />
                          </div>
                          <span className="text-[0.66rem] font-semibold text-[#6B7280]">{p.progress}%</span>
                        </div>
                        <div className="mt-2 flex items-center justify-between text-[0.66rem] text-[#9CA3AF]">
                          <span>Lead: {p.leadName}</span>
                          <span>Due: {p.deadline}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {activeTab === "missions" && (
                <div className="rounded-[18px] border border-[#E8EDF3] bg-white p-5">
                  <DataTable
                    columns={[
                      { label: "ID", key: "id" },
                      { label: "Objective", key: "objective" },
                      { label: "Status", key: "status" },
                      { label: "Agent", key: "agent" },
                      { label: "Duration", key: "duration" },
                      { label: "Confidence", key: "confidence", render: (row: Record<string, unknown>) => `${((row.confidence as number) * 100).toFixed(0)}%` },
                    ]}
                    data={DEMO_MISSIONS as unknown as Record<string, unknown>[]}
                  />
                </div>
              )}

              {activeTab === "graph" && (
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="rounded-[18px] border border-[#E8EDF3] bg-white p-5">
                    <h3 className="text-[0.9rem] font-bold text-[#111827] mb-3">Knowledge Graph Entities</h3>
                    <div className="space-y-2 max-h-[400px] overflow-y-auto">
                      {DEMO_KNOWLEDGE_GRAPH.map((e) => (
                        <div key={e.id} className="flex items-center gap-3 p-2 rounded-[8px] hover:bg-[#F8FAFC]">
                          <div className="w-2 h-2 rounded-full bg-[#38B88A]" />
                          <span className="text-[0.75rem] font-medium text-[#111827]">{e.name}</span>
                          <StatusBadge tone="healthy" label={e.type} />
                        </div>
                      ))}
                    </div>
                  </div>
                  <div className="rounded-[18px] border border-[#E8EDF3] bg-white p-5">
                    <h3 className="text-[0.9rem] font-bold text-[#111827] mb-3">Memory Records</h3>
                    <div className="space-y-2 max-h-[400px] overflow-y-auto">
                      {DEMO_MEMORY_RECORDS.map((m) => (
                        <div key={m.id} className="p-2 rounded-[8px] border border-[#E8EDF3]">
                          <div className="flex items-center gap-2 mb-1">
                            <StatusBadge tone={m.type === "semantic" ? "healthy" : m.type === "episodic" ? "active" : "pending"} label={m.type} />
                            <span className="text-[0.66rem] text-[#9CA3AF]">{m.agent}</span>
                          </div>
                          <p className="text-[0.72rem] text-[#6B7280]">{m.content}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {activeTab === "activity" && (
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="rounded-[18px] border border-[#E8EDF3] bg-white p-5">
                    <h3 className="text-[0.9rem] font-bold text-[#111827] mb-3">Connector Activity</h3>
                    <DataTable
                      columns={[
                        { label: "Connector", key: "connector" },
                        { label: "Action", key: "action" },
                        { label: "Status", key: "status" },
                        { label: "Duration", key: "duration" },
                      ]}
                      data={DEMO_CONNECTOR_ACTIVITY}
                    />
                  </div>
                  <div className="rounded-[18px] border border-[#E8EDF3] bg-white p-5">
                    <h3 className="text-[0.9rem] font-bold text-[#111827] mb-3">Approvals</h3>
                    <DataTable
                      columns={[
                        { label: "Action", key: "action" },
                        { label: "Requester", key: "requester" },
                        { label: "Risk", key: "riskLevel" },
                        { label: "Status", key: "status" },
                      ]}
                      data={DEMO_APPROVALS}
                    />
                  </div>
                </div>
              )}
            </motion.div>
          </motion.div>
        </main>
      </div>
    </div>
  )
}