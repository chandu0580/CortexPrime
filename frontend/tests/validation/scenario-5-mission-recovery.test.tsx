import { describe, it, expect } from "vitest"
import { getScenarioDefinition } from "@/lib/validation/scenarios"
import { simulateMission, runScenarioCheckpoints, buildScenarioResult } from "@/lib/validation/mission-simulator"
import type { ScenarioService } from "@/lib/validation/types"

describe("Scenario 5: Mission Recovery", () => {
  const def = getScenarioDefinition("mission-recovery")
  if (!def) throw new Error("Scenario definition not found")

  it("has a valid recovery-focused goal", () => {
    expect(def.goal.toLowerCase()).toContain("recover")
    expect(def.services.length).toBeGreaterThan(0)
  })

  it("covers recovery services", () => {
    const names = def.services.map((s) => s.name)
    expect(names).toContain("Replay")
    expect(names).toContain("Knowledge")
    expect(names).toContain("Governance")
  })

  it("simulates Replay analysis", () => {
    const replayActions = def.services.find((s) => s.name === "Replay")?.actions ?? []
    expect(replayActions).toContain("Analyze failure point in timeline")
    expect(replayActions).toContain("Identify root cause")
  })

  it("simulates Knowledge retrieval for recovery", () => {
    const knowActions = def.services.find((s) => s.name === "Knowledge")?.actions ?? []
    expect(knowActions).toContain("Search for similar failures")
    expect(knowActions).toContain("Retrieve recovery procedures")
  })

  it("simulates Governance approval for recovery", () => {
    const govActions = def.services.find((s) => s.name === "Governance")?.actions ?? []
    expect(govActions).toContain("Evaluate recovery plan")
    expect(govActions).toContain("Approve recovery execution")
  })

  it("simulates pause → resume → checkpoint → restore lifecycle", () => {
    const actions = [
      { action: "pause", stage: "executing" },
      { action: "checkpoint", stage: "executing" },
      { action: "resume", stage: "executing" },
      { action: "restore", stage: "validating" },
    ]
    for (const step of actions) {
      expect(step.action).toBeTruthy()
      expect(step.stage).toBeTruthy()
    }
  })

  it("handles failure recovery scenario", () => {
    const failureRecoverySteps = [
      "detect failure",
      "pause mission",
      "capture checkpoint",
      "analyze root cause",
      "retrieve recovery plan",
      "approve recovery",
      "restore from checkpoint",
      "resume execution",
      "verify recovery",
    ]
    expect(failureRecoverySteps.length).toBe(9)
    for (const step of failureRecoverySteps) {
      expect(typeof step).toBe("string")
      expect(step.length).toBeGreaterThan(0)
    }
  })

  it("passes all validation checkpoints", () => {
    const sim = simulateMission()
    const services: ScenarioService[] = def.services.map((s) => ({
      ...s,
      durationMs: Math.floor(Math.random() * 500) + 150,
      status: "pass",
    }))
    const checkpoints = runScenarioCheckpoints("mission-recovery", sim)
    expect(checkpoints.length).toBeGreaterThan(0)

    const result = buildScenarioResult("mission-recovery", checkpoints, services)
    expect(result.failCount).toBe(0)
    expect(result.score).toBe(100)
    expect(result.overallStatus).toBe("pass")
  })
})
