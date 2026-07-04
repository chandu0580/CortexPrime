import { SectionHeader } from "@/components/mission-control/shared/SectionHeader"
import { InfoCard } from "@/components/mission-control/shared/InfoCard"

const cards = [
  { label: "Business Goals",       skeletonWidth: "w-3/5" },
  { label: "Active Initiatives",   skeletonWidth: "w-2/5" },
  { label: "Mission Count",        skeletonWidth: "w-1/4" },
  { label: "Portfolio Health",     skeletonWidth: "w-1/2" },
  { label: "Enterprise Alignment", skeletonWidth: "w-3/5" },
]

export function PortfolioSummary() {
  return (
    <section>
      <SectionHeader title="Portfolio Summary" suffix={<span className="text-[0.7rem] text-[#B0B7C3]">Last reviewed —</span>} />

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {cards.map((card) => (
          <InfoCard key={card.label} label={card.label} skeletonWidth={card.skeletonWidth} />
        ))}
      </div>
    </section>
  )
}
