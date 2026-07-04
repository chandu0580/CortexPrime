import { SectionHeader } from "@/components/mission-control/shared/SectionHeader"
import type { MissionAssessment, MissionContext } from "@/types/intelligence"

interface AssessmentPanelProps {
  assessment?: MissionAssessment | null
  context?: MissionContext | null
}

export function AssessmentPanel({ assessment, context }: AssessmentPanelProps) {
  if (assessment && context) {
    const priorityColor =
      context.priority === "critical" ? "#EF4444"
        : context.priority === "high" ? "#F59E0B"
        : context.priority === "medium" ? "#3B82F6"
        : "#9CA3AF"

    const priorityBg =
      context.priority === "critical" ? "#FEF2F2"
        : context.priority === "high" ? "#FFFBEB"
        : context.priority === "medium" ? "#EFF6FF"
        : "#F9FAFB"

    return (
      <section>
        <SectionHeader title="Opportunity Assessment" />
        <div className="rounded-[12px] border border-[#EAEFF5] bg-white p-5">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-[10px]" style={{ backgroundColor: priorityBg }}>
              <div className="h-3 w-3 rounded-full" style={{ backgroundColor: priorityColor }} />
            </div>
            <div>
              <p className="text-[0.84rem] font-medium text-[#111827]">{context.businessDomain}</p>
              <p className="text-[0.72rem] text-[#9CA3AF]">{context.priority.charAt(0).toUpperCase() + context.priority.slice(1)} priority · {(assessment.feasibility * 100).toFixed(0)}% feasibility</p>
            </div>
          </div>
          <div className="mt-4 space-y-2">
            <p className="text-[0.72rem] font-medium uppercase tracking-wider text-[#9CA3AF]">Recommendations</p>
            <ul className="space-y-1">
              {assessment.recommendations.map((rec, i) => (
                <li key={i} className="flex items-start gap-2 text-[0.78rem] text-[#6B7280]">
                  <span className="mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[#38B88A]" />
                  {rec}
                </li>
              ))}
            </ul>
          </div>
          <div className="mt-3 flex items-center gap-2">
            <span className="text-[0.68rem] text-[#9CA3AF]">Est. duration: {assessment.estimatedDuration}</span>
            <span className="text-[0.68rem] text-[#D1D5DB]">·</span>
            <span className="text-[0.68rem] text-[#9CA3AF]">{assessment.resourceRequirements.length} resource areas</span>
          </div>
        </div>
      </section>
    )
  }

  return (
    <section>
      <SectionHeader title="Opportunity Assessment" />
      <div className="rounded-[12px] border border-[#EAEFF5] bg-white p-5">
        <div className="flex items-center gap-3">
          <div aria-hidden="true" className="flex h-9 w-9 items-center justify-center rounded-[10px] bg-[#F8FAFC]">
            <div className="h-4 w-4 rounded-[4px] border-2 border-[#D1D5DB]" />
          </div>
          <div>
            <p className="text-[0.84rem] font-medium text-[#111827]">Not Assessed</p>
            <p className="text-[0.72rem] text-[#9CA3AF]">
              Define an intent and analyze to receive opportunity assessment
            </p>
          </div>
        </div>
      </div>
      <div className="mt-2 flex items-center gap-3 px-1">
        <div className="flex items-center gap-2">
          <span aria-hidden="true" className="h-2 w-2 rounded-full bg-[#D1D5DB]" />
          <span className="text-[0.72rem] text-[#9CA3AF]">Not assessed</span>
        </div>
        <div className="flex items-center gap-2">
          <span aria-hidden="true" className="h-2 w-2 rounded-full bg-[#F59E0B]" />
          <span className="text-[0.72rem] text-[#9CA3AF]">Assessment pending</span>
        </div>
        <div className="flex items-center gap-2">
          <span aria-hidden="true" className="h-2 w-2 rounded-full bg-[#38B88A]" />
          <span className="text-[0.72rem] text-[#9CA3AF]">Assessed</span>
        </div>
      </div>
    </section>
  )
}
