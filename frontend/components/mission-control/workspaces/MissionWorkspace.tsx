import { MissionOverview } from "./mission/MissionOverview"
import { ObjectivesPanel } from "./mission/ObjectivesPanel"
import { ConstraintsPanel } from "./mission/ConstraintsPanel"
import { RiskPanel } from "./mission/RiskPanel"
import { DependencyGraph } from "./mission/DependencyGraph"
import { StakeholdersPanel } from "./mission/StakeholdersPanel"
import { ArtifactsPanel } from "./mission/ArtifactsPanel"
import { ExecutionReadiness } from "./mission/ExecutionReadiness"
import { WorkspaceFooter } from "./mission/WorkspaceFooter"

export function MissionWorkspace() {
  return (
    <div className="flex flex-1 flex-col gap-5 overflow-y-auto p-6">
      <div className="mx-auto flex w-full max-w-[960px] flex-col gap-5">
        <MissionOverview />
        <ObjectivesPanel />
        <ConstraintsPanel />
        <RiskPanel />
        <DependencyGraph />
        <StakeholdersPanel />
        <ArtifactsPanel />
        <ExecutionReadiness />
        <WorkspaceFooter />
      </div>
    </div>
  )
}
