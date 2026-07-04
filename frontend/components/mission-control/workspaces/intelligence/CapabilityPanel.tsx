import { SectionHeader } from "@/components/mission-control/shared/SectionHeader"

export function CapabilityPanel() {
  return (
    <section>
      <SectionHeader title="Recommended Capabilities" />

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className="rounded-[10px] border border-[#EAEFF5] bg-white p-4"
          >
            <div aria-hidden="true" className="mb-3 h-2.5 w-3/4 rounded bg-[#F0F4F8]" />
            <div aria-hidden="true" className="space-y-1.5">
              <div className="h-2 w-full rounded bg-[#F0F4F8]" />
              <div className="h-2 w-4/5 rounded bg-[#F0F4F8]" />
            </div>
            <div aria-hidden="true" className="mt-3 flex items-center gap-2">
              <div className="h-5 w-5 rounded-full bg-[#F0F4F8]" />
              <div className="h-2 w-12 rounded bg-[#F0F4F8]" />
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}
