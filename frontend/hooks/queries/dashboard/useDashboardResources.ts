"use client"

import { useQuery } from "@tanstack/react-query"
import { queryKeys } from "@/lib/query"
import { fetchDashboardResources } from "@/services/dashboard/resources"

export function useDashboardResources() {
    return useQuery({
        queryKey: queryKeys.dashboard.resources(),
        queryFn:  fetchDashboardResources,
        refetchInterval: 15_000,
    })
}
