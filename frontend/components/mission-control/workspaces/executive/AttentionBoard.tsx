import { SectionHeader } from "@/components/mission-control/shared/SectionHeader"

const tiers = [
  { label: "Critical",      color: "#EF4444", bg: "#FEF2F2" },
  { label: "High",          color: "#F59E0B", bg: "#FFFBEB" },
  { label: "Medium",        color: "#3B82F6", bg: "#EFF6FF" },
  { label: "Informational", color: "#9CA3AF", bg: "#F9FAFB" },
]

export function AttentionBoard() {
  return (
    <section>
      <SectionHeader title="Executive Attention Board" />

      <div className="space-y-2">
        {tiers.map((tier) => (
          <div
            key={tier.label}
            className="rounded-[10px] border border-[#EAEFF5] bg-white px-4 py-3"
          >
            <div className="flex items-center gap-2.5">
              <div aria-hidden="true" className="flex h-7 w-7 items-center justify-center rounded-[6px]" style={{ backgroundColor: tier.bg }}>
                <div className="h-2 w-2 rounded-full" style={{ backgroundColor: tier.color }} />
              </div>
              <span className="text-[0.84rem] font-medium text-[#111827]">{tier.label}</span>
              <div className="ml-auto flex items-center gap-2">
                <div aria-hidden="true" className="h-2 w-8 rounded bg-[#F0F4F8]" />
                <span className="text-[0.7rem] text-[#B0B7C3]">0</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}
