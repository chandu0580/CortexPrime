"use client"

import { useWorkspaceExecutive } from "@/hooks"
import { WorkspaceFooter as WorkspaceFooterBase } from "@/components/mission-control/shared/WorkspaceFooter"

export function WorkspaceFooter() {
  const { data } = useWorkspaceExecutive()

  const activeMissions = data?.activeMissions ?? 0
  const totalMissions = data?.totalMissions ?? 0

  return (
    <WorkspaceFooterBase
      actions={[
        { label: "Review Decisions", dot: (data?.queueDepth ?? 0) > 0 },
        { label: "Export Brief" },
        { label: "Open Portfolio" },
      ]}
      statusText={
        totalMissions > 0
          ? `${activeMissions} active · ${data?.completedMissions ?? 0} completed · ${data?.failedMissions ?? 0} failed`
          : "No active portfolio"
      }
    />
  )
}
