import { SectionHeader } from "@/components/mission-control/shared/SectionHeader"
import { EmptyState } from "@/components/mission-control/shared/EmptyState"
import type { MissionPreview } from "@/types/intelligence"

interface MissionPreviewProps {
  preview?: MissionPreview | null
  isAnalyzing?: boolean
}

export function MissionPreview({ preview, isAnalyzing = false }: MissionPreviewProps) {
  if (preview) {
    return (
      <section>
        <SectionHeader title="Mission Preview" />
        <div className="rounded-[12px] border border-[#EAEFF5] bg-white p-5">
          <h4 className="mb-2 text-[0.92rem] font-bold text-[#111827]">{preview.title}</h4>
          <p className="mb-4 text-[0.82rem] leading-relaxed text-[#6B7280]">{preview.summary}</p>

          <div className="mb-4">
            <p className="mb-1.5 text-[0.72rem] font-semibold uppercase tracking-wider text-[#9CA3AF]">Objectives</p>
            <ul className="space-y-1">
              {preview.objectives.map((obj, i) => (
                <li key={i} className="flex items-start gap-2 text-[0.78rem] text-[#111827]">
                  <span className="mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[#38B88A]" />
                  {obj}
                </li>
              ))}
            </ul>
          </div>

          <div className="mb-4">
            <p className="mb-1.5 text-[0.72rem] font-semibold uppercase tracking-wider text-[#9CA3AF]">Expected Outcomes</p>
            <ul className="space-y-1">
              {preview.expectedOutcomes.map((outcome, i) => (
                <li key={i} className="flex items-start gap-2 text-[0.78rem] text-[#111827]">
                  <span className="mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[#9CA3AF]" />
                  {outcome}
                </li>
              ))}
            </ul>
          </div>

          <div className="flex items-center gap-4 border-t border-[#EAEFF5] pt-3">
            <div>
              <span className="text-[0.68rem] font-medium uppercase tracking-wider text-[#9CA3AF]">Estimated Effort</span>
              <p className="text-[0.82rem] font-medium text-[#111827]">{preview.estimatedEffort}</p>
            </div>
            <div>
              <span className="text-[0.68rem] font-medium uppercase tracking-wider text-[#9CA3AF]">Capabilities</span>
              <p className="text-[0.82rem] font-medium text-[#111827]">{preview.suggestedCapabilities.join(", ")}</p>
            </div>
          </div>
        </div>
      </section>
    )
  }

  return (
    <section>
      <SectionHeader title="Mission Preview" />
      <EmptyState
        variant="shell"
        icon={
          <svg className="h-5 w-5 text-[#D1D5DB]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
            <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z" />
          </svg>
        }
        title={isAnalyzing ? "Generating mission preview..." : "No mission generated"}
        description={isAnalyzing ? undefined : "Analyze an intent to generate a mission preview"}
      />
    </section>
  )
}
