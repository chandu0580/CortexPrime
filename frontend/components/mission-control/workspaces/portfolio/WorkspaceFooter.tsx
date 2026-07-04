import { WorkspaceFooter as WorkspaceFooterBase } from "@/components/mission-control/shared/WorkspaceFooter"

export function WorkspaceFooter() {
  return (
    <WorkspaceFooterBase
      actions={[
        { label: "Review Portfolio" },
        { label: "Export Portfolio" },
        { label: "Create Initiative" },
      ]}
      statusText="No active portfolio"
    />
  )
}
