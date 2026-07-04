import dynamic from "next/dynamic"
import type { ComponentType } from "react"
import type { WorkspaceId } from "./WorkspaceNavigation"

const ExecutiveWorkspace = dynamic(() =>
  import("./workspaces/ExecutiveWorkspace").then((m) => ({ default: m.ExecutiveWorkspace })),
  { ssr: false },
)
const IntelligenceWorkspace = dynamic(() =>
  import("./workspaces/IntelligenceWorkspace").then((m) => ({ default: m.IntelligenceWorkspace })),
  { ssr: false },
)
const MissionWorkspace = dynamic(() =>
  import("./workspaces/MissionWorkspace").then((m) => ({ default: m.MissionWorkspace })),
  { ssr: false },
)
const PortfolioWorkspace = dynamic(() =>
  import("./workspaces/PortfolioWorkspace").then((m) => ({ default: m.PortfolioWorkspace })),
  { ssr: false },
)
const ReviewWorkspace = dynamic(() => import("@/components/review-workspace/ReviewWorkspace"), { ssr: false })
const InterventionWorkspace = dynamic(() => import("@/components/intervention-workspace/InterventionWorkspace"), { ssr: false })
const LearningWorkspace = dynamic(() => import("@/components/learning-workspace/LearningWorkspace"), { ssr: false })

const workspaceMap: Record<WorkspaceId, ComponentType> = {
  executive:    ExecutiveWorkspace,
  intelligence: IntelligenceWorkspace,
  mission:      MissionWorkspace,
  portfolio:    PortfolioWorkspace,
  review:       ReviewWorkspace,
  intervention: InterventionWorkspace,
  learning:     LearningWorkspace,
}

interface WorkspaceHostProps {
  workspace: WorkspaceId
}

export function WorkspaceHost({ workspace }: WorkspaceHostProps) {
  const Component = workspaceMap[workspace]
  return (
    <div className="flex flex-1 flex-col overflow-y-auto">
      <Component />
    </div>
  )
}
