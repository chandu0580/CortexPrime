export function SectionHead({ title, action }: { title: string; action?: React.ReactNode }) {
  return (
    <div className="mb-4 flex items-center justify-between">
      <h2 className="text-[0.98rem] font-semibold text-[#111827]">{title}</h2>
      {action && <span className="text-[0.8rem] font-semibold text-[#38B88A] cursor-pointer hover:underline">{action}</span>}
    </div>
  )
}
