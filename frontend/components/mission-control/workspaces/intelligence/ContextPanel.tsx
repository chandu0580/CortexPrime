import { SectionHeader } from "@/components/mission-control/shared/SectionHeader"
import { InfoCard } from "@/components/mission-control/shared/InfoCard"
import type { MissionContext } from "@/types/intelligence"

const emptyFields = [
  { label: "Business Goal",        width: "w-3/5" },
  { label: "Constraints",          width: "w-1/2" },
  { label: "Success Criteria",     width: "w-2/3" },
  { label: "Stakeholders",         width: "w-2/5" },
  { label: "Priority",             width: "w-1/3" },
  { label: "Business Domain",      width: "w-1/4" },
]

interface ContextPanelProps {
  context?: MissionContext | null
}

export function ContextPanel({ context }: ContextPanelProps) {
  if (context) {
    const fields = [
      { label: "Business Goal",    value: context.businessGoal },
      { label: "Constraints",      value: context.constraints.join(", ") },
      { label: "Success Criteria", value: context.successCriteria.join(", ") },
      { label: "Stakeholders",     value: context.stakeholders.join(", ") },
      { label: "Priority",         value: context.priority.charAt(0).toUpperCase() + context.priority.slice(1) },
      { label: "Business Domain",  value: context.businessDomain },
    ]

    return (
      <section>
        <SectionHeader title="Context" />
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {fields.map((field) => (
            <InfoCard key={field.label}>
              <div className="mb-2 flex items-center justify-between">
                <span className="text-[0.7rem] font-medium uppercase tracking-wider text-[#9CA3AF]">
                  {field.label}
                </span>
              </div>
              <p className="text-[0.82rem] font-medium text-[#111827]">{field.value}</p>
            </InfoCard>
          ))}
        </div>
      </section>
    )
  }

  return (
    <section>
      <SectionHeader title="Context" />
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {emptyFields.map((field) => (
          <InfoCard key={field.label}>
            <div className="mb-2 flex items-center justify-between">
              <span className="text-[0.7rem] font-medium uppercase tracking-wider text-[#9CA3AF]">
                {field.label}
              </span>
              <div aria-hidden="true" className="h-4 w-4 rounded border border-[#EAEFF5] bg-[#F8FAFC]" />
            </div>
            <div aria-hidden="true" className={field.width}>
              <div className="h-3 rounded bg-[#F0F4F8]" />
              <div className="mt-1.5 h-4 w-4/5 rounded bg-[#F0F4F8]" />
            </div>
          </InfoCard>
        ))}
      </div>
    </section>
  )
}
