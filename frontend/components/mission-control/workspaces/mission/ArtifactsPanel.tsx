import { SectionHeader } from "@/components/mission-control/shared/SectionHeader"

const artifactTypes = ["Evidence", "Documents", "Knowledge Assets", "Reports"]

export function ArtifactsPanel() {
  return (
    <section>
      <SectionHeader title="Artifacts" />

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {artifactTypes.map((type) => (
          <div
            key={type}
            className="rounded-[10px] border border-dashed border-[#D1D9E6] bg-white p-4"
          >
            <div aria-hidden="true" className="mb-2 flex h-8 w-8 items-center justify-center rounded-[8px] bg-[#F8FAFC]">
              <div className="h-4 w-4 rounded-[4px] border border-[#D1D5DB]" />
            </div>
            <p className="text-[0.8rem] font-medium text-[#111827]">{type}</p>
            <p className="mt-0.5 text-[0.68rem] text-[#B0B7C3]">No artifacts</p>
          </div>
        ))}
      </div>
    </section>
  )
}
