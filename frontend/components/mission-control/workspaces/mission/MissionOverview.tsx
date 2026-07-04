import { SectionHeader } from "@/components/mission-control/shared/SectionHeader"
import { SkeletonField } from "@/components/mission-control/shared/SkeletonField"

const fields = [
  { label: "Mission Title",        width: "w-2/5" },
  { label: "Mission Purpose",      width: "w-3/5" },
  { label: "Business Goal",        width: "w-1/2" },
  { label: "Mission Status",       width: "w-1/4" },
  { label: "Mission Priority",     width: "w-1/5" },
  { label: "Mission Owner",        width: "w-1/3" },
  { label: "Mission Classification", width: "w-1/4" },
]

export function MissionOverview() {
  return (
    <section>
      <SectionHeader
        title="Mission Overview"
        suffix={
          <div className="flex h-6 items-center gap-1.5 rounded-[6px] bg-[#F0F4F8] px-2.5 text-[0.65rem] font-medium uppercase tracking-wider text-[#9CA3AF]">
            <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-[#D1D5DB]" />
            Draft
          </div>
        }
      />

      <div className="rounded-[12px] border border-[#EAEFF5] bg-white p-5">
        <div className="grid grid-cols-1 gap-x-8 gap-y-4 sm:grid-cols-2 lg:grid-cols-3">
          {fields.map((field) => (
            <SkeletonField key={field.label} label={field.label} width={field.width} />
          ))}
        </div>
      </div>
    </section>
  )
}
