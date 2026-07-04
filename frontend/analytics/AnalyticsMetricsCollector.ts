import type { AnalyticsMetrics } from "./types"
import { AnalyticsSessionManager } from "./AnalyticsSessionManager"
import { MetricAggregationEngine } from "./MetricAggregationEngine"
import { KPIEngine } from "./KPIEngine"
import { ExecutiveReportingEngine } from "./ExecutiveReportingEngine"
import { TrendAnalysisEngine } from "./TrendAnalysisEngine"
import { OperationalInsightsEngine } from "./OperationalInsightsEngine"
import { ForecastPreparationEngine } from "./ForecastPreparationEngine"

export const AnalyticsMetricsCollector = {
  async collectAll(): Promise<AnalyticsMetrics> {
    const sessions = await AnalyticsSessionManager.listSessions()
    const aggregations = await MetricAggregationEngine.getAggregationCount()
    const kpis = await KPIEngine.kpiCount()
    const reports = await ExecutiveReportingEngine.reportCount()
    const trends = await TrendAnalysisEngine.getAllTrends()
    const insights = await OperationalInsightsEngine.insightCount()
    const datasets = await ForecastPreparationEngine.datasetCount()

    return {
      totalSessions: sessions.length,
      activeSessions: sessions.filter((s) => s.state === "active").length,
      totalAggregations: aggregations,
      totalKPIs: kpis,
      totalReports: reports,
      totalTrends: trends.length,
      totalInsights: insights,
      totalDatasets: datasets,
    }
  },

  async collectSessions(): Promise<{ total: number; active: number }> {
    const sessions = await AnalyticsSessionManager.listSessions()
    return { total: sessions.length, active: sessions.filter((s) => s.state === "active").length }
  },

  async collectAggregations(): Promise<number> {
    return MetricAggregationEngine.getAggregationCount()
  },

  async collectKPIs(): Promise<number> {
    return KPIEngine.kpiCount()
  },

  async collectReports(): Promise<number> {
    return ExecutiveReportingEngine.reportCount()
  },

  async collectTrends(): Promise<number> {
    const trends = await TrendAnalysisEngine.getAllTrends()
    return trends.length
  },

  async collectDatasets(): Promise<number> {
    return ForecastPreparationEngine.datasetCount()
  },
}
