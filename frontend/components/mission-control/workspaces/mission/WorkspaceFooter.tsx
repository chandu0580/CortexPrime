import { WorkspaceFooter as WorkspaceFooterBase } from "@/components/mission-control/shared/WorkspaceFooter"

export function WorkspaceFooter() {
  return (
    <WorkspaceFooterBase
      actions={[
        { label: "Validate Mission", dot: true },
        { label: "Approve Mission", dot: true },
        { label: "Send to Runtime", dot: true },
      ]}
      statusText="Not ready for execution"
    />
  )
}
