import type { OperationalInsight, AggregatedMetric, TrendAnalysis } from "./types"
import { generateId } from "./shared"

const insights = new Map<string, OperationalInsight>()

export const OperationalInsightsEngine = {
  async generateInsights(aggregations: AggregatedMetric[], trends: TrendAnalysis[]): Promise<OperationalInsight[]> {
    const results: OperationalInsight[] = []

    const anomalyResults = await OperationalInsightsEngine.detectAnomalies(aggregations)
    results.push(...anomalyResults)

    const issueResults = await OperationalInsightsEngine.identifyTopIssues(aggregations, trends)
    results.push(...issueResults)

    const summaryResults = await OperationalInsightsEngine.summarizeOperations(aggregations, trends)
    results.push(...summaryResults)

    for (const insight of results) {
      insights.set(insight.id, insight)
    }

    return results
  },

  async detectAnomalies(aggregations: AggregatedMetric[]): Promise<OperationalInsight[]> {
    const results: OperationalInsight[] = []

    for (const agg of aggregations) {
      if (agg.count === 0) continue
      const variance = agg.max - agg.min
      const rangeRatio = agg.avg === 0 ? variance : variance / agg.avg

      if (rangeRatio > 2) {
        results.push({
          id: generateId("insight"),
          type: "anomaly",
          severity: "warning",
          message: `High variance detected in "${agg.name}": range ${variance.toFixed(2)} (${(rangeRatio * 100).toFixed(0)}% of average)`,
          detail: `Min: ${agg.min}, Max: ${agg.max}, Avg: ${agg.avg.toFixed(2)}`,
          metricName: agg.name,
          timestamp: new Date().toISOString(),
          source: "OperationalInsightsEngine",
        })
      }

      if (agg.avg < 0) {
        results.push({
          id: generateId("insight"),
          type: "anomaly",
          severity: "critical",
          message: `Negative average value detected in "${agg.name}": ${agg.avg.toFixed(2)}`,
          detail: `All values in this aggregation are negative on average`,
          metricName: agg.name,
          timestamp: new Date().toISOString(),
          source: "OperationalInsightsEngine",
        })
      }
    }
    return results
  },

  async identifyTopIssues(aggregations: AggregatedMetric[], trends: TrendAnalysis[]): Promise<OperationalInsight[]> {
    const results: OperationalInsight[] = []

    const downwardTrends = trends.filter((t) => t.direction === "down" && Math.abs(t.changePercent) > 20)
    for (const trend of downwardTrends) {
      results.push({
        id: generateId("insight"),
        type: "trend_issue",
        severity: "warning",
        message: `Significant downward trend detected: "${trend.metricName}" dropped ${Math.abs(trend.changePercent).toFixed(1)}%`,
        detail: `Period: ${trend.period}, Confidence: ${(trend.confidence * 100).toFixed(0)}%`,
        metricName: trend.metricName,
        timestamp: new Date().toISOString(),
        source: "OperationalInsightsEngine",
      })
    }

    const highCountAggs = aggregations.filter((a) => a.count > 100)
    for (const agg of highCountAggs) {
      results.push({
        id: generateId("insight"),
        type: "scale_note",
        severity: "info",
        message: `High data volume for "${agg.name}": ${agg.count} data points`,
        detail: `Consider reviewing sampling rate`,
        metricName: agg.name,
        timestamp: new Date().toISOString(),
        source: "OperationalInsightsEngine",
      })
    }

    return results
  },

  async summarizeOperations(aggregations: AggregatedMetric[], trends: TrendAnalysis[]): Promise<OperationalInsight[]> {
    const results: OperationalInsight[] = []

    const upTrends = trends.filter((t) => t.direction === "up")
    const downTrends = trends.filter((t) => t.direction === "down")
    const flatTrends = trends.filter((t) => t.direction === "flat")

    results.push({
      id: generateId("insight"),
      type: "summary",
      severity: "info",
      message: `Operations summary: ${upTrends.length} metrics trending up, ${downTrends.length} trending down, ${flatTrends.length} stable`,
      detail: `Based on ${trends.length} trend analyses across ${aggregations.length} aggregated metrics`,
      metricName: "operations",
      timestamp: new Date().toISOString(),
      source: "OperationalInsightsEngine",
    })

    return results
  },

  async getInsight(id: string): Promise<OperationalInsight | null> {
    return insights.get(id) ?? null
  },

  async getAllInsights(): Promise<OperationalInsight[]> {
    return Array.from(insights.values())
  },

  async insightCount(): Promise<number> {
    return insights.size
  },
}
