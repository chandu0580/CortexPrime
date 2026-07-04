"use client";

import LearningSummary from "./LearningSummary";
import LessonsLearned from "./LessonsLearned";
import KnowledgeAssets from "./KnowledgeAssets";
import PatternsInsights from "./PatternsInsights";
import Recommendations from "./Recommendations";
import InstitutionalMemory from "./InstitutionalMemory";
import ContinuousImprovement from "./ContinuousImprovement";
import WorkspaceFooter from "./WorkspaceFooter";

export default function LearningWorkspace() {
  return (
    <div className="mx-auto max-w-7xl space-y-8 pb-12">
      <LearningSummary />
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-3">
        <div className="lg:col-span-1">
          <LessonsLearned />
        </div>
        <div className="lg:col-span-2">
          <KnowledgeAssets />
        </div>
      </div>
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <PatternsInsights />
        </div>
        <div className="lg:col-span-1">
          <Recommendations />
        </div>
      </div>
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <InstitutionalMemory />
        </div>
        <div className="lg:col-span-1">
          <ContinuousImprovement />
        </div>
      </div>
      <WorkspaceFooter />
    </div>
  );
}
