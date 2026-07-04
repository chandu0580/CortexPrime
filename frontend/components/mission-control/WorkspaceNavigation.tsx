"use client"

import {
  AlertTriangle,
  BookOpen,
  ClipboardCheck,
  LayoutDashboard,
  LayoutGrid,
  Lightbulb,
  Target,
} from "lucide-react"
import { cn } from "@/utils/cn"

export type WorkspaceId =
  | "executive"
  | "intelligence"
  | "mission"
  | "portfolio"
  | "review"
  | "intervention"
  | "learning"

interface WorkspaceEntry {
  id: WorkspaceId
  label: string
  icon: typeof LayoutDashboard
  description: string
}

export const WORKSPACES: WorkspaceEntry[] = [
  { id: "executive",     label: "Executive",     icon: LayoutDashboard, description: "Portfolio health and strategic overview" },
  { id: "intelligence",  label: "Intelligence",   icon: Lightbulb,      description: "Define intents and explore opportunities" },
  { id: "mission",       label: "Mission",        icon: Target,         description: "Single mission deep-dive" },
  { id: "portfolio",     label: "Portfolio",      icon: LayoutGrid,     description: "Mission portfolio management" },
  { id: "review",        label: "Review",         icon: ClipboardCheck, description: "Approvals, exceptions, and governance" },
  { id: "intervention",  label: "Intervention",   icon: AlertTriangle,  description: "Active interventions and incidents" },
  { id: "learning",      label: "Learning",       icon: BookOpen,       description: "Knowledge, patterns, and templates" },
]

interface WorkspaceNavigationProps {
  selected: WorkspaceId
  onSelect: (id: WorkspaceId) => void
}

export function WorkspaceNavigation({ selected, onSelect }: WorkspaceNavigationProps) {
  return (
    <nav aria-label="Workspaces" className="flex w-[56px] flex-col border-r border-[#EAEFF5] bg-white py-3">
      <div className="mb-4 flex justify-center">
        <div className="flex h-9 w-9 items-center justify-center rounded-[10px] bg-[#38B88A]">
          <svg aria-hidden="true" viewBox="0 0 48 48" className="h-5 w-5 text-white" fill="none">
            <path d="M24 4.5 39 13v22L24 43.5 9 35V13L24 4.5Z" stroke="currentColor" strokeWidth="3.5" strokeLinejoin="round" />
            <path d="M24 13 31 17v14l-7 4-7-4V17l7-4Z" fill="currentColor" fillOpacity=".3" stroke="currentColor" strokeWidth="2.8" strokeLinejoin="round" />
          </svg>
        </div>
      </div>

      <div className="flex flex-col items-center gap-1 px-1">
        {WORKSPACES.map((ws) => {
          const Icon = ws.icon
          const isActive = selected === ws.id
          return (
            <button
              key={ws.id}
              onClick={() => onSelect(ws.id)}
              aria-label={ws.label}
              aria-current={isActive ? "page" : undefined}
              className={cn(
                "flex h-10 w-10 items-center justify-center rounded-[10px] transition-all",
                isActive
                  ? "bg-[#ECFBF4] text-[#2F9F77]"
                  : "text-[#9CA3AF] hover:bg-[#F8FAFC] hover:text-[#374151]",
              )}
            >
              <Icon className="h-4.5 w-4.5" aria-hidden="true" />
            </button>
          )
        })}
      </div>
    </nav>
  )
}
