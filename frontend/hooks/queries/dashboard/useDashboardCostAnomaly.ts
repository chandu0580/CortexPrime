"use client"

import { useQuery } from "@tanstack/react-query"
import { queryKeys } from "@/lib/query"
import { fetchDashboardCostAnomaly } from "@/services/dashboard/costAnomaly"

export function useDashboardCostAnomaly() {
    const query = useQuery({
        queryKey: queryKeys.dashboard.costAnomaly(),
        queryFn: fetchDashboardCostAnomaly,
        refetchInterval: 15000,
    })

    return {
        data: query.data,
        isLoading: query.isLoading,
        isError: query.isError,
        error: query.error,
        isPartialFailure: query.data?.isPartialFailure ?? false,
    }
}
