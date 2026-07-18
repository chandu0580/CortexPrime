"use client"

import { useState } from "react"
import { useAgents, useAgentHistory, useRunAgents, useRuntimeStatus } from "@/hooks/queries/useAgents"
import { Play } from "lucide-react"
import { DelegationGraph, AgentHistoryList } from "@/components/enterprise"
import { Button, Input } from "@/components/enterprise/ui"

export default function AgentCenter() {
  const { data: agentsData } = useAgents()
  const runAgents = useRunAgents()
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null)
  const { data: agentHistory } = useAgentHistory(selectedAgent || "")
  const [goal, setGoal] = useState("")
  const agents = agentsData?.agents ?? []

  const agentNodes = agents.map((a) => ({
    id: a.agent_id,
    label: a.agent_type,
    status: a.status,
    capabilities: a.capabilities,
  }))

  return (
    <div className="space-y-6 max-w-7xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="type-heading-xl text-[var(--text-primary)]">Agent Center</h1>
          <p className="type-body text-[var(--text-muted)] mt-1">{agents.length} registered agents</p>
        </div>
      </div>

      <div className="surface-panel p-5">
        <h2 className="type-heading-sm text-[var(--text-primary)] mb-3">Run Multi-Agent Mission</h2>
        <div className="flex gap-3">
          <div className="flex-1">
            <Input
              placeholder="Describe the mission for agents..."
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && goal.trim()) {
                  runAgents.mutate({ goal: goal.trim(), mode: "dependency" }, { onSuccess: () => setGoal("") })
                }
              }}
            />
          </div>
          <Button
            onClick={() => goal.trim() && runAgents.mutate({ goal: goal.trim(), mode: "dependency" }, { onSuccess: () => setGoal("") })}
            disabled={!goal.trim() || runAgents.isPending}
            loading={runAgents.isPending}
            leftIcon={<Play className="w-4 h-4" />}
          >
            {runAgents.isPending ? "Running..." : "Run"}
          </Button>
        </div>
      </div>

      <DelegationGraph
        agents={agentNodes}
        selectedAgent={selectedAgent}
        onSelect={setSelectedAgent}
      />

      {selectedAgent && agentHistory && (
        <div className="surface-panel p-5">
          <h2 className="type-heading-sm text-[var(--text-primary)] mb-3">
            History: {selectedAgent}
          </h2>
          <AgentHistoryList history={agentHistory.history as Record<string, unknown>[]} />
        </div>
      )}
    </div>
  )
}
