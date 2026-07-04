"use client"

import { useQuery } from "@tanstack/react-query"
import { queryKeys } from "@/lib/query"
import { fetchDashboardEvents } from "@/services/dashboard/events"

export function useDashboardEvents() {
    const query = useQuery({
        queryKey: queryKeys.dashboard.events(),
        queryFn: fetchDashboardEvents,
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
