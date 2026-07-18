import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import {
  enterpriseAnalyticsApi,
  MetricItem,
  TrendItem,
  AnalyticsReport,
} from "@/services/enterprise/analytics"

export function useAnalyticsDashboard() {
  return useQuery({
    queryKey: ["analytics-dashboard"],
    queryFn: () => enterpriseAnalyticsApi.getDashboard(),
    staleTime: 30_000,
  })
}

export function useMetrics(params?: {
  metric_type?: string
  name?: string
  from_time?: string
  to_time?: string
  limit?: number
}) {
  return useQuery({
    queryKey: ["metrics", params],
    queryFn: async () => {
      const res = await enterpriseAnalyticsApi.getMetrics(params)
      return res.metrics as MetricItem[]
    },
    staleTime: 30_000,
  })
}

export function useMetricSummary(metric_type?: string) {
  return useQuery({
    queryKey: ["metric-summary", metric_type],
    queryFn: () => enterpriseAnalyticsApi.getMetricSummary(metric_type),
    staleTime: 30_000,
  })
}

export function useTrends(metric_type?: string, window?: number) {
  return useQuery({
    queryKey: ["trends", metric_type, window],
    queryFn: async () => {
      const res = await enterpriseAnalyticsApi.detectTrends(metric_type, window)
      return res.trends as TrendItem[]
    },
    staleTime: 60_000,
  })
}

export function useGenerateReport() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: Parameters<typeof enterpriseAnalyticsApi.generateReport>[0]) =>
      enterpriseAnalyticsApi.generateReport(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["reports"] }),
  })
}

export function useReportList(report_type?: string, limit?: number) {
  return useQuery({
    queryKey: ["reports", report_type, limit],
    queryFn: async () => {
      const res = await enterpriseAnalyticsApi.listReports(report_type, limit)
      return res.reports as AnalyticsReport[]
    },
    staleTime: 30_000,
  })
}

export function useReportDetail(id: string) {
  return useQuery({
    queryKey: ["reports", id],
    queryFn: () => enterpriseAnalyticsApi.getReport(id),
    enabled: !!id,
    staleTime: 60_000,
  })
}
