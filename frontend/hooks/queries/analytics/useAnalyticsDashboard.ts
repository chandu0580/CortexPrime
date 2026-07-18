"use client"

import { useQuery } from "@tanstack/react-query"
import { queryKeys } from "@/lib/query"
import { fetchAnalyticsDashboard } from "@/services/dashboard/analytics"

export function useAnalyticsDashboard() {
    return useQuery({
        queryKey: queryKeys.analyticsDashboard.data(),
        queryFn:  fetchAnalyticsDashboard,
    })
}
