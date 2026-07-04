import { SectionHeader } from "@/components/mission-control/shared/SectionHeader"

export function StrategicInitiatives() {
  return (
    <section>
      <SectionHeader title="Strategic Initiatives" />

      <div className="rounded-[12px] border border-[#EAEFF5] bg-white p-5">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="flex flex-col items-center justify-center rounded-[10px] border border-dashed border-[#D1D9E6] py-6">
              <div aria-hidden="true" className="mb-2 flex h-8 w-8 items-center justify-center rounded-[8px] bg-[#F8FAFC]">
                <div className="h-4 w-4 rounded-full border-2 border-[#D1D5DB]" />
              </div>
              <p className="text-[0.76rem] font-medium text-[#9CA3AF]">Initiative {i}</p>
              <p className="mt-0.5 text-[0.66rem] text-[#B0B7C3]">Not started</p>
            </div>
          ))}
        </div>
        <div className="mt-4 border-t border-[#EAEFF5] pt-4 text-center">
          <p className="text-[0.74rem] text-[#B0B7C3]">No strategic initiatives available</p>
        </div>
      </div>
    </section>
  )
}
