import type { ExecutiveReport, ExecutiveSection, KPI, AggregatedMetric, TrendAnalysis, OperationalInsight } from "./types"
import { generateId } from "./shared"

const reports = new Map<string, ExecutiveReport>()

export const ExecutiveReportingEngine = {
  async generateReport(
    title: string,
    period: string,
    kpis: KPI[],
    aggregations: AggregatedMetric[],
    trends: TrendAnalysis[],
    insights: OperationalInsight[],
    metadata: Record<string, unknown> = {},
  ): Promise<ExecutiveReport> {
    const sections: ExecutiveSection[] = [
      {
        id: generateId("sec"),
        title: "KPI Overview",
        type: "kpi_summary",
        content: { kpis: kpis.map((k) => ({ name: k.name, value: k.value, status: k.status, target: k.target })) },
        metrics: { totalKPIs: kpis.length, criticalKPIs: kpis.filter((k) => k.status === "critical").length },
      },
      {
        id: generateId("sec"),
        title: "Metric Aggregations",
        type: "aggregation_summary",
        content: { aggregations: aggregations.map((a) => ({ name: a.name, avg: a.avg, min: a.min, max: a.max, count: a.count })) },
        metrics: { totalAggregations: aggregations.length },
      },
      {
        id: generateId("sec"),
        title: "Trend Analysis",
        type: "trend_summary",
        content: { trends: trends.map((t) => ({ metric: t.metricName, direction: t.direction, changePercent: t.changePercent, confidence: t.confidence })) },
        metrics: { totalTrends: trends.length },
      },
      {
        id: generateId("sec"),
        title: "Operational Insights",
        type: "insight_summary",
        content: { insights: insights.map((i) => ({ type: i.type, severity: i.severity, message: i.message })) },
        metrics: { totalInsights: insights.length, criticalInsights: insights.filter((i) => i.severity === "critical").length },
      },
    ]

    const healthScore = kpis.length === 0 ? 0 : Math.round((kpis.filter((k) => k.status === "good").length / kpis.length) * 100)
    const summary = `Executive Report "${title}" for period ${period}: Health score ${healthScore}%, ${kpis.length} KPIs, ${aggregations.length} aggregations, ${trends.length} trends, ${insights.length} insights`

    const report: ExecutiveReport = {
      id: generateId("report"),
      title,
      period,
      sections,
      generatedAt: new Date().toISOString(),
      summary,
      metadata,
    }
    reports.set(report.id, report)
    return report
  },

  async generateSummary(reportId: string): Promise<string> {
    const report = reports.get(reportId)
    if (!report) throw new Error(`Report not found: ${reportId}`)
    return report.summary
  },

  async buildSections(reportId: string): Promise<ExecutiveSection[]> {
    const report = reports.get(reportId)
    if (!report) throw new Error(`Report not found: ${reportId}`)
    return report.sections
  },

  async exportStructure(reportId: string): Promise<{ title: string; period: string; sections: { title: string; type: string }[] }> {
    const report = reports.get(reportId)
    if (!report) throw new Error(`Report not found: ${reportId}`)
    return {
      title: report.title,
      period: report.period,
      sections: report.sections.map((s) => ({ title: s.title, type: s.type })),
    }
  },

  async getReport(id: string): Promise<ExecutiveReport | null> {
    return reports.get(id) ?? null
  },

  async listReports(): Promise<ExecutiveReport[]> {
    return Array.from(reports.values()).sort((a, b) => new Date(b.generatedAt).getTime() - new Date(a.generatedAt).getTime())
  },

  async reportCount(): Promise<number> {
    return reports.size
  },
}
