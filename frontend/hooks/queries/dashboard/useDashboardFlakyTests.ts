"use client"

import { useQuery } from "@tanstack/react-query"
import { queryKeys } from "@/lib/query"
import { fetchDashboardFlakyTests } from "@/services/dashboard/flakyTests"

export function useDashboardFlakyTests() {
    const query = useQuery({
        queryKey: queryKeys.dashboard.flakyTests(),
        queryFn: fetchDashboardFlakyTests,
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
