"use client"

import { use } from "react"
import { useMission, usePauseMission, useResumeMission, useCancelMission, useRestartMission } from "@/hooks/queries/useMissions"
import { useRuntimeStatus } from "@/hooks/queries/useAgents"
import { Pause, Play, XCircle, RotateCcw } from "lucide-react"
import { Badge, Button } from "@/components/enterprise/ui"
import { MissionTimeline, ReasoningTrace, StageMetricsPanel } from "@/components/enterprise"

export default function MissionDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const { data: mission, isLoading } = useMission(id)
  const { data: runtimeStatus } = useRuntimeStatus()
  const pause = usePauseMission()
  const resume = useResumeMission()
  const cancel = useCancelMission()
  const restart = useRestartMission()

  if (isLoading) return <div className="flex items-center justify-center h-64"><span className="animate-blink text-[var(--text-muted)]">Loading mission...</span></div>
  if (!mission) return <div className="type-body text-[var(--danger)]">Mission not found</div>

  const stages = Object.entries(mission.stages || {})
  const metrics = Object.entries(mission.stage_metrics || {})

  return (
    <div className="space-y-6 max-w-7xl">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="type-heading-xl text-[var(--text-primary)]">{mission.goal}</h1>
          <div className="flex items-center gap-3 mt-2">
            <Badge variant={mission.status === "running" ? "info" : mission.status === "failed" ? "danger" : "default"}>
              {mission.status}
            </Badge>
            <span className="type-caption text-[var(--text-muted)]">{mission.mission_id}</span>
          </div>
        </div>
        <div className="flex gap-2">
          {mission.status === "running" && (
            <Button variant="secondary" size="sm" leftIcon={<Pause className="w-4 h-4" />} onClick={() => pause.mutate(id)}>Pause</Button>
          )}
          {mission.status === "paused" && (
            <Button variant="primary" size="sm" leftIcon={<Play className="w-4 h-4" />} onClick={() => resume.mutate(id)}>Resume</Button>
          )}
          {(mission.status === "running" || mission.status === "paused") && (
            <Button variant="danger" size="sm" leftIcon={<XCircle className="w-4 h-4" />} onClick={() => cancel.mutate(id)}>Cancel</Button>
          )}
          {mission.status === "failed" && (
            <Button variant="primary" size="sm" leftIcon={<RotateCcw className="w-4 h-4" />} onClick={() => restart.mutate(id)}>Restart</Button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <div className="surface-panel p-5">
            <h2 className="type-heading-sm text-[var(--text-primary)] mb-4">Lifecycle Timeline</h2>
            <MissionTimeline stages={stages} />
          </div>

          {mission.reasoning_trace && mission.reasoning_trace.length > 0 && (
            <div className="surface-panel p-5">
              <h2 className="type-heading-sm text-[var(--text-primary)] mb-4">Reasoning Trace</h2>
              <ReasoningTrace steps={mission.reasoning_trace} />
            </div>
          )}
        </div>

        <div className="space-y-4">
          <StageMetricsPanel metrics={metrics} />

          {mission.context && Object.keys(mission.context).length > 0 && (
            <div className="surface-panel p-5">
              <h3 className="type-label-sm text-[var(--text-muted)] mb-3">Context</h3>
              <div className="space-y-2">
                {Object.entries(mission.context).map(([k, v]) => (
                  <div key={k} className="flex justify-between text-xs">
                    <span className="text-[var(--text-muted)]">{k}</span>
                    <span className="text-[var(--text-secondary)]">{String(v).slice(0, 30)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="surface-panel p-5">
            <h3 className="type-label-sm text-[var(--text-muted)] mb-3">Runtime Status</h3>
            <div className="space-y-2">
              {runtimeStatus?.runtimes && Object.entries(runtimeStatus.runtimes).map(([name, available]) => (
                <div key={name} className="flex items-center justify-between">
                  <span className="type-body-sm text-[var(--text-secondary)] capitalize">{name.replace(/_/g, " ")}</span>
                  <span className={`w-2 h-2 rounded-full ${available ? "bg-[var(--success)]" : "bg-[var(--danger)]"}`} />
                </div>
              ))}
            </div>
          </div>

          {mission.artifacts && mission.artifacts.length > 0 && (
            <div className="surface-panel p-5">
              <h3 className="type-label-sm text-[var(--text-muted)] mb-3">Artifacts ({mission.artifacts.length})</h3>
              <div className="space-y-1">
                {mission.artifacts.map((a) => (
                  <div key={a.artifact_id} className="type-body-sm text-[var(--text-secondary)] truncate">{a.name}</div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
