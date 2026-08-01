"use client"

import { useQuery } from "@tanstack/react-query"
import { queryKeys } from "@/lib/query"
import { fetchDashboardIncidents } from "@/services/dashboard/incidents"

export function useDashboardIncidents() {
    const query = useQuery({
        queryKey: queryKeys.dashboard.incidents(),
        queryFn: fetchDashboardIncidents,
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
