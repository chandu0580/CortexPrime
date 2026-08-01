"use client"

import { useQuery } from "@tanstack/react-query"
import { queryKeys } from "@/lib/query"
import { fetchDashboardCredentials } from "@/services/dashboard/credentials"

export function useDashboardCredentials() {
    const query = useQuery({
        queryKey: queryKeys.dashboard.credentials(),
        queryFn: fetchDashboardCredentials,
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
