"use client"

import { useWorkspaceIntelligence } from "@/hooks"
import { WorkspaceFooter as WorkspaceFooterBase } from "@/components/mission-control/shared/WorkspaceFooter"

export function WorkspaceFooter() {
  const { data } = useWorkspaceIntelligence()
  const hasActivity = (data?.activeCount ?? 0) > 0

  return (
    <WorkspaceFooterBase
      actions={[
        { label: "Analyze Intent", dot: true },
        { label: "Save Draft", dot: hasActivity },
        { label: "Clear" },
      ]}
      statusText={
        hasActivity
          ? `${data?.activeCount ?? 0} active · ${data?.totalCount ?? 0} total · ${data?.successRate ?? 100}% success`
          : "No active intent"
      }
    />
  )
}
