export function StatusFooter() {
  return (
    <footer className="flex h-7 items-center gap-4 border-t border-[#EAEFF5] bg-white px-5">
      <div className="flex items-center gap-2">
        <span className="h-1.5 w-1.5 rounded-full bg-[#38B88A]" />
        <span className="text-[0.68rem] text-[#9CA3AF]">System Healthy</span>
      </div>
      <span className="text-[0.68rem] text-[#D1D5DB]">|</span>
      <span className="text-[0.68rem] text-[#9CA3AF]">Workspace: Operational</span>
      <span className="text-[0.68rem] text-[#D1D5DB]">|</span>
      <span className="text-[0.68rem] text-[#9CA3AF]">Connected</span>
      <div className="flex-1" />
      <span className="text-[0.68rem] text-[#B0B7C3]">v1.0.0</span>
    </footer>
  )
}
