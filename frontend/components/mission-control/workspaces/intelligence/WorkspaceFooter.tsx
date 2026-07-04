import { WorkspaceFooter as WorkspaceFooterBase } from "@/components/mission-control/shared/WorkspaceFooter"

export function WorkspaceFooter() {
  return (
    <WorkspaceFooterBase
      actions={[
        { label: "Analyze Intent", dot: true },
        { label: "Save Draft" },
        { label: "Clear" },
      ]}
      statusText="No active intent"
    />
  )
}
