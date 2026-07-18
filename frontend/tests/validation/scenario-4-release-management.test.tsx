import { describe, it, expect } from "vitest"
import { getScenarioDefinition } from "@/lib/validation/scenarios"
import { simulateMission, runScenarioCheckpoints, buildScenarioResult } from "@/lib/validation/mission-simulator"
import type { ScenarioService } from "@/lib/validation/types"

describe("Scenario 4: Release Management", () => {
  const def = getScenarioDefinition("release-management")
  if (!def) throw new Error("Scenario definition not found")

  it("has a valid release-focused goal", () => {
    expect(def.goal.toLowerCase()).toContain("release")
    expect(def.services.length).toBe(5)
  })

  it("covers all release services", () => {
    const names = def.services.map((s) => s.name)
    expect(names).toContain("Planner")
    expect(names).toContain("Execution")
    expect(names).toContain("Docker")
    expect(names).toContain("Kubernetes")
    expect(names).toContain("Rollback")
  })

  it("simulates Planner agent actions", () => {
    const planActions = def.services.find((s) => s.name === "Planner")?.actions ?? []
    expect(planActions).toContain("Create release plan")
    expect(planActions).toContain("Define canary strategy")
    expect(planActions).toContain("Set success criteria")
  })

  it("simulates Execution agent actions", () => {
    const execActions = def.services.find((s) => s.name === "Execution")?.actions ?? []
    expect(execActions).toContain("Build release artifacts")
    expect(execActions).toContain("Run migration tasks")
    expect(execActions).toContain("Coordinate deployment")
  })

  it("simulates Docker build workflow", () => {
    const dockerActions = def.services.find((s) => s.name === "Docker")?.actions ?? []
    expect(dockerActions).toContain("Build production images")
    expect(dockerActions).toContain("Tag with version")
    expect(dockerActions).toContain("Push to registry")
  })

  it("simulates Kubernetes canary deployment", () => {
    const k8sActions = def.services.find((s) => s.name === "Kubernetes")?.actions ?? []
    expect(k8sActions).toContain("Apply canary deployment")
    expect(k8sActions).toContain("Monitor canary health")
    expect(k8sActions).toContain("Scale to full rollout")
  })

  it("simulates Rollback capability", () => {
    const rollbackActions = def.services.find((s) => s.name === "Rollback")?.actions ?? []
    expect(rollbackActions).toContain("Define rollback triggers")
    expect(rollbackActions).toContain("Execute rollback on failure")
    expect(rollbackActions).toContain("Verify pre-release state")
  })

  it("passes all validation checkpoints", () => {
    const sim = simulateMission()
    const services: ScenarioService[] = def.services.map((s) => ({
      ...s,
      durationMs: Math.floor(Math.random() * 800) + 300,
      status: "pass",
    }))
    const checkpoints = runScenarioCheckpoints("release-management", sim)
    expect(checkpoints.length).toBeGreaterThan(0)

    const result = buildScenarioResult("release-management", checkpoints, services)
    expect(result.failCount).toBe(0)
    expect(result.score).toBe(100)
    expect(result.overallStatus).toBe("pass")
  })
})
