"use client"

import { useState } from "react"
import { WorkspaceNavigation } from "./WorkspaceNavigation"
import { MissionHeader } from "./MissionHeader"
import { PersistentContextBar } from "./PersistentContextBar"
import { WorkspaceHost } from "./WorkspaceHost"
import { InspectorPanel } from "./InspectorPanel"
import { ActivityRail } from "./ActivityRail"
import { StatusFooter } from "./StatusFooter"
import type { WorkspaceId } from "./WorkspaceNavigation"

interface MissionControlShellProps {
  initialWorkspace?: WorkspaceId
}

export function MissionControlShell({ initialWorkspace = "executive" }: MissionControlShellProps) {
  const [selectedWorkspace, setSelectedWorkspace] = useState<WorkspaceId>(initialWorkspace)

  return (
    <div className="flex h-screen bg-[#F4F7FA]">
      <WorkspaceNavigation selected={selectedWorkspace} onSelect={setSelectedWorkspace} />

      <div className="flex flex-1 flex-col overflow-hidden">
        <MissionHeader workspace={selectedWorkspace} />

        <PersistentContextBar />

        <div className="flex flex-1 overflow-hidden">
          <div className="flex flex-1 flex-col overflow-hidden">
            <WorkspaceHost workspace={selectedWorkspace} />
            <ActivityRail />
          </div>
          <InspectorPanel />
        </div>

        <StatusFooter />
      </div>
    </div>
  )
}
