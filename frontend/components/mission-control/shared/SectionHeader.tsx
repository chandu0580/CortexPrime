import { memo, type ReactNode } from "react"

interface SectionHeaderProps {
  title: string
  suffix?: ReactNode
}

export const SectionHeader = memo(function SectionHeader({ title, suffix }: SectionHeaderProps) {
  if (suffix) {
    return (
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-[0.92rem] font-bold text-[#111827]">{title}</h3>
        {suffix}
      </div>
    )
  }

  return <h3 className="mb-3 text-[0.92rem] font-bold text-[#111827]">{title}</h3>
})
SectionHeader.displayName = "SectionHeader"
