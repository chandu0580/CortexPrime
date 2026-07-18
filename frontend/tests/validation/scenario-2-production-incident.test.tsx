import { describe, it, expect } from "vitest"
import { getScenarioDefinition } from "@/lib/validation/scenarios"
import { simulateMission, runScenarioCheckpoints, buildScenarioResult } from "@/lib/validation/mission-simulator"
import type { ScenarioService } from "@/lib/validation/types"

describe("Scenario 2: Production Incident Response", () => {
  const def = getScenarioDefinition("production-incident")
  if (!def) throw new Error("Scenario definition not found")

  it("has a valid goal targeting incident response", () => {
    expect(def.goal.toLowerCase()).toContain("incident")
    expect(def.services.length).toBe(5)
    expect(def.checkpointDefinitions.length).toBeGreaterThan(0)
  })

  it("covers all 5 incident response services", () => {
    const names = def.services.map((s) => s.name)
    expect(names).toContain("Prometheus")
    expect(names).toContain("Grafana")
    expect(names).toContain("GitHub")
    expect(names).toContain("Jira")
    expect(names).toContain("Slack")
  })

  it("simulates Prometheus alert flow", () => {
    const promActions = def.services.find((s) => s.name === "Prometheus")?.actions ?? []
    expect(promActions).toContain("Alert triggered: HighCPUUsage")
    expect(promActions).toContain("Alert severity evaluation")
  })

  it("simulates Grafana dashboard visualization", () => {
    const grafanaActions = def.services.find((s) => s.name === "Grafana")?.actions ?? []
    expect(grafanaActions).toContain("Open relevant dashboard")
    expect(grafanaActions).toContain("Visualize CPU metrics")
  })

  it("simulates GitHub issue creation", () => {
    const ghActions = def.services.find((s) => s.name === "GitHub")?.actions ?? []
    expect(ghActions).toContain("Create incident issue")
    expect(ghActions).toContain("Assign incident commander")
  })

  it("simulates Jira ticket tracking", () => {
    const jiraActions = def.services.find((s) => s.name === "Jira")?.actions ?? []
    expect(jiraActions).toContain("Create incident ticket")
    expect(jiraActions).toContain("Set priority as Critical")
  })

  it("simulates Slack notification flow", () => {
    const slackActions = def.services.find((s) => s.name === "Slack")?.actions ?? []
    expect(slackActions).toContain("Post alert to #ops channel")
    expect(slackActions).toContain("Notify on-call engineer")
  })

  it("passes all validation checkpoints", () => {
    const sim = simulateMission()
    const services: ScenarioService[] = def.services.map((s) => ({
      ...s,
      durationMs: Math.floor(Math.random() * 400) + 80,
      status: "pass",
    }))
    const checkpoints = runScenarioCheckpoints("production-incident", sim)
    expect(checkpoints.length).toBeGreaterThan(0)

    const result = buildScenarioResult("production-incident", checkpoints, services)
    expect(result.failCount).toBe(0)
    expect(result.score).toBe(100)
    expect(result.overallStatus).toBe("pass")
  })
})
