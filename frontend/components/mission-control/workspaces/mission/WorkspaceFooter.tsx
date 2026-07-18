"use client"

import { useWorkspaceMission } from "@/hooks"
import { WorkspaceFooter as WorkspaceFooterBase } from "@/components/mission-control/shared/WorkspaceFooter"

export function WorkspaceFooter() {
  const { data } = useWorkspaceMission()

  const hasActive = (data?.activeMissions.length ?? 0) > 0
  const hasCompleted = (data?.completedCount ?? 0) > 0

  return (
    <WorkspaceFooterBase
      actions={[
        { label: "Validate Mission", dot: hasActive },
        { label: "Approve Mission", dot: hasActive },
        { label: "Review Results", dot: hasCompleted },
      ]}
      statusText={
        hasActive
          ? `${data?.activeMissions.length} active · ${data?.completedCount} completed`
          : "Not ready for execution"
      }
    />
  )
}
