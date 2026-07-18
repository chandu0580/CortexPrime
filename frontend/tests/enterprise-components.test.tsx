import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import { MissionTimeline } from "@/components/enterprise/MissionTimeline"
import { ReasoningTrace } from "@/components/enterprise/ReasoningTrace"
import { StageMetricsPanel } from "@/components/enterprise/StageMetrics"
import { ChatMessageBubble } from "@/components/enterprise/ChatWindow"
import { AgentHistoryList } from "@/components/enterprise/DelegationGraph"
import { ConnectorCard } from "@/components/enterprise/ConnectorCard"
import { TopologyGraph } from "@/components/enterprise/TopologyGraph"

describe("MissionTimeline", () => {
  it("renders stage entries", () => {
    const stages: [string, { success: boolean; error?: string; runtime?: string } | undefined][] = [
      ["mission_received", { success: true, runtime: "orchestrator" }],
      ["mission_analyzed", { success: true }],
      ["governance_evaluated", { success: false, error: "Policy denied" }],
    ]
    render(<MissionTimeline stages={stages} />)
    expect(screen.getByText("mission received")).toBeInTheDocument()
    expect(screen.getByText("mission analyzed")).toBeInTheDocument()
    expect(screen.getByText("governance evaluated")).toBeInTheDocument()
    expect(screen.getByText("Policy denied")).toBeInTheDocument()
    expect(screen.getByText("PASS")).toBeInTheDocument()
    expect(screen.getByText("FAIL")).toBeInTheDocument()
  })

  it("returns null for empty stages", () => {
    const { container } = render(<MissionTimeline stages={[]} />)
    expect(container.innerHTML).toBe("")
  })
})

describe("ReasoningTrace", () => {
  it("renders reasoning steps", () => {
    const steps = [
      { description: "Analyzing mission", decision: "Proceed", confidence: 0.9, critical: false },
      { description: "Validating policy", decision: "Approve", confidence: 0.8, critical: true },
    ]
    render(<ReasoningTrace steps={steps} />)
    expect(screen.getByText("Analyzing mission")).toBeInTheDocument()
    expect(screen.getByText("Validating policy")).toBeInTheDocument()
    expect(screen.getByText("Decision: Proceed")).toBeInTheDocument()
    expect(screen.getByText("Decision: Approve")).toBeInTheDocument()
  })

  it("returns null for empty steps", () => {
    const { container } = render(<ReasoningTrace steps={[]} />)
    expect(container.innerHTML).toBe("")
  })
})

describe("StageMetricsPanel", () => {
  it("renders stage metrics", () => {
    const metrics: [string, { duration_seconds: number; runtime_invoked: string; success: boolean; artifacts_produced: number; errors: string[]; decision_rationale: string; connector_invoked: string }][] = [
      ["execution", { duration_seconds: 12.5, runtime_invoked: "execution", success: true, artifacts_produced: 2, errors: [], decision_rationale: "", connector_invoked: "" }],
    ]
    render(<StageMetricsPanel metrics={metrics} />)
    expect(screen.getByText("execution")).toBeInTheDocument()
    expect(screen.getByText("12.5s")).toBeInTheDocument()
  })

  it("returns null for empty metrics", () => {
    const { container } = render(<StageMetricsPanel metrics={[]} />)
    expect(container.innerHTML).toBe("")
  })
})

describe("ChatMessageBubble", () => {
  it("renders user message", () => {
    render(<ChatMessageBubble msg={{ id: "1", role: "user", content: "Hello", timestamp: "" }} />)
    expect(screen.getByText("Hello")).toBeInTheDocument()
  })

  it("renders assistant message", () => {
    render(<ChatMessageBubble msg={{ id: "2", role: "assistant", content: "Hi there", timestamp: "" }} />)
    expect(screen.getByText("Hi there")).toBeInTheDocument()
  })
})

describe("AgentHistoryList", () => {
  it("renders history items", () => {
    const history = [
      { task_id: "task-1", agent_type: "planner", success: true },
      { task_id: "task-2", agent_type: "sre", success: false, error: "Timeout" },
    ]
    render(<AgentHistoryList history={history as unknown as Record<string, unknown>[]} />)
    expect(screen.getByText("task-1")).toBeInTheDocument()
    expect(screen.getByText("task-2")).toBeInTheDocument()
    expect(screen.getByText("Timeout")).toBeInTheDocument()
    expect(screen.getByText("SUCCESS")).toBeInTheDocument()
    expect(screen.getByText("FAILED")).toBeInTheDocument()
  })

  it("shows empty state", () => {
    render(<AgentHistoryList history={[]} />)
    expect(screen.getByText("No task history")).toBeInTheDocument()
  })
})

describe("ConnectorCard", () => {
  it("renders default connector", () => {
    render(<ConnectorCard isDefault name="github" />)
    expect(screen.getByText("github")).toBeInTheDocument()
    expect(screen.getByText("unavailable")).toBeInTheDocument()
  })

  it("renders active connector", () => {
    render(<ConnectorCard connector={{ connector_type: "slack", name: "Slack Workspace", status: "connected", capabilities: ["messaging"] } as unknown as Record<string, unknown>} />)
    expect(screen.getByText("Slack Workspace")).toBeInTheDocument()
    expect(screen.getByText("connected")).toBeInTheDocument()
  })
})

describe("TopologyGraph", () => {
  const nodes = [
    { id: "core", label: "Core", type: "core", icon: "div" as unknown as React.ComponentType<{ className?: string }>, status: "active" as const },
    { id: "runtime", label: "Runtime", type: "runtime", icon: "div" as unknown as React.ComponentType<{ className?: string }>, status: "inactive" as const },
  ]
  const connections = [
    { from: "core", to: "runtime", label: "connects" },
  ]

  it("renders topology nodes", () => {
    render(<TopologyGraph nodes={nodes} connections={connections} />)
    expect(screen.getByText("Core")).toBeInTheDocument()
    expect(screen.getByText("Runtime")).toBeInTheDocument()
    expect(screen.getByText("Active")).toBeInTheDocument()
    expect(screen.getByText("Standby")).toBeInTheDocument()
  })
})
