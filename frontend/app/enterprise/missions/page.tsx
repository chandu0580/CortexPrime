"use client"

import { useState } from "react"
import { motion } from "framer-motion"
import { useMissions, useStartMission } from "@/hooks/queries/useMissions"
import { Plus } from "lucide-react"
import { Button, Input, Modal } from "@/components/enterprise/ui"
import MissionCard from "../dashboard/MissionCard"

export default function MissionCenter() {
  const [statusFilter, setStatusFilter] = useState("")
  const [showNew, setShowNew] = useState(false)
  const [goal, setGoal] = useState("")
  const { data } = useMissions(statusFilter || undefined)
  const startMission = useStartMission()
  const missions = data?.missions ?? []

  return (
    <div className="space-y-6 max-w-7xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="type-heading-xl text-[var(--text-primary)]">Mission Center</h1>
          <p className="type-body text-[var(--text-muted)] mt-1">Manage and monitor autonomous missions</p>
        </div>
        <Button leftIcon={<Plus className="w-4 h-4" />} onClick={() => setShowNew(true)}>
          New Mission
        </Button>
      </div>

      <Modal open={showNew} onClose={() => setShowNew(false)} title="Start New Mission">
        <p className="type-body-sm text-[var(--text-muted)] mb-4">Describe what you want the autonomous system to accomplish.</p>
        <div className="flex gap-3">
          <div className="flex-1">
            <Input
              placeholder="Describe the mission goal..."
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && goal.trim()) {
                  startMission.mutate({ goal: goal.trim() }, {
                    onSuccess: () => { setGoal(""); setShowNew(false) },
                  })
                }
              }}
            />
          </div>
          <Button
            onClick={() => goal.trim() && startMission.mutate({ goal: goal.trim() }, {
              onSuccess: () => { setGoal(""); setShowNew(false) },
            })}
            disabled={!goal.trim() || startMission.isPending}
            loading={startMission.isPending}
          >
            {startMission.isPending ? "Starting..." : "Start"}
          </Button>
        </div>
      </Modal>

      <div className="flex items-center gap-2">
        {["", "running", "pending", "completed", "failed", "paused"].map((s) => (
          <button
            key={s}
            onClick={() => setStatusFilter(s)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              statusFilter === s
                ? "bg-[var(--accent-muted)] text-[var(--accent)]"
                : "text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-raised)]"
            }`}
          >
            {s || "All"}
          </button>
        ))}
      </div>

      <div className="surface-panel p-5">
        <div className="space-y-1">
          {missions.map((m) => (
            <MissionCard key={m.mission_id} mission={m} />
          ))}
          {missions.length === 0 && (
            <p className="type-body text-[var(--text-muted)] text-center py-8">No missions found</p>
          )}
        </div>
      </div>
    </div>
  )
}
