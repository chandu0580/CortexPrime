const roles = [
  { label: "Business Owner",  icon: "👤" },
  { label: "Approver",        icon: "✓" },
  { label: "Operator",        icon: "⚙" },
  { label: "Observer",        icon: "👁" },
  { label: "AI Coordinator",  icon: "◆" },
]

import { SectionHeader } from "@/components/mission-control/shared/SectionHeader"

export function StakeholdersPanel() {
  return (
    <section>
      <SectionHeader title="Stakeholders" />

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {roles.map((role) => (
          <div
            key={role.label}
            className="rounded-[10px] border border-[#EAEFF5] bg-white p-4 text-center"
          >
            <div aria-hidden="true" className="mx-auto mb-2 flex h-9 w-9 items-center justify-center rounded-full bg-[#F0F4F8] text-[0.8rem] text-[#9CA3AF]">
              {role.icon}
            </div>
            <p className="text-[0.8rem] font-medium text-[#111827]">{role.label}</p>
            <p className="mt-1 text-[0.68rem] text-[#B0B7C3]">Not assigned</p>
          </div>
        ))}
      </div>
    </section>
  )
}
