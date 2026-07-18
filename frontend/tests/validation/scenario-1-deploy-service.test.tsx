import { describe, it, expect } from "vitest"
import { getScenarioDefinition } from "@/lib/validation/scenarios"
import { simulateMission, runScenarioCheckpoints, buildScenarioResult } from "@/lib/validation/mission-simulator"
import type { ScenarioService } from "@/lib/validation/types"

describe("Scenario 1: Deploy Service", () => {
  const def = getScenarioDefinition("deploy-service")
  if (!def) throw new Error("Scenario definition not found")

  it("has a valid goal and service definitions", () => {
    expect(def.goal).toBeTruthy()
    expect(def.services.length).toBeGreaterThan(0)
    expect(def.checkpointDefinitions.length).toBeGreaterThan(0)
  })

  it("simulates full mission lifecycle", () => {
    const sim = simulateMission()
    expect(sim.context.stage).toBe("completed")
    expect(sim.metrics.stagesCompleted).toBe(7)
    expect(sim.metrics.agentsActivated).toBeGreaterThanOrEqual(5)
    expect(sim.metrics.totalEvents).toBeGreaterThan(0)
  })

  it("simulates GitHub connector actions", () => {
    const sim = simulateMission()
    const ghActions = def.services.find((s) => s.name === "GitHub")?.actions ?? []
    expect(ghActions).toContain("Checkout source code")
    expect(ghActions).toContain("Trigger CI pipeline")
    expect(ghActions).toContain("Tag release v2.1.0")
  })

  it("simulates Docker connector actions", () => {
    const dockerActions = def.services.find((s) => s.name === "Docker")?.actions ?? []
    expect(dockerActions).toContain("Build container image")
    expect(dockerActions).toContain("Push to registry")
  })

  it("simulates Kubernetes connector actions", () => {
    const k8sActions = def.services.find((s) => s.name === "Kubernetes")?.actions ?? []
    expect(k8sActions).toContain("Apply deployment manifest")
    expect(k8sActions).toContain("Rollout status check")
  })

  it("passes all validation checkpoints", () => {
    const sim = simulateMission()
    const services: ScenarioService[] = def.services.map((s) => ({
      ...s,
      durationMs: Math.floor(Math.random() * 500) + 100,
      status: "pass",
    }))
    const checkpoints = runScenarioCheckpoints("deploy-service", sim)
    expect(checkpoints.length).toBeGreaterThan(0)

    const result = buildScenarioResult("deploy-service", checkpoints, services)
    expect(result.passCount).toBe(result.checkpoints.length)
    expect(result.failCount).toBe(0)
    expect(result.score).toBe(100)
    expect(result.overallStatus).toBe("pass")
  })
})
