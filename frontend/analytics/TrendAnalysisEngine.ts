import type { TrendAnalysis, TrendPoint, TrendDirection, AnalyticsMetric } from "./types"
import { generateId } from "./shared"

const trends = new Map<string, TrendAnalysis>()

export const TrendAnalysisEngine = {
  async analyzeTrend(metricName: string, points: TrendPoint[]): Promise<TrendAnalysis> {
    const values = points.map((p) => p.value)
    const direction = TrendAnalysisEngine.determineDirection(values)
    const changePercent = TrendAnalysisEngine.calculateChangePercent(values)

    const analysis: TrendAnalysis = {
      id: generateId("trend"),
      metricName,
      direction,
      changePercent,
      points,
      period: points.length > 0 ? `${points[0].label} - ${points[points.length - 1].label}` : "empty",
      confidence: values.length >= 3 ? 0.8 : 0.4,
      generatedAt: new Date().toISOString(),
    }
    trends.set(analysis.id, analysis)
    return analysis
  },

  determineDirection(values: number[]): TrendDirection {
    if (values.length < 2) return "flat"
    const first = values[0]
    const last = values[values.length - 1]
    const change = ((last - first) / first) * 100
    if (change > 5) return "up"
    if (change < -5) return "down"
    const variance = values.reduce((sum, v) => sum + Math.abs(v - values.reduce((a, b) => a + b, 0) / values.length), 0) / values.length
    if (variance / (values.reduce((a, b) => a + b, 0) / values.length) > 0.1) return "volatile"
    return "flat"
  },

  calculateChangePercent(values: number[]): number {
    if (values.length < 2) return 0
    const first = values[0]
    const last = values[values.length - 1]
    if (first === 0) return last === 0 ? 0 : 100
    return ((last - first) / first) * 100
  },

  async detectTrendChanges(metricName: string, points: TrendPoint[], windowSize: number = 3): Promise<TrendAnalysis[]> {
    const changes: TrendAnalysis[] = []
    if (points.length < windowSize * 2) return changes

    for (let i = 0; i <= points.length - windowSize * 2; i++) {
      const window1 = points.slice(i, i + windowSize)
      const window2 = points.slice(i + windowSize, i + windowSize * 2)
      const avg1 = window1.reduce((s, p) => s + p.value, 0) / window1.length
      const avg2 = window2.reduce((s, p) => s + p.value, 0) / window2.length
      const changePercent = avg1 === 0 ? (avg2 === 0 ? 0 : 100) : ((avg2 - avg1) / avg1) * 100

      if (Math.abs(changePercent) > 10) {
        changes.push({
          id: generateId("trend"),
          metricName,
          direction: changePercent > 0 ? "up" : "down",
          changePercent,
          points: window2,
          period: `${window2[0].label} - ${window2[window2.length - 1].label}`,
          confidence: 0.7,
          generatedAt: new Date().toISOString(),
        })
      }
    }
    return changes
  },

  async compareTimeWindows(metricName: string, current: TrendPoint[], previous: TrendPoint[]): Promise<TrendAnalysis> {
    const currentAvg = current.reduce((s, p) => s + p.value, 0) / current.length
    const previousAvg = previous.reduce((s, p) => s + p.value, 0) / previous.length
    const changePercent = previousAvg === 0 ? (currentAvg === 0 ? 0 : 100) : ((currentAvg - previousAvg) / previousAvg) * 100

    const analysis: TrendAnalysis = {
      id: generateId("trend"),
      metricName,
      direction: changePercent > 5 ? "up" : changePercent < -5 ? "down" : "flat",
      changePercent,
      points: current,
      period: "window_comparison",
      confidence: 0.7,
      generatedAt: new Date().toISOString(),
    }
    trends.set(analysis.id, analysis)
    return analysis
  },

  async summarizeTrend(metricName: string, points: TrendPoint[]): Promise<string> {
    if (points.length === 0) return `No data available for "${metricName}"`
    const analysis = await TrendAnalysisEngine.analyzeTrend(metricName, points)
    return `Trend for "${metricName}": ${analysis.direction} (${analysis.changePercent.toFixed(1)}%) over ${points.length} data points with ${(analysis.confidence * 100).toFixed(0)}% confidence`
  },

  async getTrend(id: string): Promise<TrendAnalysis | null> {
    return trends.get(id) ?? null
  },

  async getAllTrends(): Promise<TrendAnalysis[]> {
    return Array.from(trends.values())
  },
}
