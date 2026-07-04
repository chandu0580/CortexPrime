import type { ValidationResult, AggregatedMetric, KPI, TrendAnalysis, ExecutiveReport, ForecastDataset } from "./types"
import { generateId } from "./shared"

const validations = new Map<string, ValidationResult>()

export const AnalyticsValidationEngine = {
  async validateAggregationCompleteness(aggregations: AggregatedMetric[]): Promise<ValidationResult> {
    const errors: string[] = []
    const warnings: string[] = []

    for (const agg of aggregations) {
      if (!agg.id) errors.push("Aggregation missing id")
      if (!agg.name) errors.push("Aggregation missing name")
      if (agg.count === 0) warnings.push(`Aggregation "${agg.name}" has zero data points`)
      if (isNaN(agg.avg)) errors.push(`Aggregation "${agg.name}" has NaN average`)
    }

    if (aggregations.length === 0) warnings.push("No aggregations to validate")

    const result: ValidationResult = {
      id: generateId("aval"),
      type: "aggregation_completeness",
      passed: errors.length === 0,
      errors,
      warnings,
      details: { aggregationCount: aggregations.length },
    }
    validations.set(result.id, result)
    return result
  },

  async validateKPIConsistency(kpis: KPI[]): Promise<ValidationResult> {
    const errors: string[] = []
    const warnings: string[] = []

    for (const kpi of kpis) {
      if (!kpi.id) errors.push("KPI missing id")
      if (!kpi.name) errors.push("KPI missing name")
      if (isNaN(kpi.value)) errors.push(`KPI "${kpi.name}" has NaN value`)
      if (kpi.target === 0) warnings.push(`KPI "${kpi.name}" has target of 0`)
    }

    if (kpis.length === 0) warnings.push("No KPIs to validate")

    const result: ValidationResult = {
      id: generateId("aval"),
      type: "kpi_consistency",
      passed: errors.length === 0,
      errors,
      warnings,
      details: { kpiCount: kpis.length },
    }
    validations.set(result.id, result)
    return result
  },

  async validateTrendIntegrity(trends: TrendAnalysis[]): Promise<ValidationResult> {
    const errors: string[] = []
    const warnings: string[] = []

    for (const trend of trends) {
      if (!trend.id) errors.push("Trend analysis missing id")
      if (!trend.metricName) errors.push("Trend analysis missing metric name")
      if (trend.points.length < 2) warnings.push(`Trend "${trend.metricName}" has fewer than 2 data points`)
      if (trend.confidence < 0 || trend.confidence > 1) errors.push(`Trend "${trend.metricName}" has invalid confidence: ${trend.confidence}`)
    }

    if (trends.length === 0) warnings.push("No trends to validate")

    const result: ValidationResult = {
      id: generateId("aval"),
      type: "trend_integrity",
      passed: errors.length === 0,
      errors,
      warnings,
      details: { trendCount: trends.length },
    }
    validations.set(result.id, result)
    return result
  },

  async validateReportCompleteness(report: ExecutiveReport): Promise<ValidationResult> {
    const errors: string[] = []
    const warnings: string[] = []

    if (!report.id) errors.push("Report missing id")
    if (!report.title) errors.push("Report missing title")
    if (!report.period) errors.push("Report missing period")
    if (report.sections.length === 0) warnings.push("Report has no sections")

    for (const section of report.sections) {
      if (!section.title) errors.push("Section missing title")
    }

    const result: ValidationResult = {
      id: generateId("aval"),
      type: "report_completeness",
      passed: errors.length === 0,
      errors,
      warnings,
      details: { reportId: report.id, sectionCount: report.sections.length },
    }
    validations.set(result.id, result)
    return result
  },

  async validateForecastReadiness(dataset: ForecastDataset): Promise<ValidationResult> {
    const errors: string[] = []
    const warnings: string[] = []

    if (!dataset.id) errors.push("Dataset missing id")
    if (!dataset.name) errors.push("Dataset missing name")
    if (!dataset.metricName) errors.push("Dataset missing metric name")
    if (dataset.timeSeries.length === 0) errors.push("Dataset has no time series data")
    if (dataset.timeSeries.length < 3) warnings.push("Dataset has fewer than 3 data points, forecasts may be unreliable")

    const result: ValidationResult = {
      id: generateId("aval"),
      type: "forecast_readiness",
      passed: errors.length === 0,
      errors,
      warnings,
      details: { datasetId: dataset.id, dataPointCount: dataset.timeSeries.length },
    }
    validations.set(result.id, result)
    return result
  },

  async getValidations(type?: string): Promise<ValidationResult[]> {
    let result = Array.from(validations.values())
    if (type) result = result.filter((v) => v.type === type)
    return result
  },
}
