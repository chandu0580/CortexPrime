import { PortfolioSummary } from "./portfolio/PortfolioSummary"
import { StrategicInitiatives } from "./portfolio/StrategicInitiatives"
import { MissionPortfolioMap } from "./portfolio/MissionPortfolioMap"
import { OutcomeTracking } from "./portfolio/OutcomeTracking"
import { DependencyNetwork } from "./portfolio/DependencyNetwork"
import { PortfolioRisks } from "./portfolio/PortfolioRisks"
import { PortfolioLearning } from "./portfolio/PortfolioLearning"
import { WorkspaceFooter } from "./portfolio/WorkspaceFooter"

export function PortfolioWorkspace() {
  return (
    <div className="flex flex-1 flex-col gap-5 overflow-y-auto p-6">
      <div className="mx-auto flex w-full max-w-[960px] flex-col gap-5">
        <PortfolioSummary />
        <StrategicInitiatives />
        <MissionPortfolioMap />
        <OutcomeTracking />
        <DependencyNetwork />
        <PortfolioRisks />
        <PortfolioLearning />
        <WorkspaceFooter />
      </div>
    </div>
  )
}
