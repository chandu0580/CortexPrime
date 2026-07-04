import type { AnalyticsSession, AnalyticsMetric, AggregatedMetric, TrendAnalysis, TrendPoint, KPI, KPIThreshold, ExecutiveReport, OperationalInsight, ForecastDataset, AnalyticsPolicy, AnalyticsDecision, AnalyticsMetrics, AnalyticsHealth, AnalyticsCapabilityDefinition, ValidationResult, HealthSnapshot } from "./types"
import type { AnalyticsState, TrendDirection, KPIStatus, ForecastState, AnalyticsResult } from "./types"
import { AnalyticsSessionManager } from "./AnalyticsSessionManager"
import { MetricAggregationEngine } from "./MetricAggregationEngine"
import { TrendAnalysisEngine } from "./TrendAnalysisEngine"
import { KPIEngine } from "./KPIEngine"
import { ExecutiveReportingEngine } from "./ExecutiveReportingEngine"
import { ForecastPreparationEngine } from "./ForecastPreparationEngine"
import { OperationalInsightsEngine } from "./OperationalInsightsEngine"
import { AnalyticsPolicyEngine } from "./AnalyticsPolicyEngine"
import { AnalyticsValidationEngine } from "./AnalyticsValidationEngine"
import { AnalyticsMetricsCollector } from "./AnalyticsMetricsCollector"
import { AnalyticsHealthManager } from "./AnalyticsHealthManager"
import { AnalyticsCapability } from "./AnalyticsCapability"
import { cortexEventBus } from "@/event-bus/cortexEventBus"

export const AnalyticsEngine = {
  async aggregate(metrics: AnalyticsMetric[], mode: "all" | "category" | "worker" | "mission" = "all"): Promise<AggregatedMetric[]> {
    let results: AggregatedMetric[] = []

    switch (mode) {
      case "all":
        results = await MetricAggregationEngine.aggregateMetrics(metrics)
        break
      case "category":
        results = await MetricAggregationEngine.aggregateByCategory(metrics)
        break
      case "worker":
        results = await MetricAggregationEngine.aggregateByWorker(metrics)
        break
      case "mission":
        results = await MetricAggregationEngine.aggregateByMission(metrics)
        break
    }

    await cortexEventBus.publish("analytics", "analytics", `analytics.aggregate.${mode}`, "AnalyticsEngine", {
      mode,
      inputCount: metrics.length,
      resultCount: results.length,
    }, "low", "analytics")

    return results
  },

  async trends(metricName: string, points: TrendPoint[]): Promise<TrendAnalysis> {
    const analysis = await TrendAnalysisEngine.analyzeTrend(metricName, points)

    await cortexEventBus.publish("analytics", "analytics", "analytics.trend.analyzed", "AnalyticsEngine", {
      metricName,
      direction: analysis.direction,
      changePercent: analysis.changePercent,
      confidence: analysis.confidence,
    }, "low", "analytics")

    return analysis
  },

  async kpis(aggregations: AggregatedMetric[], thresholds: Map<string, KPIThreshold>): Promise<KPI[]> {
    const results = await KPIEngine.calculateKPIs(aggregations, thresholds)
    const summary = await KPIEngine.summarizeKPIs(results)

    await cortexEventBus.publish("analytics", "analytics", "analytics.kpi.calculated", "AnalyticsEngine", {
      kpiCount: results.length,
      healthScore: summary.healthScore,
      criticalCount: summary.critical,
    }, summary.critical > 0 ? "high" : "low", "analytics")

    return results
  },

  async reports(
    title: string,
    period: string,
    kpis: KPI[],
    aggregations: AggregatedMetric[],
    trends: TrendAnalysis[],
    insights: OperationalInsight[],
    metadata?: Record<string, unknown>,
  ): Promise<ExecutiveReport> {
    const report = await ExecutiveReportingEngine.generateReport(title, period, kpis, aggregations, trends, insights, metadata)

    await cortexEventBus.publish("analytics", "analytics", "analytics.report.generated", "AnalyticsEngine", {
      reportId: report.id,
      title,
      period,
      sections: report.sections.length,
    }, "low", "analytics")

    return report
  },

  async insights(aggregations: AggregatedMetric[], trends: TrendAnalysis[]): Promise<OperationalInsight[]> {
    const results = await OperationalInsightsEngine.generateInsights(aggregations, trends)
    const criticalCount = results.filter((i) => i.severity === "critical").length

    await cortexEventBus.publish("analytics", "analytics", "analytics.insights.generated", "AnalyticsEngine", {
      insightCount: results.length,
      criticalCount,
    }, criticalCount > 0 ? "high" : "low", "analytics")

    return results
  },

  async forecastData(name: string, metricName: string, points: TrendPoint[], parameters?: Record<string, unknown>): Promise<ForecastDataset> {
    const dataset = await ForecastPreparationEngine.prepareDataset(name, metricName, points, parameters)
    const validation = await ForecastPreparationEngine.validateForecastInput(dataset.id)

    if (validation.valid) {
      await ForecastPreparationEngine.markReady(dataset.id)
    } else {
      await ForecastPreparationEngine.markFailed(dataset.id)
    }

    await cortexEventBus.publish("analytics", "analytics", "analytics.forecast.dataset_prepared", "AnalyticsEngine", {
      datasetId: dataset.id,
      metricName,
      dataPoints: points.length,
      valid: validation.valid,
    }, validation.valid ? "low" : "high", "analytics")

    return dataset
  },

  async validate(type: string, data: Record<string, unknown>): Promise<ValidationResult> {
    let result: ValidationResult

    switch (type) {
      case "aggregation_completeness": {
        const aggs = data as unknown as AggregatedMetric[]
        result = await AnalyticsValidationEngine.validateAggregationCompleteness(aggs)
        break
      }
      case "kpi_consistency": {
        const kpiList = data as unknown as KPI[]
        result = await AnalyticsValidationEngine.validateKPIConsistency(kpiList)
        break
      }
      case "trend_integrity": {
        const trendList = data as unknown as TrendAnalysis[]
        result = await AnalyticsValidationEngine.validateTrendIntegrity(trendList)
        break
      }
      case "report_completeness": {
        const report = data as unknown as ExecutiveReport
        result = await AnalyticsValidationEngine.validateReportCompleteness(report)
        break
      }
      case "forecast_readiness": {
        const dataset = data as unknown as ForecastDataset
        result = await AnalyticsValidationEngine.validateForecastReadiness(dataset)
        break
      }
      default:
        throw new Error(`Unknown validation type: ${type}`)
    }

    await cortexEventBus.publish("analytics", "analytics", `analytics.validate.${type}`, "AnalyticsEngine", {
      validationId: result.id,
      passed: result.passed,
      errors: result.errors.length,
    }, result.passed ? "low" : "high", "analytics")

    return result
  },

  async metrics(): Promise<AnalyticsMetrics> {
    return AnalyticsMetricsCollector.collectAll()
  },

  async health(): Promise<AnalyticsHealth> {
    return AnalyticsHealthManager.getHealth()
  },

  async createSession(name: string, metricIds?: string[], metadata?: Record<string, unknown>): Promise<AnalyticsSession> {
    const session = await AnalyticsSessionManager.createSession(name, metricIds, metadata)

    await cortexEventBus.publish("analytics", "analytics", "analytics.session.created", "AnalyticsEngine", {
      sessionId: session.id,
      name,
    }, "low", session.id)

    return session
  },

  async closeSession(sessionId: string): Promise<AnalyticsSession> {
    const session = await AnalyticsSessionManager.closeSession(sessionId)

    await cortexEventBus.publish("analytics", "analytics", "analytics.session.closed", "AnalyticsEngine", {
      sessionId,
    }, "low", sessionId)

    return session
  },

  async detectTrendChanges(metricName: string, points: TrendPoint[], windowSize?: number): Promise<TrendAnalysis[]> {
    return TrendAnalysisEngine.detectTrendChanges(metricName, points, windowSize)
  },

  async compareWindows(metricName: string, current: TrendPoint[], previous: TrendPoint[]): Promise<TrendAnalysis> {
    return TrendAnalysisEngine.compareTimeWindows(metricName, current, previous)
  },

  async getCapabilities(): Promise<AnalyticsCapabilityDefinition[]> {
    return AnalyticsCapability.list()
  },

  async isCapabilityEnabled(name: string): Promise<boolean> {
    return AnalyticsCapability.isEnabled(name)
  },

  async snapshot(component: string, metrics: Record<string, number>, details?: string): Promise<HealthSnapshot> {
    return AnalyticsHealthManager.snapshot(component, metrics, details)
  },

  async buildTimeSeries(metricName: string, values: { timestamp: string; value: number }[]): Promise<TrendPoint[]> {
    return ForecastPreparationEngine.buildTimeSeries(metricName, values)
  },
}
