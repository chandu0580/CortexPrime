import { SituationSummary } from "./executive/SituationSummary"
import { DecisionQueue } from "./executive/DecisionQueue"
import { AttentionBoard } from "./executive/AttentionBoard"
import { PortfolioOverview } from "./executive/PortfolioOverview"
import { EnterpriseSignals } from "./executive/EnterpriseSignals"
import { UpcomingReviews } from "./executive/UpcomingReviews"
import { ExecutiveNotes } from "./executive/ExecutiveNotes"
import { WorkspaceFooter } from "./executive/WorkspaceFooter"

export function ExecutiveWorkspace() {
  return (
    <div className="flex flex-1 flex-col gap-5 overflow-y-auto p-6">
      <div className="mx-auto flex w-full max-w-[960px] flex-col gap-5">
        <SituationSummary />
        <DecisionQueue />
        <AttentionBoard />
        <PortfolioOverview />
        <EnterpriseSignals />
        <UpcomingReviews />
        <ExecutiveNotes />
        <WorkspaceFooter />
      </div>
    </div>
  )
}
