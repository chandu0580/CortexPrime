import { SectionHeader } from "@/components/mission-control/shared/SectionHeader"
import { InfoCard } from "@/components/mission-control/shared/InfoCard"

const cards = [
  { label: "Strategic Health",  icon: "♢" },
  { label: "Mission Portfolio", icon: "▣" },
  { label: "Pending Decisions",  icon: "◈" },
  { label: "Critical Risks",    icon: "△" },
  { label: "Enterprise Confidence", icon: "◇" },
]

export function SituationSummary() {
  return (
    <section>
      <SectionHeader title="Situation Summary" suffix={<span className="text-[0.7rem] text-[#B0B7C3]">Updated —</span>} />

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {cards.map((card) => (
          <InfoCard key={card.label} icon={<span aria-hidden="true" className="text-[0.8rem] text-[#9CA3AF]">{card.icon}</span>} skeletonWidth="w-3/5">
            <p className="mb-2 text-[0.78rem] font-medium text-[#111827]">{card.label}</p>
          </InfoCard>
        ))}
      </div>
    </section>
  )
}
