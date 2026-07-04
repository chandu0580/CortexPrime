import { SectionHeader } from "@/components/mission-control/shared/SectionHeader"

export function ExecutiveNotes() {
  return (
    <section>
      <SectionHeader title="Executive Notes" />

      <div className="min-h-[140px] rounded-[12px] border border-[#EAEFF5] bg-white p-5">
        <p className="text-[0.82rem] italic text-[#B0B7C3]">
          Reserved for executive observations, strategic annotations, and mission commentary.
        </p>
        <div aria-hidden="true" className="mt-4 flex items-center gap-2">
          <div className="h-2 w-8 rounded bg-[#F0F4F8]" />
          <div className="h-2 w-16 rounded bg-[#F0F4F8]" />
          <div className="h-2 w-12 rounded bg-[#F0F4F8]" />
        </div>
      </div>
    </section>
  )
}
