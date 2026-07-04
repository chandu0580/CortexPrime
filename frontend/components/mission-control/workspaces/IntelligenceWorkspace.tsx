"use client"

import { useAnalyzeIntent } from "@/hooks/queries/intelligence"
import { IntentComposer } from "./intelligence/IntentComposer"
import { ContextPanel } from "./intelligence/ContextPanel"
import { AssessmentPanel } from "./intelligence/AssessmentPanel"
import { MissionPreview } from "./intelligence/MissionPreview"
import { KnowledgePanel } from "./intelligence/KnowledgePanel"
import { CapabilityPanel } from "./intelligence/CapabilityPanel"
import { WorkspaceFooter } from "./intelligence/WorkspaceFooter"

export function IntelligenceWorkspace() {
  const { mutate, data: analysis, isPending } = useAnalyzeIntent()

  const handleSubmit = (text: string) => {
    mutate({
      text,
      timestamp: new Date().toISOString(),
    })
  }

  return (
    <div className="flex flex-1 flex-col gap-5 overflow-y-auto p-6">
      <div className="mx-auto flex w-full max-w-[960px] flex-col gap-5">
        <IntentComposer onSubmit={handleSubmit} isAnalyzing={isPending} />
        <ContextPanel context={analysis?.context ?? null} />
        <AssessmentPanel assessment={analysis?.assessment ?? null} context={analysis?.context ?? null} />
        <MissionPreview preview={analysis?.preview ?? null} isAnalyzing={isPending} />
        <KnowledgePanel />
        <CapabilityPanel />
        <WorkspaceFooter />
      </div>
    </div>
  )
}
