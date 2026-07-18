"use client"

import { use, useState } from "react"
import { useMission } from "@/hooks/queries/useMissions"
import { Play, Pause, SkipBack, SkipForward } from "lucide-react"
import { motion } from "framer-motion"
import { Badge, Button } from "@/components/enterprise/ui"

const stateFlow = [
  "mission_received", "mission_analyzed", "mission_planned",
  "knowledge_retrieved", "learning_retrieved", "governance_evaluated",
  "execution_planned", "execution_started", "execution_completed",
  "verification", "knowledge_updated", "learning_updated", "mission_archived",
]

export default function ReplayDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const { data: mission, isLoading } = useMission(id)
  const [currentStep, setCurrentStep] = useState(0)
  const [playing, setPlaying] = useState(false)

  if (isLoading) return <div className="flex items-center justify-center h-64"><span className="animate-blink text-[var(--text-muted)]">Loading replay...</span></div>
  if (!mission) return <div className="type-body text-[var(--danger)]">Mission not found</div>

  const completedStates = Object.keys(mission.stages || {})
  const timeline = stateFlow.filter((s) => completedStates.includes(s))

  return (
    <div className="space-y-6 max-w-7xl">
      <div>
        <h1 className="type-heading-xl text-[var(--text-primary)]">Replay: {mission.goal}</h1>
        <p className="type-body text-[var(--text-muted)] mt-1">{mission.mission_id}</p>
      </div>

      <div className="surface-panel p-5">
        <div className="flex items-center justify-center gap-4 mb-6">
          <Button variant="secondary" size="sm" leftIcon={<SkipBack className="w-4 h-4" />} onClick={() => setCurrentStep(0)} />
          <Button
            variant="primary"
            leftIcon={playing ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
            onClick={() => setPlaying(!playing)}
          >
            {playing ? "Pause" : "Play"}
          </Button>
          <Button variant="secondary" size="sm" leftIcon={<SkipForward className="w-4 h-4" />} onClick={() => setCurrentStep(timeline.length - 1)} />
        </div>

        <div className="space-y-3">
          {timeline.map((state, i) => {
            const result = mission.stages?.[state]
            const isActive = i === currentStep
            const isPast = i < currentStep
            return (
              <motion.div
                key={state}
                animate={{
                  opacity: isPast ? 0.5 : 1,
                  scale: isActive ? 1.02 : 1,
                }}
                className={`flex items-center gap-3 p-3 rounded-xl cursor-pointer transition-colors ${
                  isActive ? "accent-border bg-[var(--accent-muted)]" : "hover:bg-[var(--surface-raised)]"
                }`}
                onClick={() => setCurrentStep(i)}
              >
                <div className={`w-3 h-3 rounded-full ${
                  result?.success ? "bg-[var(--success)]" : isActive ? "bg-[var(--accent)]" : "bg-[var(--text-muted)]"
                }`} />
                <div className="flex-1">
                  <p className="type-body-sm text-[var(--text-primary)] capitalize">{state.replace(/_/g, " ")}</p>
                  {result && (
                    <p className="type-caption text-[var(--text-muted)]">
                      Duration: {result.duration.toFixed(1)}s — Runtime: {result.runtime || "N/A"}
                    </p>
                  )}
                </div>
                <Badge variant={result?.success ? "success" : "danger"}>
                  {result?.success ? "PASS" : result ? "FAIL" : "—"}
                </Badge>
              </motion.div>
            )
          })}
        </div>
      </div>

      {mission.artifacts && mission.artifacts.length > 0 && (
        <div className="surface-panel p-5">
          <h2 className="type-heading-sm text-[var(--text-primary)] mb-3">Artifacts</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {mission.artifacts.map((a) => (
              <div key={a.artifact_id} className="p-3 rounded-xl bg-[var(--surface-raised)]">
                <p className="type-body-sm text-[var(--text-primary)]">{a.name}</p>
                <p className="type-caption text-[var(--text-muted)]">{a.artifact_type}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
