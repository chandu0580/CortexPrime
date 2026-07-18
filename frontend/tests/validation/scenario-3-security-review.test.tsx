import { describe, it, expect } from "vitest"
import { getScenarioDefinition } from "@/lib/validation/scenarios"
import { simulateMission, runScenarioCheckpoints, buildScenarioResult } from "@/lib/validation/mission-simulator"
import type { ScenarioService } from "@/lib/validation/types"

describe("Scenario 3: Security Review", () => {
  const def = getScenarioDefinition("security-review")
  if (!def) throw new Error("Scenario definition not found")

  it("has a valid security-focused goal", () => {
    expect(def.goal.toLowerCase()).toContain("security")
    expect(def.services.length).toBe(4)
    expect(def.checkpointDefinitions.length).toBeGreaterThan(0)
  })

  it("covers all security services", () => {
    const names = def.services.map((s) => s.name)
    expect(names).toContain("Security Agent")
    expect(names).toContain("Compliance Agent")
    expect(names).toContain("Knowledge")
    expect(names).toContain("Governance")
  })

  it("simulates Security Agent scanning", () => {
    const secActions = def.services.find((s) => s.name === "Security Agent")?.actions ?? []
    expect(secActions).toContain("Scan active deployments")
    expect(secActions).toContain("Check dependency CVEs")
    expect(secActions).toContain("Generate security report")
  })

  it("simulates Compliance Agent checks", () => {
    const compActions = def.services.find((s) => s.name === "Compliance Agent")?.actions ?? []
    expect(compActions).toContain("Run compliance checks")
    expect(compActions).toContain("Check policy adherence")
    expect(compActions).toContain("Flag violations")
  })

  it("simulates Knowledge base indexing", () => {
    const knowActions = def.services.find((s) => s.name === "Knowledge")?.actions ?? []
    expect(knowActions).toContain("Store scan results")
    expect(knowActions).toContain("Index findings")
    expect(knowActions).toContain("Link to prior reviews")
  })

  it("simulates Governance policy evaluation", () => {
    const govActions = def.services.find((s) => s.name === "Governance")?.actions ?? []
    expect(govActions).toContain("Evaluate policies")
    expect(govActions).toContain("Record audit trail")
    expect(govActions).toContain("Generate compliance score")
  })

  it("passes all validation checkpoints", () => {
    const sim = simulateMission()
    const services: ScenarioService[] = def.services.map((s) => ({
      ...s,
      durationMs: Math.floor(Math.random() * 600) + 200,
      status: "pass",
    }))
    const checkpoints = runScenarioCheckpoints("security-review", sim)
    expect(checkpoints.length).toBeGreaterThan(0)

    const result = buildScenarioResult("security-review", checkpoints, services)
    expect(result.failCount).toBe(0)
    expect(result.score).toBe(100)
    expect(result.overallStatus).toBe("pass")
  })
})
