"use client"

import { useQuery } from "@tanstack/react-query"
import { queryKeys } from "@/lib/query"
import { fetchDashboardRootCause } from "@/services/dashboard/rootCause"

export function useDashboardRootCause() {
    const query = useQuery({
        queryKey: queryKeys.dashboard.rootCause(),
        queryFn: fetchDashboardRootCause,
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
