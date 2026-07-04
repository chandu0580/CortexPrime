import { TestStatus, type ConnectorMetricResult } from "./types"

export const ConnectorMetricsValidator = {
  async validateMetricsRegistered(metrics: unknown[], expected: number): Promise<{ valid: boolean; count: number }> {
    return { valid: metrics.length >= expected, count: metrics.length }
  },

  async validateAggregation(metrics: { name: string; value: number }[]): Promise<boolean> {
    return metrics.length > 0 && metrics.every((m) => typeof m.value === "number")
  },

  async validate(
    metrics: { name: string; value: number }[],
    expectedCount: number,
  ): Promise<ConnectorMetricResult> {
    const errors: string[] = []
    const regResult = await this.validateMetricsRegistered(metrics, expectedCount)
    if (!regResult.valid) errors.push(`expected at least ${expectedCount} metrics, found ${regResult.count}`)

    const aggregationSupported = await this.validateAggregation(metrics)
    if (!aggregationSupported) errors.push("metric aggregation validation failed")

    const status: TestStatus = errors.length === 0 ? TestStatus.PASSED : TestStatus.FAILED
    return {
      metricsRegistered: regResult.valid,
      aggregationSupported,
      reportingSupported: regResult.valid,
      metricCount: regResult.count,
      status,
      errors,
    }
  },
}