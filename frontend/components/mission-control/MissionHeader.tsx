"use client"

import { Search } from "lucide-react"
import { WORKSPACES, type WorkspaceId } from "./WorkspaceNavigation"

interface MissionHeaderProps {
  workspace: WorkspaceId
}

export function MissionHeader({ workspace }: MissionHeaderProps) {
  const ws = WORKSPACES.find((w) => w.id === workspace)

  return (
    <header className="flex h-14 items-center gap-4 border-b border-[#EAEFF5] bg-white px-5">
      {/* Breadcrumbs */}
      <div className="flex items-center gap-2 text-[0.76rem] text-[#9CA3AF]">
        <span>CortexPrime</span>
        <span>/</span>
        <span className="font-semibold text-[#111827]">{ws?.label ?? "Mission Control"}</span>
      </div>

      {/* Workspace title + description */}
      <div className="ml-2 flex items-baseline gap-2">
        <h1 className="text-[0.92rem] font-bold text-[#111827]">{ws?.label ?? "Mission Control"}</h1>
        <p className="hidden text-[0.72rem] text-[#9CA3AF] md:block">{ws?.description}</p>
      </div>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Global search placeholder */}
      <label className="relative flex h-8 w-[180px] shrink-0 items-center">
        <Search className="pointer-events-none absolute left-2.5 h-3.5 w-3.5 text-[#9CA3AF]" />
        <input
          type="search"
          placeholder="Search..."
          className="h-full w-full rounded-[10px] border border-[#EAEFF5] bg-[#F8FAFC] pl-8 pr-3 text-[0.8rem] outline-none placeholder:text-[#9CA3AF] focus:border-[#B7E5D3] focus:ring-2 focus:ring-[#EAF8F1]"
        />
      </label>

      {/* Context actions placeholder */}
      <div className="flex items-center gap-2">
        <div className="h-7 w-7 rounded-[8px] border border-[#EAEFF5] bg-white" />
        <div className="h-7 w-7 rounded-[8px] border border-[#EAEFF5] bg-white" />
      </div>
    </header>
  )
}
