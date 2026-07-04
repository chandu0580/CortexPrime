import { memo, type ReactNode } from "react"

export interface FooterAction {
  label: string
  dot?: boolean
  icon?: ReactNode
}

interface WorkspaceFooterProps {
  actions: FooterAction[]
  statusText: string
}

export const WorkspaceFooter = memo(function WorkspaceFooter({ actions, statusText }: WorkspaceFooterProps) {
  return (
    <footer className="flex items-center justify-between rounded-[12px] border border-[#EAEFF5] bg-white px-5 py-3">
      <div className="flex items-center gap-3">
        {actions.map((action) => (
          <div
            key={action.label}
            role="button"
            aria-disabled="true"
            tabIndex={-1}
            className="flex h-8 select-none items-center gap-1.5 rounded-[8px] border border-[#EAEFF5] bg-[#F8FAFC] px-4 text-[0.8rem] font-medium text-[#9CA3AF]"
          >
            {action.dot && <div aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-[#D1D5DB]" />}
            {action.icon && <span aria-hidden="true">{action.icon}</span>}
            {action.label}
          </div>
        ))}
      </div>
      <span className="text-[0.7rem] text-[#B0B7C3]">{statusText}</span>
    </footer>
  )
})
WorkspaceFooter.displayName = "WorkspaceFooter"
