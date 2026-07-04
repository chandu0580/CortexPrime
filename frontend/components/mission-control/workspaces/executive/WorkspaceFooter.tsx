import { WorkspaceFooter as WorkspaceFooterBase } from "@/components/mission-control/shared/WorkspaceFooter"

export function WorkspaceFooter() {
  return (
    <WorkspaceFooterBase
      actions={[
        { label: "Review Decisions" },
        { label: "Export Brief" },
        { label: "Open Portfolio" },
      ]}
      statusText="No active portfolio"
    />
  )
}
