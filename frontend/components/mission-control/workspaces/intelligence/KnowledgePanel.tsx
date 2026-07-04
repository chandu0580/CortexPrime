import { SectionHeader } from "@/components/mission-control/shared/SectionHeader"

export function KnowledgePanel() {
  return (
    <section>
      <SectionHeader title="Knowledge Context" />

      <div className="rounded-[12px] border border-[#EAEFF5] bg-white p-5">
        <div className="grid grid-cols-4 gap-4">
          {["Related Missions", "Knowledge Assets", "Evidence", "Templates"].map((item) => (
            <div key={item} className="space-y-2">
              <div aria-hidden="true" className="flex items-center gap-1.5">
                <div className="h-3 w-3 rounded-[4px] bg-[#F0F4F8]" />
                <span className="text-[0.72rem] font-medium text-[#9CA3AF]">{item}</span>
              </div>
              <div aria-hidden="true" className="space-y-1">
                <div className="h-2.5 w-full rounded bg-[#F0F4F8]" />
                <div className="h-2.5 w-4/5 rounded bg-[#F0F4F8]" />
                <div className="h-2.5 w-3/5 rounded bg-[#F0F4F8]" />
              </div>
            </div>
          ))}
        </div>
        <p className="mt-4 text-center text-[0.72rem] text-[#B0B7C3]">
          Knowledge context will populate from related missions and organizational memory
        </p>
      </div>
    </section>
  )
}
