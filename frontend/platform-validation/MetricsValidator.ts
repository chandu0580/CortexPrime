import type { MetricsValidation } from "./types"

export const MetricsValidator = {
  async validateMetricsCollection(metricsCount: number, expected: number): Promise<{ valid: boolean; errors: string[] }> {
    const errors: string[] = []
    if (metricsCount < expected) errors.push(`expected at least ${expected} metrics, collected ${metricsCount}`)
    return { valid: errors.length === 0, errors }
  },

  async validateCoverage(activeModules: number, totalModules: number, threshold: number = 80): Promise<{ valid: boolean; errors: string[] }> {
    const errors: string[] = []
    const coverage = totalModules > 0 ? Math.round((activeModules / totalModules) * 100) : 0
    if (coverage < threshold) errors.push(`coverage ${coverage}% is below threshold ${threshold}%`)
    return { valid: errors.length === 0, errors }
  },

  async validateStartupDuration(durationMs: number, maxMs: number = 30000): Promise<{ valid: boolean; errors: string[] }> {
    const errors: string[] = []
    if (durationMs > maxMs) errors.push(`startup duration ${durationMs}ms exceeds max ${maxMs}ms`)
    return { valid: errors.length === 0, errors }
  },

  async validateShutdownDuration(durationMs: number, maxMs: number = 15000): Promise<{ valid: boolean; errors: string[] }> {
    const errors: string[] = []
    if (durationMs > maxMs) errors.push(`shutdown duration ${durationMs}ms exceeds max ${maxMs}ms`)
    return { valid: errors.length === 0, errors }
  },

  async validateAll(
    metricsCount: number,
    expectedMetrics: number,
    activeModules: number,
    totalModules: number,
    startupDurationMs: number,
    shutdownDurationMs: number,
  ): Promise<MetricsValidation> {
    const errors: string[] = []

    const mc = await this.validateMetricsCollection(metricsCount, expectedMetrics)
    if (!mc.valid) errors.push(...mc.errors)

    const cv = await this.validateCoverage(activeModules, totalModules)
    if (!cv.valid) errors.push(...cv.errors)

    const sd = await this.validateStartupDuration(startupDurationMs)
    if (!sd.valid) errors.push(...sd.errors)

    const shd = await this.validateShutdownDuration(shutdownDurationMs)
    if (!shd.valid) errors.push(...shd.errors)

    return {
      metricsCollected: mc.valid,
      coverageValid: cv.valid,
      startupDurationValid: sd.valid,
      shutdownDurationValid: shd.valid,
      valid: errors.length === 0,
      errors,
    }
  },
}