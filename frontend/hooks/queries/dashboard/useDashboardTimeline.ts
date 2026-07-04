"use client"

import { useQuery } from "@tanstack/react-query"
import { queryKeys } from "@/lib/query"
import { fetchDashboardTimeline } from "@/services/dashboard/timeline"

export function useDashboardTimeline() {
    const query = useQuery({
        queryKey: queryKeys.dashboard.timeline(),
        queryFn: fetchDashboardTimeline,
        refetchInterval: 15_000,
    })

    return {
        data: query.data,
        isLoading: query.isLoading,
        isError: query.isError,
        error: query.error,
        isPartialFailure: query.data?.isPartialFailure ?? false,
    }
}
