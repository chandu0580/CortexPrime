import { SectionHeader } from "@/components/mission-control/shared/SectionHeader"
import { InfoCard } from "@/components/mission-control/shared/InfoCard"

const outcomes = [
  { label: "Expected Outcomes",  icon: "▣" },
  { label: "Current Outcomes",   icon: "◈" },
  { label: "Outcome Confidence", icon: "◇" },
  { label: "Business Value",     icon: "$" },
]

export function OutcomeTracking() {
  return (
    <section>
      <SectionHeader title="Outcome Tracking" />

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {outcomes.map((item) => (
          <InfoCard key={item.label} icon={<span aria-hidden="true" className="text-[0.8rem] text-[#9CA3AF]">{item.icon}</span>} label={item.label} skeletonWidth="w-3/5">
            <div aria-hidden="true" className="mt-1 h-6 w-2/5 rounded bg-[#F0F4F8]" />
          </InfoCard>
        ))}
      </div>
    </section>
  )
}
