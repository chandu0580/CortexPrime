import { type ValidationSession, ValidationState, type ValidationReport, type ValidationMetrics, type ValidationHealth } from "./types"
import { PlatformSmokeTest } from "./PlatformSmokeTest"
import { StartupValidator } from "./StartupValidator"
import { ShutdownValidator } from "./ShutdownValidator"
import { DependencyValidator } from "./DependencyValidator"
import { LifecycleValidator } from "./LifecycleValidator"
import { RegistrationValidator } from "./RegistrationValidator"
import { RuntimeValidator } from "./RuntimeValidator"
import { HealthValidator } from "./HealthValidator"
import { MetricsValidator } from "./MetricsValidator"
import { ValidationReportBuilder } from "./ValidationReportBuilder"
import { generateId } from "./shared"
import { cortexEventBus } from "@/event-bus/cortexEventBus"

const sessions = new Map<string, ValidationSession>()

export class PlatformValidation {
  private operationCount = 0

  smokeTest(): typeof PlatformSmokeTest { return PlatformSmokeTest }
  startupValidator(): typeof StartupValidator { return StartupValidator }
  shutdownValidator(): typeof ShutdownValidator { return ShutdownValidator }
  dependencyValidator(): typeof DependencyValidator { return DependencyValidator }
  lifecycleValidator(): typeof LifecycleValidator { return LifecycleValidator }
  registrationValidator(): typeof RegistrationValidator { return RegistrationValidator }
  runtimeValidator(): typeof RuntimeValidator { return RuntimeValidator }
  healthValidator(): typeof HealthValidator { return HealthValidator }
  metricsValidator(): typeof MetricsValidator { return MetricsValidator }

  async validate(): Promise<ValidationReport> {
    this.operationCount++
    const session: ValidationSession = {
      id: generateId("session"),
      state: ValidationState.RUNNING,
      startedAt: new Date().toISOString(),
      completedAt: null,
      summary: { total: 0, passed: 0, failed: 0, skipped: 0, warnings: 0, durationMs: 0 },
    }
    sessions.set(session.id, session)
    await this.publish("validation.started", { sessionId: session.id })

    const smokeTests = await PlatformSmokeTest.runAll()

    const depValidator = DependencyValidator
    const deps = { moduleId: "platform", dependsOn: [] as string[] }
    const dependency = await depValidator.validateAll([deps], [])

    const lcValidator = LifecycleValidator
    const lifecycle = await lcValidator.validateAll([])

    const rtValidator = RuntimeValidator
    const runtime = await rtValidator.validateAll(true, [], 20, true, true, true)

    const hValidator = HealthValidator
    const health = await hValidator.validateAll(true, true, true, 20, 20)

    const mValidator = MetricsValidator
    const metrics = await mValidator.validateAll(10, 5, 20, 20, 1000, 500)

    const report = await ValidationReportBuilder.build(smokeTests, dependency, lifecycle, runtime, health, metrics)

    session.state = ValidationState.COMPLETED
    session.completedAt = new Date().toISOString()
    session.summary = report.summary

    await this.publish("validation.completed", { sessionId: session.id, passed: report.summary.passed, failed: report.summary.failed, score: report.overallScore })
    return report
  }

  async smokeTestOnly(): Promise<ValidationReport["smokeTests"]> {
    this.operationCount++
    return PlatformSmokeTest.runAll()
  }

  async report(): Promise<ValidationReport | null> {
    const lastSession = Array.from(sessions.values()).pop()
    if (!lastSession) return null
    return {
      id: generateId("report"),
      sessionId: lastSession.id,
      summary: lastSession.summary,
      smokeTests: { total: 0, passed: 0, failed: 0, skipped: 0, durationMs: 0, tests: [] },
      dependency: { totalDependencies: 0, resolved: 0, unresolved: 0, cyclesFound: 0, valid: true, errors: [] },
      lifecycle: { moduleCount: 0, validTransitions: 0, invalidTransitions: 0, valid: true, errors: [] },
      runtime: { runtimeReady: false, compositionValid: false, startupSequenceValid: false, restartSupported: false, recoverySupported: false, valid: false, errors: [] },
      health: { platformHealthy: false, runtimeHealthy: false, dependencyHealthy: false, modulesHealthy: 0, totalModules: 0, valid: false, errors: [] },
      metrics: { metricsCollected: false, coverageValid: false, startupDurationValid: false, shutdownDurationValid: false, valid: false, errors: [] },
      issues: [],
      warnings: [],
      recommendations: [],
      overallScore: 0,
      platformReady: false,
      generatedAt: new Date().toISOString(),
    }
  }

  async getMetrics(): Promise<ValidationMetrics> {
    const allSessions = Array.from(sessions.values())
    const completed = allSessions.filter((s) => s.state === ValidationState.COMPLETED)
    const totalTests = completed.reduce((sum, s) => sum + s.summary.total, 0)
    const totalPassed = completed.reduce((sum, s) => sum + s.summary.passed, 0)
    const totalFailed = completed.reduce((sum, s) => sum + s.summary.failed, 0)
    const lastDuration = completed.length > 0 ? completed[completed.length - 1].summary.durationMs : 0
    const scores = completed.map((s) => s.summary.total > 0 ? Math.round((s.summary.passed / s.summary.total) * 100) : 0)
    const averageScore = scores.length > 0 ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length) : 0

    return {
      totalSessions: allSessions.length,
      totalTests,
      totalPassed,
      totalFailed,
      lastRunDurationMs: lastDuration,
      averageScore,
    }
  }

  async getHealth(): Promise<ValidationHealth> {
    const lastSession = Array.from(sessions.values()).pop()
    return {
      healthy: lastSession?.state === ValidationState.COMPLETED,
      lastSessionState: lastSession?.state ?? ValidationState.PENDING,
      lastError: lastSession?.state === ValidationState.FAILED ? "validation session failed" : null,
      totalIssues: 0,
    }
  }

  private async publish(event: string, data: Record<string, unknown>): Promise<void> {
    await cortexEventBus.publish("platform", "validation", `platform.validation.${event}`, "PlatformValidation", data)
  }
}
