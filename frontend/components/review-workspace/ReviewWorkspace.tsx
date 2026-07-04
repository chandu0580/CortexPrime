"use client";

import ReviewSummary from "./ReviewSummary";
import ReasoningOverview from "./ReasoningOverview";
import EvidencePanel from "./EvidencePanel";
import DecisionAlternatives from "./DecisionAlternatives";
import RiskImpact from "./RiskImpact";
import ReviewerNotes from "./ReviewerNotes";
import ApprovalTimeline from "./ApprovalTimeline";
import WorkspaceFooter from "./WorkspaceFooter";

export default function ReviewWorkspace() {
  return (
    <div className="mx-auto max-w-7xl space-y-8 pb-12">
      <ReviewSummary />
      <ReasoningOverview />
      <EvidencePanel />
      <DecisionAlternatives />
      <RiskImpact />
      <ReviewerNotes />
      <ApprovalTimeline />
      <WorkspaceFooter />
    </div>
  );
}
