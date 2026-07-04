"use client"

import { useQuery } from "@tanstack/react-query"
import { queryKeys } from "@/lib/query"
import { fetchDashboardOverview } from "@/services/dashboard/overview"

export function useDashboardOverview() {
    return useQuery({
        queryKey: queryKeys.dashboard.overview(),
        queryFn:  fetchDashboardOverview,
    })
}
