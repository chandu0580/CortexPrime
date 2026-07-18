import axios from "axios"
import { apiUrl } from "@/lib/constants"

export interface MetricItem {
  id: string
  metric_type: string
  name: string
  value: number
  labels: Record<string, string>
  source: string
  unit: string
  timestamp: string
}

export interface MetricSummary {
  count: number
  sum: number
  avg: number
  min: number
  max: number
  latest: number
}

export interface TrendItem {
  metric_name: string
  metric_type: string
  direction: string
  change_pct: number
  avg_first: number
  avg_second: number
  window: number
  detected_at: string
}

export interface AnalyticsReport {
  id: string
  title: string
  type: string
  time_range: string
  metric_types: string[]
  sections: Record<string, unknown>
  generated_at: string
  metrics_count: number
}

export interface AnalyticsDashboard {
  total_metrics: number
  metrics_by_type: Record<string, number>
  total_reports: number
  recent_trends: TrendItem[]
  latest_metrics: MetricItem[]
}

export const enterpriseAnalyticsApi = {
  getDashboard: async (): Promise<AnalyticsDashboard> => {
    const res = await axios.get(`${apiUrl}/api/analytics/dashboard`)
    return res.data
  },

  recordMetric: async (payload: {
    metric_type: string
    name: string
    value: number
    labels?: Record<string, string>
    source?: string
    unit?: string
  }): Promise<MetricItem> => {
    const res = await axios.post(`${apiUrl}/api/analytics/metrics`, payload)
    return res.data
  },

  getMetrics: async (params?: {
    metric_type?: string
    name?: string
    from_time?: string
    to_time?: string
    limit?: number
  }): Promise<{ metrics: MetricItem[] }> => {
    const searchParams = new URLSearchParams()
    if (params?.metric_type) searchParams.set("metric_type", params.metric_type)
    if (params?.name) searchParams.set("name", params.name)
    if (params?.from_time) searchParams.set("from_time", params.from_time)
    if (params?.to_time) searchParams.set("to_time", params.to_time)
    if (params?.limit) searchParams.set("limit", String(params.limit))
    const res = await axios.get(`${apiUrl}/api/analytics/metrics?${searchParams}`)
    return res.data
  },

  getMetricSummary: async (metric_type?: string): Promise<Record<string, MetricSummary>> => {
    const params = metric_type ? `?metric_type=${metric_type}` : ""
    const res = await axios.get(`${apiUrl}/api/analytics/metrics/summary${params}`)
    return res.data
  },

  detectTrends: async (metric_type?: string, window?: number): Promise<{ trends: TrendItem[] }> => {
    const params = new URLSearchParams()
    if (metric_type) params.set("metric_type", metric_type)
    if (window) params.set("window", String(window))
    const res = await axios.get(`${apiUrl}/api/analytics/trends?${params}`)
    return res.data
  },

  generateReport: async (payload: {
    title: string
    report_type?: string
    metric_types?: string[]
    include_trends?: boolean
    time_range?: string
  }): Promise<AnalyticsReport> => {
    const res = await axios.post(`${apiUrl}/api/analytics/reports`, payload)
    return res.data
  },

  listReports: async (report_type?: string, limit?: number): Promise<{ reports: AnalyticsReport[] }> => {
    const params = new URLSearchParams()
    if (report_type) params.set("report_type", report_type)
    if (limit) params.set("limit", String(limit))
    const res = await axios.get(`${apiUrl}/api/analytics/reports?${params}`)
    return res.data
  },

  getReport: async (id: string): Promise<AnalyticsReport> => {
    const res = await axios.get(`${apiUrl}/api/analytics/reports/${id}`)
    return res.data
  },
}
