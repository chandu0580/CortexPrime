"use client"

import { Activity, Bot, Target } from "lucide-react"
import type { OrchestratorMission, AgentInfo } from "@/types/enterprise"

export default function ActivityFeed({
  missions, agents, health,
}: {
  missions: OrchestratorMission[]; agents: AgentInfo[]; health?: { status: string; active_missions: number; total_missions: number }
}) {
  return (
    <div className="surface-panel p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="type-heading-sm text-[var(--text-primary)]">System Status</h2>
        <Activity className="w-4 h-4 text-[var(--text-muted)]" />
      </div>
      <div className="space-y-4">
        <div className="flex items-center justify-between p-3 rounded-xl bg-[var(--surface-raised)]">
          <div className="flex items-center gap-3">
            <Target className="w-4 h-4 text-[var(--accent)]" />
            <span className="type-body-sm text-[var(--text-primary)]">Active Missions</span>
          </div>
          <span className="type-metric-sm text-[var(--accent)]">{health?.active_missions ?? 0}</span>
        </div>
        <div className="flex items-center justify-between p-3 rounded-xl bg-[var(--surface-raised)]">
          <div className="flex items-center gap-3">
            <Bot className="w-4 h-4 text-[var(--info)]" />
            <span className="type-body-sm text-[var(--text-primary)]">Registered Agents</span>
          </div>
          <span className="type-metric-sm text-[var(--info)]">{agents.length}</span>
        </div>
        <div className="flex items-center justify-between p-3 rounded-xl bg-[var(--surface-raised)]">
          <div className="flex items-center gap-3">
            <Activity className="w-4 h-4 text-[var(--success)]" />
            <span className="type-body-sm text-[var(--text-primary)]">Total Missions</span>
          </div>
          <span className="type-metric-sm text-[var(--success)]">{health?.total_missions ?? missions.length}</span>
        </div>
        <div className="mt-4 pt-4 border-t border-[var(--border)]">
          <h3 className="type-label-sm text-[var(--text-muted)] mb-2">Recent Activity</h3>
          {missions.slice(0, 4).map((m) => (
            <div key={m.mission_id} className="flex items-start gap-2 py-1.5">
              <span className={`w-1.5 h-1.5 rounded-full mt-1.5 shrink-0 ${
                m.status === "running" ? "bg-[var(--success)]" :
                m.status === "failed" ? "bg-[var(--danger)]" :
                "bg-[var(--text-muted)]"
              }`} />
              <p className="type-body-sm text-[var(--text-secondary)] truncate">
                <span className="font-medium">{m.goal}</span>
                <span className="text-[var(--text-muted)]"> — {m.status}</span>
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
