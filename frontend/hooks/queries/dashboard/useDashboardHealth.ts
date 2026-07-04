"use client"

import { useQuery } from "@tanstack/react-query"
import { queryKeys } from "@/lib/query"
import { fetchDashboardHealth } from "@/services/dashboard/health"

export function useDashboardHealth() {
    return useQuery({
        queryKey: queryKeys.dashboard.health(),
        queryFn:  fetchDashboardHealth,
    })
}
