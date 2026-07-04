"use client";

import InterventionSummary from "./InterventionSummary";
import ActiveInterventionQueue from "./ActiveInterventionQueue";
import EscalationPath from "./EscalationPath";
import InterventionDetails from "./InterventionDetails";
import DecisionSupport from "./DecisionSupport";
import ResolutionHistory from "./ResolutionHistory";
import HumanCollaboration from "./HumanCollaboration";
import WorkspaceFooter from "./WorkspaceFooter";

export default function InterventionWorkspace() {
  return (
    <div className="mx-auto max-w-7xl space-y-8 pb-12">
      <InterventionSummary />
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-3">
        <div className="lg:col-span-1">
          <ActiveInterventionQueue />
        </div>
        <div className="lg:col-span-2">
          <EscalationPath />
        </div>
      </div>
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <InterventionDetails />
        </div>
        <div className="lg:col-span-1">
          <DecisionSupport />
        </div>
      </div>
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-3">
        <div className="lg:col-span-1">
          <ResolutionHistory />
        </div>
        <div className="lg:col-span-2">
          <HumanCollaboration />
        </div>
      </div>
      <WorkspaceFooter />
    </div>
  );
}
