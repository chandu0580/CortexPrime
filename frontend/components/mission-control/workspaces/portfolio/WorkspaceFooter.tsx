"use client"

import { useWorkspacePortfolio } from "@/hooks"
import { WorkspaceFooter as WorkspaceFooterBase } from "@/components/mission-control/shared/WorkspaceFooter"

export function WorkspaceFooter() {
  const { data } = useWorkspacePortfolio()

  const hasMissions = (data?.activeMissions ?? 0) > 0 || (data?.completedMissions ?? 0) > 0

  return (
    <WorkspaceFooterBase
      actions={[
        { label: "Review Portfolio", dot: hasMissions },
        { label: "Export Portfolio", dot: hasMissions },
        { label: "Create Initiative" },
      ]}
      statusText={
        hasMissions
          ? `${data?.activeMissions ?? 0} active · ${data?.completedMissions ?? 0} completed · ${(data?.successRate ?? 100)}% success`
          : "No active portfolio"
      }
    />
  )
}
